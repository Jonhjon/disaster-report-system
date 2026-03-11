# 智慧災害通報系統 - 實作計劃

## 實作階段

### 階段 1: 基礎建設
1. **建立專案結構** — 建立前後端目錄結構
2. **Docker Compose** — 設定 PostgreSQL + PostGIS 容器
3. **後端基礎** — FastAPI 應用程式、CORS、設定檔、.env
4. **資料庫模型** — SQLAlchemy + GeoAlchemy2 模型定義
5. **資料庫遷移** — Alembic 初始化與初始遷移
6. **前端基礎** — React + Vite + TypeScript + Tailwind CSS 初始化

### 階段 2: 核心後端 API
7. **事件 CRUD API** — GET/PUT /api/events, GET /api/events/{id}
8. **通報 API** — GET /api/reports, GET /api/reports/{id}
9. **地理空間查詢** — GET /api/events/map（地圖範圍查詢）
10. **搜尋篩選排序** — 關鍵字搜尋、多條件篩選、排序、分頁

### 階段 3: LLM 對話通報
11. **LLM Service** — Claude API 整合，Tool Use 設定
12. **System Prompt** — 設計引導通報的 system prompt
13. **Chat API** — POST /api/chat，SSE streaming 回應
14. **Geocoding Service** — Nominatim API 整合（地址 → 座標）
15. **去重 Service** — PostGIS 近鄰查詢 + Claude 比對判斷

### 階段 4: 前端介面
16. **Layout 與路由** — Header、Sidebar、React Router
17. **地圖總覽頁** — Leaflet 地圖、marker、clustering、popup、篩選
18. **對話通報頁** — Chat UI、streaming 顯示、摘要確認
19. **災情列表頁** — 表格、搜尋、篩選、排序、分頁
20. **災情詳情頁** — 事件資訊、關聯通報、編輯表單、狀態更新

### 階段 5: 整合與完善
21. **前後端整合測試** — 完整流程測試
22. **完善去重邏輯** — 調整空間半徑、LLM prompt
23. **錯誤處理** — 載入狀態、錯誤訊息、邊界情況

---

## 前置需求
- Node.js 18+ (前端)
- Python 3.11+ (後端)
- Docker Desktop (PostgreSQL + PostGIS)
- Anthropic API Key (Claude)

---

## 驗證方式
1. **後端 API**: FastAPI Swagger UI (`/docs`)
2. **LLM 對話**: 模擬通報對話，驗證結構化擷取
3. **去重邏輯**: 多筆相近通報，驗證正確合併
4. **地圖顯示**: 事件正確顯示，不同類型不同圖示
5. **搜尋篩選**: 各種篩選組合驗證
