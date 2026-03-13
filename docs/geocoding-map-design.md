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
  LLM (Gemini) 解析對話
  └─ 工具呼叫: submit_disaster_report
     ├─ location_text（文字地址，必填）
     └─ latitude / longitude（若 LLM 能直接判斷則提供）
        │
        ▼
  _process_tool_use()           ← chat.py
  └─ 若 LLM 未提供座標
     └─ geocode_address(location_text)
        │
        ▼
  [三層 Geocoding Fallback]
  1. Claude Haiku 正規化地址
  2. TGOS API
  3. Nominatim / OpenStreetMap
  └─ 若全部失敗 → 預設台灣中心 (23.5, 121.0)
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

### 三層 Fallback 策略

`geocode_address()` 依序嘗試以下三個方法，任一成功即停止：

| 順序 | 函式 | 說明 |
|------|------|------|
| 1 | `extract_structured_address()` + TGOS | 先用 Claude Haiku 將口語地址正規化，再查詢台灣政府地理資訊系統 |
| 2 | Nominatim | 直接對原始 `location_text` 查詢 OpenStreetMap |
| Fallback | 硬編碼 | 全部失敗時使用台灣中心點 (23.5, 121.0) |

### 第一層：地址正規化

`extract_structured_address(text)` 呼叫 Claude Haiku，將民眾的口語描述轉換為可搜尋的正式地址：

```
輸入：「我在基隆路跟信義路的交叉口附近」
輸出：「台北市信義區基隆路」
```

正規化後的地址再送入 TGOS API 查詢，準確率顯著提升。

### 第二層：TGOS API（台灣優先）

`geocode_tgos(address)` 查詢行政院主導的台灣地理資訊系統，專為台灣地址優化，回傳格式：

```json
{
  "latitude": 25.033,
  "longitude": 121.565,
  "display_name": "台北市信義區基隆路一段"
}
```

### 第三層：Nominatim（備援）

`geocode_address()` 最終使用 OpenStreetMap 的 Nominatim 服務，全球通用但台灣地址精確度低於 TGOS。

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
