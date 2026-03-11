# 智慧災害通報系統 — Code Review 報告

## 背景

本報告針對整個專案（後端 FastAPI + 前端 React/TypeScript）進行全面的安全漏洞與程式品質審查。
範圍包含：後端 API、服務層、資料模型、Schema 驗證、前端元件、環境配置、部署設定。

---

## 問題總覽

| 嚴重程度 | 數量 |
|---------|------|
| 🔴 Critical | 4 |
| 🟠 High | 12 |
| 🟡 Medium | 11 |
| 🔵 Low | 8 |

---

## 🔴 Critical 級別

### C-1：真實 Google API Key 暴露
- **檔案**：`backend/.env` 第 2 行
- **問題**：`.env` 含有真實 `GOOGLE_API_KEY=AIzaSy...`，若被提交進版本控制，攻擊者可濫用 LLM API 造成高額費用。
- **建議**：立即在 Google Cloud Console 撤銷並重新生成此 Key；確認 `.env` 已加入 `.gitignore`。

### C-2：整個專案缺少 `.gitignore`
- **檔案**：專案根目錄（不存在 `.gitignore`）
- **問題**：`.env`、`__pycache__/`、`node_modules/`、`*.pyc` 等敏感或無用檔案可能被提交到 Git。
- **建議**：在根目錄建立 `.gitignore`，至少包含：
  ```
  .env
  .env.*.local
  __pycache__/
  *.pyc
  node_modules/
  .pytest_cache/
  venv/
  ```

### C-3：所有 API 端點無任何認證/授權
- **檔案**：`backend/app/api/events.py`、`reports.py`、`chat.py`
- **問題**：任何人都可以呼叫 `PUT /api/events/{id}` 修改傷亡人數、`GET /api/reports` 取得所有通報者個資，完全無身份驗證。
- **建議**：至少為寫入端點（PUT）和含個資的端點加上 JWT / OAuth2 Bearer token 驗證，並設計 RBAC（公眾/應急人員/管理員）。

### C-4：缺少 Rate Limiting（LLM 被濫用風險）
- **檔案**：`backend/app/api/chat.py` 第 136–163 行
- **問題**：`POST /api/chat` 無速率限制，攻擊者可大量請求觸發 LLM API 調用，導致高額費用或服務中斷。
- **建議**：使用 `slowapi` 或 `fastapi-limiter`，對 `/chat` 設定如 10 requests/min per IP。

---

## 🟠 High 級別

### H-1：CORS 過於寬鬆
- **檔案**：`backend/app/main.py` 第 8–14 行
- **問題**：`allow_methods=["*"]`、`allow_headers=["*"]` 允許任何方法與 header；`allow_origins` 硬碼為開發環境 URL，生產環境無法正確使用。
- **建議**：明確列出方法（`["GET","POST","PUT"]`）和 headers（`["Content-Type","Authorization"]`），origins 改從環境變數 `ALLOWED_ORIGINS` 讀取。

### H-2：資料庫憑證硬碼（預設弱密碼）
- **檔案**：`backend/app/config.py` 第 5 行、`alembic.ini` 第 3 行、`docker-compose.yml`
- **問題**：`postgres:postgres` 預設密碼硬碼於多處，生產環境若未改動即為高風險。
- **建議**：`config.py` 的預設值移除或改為空字串（強制必須設環境變數）；`alembic.ini` 改用 `%(DATABASE_URL)s` 佔位；`docker-compose.yml` 改用 `${DB_PASSWORD}`。

### H-3：通報者個資（PII）在公開 API 中完整回傳
- **檔案**：`backend/app/schemas/report.py`、`app/api/events.py` 第 81–97 行、`app/api/reports.py`
- **問題**：`reporter_name`、`reporter_phone` 在無認證的情況下對所有人回傳，違反個資保護原則。
- **建議**：建立 `ReportResponsePublic`（不含 PII）和 `ReportResponseAdmin`（含 PII）兩種 schema，公開端點使用前者。

### H-4：ChatRequest 缺少輸入長度限制
- **檔案**：`backend/app/schemas/chat.py` 第 9–12 行
- **問題**：`message: str` 無長度上限（可傳超長文字消耗大量 token）；`history` 無最大筆數限制；`conversation_id` 無格式驗證。
- **建議**：
  ```python
  message: str = Field(min_length=1, max_length=5000)
  history: list[ChatMessage] = Field(default=[], max_length=50)
  conversation_id: str | None = Field(default=None, pattern=r"^[a-f0-9-]{36}$")
  ```

