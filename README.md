# 智慧災害通報系統

讓民眾透過 AI 對話快速通報地震、颱風、水災等災情，系統自動整理資訊、呈現地圖，並判斷是否為同一事件。管理人員透過管理中心端進行災情管理與監控。

## 系統架構

| 應用 | 說明 | 網址 |
|------|------|------|
| 民眾端 | 免登入，災情通報 + 唯讀地圖 | http://localhost:5173 |
| 管理中心端 | 需登入，災情管理 + LLM 監控 | http://localhost:5174 |
| 後端 API | FastAPI + JWT 認證 | http://localhost:8000 |
| API 文件 | Swagger UI | http://localhost:8000/docs |

## 系統需求

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — 執行 PostgreSQL + PostGIS
- [Python 3.11+](https://www.python.org/downloads/) — 後端
- [Node.js 18+](https://nodejs.org/) — 前端
- Anthropic API Key — [申請地址](https://console.anthropic.com/)
- Google Maps API Key — [申請地址](https://console.cloud.google.com/google/maps-apis)（地圖元件使用）

---

## Windows 一鍵啟動

```powershell
.\start.ps1   # 啟動全系統（資料庫 + 後端 + 民眾端 + 管理中心端）
.\stop.ps1    # 停止全系統
```

`start.ps1` 會自動檢查 `.running_pids`、相關程序與 port 佔用，若偵測到系統已在執行，會提示「強制重啟 / 取消」，避免重複啟動造成 port 衝突。

---

## 手動啟動

### 步驟 1：啟動資料庫

```bash
docker compose up -d
```

### 步驟 2：設定後端環境

```bash
cd backend
cp .env.example .env
```

編輯 `backend/.env`：

```
DATABASE_URL=postgresql://app_user:changeme_in_production@localhost:5432/disaster_report
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GOOGLE_MAPS_API_KEY=your-google-maps-api-key-here
```

**進階／生產環境設定**（程式碼層有預設值，必要時於 `.env` 覆寫）：

| 變數 | 說明 |
|------|------|
| `ANTHROPIC_BASE_URL` · `CLAUDE_MODEL` · `DEDUP_MODEL` | LLM 來源與模型切換，詳見下方「[LLM 設定](#llm-設定)」章節 |
| `JWT_SECRET_KEY` | 生產環境必填 ≥32 字元；建議 `openssl rand -hex 32` |
| `DB_REQUIRE_SSL` | 生產環境設 `True` 啟用 PostgreSQL SSL |
| `APP_DB_PASSWORD` | 與 `docker-compose.yml` 中的 `APP_DB_PASSWORD` 保持一致 |

### 步驟 3：安裝套件與初始化資料庫

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
alembic upgrade head
```

### 步驟 4：啟動後端

```bash
cd backend
uvicorn app.main:app --reload
```

### 步驟 5：啟動民眾端

```bash
cd frontend-public
npm install
npm run dev
```

開啟瀏覽器：http://localhost:5173

### 步驟 6：啟動管理中心端

```bash
cd frontend-admin
npm install
npm run dev
```

開啟瀏覽器：http://localhost:5174

**預設管理員帳號：** `admin` / `admin123`（部署時請更改密碼）

---

## 技術堆疊

| 層級 | 技術 |
|------|------|
| 後端 | Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic |
| 認證 | JWT (python-jose) · bcrypt |
| 即時通訊 | SSE（sse-starlette）：LLM 串流 + 管理中心即時通知 |
| 民眾端前端 | React 18 · TypeScript · Vite · Tailwind CSS · zod · lucide-react |
| 管理中心前端 | React 18 · TypeScript · Vite · Tailwind CSS · zod · lucide-react |
| 地圖 | Leaflet · react-leaflet · leaflet.markercluster · OpenStreetMap |
| 資料庫 | PostgreSQL 16 · PostGIS 3 |
| LLM | Anthropic Claude API（Tool Use · SSE 串流） |
| 地理編碼 | Nominatim (OSM) · Google Geocoding（fallback） |
| 檔案儲存 | 本地 `static/uploads/`（背景任務自動清理孤兒附件） |

## LLM 設定

本系統透過 [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) 的 `AsyncAnthropic` 呼叫 LLM，預設指向 Anthropic 官方端點；也支援指向任何 Anthropic-compatible 代理服務。

### LLM 來源

- 留空 `ANTHROPIC_BASE_URL`（預設）：使用 Anthropic 官方 API <https://api.anthropic.com>
- 指定 `ANTHROPIC_BASE_URL=<代理 URL>`：路由到自架／第三方 Anthropic-compatible 代理

對應實作：`backend/app/services/api_clients.py`（lazy-init singleton，多 request 共用 connection pool）。

### 模型用途

| 環境變數 | 預設模型 | 用途 |
|---|---|---|
| `CLAUDE_MODEL` | `gpt-5.4` | 主要對話：通報擷取、描述合併、合併後數字再萃取 |
| `DEDUP_MODEL` | `gpt-5.4` | 去重判斷：當事件相似度落在 0.5–0.8 區間，呼叫此模型協助判讀 |

兩個變數分開設計：對話模型優先成本效率（Haiku），去重判斷需較強推理能力（Sonnet）。

### 互動方式

- **Tool Use**：定義單一工具 `submit_disaster_report`（見 `backend/app/schemas/llm_tools.py`），由模型擷取災情類型、位置、嚴重程度、時間、傷亡／受困／受傷人數、通報者資訊等結構化欄位
- **SSE 串流**：`POST /api/chat` 透過 `sse-starlette` 即時回傳 `text`、`tool_use`、`candidates_selection`、`report_submitted` 等事件
- **LLM 日誌**：所有呼叫記錄於 `llm_logs` 表（model、latency_ms、input／output token、status、prompt、output 摘要），管理中心端「LLM 日誌」頁面可查閱

### 系統內 LLM 用途清單

| 用途 | 模組 | 模型 |
|---|---|---|
| 通報對話擷取 | `services/llm_service.py` | `CLAUDE_MODEL` |
| 重複事件判斷 | `services/dedup_service.py` | `DEDUP_MODEL` |
| 災情描述合併 | `services/llm_service.merge_event_descriptions` | `CLAUDE_MODEL` |
| 合併後數字再萃取 | `services/llm_service.reextract_numbers_from_description` | `CLAUDE_MODEL` |

## 功能說明

### 民眾端
| 頁面 | 說明 |
|------|------|
| 地圖總覽 | 在地圖上查看所有災情事件（唯讀） |
| 通報災情 | 透過 AI 對話通報災情，系統自動擷取結構化資料；支援附件照片上傳（最多 3 張，JPEG/PNG/WebP，每張 5 MB）；LLM 候選位置選擇卡協助精準定位 |
| 使用說明 | 系統操作指引與功能介紹 |

### 管理中心端
| 功能 | 說明 |
|------|------|
| 登入 | 帳號密碼登入（JWT 認證） |
| 地圖總覽 | 查看災情事件，支援位置修正功能 |
| 災情列表 | 搜尋、篩選、排序所有災情事件 |
| 災情詳情 | 查看完整事件資訊、編輯、刪除、**事件合併**、**報告照片燈箱預覽** |
| 即時通知 | 透過 SSE 推播新事件 / 新報告，含通知鈴鐺與通知面板 |
| LLM 日誌 | 監控 AI 模型呼叫紀錄（延遲、token 用量） |
| 使用說明 | 管理功能操作指引 |

## 目錄結構

```
智慧災害通報系統/
├── backend/                  # Python FastAPI 後端
│   ├── app/
│   │   ├── api/              # auth、chat、events、reports、monitor、notifications、uploads
│   │   ├── models/           # user、disaster_event、disaster_report、report_attachment、llm_log
│   │   ├── schemas/          # auth、event、report、chat、attachment、llm_tools
│   │   ├── services/         # auth、llm、event、geocoding、dedup、notification_broker、attachment_cleanup、api_clients
│   │   ├── static/uploads/   # 附件照片儲存（背景任務每小時清理孤兒檔）
│   │   └── main.py           # FastAPI app + lifespan 背景任務
│   ├── alembic/              # 資料庫遷移腳本（001 ~ 010）
│   └── tests/                # 後端測試
├── frontend-public/          # 民眾端（port 5173）
│   └── src/
│       ├── pages/            # MapPage、ReportPage、HelpPage
│       └── components/
│           ├── chat/         # ChatWindow、ChatMessage、PhotoUploader、CandidateSelectionCard、ReportSummary
│           ├── map/          # DisasterMap、EventMarker、MapFilters
│           └── layout/       # Header、Sidebar、ErrorBoundary
├── frontend-admin/           # 管理中心端（port 5174）
│   └── src/
│       ├── contexts/         # AuthContext、NotificationContext
│       ├── pages/            # Login、Dashboard、EventList、EventDetail、LLMLogs、Help
│       └── components/
│           ├── events/       # EventDetail、EventEditForm、EventTable、EventFilters、ImageLightbox
│           ├── notifications/ # NotificationBell、NotificationPanel
│           ├── auth/         # ProtectedRoute
│           ├── map/、layout/
├── frontend/                 # 舊版單一前端（保留參考）
├── docs/                     # 系統設計文件
├── docker-compose.yml
├── start.ps1                 # Windows 一鍵啟動（含重複啟動檢查）
└── stop.ps1                  # Windows 一鍵停止
```

## 停止服務

```bash
# 停止資料庫（保留資料）
docker compose stop

# 清除所有資料
docker compose down -v
```
