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

---

## Windows 一鍵啟動

```powershell
.\start.ps1   # 啟動全系統（資料庫 + 後端 + 民眾端 + 管理中心端）
.\stop.ps1    # 停止全系統
```

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
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/disaster_report
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
CLAUDE_MODEL=claude-haiku-4-5-20251001
GOOGLE_MAPS_API_KEY=                      # 選用
JWT_SECRET_KEY=your-production-secret     # 生產環境請更改
```

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
| 民眾端前端 | React 18 · TypeScript · Vite · Tailwind CSS |
| 管理中心前端 | React 18 · TypeScript · Vite · Tailwind CSS |
| 地圖 | Leaflet · react-leaflet · OpenStreetMap |
| 資料庫 | PostgreSQL 16 · PostGIS 3 |
| LLM | Anthropic Claude API（Tool Use · SSE 串流） |
| 地理編碼 | Google Places · Nominatim (OSM) · Google Geocoding |

## 功能說明

### 民眾端
| 頁面 | 說明 |
|------|------|
| 地圖總覽 | 在地圖上查看所有災情事件（唯讀） |
| 通報災情 | 透過 AI 對話通報災情，系統自動擷取結構化資料 |
| 使用說明 | 系統操作指引與功能介紹 |

### 管理中心端
| 頁面 | 說明 |
|------|------|
| 登入 | 帳號密碼登入（JWT 認證） |
| 地圖總覽 | 查看災情事件，支援位置修正功能 |
| 災情列表 | 搜尋、篩選、排序所有災情事件 |
| 災情詳情 | 查看完整事件資訊、編輯、刪除 |
| LLM 日誌 | 監控 AI 模型呼叫紀錄（延遲、token 用量） |
| 使用說明 | 管理功能操作指引 |

## 目錄結構

```
智慧災害通報系統/
├── backend/                  # Python FastAPI 後端
│   ├── app/
│   │   ├── api/              # 路由（auth、chat、events、reports、monitor）
│   │   ├── models/           # 資料模型（event、report、user、llm_log）
│   │   ├── schemas/          # Pydantic 結構（event、report、chat、auth）
│   │   └── services/         # 業務邏輯（LLM、去重、地理編碼、認證）
│   ├── alembic/              # 資料庫遷移腳本（001~007）
│   └── tests/                # 後端測試
├── frontend-public/          # 民眾端（port 5173）
│   └── src/
│       ├── components/       # 地圖、聊天元件（唯讀）
│       └── pages/            # MapPage、ReportPage、HelpPage
├── frontend-admin/           # 管理中心端（port 5174）
│   └── src/
│       ├── contexts/         # AuthContext（JWT 認證狀態）
│       ├── components/       # 地圖、事件管理、認證元件
│       └── pages/            # Login、Dashboard、EventList、EventDetail、LLMLogs、Help
├── frontend/                 # 舊版單一前端（保留參考）
├── docs/                     # 系統設計文件
├── docker-compose.yml
├── start.ps1                 # Windows 一鍵啟動
└── stop.ps1                  # Windows 一鍵停止
```

## 停止服務

```bash
# 停止資料庫（保留資料）
docker compose stop

# 清除所有資料
docker compose down -v
```