### H-5：LLM 工具回傳參數直接使用，未做驗證
- **檔案**：`backend/app/api/chat.py` 第 21–133 行 `_process_tool_use()`
- **問題**：LLM 回傳的 `latitude`、`longitude`、`severity`、`reporter_phone` 等欄位直接寫入資料庫，無邊界或格式驗證（如 lat 應在 −90~90）。
- **建議**：建立 `DisasterReportData` Pydantic model 驗證所有工具參數，包含數值範圍與電話格式。

### H-6：LIKE 查詢特殊字元未轉義（潛在 LIKE Injection）
- **檔案**：`backend/app/services/event_service.py` 第 57–65 行
- **問題**：`pattern = f"%{search}%"` 未轉義 `%`、`_` 通配字元，攻擊者可構造特殊搜尋詞造成效能問題或資訊洩漏。
- **建議**：
  ```python
  search_escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
  pattern = f"%{search_escaped}%"
  query = query.filter(DisasterEvent.title.ilike(pattern, escape="\\"))
  ```

### H-7：前端 XSS 風險（聊天訊息未 sanitize）
- **檔案**：`frontend/src/components/chat/ChatMessage.tsx` 第 15 行、`ReportSummary.tsx` 第 19 行
- **問題**：後端回傳的訊息內容直接渲染，未做 HTML sanitization，若後端資料遭污染可觸發 XSS。
- **建議**：引入 `dompurify`，對所有動態文字內容進行 `DOMPurify.sanitize()`。

### H-8：前端缺少 Content Security Policy
- **檔案**：`frontend/index.html`
- **問題**：HTML `<head>` 沒有 CSP meta tag，無法阻擋 inline script 注入。
- **建議**：加入 CSP 標頭（透過 meta tag 或 web server 設定），至少設定 `default-src 'self'`。

### H-9：MapEventLoader 缺少 `useCallback`，可能引發無限重繪
- **檔案**：`frontend/src/components/map/DisasterMap.tsx` 第 24–37 行
- **問題**：`onEventsLoaded` 在父元件每次 render 都產生新的函式引用，若作為 `useEffect` dependency 將觸發無限循環載入地圖資料。
- **建議**：在 `DisasterMap` 中用 `useCallback` 包裝 `handleEventsLoaded`。

### H-10：缺少 React Error Boundary
- **檔案**：`frontend/src/App.tsx`
- **問題**：無全局 Error Boundary，任何子元件的 render 錯誤都會讓整個應用崩潰，白屏無提示。
- **建議**：建立 `ErrorBoundary` 元件包裹路由，顯示友善的錯誤頁面。

### H-11：uvicorn `--reload` 被列入啟動文件，易被誤用於生產
- **檔案**：`README.md` 第 65 行
- **問題**：文件中的啟動指令 `uvicorn app.main:app --reload` 若被直接複製到生產環境，會降低效能並增加不穩定風險。
- **建議**：分開說明開發 vs 生產啟動指令；生產建議使用 `gunicorn -w 4 -k uvicorn.workers.UvicornWorker`。

### H-12：PII 可能無意間記錄到日誌
- **檔案**：`backend/app/api/chat.py` 第 143–145 行
- **問題**：聊天歷史 `raw_message` 的組裝過程可能包含通報者電話、姓名，一旦日誌系統啟用即造成 PII 洩漏。
- **建議**：在組裝 `raw_message` 時對敏感欄位遮蔽；未來新增日誌時明確排除 PII 欄位。

---

## 🟡 Medium 級別

### M-1：資料庫 Session 異常時無 rollback
- **檔案**：`backend/app/api/chat.py` 第 89、123–128 行
- **問題**：`_process_tool_use()` 中呼叫 `db.commit()` 前若發生例外（如地理編碼失敗），資料庫狀態可能不一致，且沒有 `try/except/rollback` 保護。
- **建議**：所有 `db.commit()` 前加上 `try/except`，`except` 中呼叫 `db.rollback()`。

