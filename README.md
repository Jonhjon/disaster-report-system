# 智慧災害通報系統

讓民眾透過 AI 對話快速通報地震、颱風、水災等災情，系統自動整理資訊、呈現地圖，並判斷是否為同一事件。

## 系統需求

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — 執行 PostgreSQL + PostGIS
- [Python 3.11+](https://www.python.org/downloads/) — 後端
- [Node.js 18+](https://nodejs.org/) — 前端
- Anthropic API Key — [申請地址](https://console.anthropic.com/)

---

## Windows 一鍵啟動（選用）

若使用 Windows，可直接執行 PowerShell 腳本自動完成所有步驟：

```powershell
.\start.ps1   # 啟動全系統
.\stop.ps1    # 停止全系統
```

---

## 快速啟動

### 步驟 1：啟動資料庫

```bash
docker compose up -d
```

等待約 10 秒，確認 PostgreSQL 已就緒：

```bash
docker compose ps
```

### 步驟 2：設定後端環境

```bash
cd backend

# 複製環境變數設定
cp .env.example .env
```

編輯 `backend/.env`，填入你的 Anthropic API Key：

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/disaster_report
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
CLAUDE_MODEL=claude-haiku-4-5-20251001   # 可選，預設使用 claude-haiku-4-5-20251001
GOOGLE_MAPS_API_KEY=                      # 選用：啟用 Google Places 地理編碼，留空則使用 Nominatim (OSM)
```

### 步驟 3：安裝後端套件與初始化資料庫

```bash
# 在 backend/ 目錄下執行

# 建立虛擬環境（建議）
python -m venv venv
venv\Scripts\activate      # Windows
# 或 source venv/bin/activate  # Mac/Linux

# 安裝套件
pip install -r requirements.txt

# 建立資料庫表格
alembic upgrade head
```

### 步驟 4：啟動後端

```bash
# 在 backend/ 目錄下執行
uvicorn app.main:app --reload
```

後端啟動後可在瀏覽器開啟 API 文件：
- Swagger UI：http://localhost:8000/docs

### 步驟 5：安裝前端套件

```bash
cd frontend
npm install
```

### 步驟 6：啟動前端

```bash
# 在 frontend/ 目錄下執行
npm run dev
```

前端啟動後開啟瀏覽器：
- http://localhost:5173

---

## 技術堆疊

| 層級 | 技術 |
|------|------|
| 後端 | Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic |
| 前端 | React 18 · TypeScript · Vite · Tailwind CSS |
| 地圖 | Leaflet · react-leaflet · OpenStreetMap |
| 資料庫 | PostgreSQL 16 · PostGIS 3 |
| LLM | Anthropic Claude API（Tool Use · SSE 串流） |
| 地理編碼 | Nominatim (OSM)・Google Places（選用） |

## 功能說明

| 頁面 | 說明 |
|------|------|
| 地圖總覽 | 在地圖上查看所有災情事件，點擊標記查看摘要 |
| 通報災情 | 透過 AI 對話通報災情，系統自動擷取結構化資料 |
| 災情列表 | 搜尋、篩選、排序所有災情事件 |
| 災情詳情 | 查看完整事件資訊、相關通報記錄，並可手動更新 |
| 使用說明 | 系統操作指引與功能介紹 |

## 目錄結構

```
智慧災害通報系統/
├── backend/                  # Python FastAPI 後端
│   ├── app/
│   │   ├── api/              # 路由（chat、events、reports、monitor）
│   │   ├── models/           # SQLAlchemy 資料模型
│   │   ├── schemas/          # Pydantic 請求 / 回應結構
│   │   ├── services/         # 業務邏輯（LLM、去重、地理編碼）
│   │   ├── config.py         # 環境變數設定
│   │   └── main.py           # FastAPI 應用程式進入點
│   ├── alembic/              # 資料庫遷移腳本
│   ├── tests/                # 後端測試
│   ├── .env.example
│   └── requirements.txt
├── frontend/                 # React 前端
│   └── src/
│       ├── components/       # UI 元件（地圖、聊天、事件）
│       ├── pages/            # 頁面（儀表板、通報、列表、詳情、說明）
│       ├── services/         # API 呼叫封裝
│       └── types/            # TypeScript 型別定義
├── docs/                     # 系統設計文件
├── docker-compose.yml
├── start.ps1                 # Windows 一鍵啟動腳本
└── stop.ps1                  # Windows 一鍵停止腳本
```

## 停止服務

```bash
# 停止資料庫
docker compose down

# 保留資料：加 --volumes=false（預設）
# 清除所有資料：
docker compose down -v
```
