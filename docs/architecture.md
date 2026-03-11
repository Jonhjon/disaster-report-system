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
| Geocoding | Nominatim (OSM) | 免費地址轉座標服務 |

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

### 去重流程
```
新通報進入 → PostGIS 空間查詢 (ST_DWithin) 候選事件
→ 時間篩選 (72hr) → 類型篩選 → Claude LLM 比對判斷
→ 同一事件: 更新事件+關聯通報 / 不同事件: 新建事件
```