### M-2：SSE 流式事件生成器無錯誤處理
- **檔案**：`backend/app/api/chat.py` 第 147–162 行 `event_generator()`
- **問題**：LLM 串流過程若發生例外，客戶端不會收到錯誤通知，連線直接中斷無說明。
- **建議**：在 `event_generator()` 中加入 try/except，捕捉例外後 yield 一個 `{"type":"error","message":"..."}` 事件。

### M-3：地理編碼失敗 fallback 至台灣中心座標（誤導性）
- **檔案**：`backend/app/api/chat.py` 第 27–35 行
- **問題**：`geocode_address` 失敗時，自動使用 `(23.5, 121.0)`（台灣中心）作為事件座標，導致地圖上顯示錯誤位置。
- **建議**：地理編碼失敗時應記錄警告並要求使用者提供更精確的地址，而非使用預設座標。

### M-4：整個專案缺少日誌記錄系統
- **檔案**：`backend/app/main.py`（及所有 API 路由檔案）
- **問題**：沒有任何 `logging` 設定，無法追蹤 API 請求、錯誤、安全事件，也無法審計敏感操作。
- **建議**：在 `main.py` 配置 `logging.dictConfig`，在各 API 路由加入 `logger.info/error` 呼叫。

### M-5：LLM 模型名稱硬碼
- **檔案**：`backend/app/services/llm_service.py`、`dedup_service.py` 中 `model="gemini-2.0-flash"`
- **問題**：模型升級需要修改原始碼並重新部署，且兩個服務中可能出現版本不一致。
- **建議**：在 `config.py` 新增 `LLM_MODEL: str = "gemini-2.0-flash"`，兩個服務統一使用 `settings.LLM_MODEL`。

### M-6：ChatWindow 元件的 SSE 連線未在卸載時清理（記憶體洩漏）
- **檔案**：`frontend/src/components/chat/ChatWindow.tsx`
- **問題**：元件卸載時若 SSE fetch 仍在進行，沒有呼叫 `AbortController.abort()`，造成記憶體洩漏及潛在的 state 更新錯誤。
- **建議**：用 `useRef` 儲存 `AbortController`，在 `useEffect` cleanup 函式中呼叫 `controller.abort()`。

### M-7：資料庫連線無 SSL/TLS
- **檔案**：`backend/app/database.py`
- **問題**：`create_engine(settings.DATABASE_URL)` 未指定 SSL 設定，生產環境中資料庫連線為明文。
- **建議**：在 DATABASE_URL 加上 `?sslmode=require` 或在 `create_engine` 傳入 `connect_args={"sslmode": "require"}`。

### M-8：資料庫使用超級用戶帳號（無最小權限原則）
- **檔案**：`docker-compose.yml`
- **問題**：應用程式直接使用 `postgres` 超級用戶，若 SQL injection 成功可執行任意 DB 指令。
- **建議**：為應用程式建立僅有 SELECT/INSERT/UPDATE/DELETE 權限的專用 DB user。

### M-9：`google-genai` 版本未鎖定（`>=1.0.0`）
- **檔案**：`backend/requirements.txt`
- **問題**：使用 `>=` 而非 `==`，pip install 時可能安裝到含有破壞性變更或漏洞的新版。
- **建議**：固定為 `google-genai==x.y.z`；並定期使用 `pip-audit` 或 `safety check` 掃描依賴漏洞。

### M-10：前端 API 回應無執行時型別驗證
- **檔案**：`frontend/src/services/api.ts`
- **問題**：後端回應直接 cast 為 TypeScript interface，若後端資料結構有誤，執行時才會發生不可預期的錯誤。
- **建議**：引入 `zod`，為主要 API 回應（EventListResponse、EventResponse）定義 schema 並在 `fetchJSON` 中做 `schema.parse(data)`。

### M-11：Sidebar emoji 圖示缺少 ARIA 標籤
- **檔案**：`frontend/src/components/layout/Sidebar.tsx` 第 4 行
- **問題**：使用 emoji 作為導覽圖示，螢幕閱讀器無法正確識別，不符合無障礙規範 WCAG 2.1。
- **建議**：在 emoji 外層加 `<span aria-hidden="true">`，並在 `<NavLink>` 加上 `aria-label={item.label}`。

---

## 🔵 Low 級別

