# 地理編碼與地圖標示設計文件

**對應原始碼：**
- `backend/app/services/geocoding_service.py`
- `backend/app/api/chat.py`
- `frontend/src/components/map/DisasterMap.tsx`
- `frontend/src/components/map/EventMarker.tsx`

---

## 目的

當民眾以口語文字通報災情時，系統需將文字地址轉換為精確的經緯度座標，並將事件標示在地圖上供救援人員查閱。

---

## 整體資料流

```
用戶輸入文字通報
        │
        ▼
  LLM (Claude) 解析對話
  └─ 工具呼叫: submit_disaster_report
     ├─ location_text（文字地址，必填）
     └─ latitude / longitude（若 LLM 能直接判斷則提供）
        │
        ▼
  _process_tool_use()           ← chat.py
  └─ 精確度判斷（_location_is_precise）
     ├─ 精確 → geocode_address(location_text)
     └─ 不精確且未超過追問上限 → 追問使用者補充地址
        │
        ▼
  [Step 0~5 Geocoding 策略]
  Step 0: 快取查詢
  Step 1: Claude Haiku 正規化地址
  Step 1.5: Named-place fast path（Google Places）
  Step 2: TGOS API ⚠️ 暫停使用
  Step 3: Nominatim / OpenStreetMap
  Step 4: Google Places Text Search（備援）
  Step 5: Google Maps Geocoding API（最終備援）
  └─ 若全部失敗 → 返回 None，座標用台灣中心 (23.5, 121.0)
        │
        ▼
  存入 PostgreSQL PostGIS
  location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        │
        ▼
  前端地圖移動 → GET /api/events/map?bounds=...
  └─ 後端 ST_Within() 查詢視窗範圍內事件
     └─ 回傳 EventMapItem[]（含 latitude, longitude, severity, disaster_type）
        │
        ▼
  <CircleMarker> 標示在地圖上
```

---

## 地理編碼（Geocoding）

### Step 0~5 策略

`geocode_address()` 依序嘗試以下步驟，任一成功即停止：

| Step | 說明 |
|------|------|
| 0 | **快取**：相同字串曾查詢過 → 直接返回（上限 500 筆，process-level） |
| 1 | **LLM 改寫（Claude Haiku）**：`extract_structured_address()` 將口語地點轉成可查格式，產生 `searchable` |
| 1.5 | **Named-place fast path**：`address` 不含路名字詞時，直接以 `address` / `searchable` 查 Google Places；若結尾含場所後綴詞則以 `_strip_place_suffix()` 剝除後再試 |
| 2 | **TGOS**（台灣政府地址 API）⚠️ 暫停使用：端點回傳 404，程式碼已註解，待找到可用端點後再啟用 |
| 3 | **Nominatim**（OpenStreetMap）：依序查 `searchable` / `searchable + " 台灣"` / `address` / `address + " 台灣"` / 結構化查詢 |
| 4 | **Google Places Text Search（備援）**：Step 1.5 未觸發才到此；回傳純行政區劃層級（`VAGUE_TYPES`）視為模糊結果，繼續 fallback |
| 5 | **Google Maps Geocoding API（最終備援）**：依序查 `address` → `searchable`；全部失敗 → 返回 `None` |

### Step 1 — 地址正規化

`extract_structured_address(text)` 呼叫 Claude Haiku，將民眾的口語描述轉換為可搜尋的正式地址：

```
輸入：「我在基隆路跟信義路的交叉口附近」
輸出 searchable：「台北市信義區基隆路」
```

### Step 1.5 — Named-place fast path

**觸發條件**：原始 `address`（非 `searchable`）不含 `路/街/大道/巷/弄`

觸發時查詢順序：
1. `address` → Google Places Text Search
2. `searchable` → Google Places Text Search
3. 若 address 結尾含場所後綴詞（教室/操場/停車場/大廳/走廊/餐廳/圖書館等），
   以 `_strip_place_suffix()` 剝除後綴 → 再次查詢 Google Places

> 判斷以 `address` 為準而非 `searchable`，避免 LLM 猜測路名導致 fast path 被略過。

### Step 2 — TGOS API（台灣優先）⚠️ 暫停使用

> **目前停用**：端點 `https://addr.tgos.tw/addr/api/addrquery/` 回傳 404，`geocode_tgos()` 呼叫已註解。待找到可用端點後再啟用。

`geocode_tgos(address)` 原本查詢行政院主導的台灣地理資訊系統，專為台灣地址優化，回傳格式：

