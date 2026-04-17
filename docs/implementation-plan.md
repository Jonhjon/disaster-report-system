# 智慧災害通報系統 - 實作計劃

## 實作階段

### 階段 1: 基礎建設 ✅
1. 建立專案結構（前後端目錄）
2. Docker Compose（PostgreSQL + PostGIS 容器）
3. 後端基礎（FastAPI、CORS、設定檔、.env）
4. 資料庫模型（SQLAlchemy + GeoAlchemy2）
5. 資料庫遷移（Alembic 001~004）
6. 前端基礎（React + Vite + TypeScript + Tailwind CSS）

### 階段 2: 核心後端 API ✅
7. 事件 CRUD API（GET/PUT/DELETE /api/events）
8. 通報 API（GET /api/reports）
9. 地理空間查詢（GET /api/events/map + ST_Within）
10. 搜尋篩選排序分頁

### 階段 3: LLM 對話通報 ✅
11. LLM Service（Claude API 整合、Tool Use、SSE 串流）
12. System Prompt 設計（引導通報語氣策略）
13. Chat API（POST /api/chat，多輪追問與確認）
14. 多層級 Geocoding Service（Google Places / Nominatim / Google Geocoding）
15. 去重 Service（多維評分 + LLM 輔助判斷）

### 階段 4: 前端介面 ✅
16. Layout 與路由（Header、Sidebar、React Router）
17. 地圖總覽頁（Leaflet、CircleMarker、篩選、位置修正）
18. 對話通報頁（Chat UI、SSE streaming、候選卡片、摘要）
19. 災情列表頁（表格、搜尋、篩選、排序、分頁）
20. 災情詳情頁（完整資訊、關聯通報、編輯表單、刪除確認）
21. 使用說明頁

### 階段 5: 進階功能 ✅
22. 事件合併邏輯（描述合併 + LLM 重新萃取傷亡數字）
23. 候選事件選擇卡片（CandidateSelectionCard）
24. 地址消歧義與精確度追問機制
25. 狀態值更新（active → open → reported）
26. LLM 呼叫日誌監控（GET /api/llm-logs）

### 階段 6: 前後端拆分 + 認證 ✅
27. 後端 JWT 認證（User model、Auth Service、Auth API）
28. 受保護端點（PUT/DELETE/PATCH events、LLM logs 需認證）
29. 民眾端前端（frontend-public/，port 5173）
30. 管理中心端前端（frontend-admin/，port 5174）
31. 啟動/停止腳本更新（start.ps1、stop.ps1）

---

## 前置需求
- Node.js 18+（前端）
- Python 3.11+（後端）
- Docker Desktop（PostgreSQL + PostGIS）
- Anthropic API Key（Claude）
- Google Maps API Key（選用，啟用 Google Places 地理編碼）

---

## 驗證方式
1. **後端 API**: FastAPI Swagger UI (`/docs`)
2. **認證**: `POST /api/auth/login` 取得 JWT → 受保護端點驗證
3. **LLM 對話**: 模擬通報對話，驗證結構化擷取
4. **去重邏輯**: 多筆相近通報，驗證候選卡片顯示與合併
5. **地圖顯示**: 民眾端唯讀 vs 管理端含修正功能
6. **搜尋篩選**: 各種篩選組合驗證
7. **民眾端隔離**: 確認無編輯/刪除 API 呼叫
8. **管理端認證**: 未登入導向 /login、登出清除 token
