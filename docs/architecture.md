# 智慧災害通報系統 - 系統架構

## 架構總覽

```
┌─────────────────────────────┐  ┌──────────────────────────────────┐
│   民眾端 (frontend-public)   │  │  管理中心端 (frontend-admin)       │
│   port 5173                  │  │  port 5174                        │
│                              │  │                                    │
│  ┌──────────┐ ┌──────────┐  │  │  ┌────────┐ ┌──────────────────┐  │
│  │ 通報對話  │ │ 唯讀地圖  │  │  │  │ 登入頁  │ │ 地圖（含修正功能） │  │
│  └────┬─────┘ └────┬─────┘  │  │  └────┬───┘ └────────┬─────────┘  │
│       │            │         │  │       │              │              │
│       │  免認證     │         │  │  ┌────▼───┐ ┌───────▼──────────┐  │
│       │            │         │  │  │ JWT 認證 │ │ 災情管理 (CRUD)   │  │
│       │            │         │  │  └────┬───┘ └───────┬──────────┘  │
│       │            │         │  │       │    ┌────────▼──────────┐  │
│       │            │         │  │       │    │ LLM 日誌監控       │  │
└───────┼────────────┼─────────┘  └───────┼────┴───────────────────┘
        │            │                    │
        ▼            ▼                    ▼
┌──────────────────────────────────────────────────────────┐
│                   Backend (FastAPI) port 8000              │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Auth API │  │ Chat API │  │ Event API│  │Monitor API│  │
│  │ /auth    │  │ /chat    │  │ /events  │  │ /llm-logs │  │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └──────────┘  │
│                     │              │                        │
│  ┌──────────────────▼──────────────▼──────────────────┐   │
│  │                   Services                          │   │
│  │  ┌────────────┐ ┌──────────┐ ┌───────────────────┐ │   │
│  │  │ LLM Service│ │  Dedup   │ │ Geocoding Service │ │   │
│  │  │ (Claude)   │ │ Service  │ │ (多層級 geocoding) │ │   │
│  │  └────────────┘ └──────────┘ └───────────────────┘ │   │
│  │  ┌────────────┐ ┌──────────┐                       │   │
│  │  │Auth Service│ │  Event   │                       │   │
│  │  │ (JWT/bcrypt)│ │ Service  │                       │   │
│  │  └────────────┘ └──────────┘                       │   │
│  └────────────────────────────────────────────────────┘   │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
                ┌─────────────────────┐
                │  PostgreSQL + PostGIS│
                │                     │
                │  disaster_events    │
                │  disaster_reports   │
                │  users              │
                │  llm_logs           │
                └─────────────────────┘
```

## 技術選型

| 層級 | 技術 | 說明 |
|------|------|------|
| 民眾端前端 | React 18 + TypeScript + Vite | 輕量通報介面，port 5173 |
| 管理中心前端 | React 18 + TypeScript + Vite | 完整管理介面，port 5174 |
| UI 樣式 | Tailwind CSS | 快速開發，響應式設計 |
| 地圖 | Leaflet + OpenStreetMap | 免費開源，支援台灣地區 |
| 後端框架 | Python FastAPI | 高效能非同步 API，自動生成 Swagger 文件 |
| 認證 | JWT (python-jose) + bcrypt | 管理端登入，8 小時 token 有效期 |
| LLM | Claude API (Anthropic) | Tool Use 結構化輸出，中文能力優秀 |
| 資料庫 | PostgreSQL 16 + PostGIS 3 | 地理空間查詢標準方案 |
| ORM | SQLAlchemy 2.0 + GeoAlchemy2 | Python 地理空間 ORM |
| 資料庫遷移 | Alembic | SQLAlchemy 的資料庫版本控制 |
| Geocoding | Google Places / Nominatim / Google Geocoding | 多層級地址轉座標策略 |

## 專案結構