```json
{
  "latitude": 25.033,
  "longitude": 121.565,
  "display_name": "台北市信義區基隆路一段"
}
```

### Step 3 — Nominatim（備援）

免費開源，僅接受台灣境內座標。依序查詢 `searchable`、`searchable + " 台灣"`、`address`、`address + " 台灣"`、結構化查詢（Claude Haiku 解析的 county/city/street）。

### 精確度判斷與追問機制

滿足以下**任一**條件即視為精確：

| 條件 | 說明 |
|------|------|
| `coords.source == "google_places"` | Google Places 找到特定商家/地標 |
| 縣市 ＋ 路名 ＋ 號 同時出現在 `location_text`（路名字詞：路/街/大道/巷/弄/道） | 符合標準門牌格式 |

判定不精確時觸發追問，依缺少的成分決定追問內容：

| 缺少 | 追問訊息 |
|------|---------|
| 縣市 | 「請問事發地點是哪個縣市？」 |
| 路名 | 「請問附近的路名或地標是什麼？」 |
| 門號 | 「請問門牌號碼或更精確的位置？」 |

- **跨輪計數**：`failed_attempts` 掃描整個對話歷史，統計含「geocoding 失敗」或「地址不夠精確」的 tool_result 訊息數量
- **continuation 強制接受**：追問過程中若 LLM 再次呼叫 `submit_disaster_report`，強制接受建立通報，不再觸發第二次追問
- 最多追問 3 次（`MAX_GEOCODING_RETRIES = 3`），超過後強制建立事件（`location_approximate=true`）

---

## 座標存入資料庫

成功取得座標後，`_process_tool_use()` 使用 GeoAlchemy2 建立 PostGIS 幾何欄位：

```python
point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
```

- 格式：`POINT`（點）
- 座標系統：SRID 4326（WGS84，與 GPS / Google Maps 相同）
- 空間索引：`idx_events_location`（GiST 索引，加速空間查詢）

`DisasterEvent` 和 `DisasterReport` 皆各自存有 `location` 欄位。

---

## 前端地圖展示

### 地圖初始化

`DisasterMap.tsx` 使用 React-Leaflet 建立地圖，預設視角為台灣中心：

```
中心點：(23.5, 121.0)
縮放層級：7（可看見全台灣）
圖層：OpenStreetMap (免費)
```

### 動態載入事件

`MapEventLoader` 元件監聽地圖的 `moveend` 事件，每次地圖移動結束後重新查詢：

```
1. 取得當前地圖邊界（南、西、北、東）
2. 呼叫 GET /api/events/map?bounds=south,west,north,east
3. 後端執行 ST_Within() 空間查詢
4. 回傳邊界內所有 EventMapItem
```

只載入當前視窗範圍內的事件，避免一次傳輸全部資料。

### 標記視覺規則

`EventMarker.tsx` 使用 `CircleMarker` 呈現每個事件：

| 屬性 | 規則 |
|------|------|
| 位置 | `[event.latitude, event.longitude]` |
| 圓圈半徑 | `6 + severity × 2`（嚴重程度 1–5 級，半徑範圍 8–16） |
| 填色 | 依 `disaster_type` 對應顏色（定義於 `types/index.ts`） |
| 透明度 | `fillOpacity: 0.5` |
| 點擊 Popup | 顯示事件標題、類型、嚴重程度、通報數，並附「查看詳情」連結 |

嚴重程度與圓圈半徑對應：

| 嚴重程度 | 圓圈半徑（px） |
|---------|-------------|
| 1 | 8 |
| 2 | 10 |
| 3 | 12 |
| 4 | 14 |
| 5 | 16 |

---

## 關鍵檔案對照

| 功能 | 檔案 | 關鍵函式 |
|------|------|---------|
| 地址正規化 | `geocoding_service.py` | `extract_structured_address()` |
| TGOS 查詢 | `geocoding_service.py` | `geocode_tgos()` |
| Geocoding 主流程 | `geocoding_service.py` | `geocode_address()` |
| 通報處理與座標存入 | `chat.py` | `_process_tool_use()` |
| 地圖容器與動態載入 | `DisasterMap.tsx` | `MapEventLoader` |
| 事件標記 | `EventMarker.tsx` | `CircleMarker` |
| 前端 API 呼叫 | `api.ts` | `getMapEvents()` |
| 後端地圖 API | `events.py` | `GET /events/map` |
