# 智慧災害通報系統 - 系統架構

## 架構總覽

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ 對話通報  │  │ 地圖總覽  │  │ 災情列表/搜尋/管理 │  │
│  │  (Chat)  │  │  (Map)   │  │   (EventList)     │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │              │                 │              │
└───────┼──────────────┼─────────────────┼─────────────┘
        │              │                 │
        ▼              ▼                 ▼
┌─────────────────────────────────────────────────────┐
│               Backend (FastAPI)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Chat API │  │ Event API│  │ Dedup Service    │   │
│  │ /chat    │  │ /events  │  │ (事件去重判斷)    │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │              │                 │              │
│  ┌────▼─────┐        │          ┌──────▼──────┐      │
│  │ Claude   │        │          │ 地理空間    │      │
│  │ API      │        │          │ 近鄰查詢    │      │
│  └──────────┘        │          └─────────────┘      │
│                      │                               │
└──────────────────────┼───────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │  PostgreSQL    │
              │  + PostGIS     │
              │                │
              │ disaster_events│
              │ disaster_reports│
              └────────────────┘
```

## 技術選型

| 層級 | 技術 | 說明 |
|------|------|------|
| 前端框架 | React 18 + TypeScript + Vite | 現代前端開發，型別安全 |
| UI 樣式 | Tailwind CSS | 快速開發，響應式設計 |
| 地圖 | Leaflet + OpenStreetMap | 免費開源，支援台灣地區 |
| 後端框架 | Python FastAPI | 高效能非同步 API，自動生成 Swagger 文件 |
| LLM | Claude API (Anthropic) | Tool Use 結構化輸出，中文能力優秀 |
| 資料庫 | PostgreSQL 16 + PostGIS 3 | 地理空間查詢標準方案 |
| ORM | SQLAlchemy 2.0 + GeoAlchemy2 | Python 地理空間 ORM |
| 資料庫遷移 | Alembic | SQLAlchemy 的資料庫版本控制 |
| Geocoding | Nominatim / TGOS / Google Maps / Google Places | 多層級地址轉座標策略 |

## 專案結構

```
智慧災害通報系統/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 應用程式進入點
│   │   ├── config.py               # 設定（環境變數）
│   │   ├── database.py             # 資料庫連線設定
│   │   ├── models/                 # SQLAlchemy 模型
│   │   │   ├── __init__.py
│   │   │   ├── disaster_event.py
│   │   │   └── disaster_report.py
│   │   ├── schemas/                # Pydantic 請求/回應模型
│   │   │   ├── __init__.py
│   │   │   ├── event.py
│   │   │   ├── report.py
│   │   │   └── chat.py
│   │   ├── api/                    # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── events.py
│   │   │   ├── reports.py
│   │   │   └── chat.py
│   │   └── services/               # 商業邏輯
│   │       ├── __init__.py
│   │       ├── llm_service.py      # Claude API 整合
│   │       ├── event_service.py    # 事件 CRUD
│   │       ├── dedup_service.py    # 事件去重邏輯
│   │       └── geocoding_service.py # 地址轉座標
│   ├── alembic/                    # 資料庫遷移
│   │   └── versions/
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── map/
│   │   │   │   ├── DisasterMap.tsx       # 主地圖元件
│   │   │   │   ├── EventMarker.tsx       # 事件標記
│   │   │   │   └── MapFilters.tsx        # 地圖篩選控制
│   │   │   ├── chat/
│   │   │   │   ├── ChatWindow.tsx        # 對話視窗
│   │   │   │   ├── ChatMessage.tsx       # 訊息氣泡
│   │   │   │   └── ReportSummary.tsx     # 通報摘要確認
│   │   │   └── events/
│   │   │       ├── EventTable.tsx        # 事件列表
│   │   │       ├── EventDetail.tsx       # 事件詳情
│   │   │       ├── EventFilters.tsx      # 搜尋篩選
│   │   │       └── EventEditForm.tsx     # 編輯表單
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx         # 儀表板（地圖 + 摘要）
│   │   │   ├── ReportPage.tsx            # 通報頁面（對話介面）
│   │   │   ├── EventListPage.tsx         # 災情列表頁
│   │   │   └── EventDetailPage.tsx       # 災情詳情頁
│   │   ├── services/
│   │   │   └── api.ts                    # API 呼叫封裝
│   │   ├── types/
│   │   │   └── index.ts                  # TypeScript 型別定義
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
├── docker-compose.yml                    # PostgreSQL + PostGIS 容器
├── docs/                                 # 規劃文件
└── README.md
```

## 核心流程

### 通報流程
```
民眾開始對話 → Claude 引導收集資訊 → Tool Use 擷取結構化資料
→ 顯示摘要確認 → 提交通報 → Geocoding 補座標
→ 事件去重判斷 → 建立/更新事件 → 地圖更新
```

### 地點判斷流程

**輸入**：LLM 擷取的 `location_text`（如「花蓮的 Booms Burger」）

#### Step 0 — 快取檢查
相同字串曾查詢過 → 直接返回（上限 500 筆，process-level）

#### Step 1 — LLM 改寫（Claude Haiku）
`extract_structured_address()` 將口語地點轉成可查格式
- 輸入：「花蓮的 Booms Burger」
- 輸出 `searchable`：「花蓮縣花蓮市中正路 Booms Burger」（可能含猜測路名）

#### Step 1.5 — Named-place fast path
**觸發條件**：原始 `address`（非 `searchable`）不含 `路/街/大道/巷/弄`

觸發時查詢順序：
1. `address`（原始文字）→ Google Places Text Search
2. `searchable`（LLM 改寫版）→ Google Places Text Search
3. 若 address 結尾含場所後綴詞（教室/操場/停車場/大廳/走廊/餐廳/圖書館等），
   以 `_strip_place_suffix()` 剝除後綴 → 再次查詢 Google Places

成功且非模糊結果（非縣市行政區層級）→ 立即返回，帶 `source="google_places"`

> **注意**：判斷以 `address` 為準而非 `searchable`，避免 LLM 猜測路名導致 fast path 被略過。

#### Step 2 — TGOS（台灣政府地址 API）⚠️ 暫停使用
適合標準門牌地址。查詢順序：`searchable` → `address`

> **目前停用**：TGOS 端點 `https://addr.tgos.tw/addr/api/addrquery/` 回傳 404，程式碼已註解。待找到可用端點後再啟用。