```
智慧災害通報系統/
├── backend/                          # Python FastAPI 後端
│   ├── app/
│   │   ├── main.py                   # FastAPI 應用程式進入點
│   │   ├── config.py                 # 環境變數設定
│   │   ├── database.py               # 資料庫連線設定
│   │   ├── models/                   # SQLAlchemy 模型
│   │   │   ├── disaster_event.py
│   │   │   ├── disaster_report.py
│   │   │   ├── llm_log.py
│   │   │   └── user.py              # 管理員帳號
│   │   ├── schemas/                  # Pydantic 請求/回應模型
│   │   │   ├── event.py
│   │   │   ├── report.py
│   │   │   ├── chat.py
│   │   │   └── auth.py              # 認證相關 schema
│   │   ├── api/                      # API 路由
│   │   │   ├── auth.py              # 登入/取得用戶 (POST /login, GET /me)
│   │   │   ├── chat.py             # SSE 串流通報
│   │   │   ├── events.py           # 事件 CRUD
│   │   │   ├── reports.py          # 通報查詢
│   │   │   ├── monitor.py          # LLM 日誌
│   │   │   └── deps.py             # 認證 dependency (get_current_user)
│   │   └── services/                 # 商業邏輯
│   │       ├── llm_service.py        # Claude API 整合
│   │       ├── event_service.py      # 事件 CRUD
│   │       ├── dedup_service.py      # 事件去重邏輯
│   │       ├── geocoding_service.py  # 地址轉座標
│   │       └── auth_service.py       # JWT 產生 / 密碼驗證
│   ├── alembic/                      # 資料庫遷移（001~007）
│   ├── tests/                        # 後端測試
│   ├── requirements.txt
│   └── .env.example
├── frontend-public/                  # 民眾端前端（port 5173）
│   └── src/
│       ├── components/
│       │   ├── layout/               # Header（紅色）、Sidebar（3 項）
│       │   ├── chat/                 # ChatWindow、ChatMessage、CandidateSelectionCard、ReportSummary
│       │   └── map/                  # DisasterMap、EventMarker（唯讀）、MapFilters
│       ├── pages/                    # MapPage、ReportPage、HelpPage
│       ├── services/api.ts           # 僅公開 API（streamChat、getMapEvents）
│       └── types/index.ts
├── frontend-admin/                   # 管理中心端前端（port 5174）
│   └── src/
│       ├── contexts/AuthContext.tsx   # JWT 認證狀態管理
│       ├── components/
│       │   ├── layout/               # Header（藍色 + 登出）、Sidebar（4 項）
│       │   ├── auth/                 # ProtectedRoute
│       │   ├── map/                  # DisasterMap、EventMarker（含修正功能）、MapFilters
│       │   └── events/               # EventTable、EventFilters、EventDetail、EventEditForm
│       ├── pages/                    # LoginPage、DashboardPage、EventListPage、EventDetailPage、LLMLogsPage、HelpPage
│       ├── services/
│       │   ├── api.ts                # 完整 API（含認證 header）
│       │   └── auth.ts              # login/logout/getStoredToken
│       └── types/index.ts            # 含 User、TokenResponse 型別
├── frontend/                         # 舊版單一前端（保留參考）
├── docker-compose.yml                # PostgreSQL + PostGIS 容器
├── docs/                             # 系統設計文件
├── start.ps1                         # Windows 一鍵啟動（後端 + 兩個前端）
└── stop.ps1                          # Windows 一鍵停止
```

## 核心流程

### 通報流程（民眾端）
```
民眾開始對話 → Claude 引導收集資訊 → Tool Use 擷取結構化資料
→ Geocoding 取得座標（多層級：Google Places → Nominatim → Google Geocoding）
→ 精確度檢查（不足則追問，最多 3 次）
→ 事件去重（語義 + 地理 + 時間 + 類型 多維評分）
→ 相似事件存在：顯示候選卡片供選擇 / 無相似事件：直接建立
→ 合併時：LLM 合併描述 + 重新萃取傷亡數字
→ 通報完成，顯示摘要
```

### 認證流程（管理端）
```
管理員輸入帳密 → POST /api/auth/login → bcrypt 驗證 → 回傳 JWT
→ JWT 存入 localStorage → 所有 API 請求帶 Authorization header
→ 後端 get_current_user dependency 解碼驗證
→ Token 過期 → 前端攔截 401 → 清除 token → 導向 /login
```

### 去重流程
```
新通報進入 → PostGIS 空間查詢候選事件（按災害類型設定半徑）
→ 多維評分（語義 30% + 地理 30% + 時間 20% + 類型 20%）
→ score ≥ 0.80：自動合併
→ 0.50 ≤ score < 0.80：Claude LLM 輔助判斷
→ score < 0.50：建立新事件
```

### 地點判斷流程

1. **快取檢查** — 相同字串已查詢過則直接返回
2. **LLM 改寫** — Claude 將口語地點轉成結構化格式
3. **地標模式偵測** — 不含路名的地點，優先查 Google Places
4. **TGOS** — 台灣政府地址 API（目前停用，端點返回 404）
5. **Nominatim** — OpenStreetMap 免費 Geocoding
6. **Google Places** — 備援
7. **Google Geocoding** — 最終備援

全部失敗 → `location_approximate = true`，座標用台灣中心點