### L-1：缺少 API 版本控制
- **建議**：prefix 從 `/api` 改為 `/api/v1`，方便未來不破壞性升級。

### L-2：缺少健康檢查端點
- **建議**：新增 `GET /health`（回傳服務狀態）和 `GET /readiness`（驗證 DB 連線），供 K8s probe 或監控系統使用。

### L-3：外部 CDN 資源缺少 Subresource Integrity (SRI)
- **檔案**：`frontend/index.html`（Leaflet CSS 從 unpkg.com 載入）
- **建議**：為 CDN link/script 加上 `integrity="sha384-..."` 屬性，防止供應鏈攻擊。

### L-4：`EventEditForm` 表單 label 未關聯 input（`htmlFor` 缺失）
- **檔案**：`frontend/src/components/events/EventEditForm.tsx`
- **建議**：所有 `<label>` 加上 `htmlFor`，對應 `<input id>` 屬性。

### L-5：型別轉換不安全（`as` 未驗證）
- **檔案**：`frontend/src/components/map/MapFilters.tsx` 第 24 行
- **問題**：`e.target.value as DisasterType` 未檢查值是否真的在允許的 enum 範圍內。
- **建議**：用 `validTypes.includes(value)` 驗證後再 cast。

### L-6：缺少 `requirements-dev.txt`
- **建議**：將 `pytest`、`pytest-asyncio`、`pytest-mock` 等僅測試用的依賴移至獨立的 `requirements-dev.txt`，避免污染生產映像。

### L-7：前端使用 Emoji 作為圖示（跨平台不一致）
- **建議**：改用圖示庫（`react-icons`、`heroicons`），確保跨 OS/瀏覽器顯示一致並方便主題化。

### L-8：過度使用 `Record<string, unknown>` 型別
- **檔案**：`frontend/src/components/events/EventDetail.tsx`、`EventEditForm.tsx`
- **建議**：定義具體的 `EventFormData` interface 以獲得完整的型別安全保障。

---

## 優先執行計劃

### 立即（今天）— Critical
1. 撤銷 Google API Key 並重新生成
2. 建立 `.gitignore`，確認 `.env` 已排除
3. 確認 `.env` 未出現在 git history 中（必要時用 `git filter-branch` 或 BFG 清理）

### 本週 — High
4. 加入 Rate Limiting（`POST /api/chat`）
5. 為寫入端點實作基礎 JWT 認證
6. 建立 `ReportResponsePublic` 隱藏 PII
7. 修正 `ChatRequest` 輸入長度限制
8. 修正 `MapEventLoader` `useCallback` 無限迴圈
9. 加入 React Error Boundary

### 本月 — Medium / Low
10. 全面加入日誌系統
11. 修正 DB Session rollback、SSE 錯誤處理
12. 固定 `google-genai` 版本、加入 `pip-audit` CI check
13. 前端加入 Zod API 回應驗證
14. 無障礙性修正（ARIA label、表格 scope）

---

## 受影響的關鍵檔案

| 路徑 | 主要問題 |
|------|---------|
| `backend/.env` | C-1：真實 API Key |
| 根目錄（缺失） | C-2：無 .gitignore |
| `backend/app/api/chat.py` | C-4, H-5, M-1, M-2, M-3 |
| `backend/app/api/events.py` | C-3, H-3, H-6 |
| `backend/app/api/reports.py` | C-3, H-3 |
| `backend/app/main.py` | H-1, M-4 |
| `backend/app/schemas/chat.py` | H-4 |
| `backend/app/config.py` | H-2, M-5 |
| `backend/app/services/event_service.py` | H-6 |
| `backend/app/services/dedup_service.py` | M-5 |
| `backend/app/database.py` | M-7 |
| `backend/requirements.txt` | M-9, L-6 |
| `frontend/src/components/chat/ChatMessage.tsx` | H-7 |
| `frontend/src/components/chat/ReportSummary.tsx` | H-7 |
| `frontend/src/components/chat/ChatWindow.tsx` | M-6 |
| `frontend/src/components/map/DisasterMap.tsx` | H-9 |
| `frontend/src/App.tsx` | H-10 |
| `frontend/index.html` | H-8, L-3 |
| `frontend/src/services/api.ts` | M-10 |