#### Step 3 — Nominatim（OpenStreetMap）
免費開源，僅接受台灣境內座標。依序查詢：
1. `searchable`
2. `searchable + " 台灣"`
3. `address`
4. `address + " 台灣"`
5. 結構化查詢（LLM 解析的 county/city/street）

#### Step 4 — Google Places Text Search（備援）
Step 1.5 未觸發才到此。查詢順序：`address` → `searchable`

Google Places 若回傳純行政區劃層級（`VAGUE_TYPES`：`locality` / `administrative_area_level_*` / `country` / `political` 等），
視為模糊結果，拒絕接受，繼續 fallback。

#### Step 5 — Google Maps Geocoding API（最終備援）
查詢順序：`address` → `searchable`
全部失敗 → 返回 `None`

---

#### 精確度判斷（`_location_is_precise`）

滿足以下**任一**條件即視為精確：

| 條件 | 說明 |
|------|------|
| `coords.source == "google_places"` | Google Places 找到特定商家/地標 |
| 縣市 ＋ 路名 ＋ 號 同時出現在 `location_text`（路名判斷字詞：路/街/大道/巷/弄/道） | 符合標準門牌格式 |

> **注意**：Step 1.5 觸發條件使用 `_ROAD_WORDS = ["路","街","大道","巷","弄"]`（5 個，不含「道」）；
> `_location_is_precise` 另包含「道」共 6 個，兩者刻意不同。

#### 追問機制（`_location_hint`）

判定不精確時，依缺少的成分決定追問內容：

| 缺少 | 追問訊息 |
|------|---------|
| 縣市 | 「請問事發地點是哪個縣市？」 |
| 路名 | 「請問附近的路名或地標是什麼？」 |
| 門號 | 「請問門牌號碼或更精確的位置？」 |

最多追問 3 次（`MAX_GEOCODING_RETRIES = 3`），超過後強制建立事件（`location_approximate=true`）。

- **跨輪計數**：`failed_attempts` 掃描整個對話歷史，統計含「geocoding 失敗」或「地址不夠精確」的 tool_result 訊息數量（非單輪計數）
- **continuation 強制接受**：追問過程中若 LLM 再次呼叫 `submit_disaster_report`，強制接受建立通報，不再觸發第二次追問

#### 最終決策

| 狀況 | 結果 |
|------|------|
| geocoding 成功且精確 | `location_approximate = false`，使用實際座標 |
| geocoding 失敗或不精確，且未超過追問上限 | 觸發追問，等使用者補充後重試 |
| 超過追問上限 或 已在追問流程中 | `location_approximate = true`，座標用台灣中心點 (23.5, 121.0) |

### 去重流程
```
新通報進入 → PostGIS 空間查詢 (ST_DWithin) 候選事件
→ 時間篩選 (72hr) → 類型篩選 → Claude LLM 比對判斷
→ 同一事件: 更新事件+關聯通報 / 不同事件: 新建事件
```
