# Code Review 報告：通報中心追問機制 Phase 1–3

**審查日期**：2026-04-18
**範圍**：通報中心追問機制（方案 A + B + C）Phase 1–3 完整實作
**審查人**：code-reviewer agent

## 功能概要

- **方案 A**：LLM 強制收集 `reporter_name` / `reporter_phone` / `preferred_channel`，計算資訊完整度
- **方案 B**：`pending_clarification` 狀態 + `chat_sessions` 表 + `session_token` 讓民眾回到同一個對話
- **方案 C**：SMS（Twilio）/ LINE Messaging / Email（SMTP）外部推播 + Webhook 回收狀態 + 每日推播上限 kill switch + 重試 + rate limiting

---

## CRITICAL 問題

### [CRITICAL-1] 硬編碼的非官方 API base_url 洩漏自訂代理伺服器位址

**檔案**：`backend/app/services/llm_service.py:135`

```python
# 現況
return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, base_url="https://api.banana2556.com")
```

**問題**：
1. 這是一個非官方的第三方代理伺服器 URL，所有傳送給 Claude 的對話內容（含完整災情描述、通報者姓名、電話、LINE user ID、email）都會經過此代理，造成嚴重的個人資料外洩風險。
2. 已被硬編碼進原始碼，將被 commit 到 git 歷史。

**建議修正**：

```python
# 移除 base_url，若需要代理則改為環境變數
base_url = settings.ANTHROPIC_BASE_URL or None
return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, base_url=base_url)
```

並在 `config.py` 新增 `ANTHROPIC_BASE_URL: str = ""`，同時在 `.env.example` 加上說明。

---

### [CRITICAL-2] JWT_SECRET_KEY 預設值為明文弱密鑰，生產環境零防護

**檔案**：`backend/app/config.py:18`

```python
JWT_SECRET_KEY: str = "change-me-in-production"
```

**問題**：若 `.env` 未設定，使用預設值即可偽造任何管理員 JWT token，等同完全繞過認證。這個預設值透過 pydantic-settings 會在 `.env` 未設定時生效。

**建議修正**：

```python
JWT_SECRET_KEY: str  # 完全不提供預設值，強制 pydantic 在缺少環境變數時啟動失敗
```

或在應用啟動時做驗證：

```python
if settings.JWT_SECRET_KEY in ("change-me-in-production", "", "secret"):
    raise RuntimeError("JWT_SECRET_KEY 必須在生產環境設定為強隨機字串")
```

---

### [CRITICAL-3] Twilio Webhook 在 `TWILIO_AUTH_TOKEN` 為空字串時仍允許任意請求通過

**檔案**：`backend/app/api/webhooks.py:48-51`

```python
validator = RequestValidator(settings.TWILIO_AUTH_TOKEN or "")
url = str(request.url)
if not validator.validate(url, form_dict, signature):
    raise HTTPException(status_code=403, detail="Twilio signature 驗證失敗")
```

**問題**：`settings.TWILIO_AUTH_TOKEN or ""` 當 token 為空字串時，`RequestValidator("")` 仍然能被初始化，且任何攻擊者只要知道驗證邏輯就可以用空 token 計算出通過驗證的簽名，進而任意修改 `ClarificationRequest.status`（如將 `failed` 改成 `delivered`）或注入惡意 LINE 訊息。

**建議修正**：

```python
if not settings.TWILIO_AUTH_TOKEN:
    raise HTTPException(status_code=503, detail="SMS webhook 未設定")
validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
```

---

### [CRITICAL-4] LINE Webhook 驗簽後有靜默 fallback 繞過路徑

**檔案**：`backend/app/api/webhooks.py:105-112`

```python
except Exception as exc:  # noqa: BLE001
    logger.warning("LINE webhook parse error: %s", exc)
    try:
        payload = json.loads(body_text)
    except Exception:
        return {"ok": True}
    events = _fallback_parse(payload)
```

**問題**：`WebhookParser.parse()` 在簽名驗證失敗時會拋出 `InvalidSignatureError`（已在 line 103 處理），但若在此之後還發生其他例外，程式直接走 `_fallback_parse`。而 `_fallback_parse` 目前固定回傳 `[]`，但若未來有人實作此函數，就形成一條不需要合法簽名即可注入 LINE 事件的通道。更糟的是：這個 catch-all 包含了所有非 `InvalidSignatureError` 的例外，包括真正的簽名驗證失敗若 library 改版拋出不同的例外類型。

**建議修正**：

```python
# 只 catch 特定的 parsing/decode 例外，不要包住驗簽邏輯
try:
    events = parser.parse(body_text, signature)
except InvalidSignatureError as exc:
    raise HTTPException(status_code=403, detail="LINE signature 驗證失敗") from exc
# 其他例外（如 JSON 解析失敗）直接讓 FastAPI 回傳 500，由 LINE 重試
```

---

### [CRITICAL-5] `_process_tool_use` 中對 `merge_event_id` 的事件狀態驗證不正確

**檔案**：`backend/app/api/chat.py:383-387`

```python
if target_event.status != "reported":
    return {
        "status": "error",
        "message": f"事件「{target_event.title}」已結案，不可合併新通報。",
    }
```

**問題**：當事件狀態為 `pending_clarification` 時（即已有追問待回覆），此條件會阻擋新通報合併，而這正是追問機制設計上最需要允許的情境（民眾回來補充資訊）。邏輯上應允許 `reported` 和 `pending_clarification` 狀態的事件接受合併。

**建議修正**：

```python
MERGEABLE_STATUSES = {"reported", "pending_clarification"}
if target_event.status not in MERGEABLE_STATUSES:
    return {
        "status": "error",
        "message": f"事件「{target_event.title}」已結案，不可合併新通報。",
    }
```

---

## HIGH 問題

### [HIGH-1] `NotificationService.send()` 在重試期間阻塞 FastAPI async worker（同步 sleep）

**檔案**：`backend/app/services/notification_service.py:75-76`

```python
time.sleep(self._retry_delay)  # 預設 30 秒！
```

**問題**：`create_clarification` 是一個同步路由函數，FastAPI 會在 threadpool 執行；但若 Twilio/LINE/SMTP 第一次失敗，`time.sleep(30)` 會直接阻塞整個 thread 30 秒。在預設 threadpool 大小（4–16）的情況下，同時有多個失敗的推播就會耗盡全部 worker，導致 API 完全無響應。

**建議修正**：
1. 短期：移除重試邏輯，改由背景工作（如 Celery/ARQ）或前端重送機制處理；
2. 或至少將 `retry_delay` 預設改為 `0`（即立即重試一次），讓呼叫端自行決定要不要 retry。

---

### [HIGH-2] `InMemoryRateLimiter` 在多 worker 部署下完全失效

**檔案**：`backend/app/api/rate_limit.py:53`

```python
session_token_rate_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60.0)
```

**問題**：這是 module-level 的 in-memory singleton，在多 process 部署（Gunicorn + 多 worker）下每個 worker 擁有各自的計數器，攻擊者可以輕鬆發送 `10 × worker數量` 次請求而不被限流。此外，`threading.Lock` 也無法跨 process 保護。

**建議**：應在問題描述中明確記錄此限制，並在有多 worker 需求時改用 Redis-based rate limiter（如 `slowapi` + Redis 後端）。

---

### [HIGH-3] `_merge_into_event` 在高並發下有 lost update（race condition）

**檔案**：`backend/app/api/chat.py:129, 165-167`

```python
target_event.report_count += 1
# ...
target_event.casualties += tool_data.get("casualties", 0)
```

**問題**：`report_count += 1` 是 read-then-write 操作，在 ORM 層面會展開成：
1. `SELECT report_count FROM disaster_events WHERE id = ?` → 取得 N
2. `UPDATE disaster_events SET report_count = N+1 WHERE id = ?`

若兩個請求同時執行，兩者都讀到 N，最終結果是 N+1 而非 N+2。

**建議修正**：使用 SQL-level 原子更新：

```python
from sqlalchemy import update
db.execute(
    update(DisasterEvent)
    .where(DisasterEvent.id == target_event.id)
    .values(report_count=DisasterEvent.report_count + 1)
)
```

或在 `db.get()` 時加上 `with_for_update=True` 悲觀鎖。

---

### [HIGH-4] `_create_new_event` 中對 `occurred_at` 的 NULL 處理與 model 宣告衝突

**檔案**：`backend/app/api/chat.py:281-284` 與 `backend/app/models/disaster_event.py:25`

```python
# Model 宣告 occurred_at 為 nullable=False
occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

# 但 _create_new_event 建立時確實填入 occurred_at
# 問題在 _merge_into_event，target_event.occurred_at 可為 None：
if target_event.occurred_at is None and tool_data.get("occurred_at"):
```

模型宣告 `nullable=False`，但程式碼仍在防禦 `occurred_at is None`，顯示實際上可能存在 null 值（例如遷移前的舊資料）。如果 model 確保 not null，則這些防禦是無意義的；如果舊資料確實有 null，則需要 migration 補填。需要確認一致性。

---

### [HIGH-5] `get_notification_service()` singleton 在多 worker 環境有初始化競爭，且測試無法重設

**檔案**：`backend/app/api/deps.py:16-24`

```python
_notification_service_instance: NotificationService | None = None

def get_notification_service() -> NotificationService:
    global _notification_service_instance
    if _notification_service_instance is None:
        _notification_service_instance = build_notification_service(settings)
    return _notification_service_instance
```

**問題**：
1. 無 lock 保護，多 thread 初始化時可能建立多個實例（雖然影響不大，但不符合 singleton 語義）；
2. 測試之間共享同一個 singleton，無法通過依賴注入 override 重設，造成測試污染。

**建議**：使用 FastAPI 的 `lifespan` 初始化 singleton，或透過 `app.dependency_overrides` 提供可替換介面。

---

### [HIGH-6] `SMTP` 未驗證 `starttls()` 是否成功，且未設定連線 timeout

**檔案**：`backend/app/services/providers/smtp_email.py:42-44`

```python
with smtplib.SMTP(self._host, self._port) as smtp:
    smtp.starttls()
    if self._user and self._password:
        smtp.login(self._user, self._password)
```

**問題**：
1. `smtplib.SMTP()` 預設無 timeout，若 SMTP 伺服器無響應，此呼叫會永久阻塞；
2. `starttls()` 失敗時（如伺服器不支援 STARTTLS）不會拋出例外，而是靜默繼續，導致認證憑證以明文傳輸。

**建議修正**：

```python
with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
    smtp.ehlo()
    code, _ = smtp.starttls()
    if code != 220:
        raise smtplib.SMTPException(f"STARTTLS 失敗：{code}")
```

---

### [HIGH-7] `ClarificationHistoryList` 在 UI 中直接顯示 `recipient` 欄位（電話號碼/email）

**檔案**：`frontend-admin/src/components/events/ClarificationHistoryList.tsx:51`

```tsx
<span className="text-gray-700">→ {item.recipient}</span>
```

**問題**：`recipient` 包含民眾的完整電話號碼、email 或 LINE user ID，在管理介面直接明文顯示，所有能登入管理端的帳號（包括低權限帳號）都能看到完整聯絡資訊，違反個資最小揭露原則。

**建議**：前端遮蔽顯示（如 `0912***678`），或在 API 回傳前由後端遮蔽。

---

## MEDIUM 問題

### [MEDIUM-1] `compute_completeness` 邊界條件：傷亡數字為 `0` 會被判為「缺漏」

**檔案**：`backend/app/services/llm_service.py:176-178`

```python
for field in ("casualties", "injured", "trapped"):
    if extracted_data.get(field) is None:
        missing.append(field)
```

**問題**：`extracted_data.get("casualties")` 當值為 `0`（整數零）時回傳 `0`，Python 中 `0 is None` 為 False，所以 `0` 不會被加入 `missing`。這是預期行為。但 `extracted_data` 在事件 snapshot 中：

```python
event_snapshot = {
    "casualties": target_event.casualties,  # model 預設 0，不會是 None
}
```

因此合併後的事件永遠不會因為傷亡欄位而被標記缺漏，即使最初通報確實未填寫傷亡。此設計與 `_create_new_event` 中 `compute_completeness(tool_data)` 的行為不一致，因為 `tool_data.get("casualties")` 若 LLM 未填入則為 `None`。

---

### [MEDIUM-2] `notification_service.send()` 重試無 exponential backoff，固定 delay 對暫時性錯誤效果差

**檔案**：`backend/app/services/notification_service.py:64-77`

固定 30 秒 delay 在網路暫時抖動時過短、在 rate limit 情況下又過短（Twilio 通常要求等更長），缺乏 jitter 也可能造成 thundering herd。應改用指數退避。

---

### [MEDIUM-3] `_process_line_event` 中透過 `line_user_id` 查詢 report 會有歧義

**檔案**：`backend/app/api/webhooks.py:137-145`

```python
report = (
    db.query(DisasterReport)
    .filter(DisasterReport.reporter_line_user_id == user_id)
    .order_by(DisasterReport.created_at.desc())
    .first()
)
```

**問題**：若同一個 LINE user 通報了多個不同事件，這裡只取最新一筆 report 對應的事件，並把回覆記錄到那個事件的 session。若民眾先通報了事件 A 和事件 B，收到事件 A 的追問後回覆，系統卻將回覆記錄到事件 B（因為 B 更新）。應改為根據 `ClarificationRequest` 的 `event_id` 尋找最新未回覆的追問對應的事件。

---

### [MEDIUM-4] `ChatSessionPublic.messages` 使用 `list[dict[str, Any]]` 無型別保護

**檔案**：`backend/app/schemas/chat_session.py:16-22`

LINE webhook 會往 `session.messages` 注入 `{"role": "user", "content": text, "source": "line"}`，這些資料透過 `GET /api/chat/session/{token}` 不加過濾地回傳給公開端點的呼叫者，包含 `source` 欄位。應在 schema 層過濾只允許 `role`/`content` 欄位輸出。

---

### [MEDIUM-5] `events.py` 中 `GET /events/{event_id}/reports` 端點無認證保護，直接暴露通報者個資

**檔案**：`backend/app/api/events.py:123-140`

```python
@router.get("/events/{event_id}/reports", response_model=ReportListResponse)
def get_event_reports(event_id: UUID, db: Session = Depends(get_db)):
```

無 `current_user: User = Depends(get_current_user)` 保護，任何人（包括未登入的民眾端）只要猜到 `event_id`，即可取得該事件所有通報者的姓名、電話。雖然 event_id 是 UUID 難以枚舉，但應遵循最小權限原則加上認證。

---

### [MEDIUM-6] `llm_service.py` 中舊 model 設定殘留 debug 痕跡與模型名稱不符

**檔案**：`backend/app/config.py:13` 與 `backend/app/services/llm_service.py:134, 202, 237`

```python
# config.py
CLAUDE_MODEL: str = "gpt-5.4"   # ← 明顯不是合法的 Anthropic model name

# llm_service.py
# return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)  # 被注解掉
return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, base_url="https://api.banana2556.com")
```

`gpt-5.4` 不是有效的 Anthropic model ID，這加上 CRITICAL-1 的代理 URL，強烈暗示此程式碼目前被路由到非官方的代理服務，所有 API 呼叫的行為、計費、資料安全皆不受 Anthropic 原廠保證。多處注解掉的程式碼（`merge_event_descriptions`/`reextract_numbers_from_description` 中也有相同的注解 model）應清理。

---

### [MEDIUM-7] `DisasterEvent.occurred_at` 解析失敗時靜默 fallback 為 now

**檔案**：`backend/app/api/chat.py:363-367`

```python
try:
    occurred_at = datetime.fromisoformat(occurred_at_str)
    ...
except ValueError:
    occurred_at = datetime.now(timezone.utc)  # fallback 為目前時間
```

Fallback 邏輯本身無誤，但沒有記錄 log 提示解析失敗，導致資料品質問題靜默發生。建議加上 `logger.warning("occurred_at 解析失敗: %s，fallback 為目前時間", occurred_at_str)`。

---

### [MEDIUM-8] `ReportSummary.tsx` 中 `window.location.origin` 在非瀏覽器環境下會炸

**檔案**：`frontend-public/src/components/chat/ReportSummary.tsx:19, 65`

```tsx
const resumeUrl = sessionToken ? `/chat/resume/${sessionToken}` : null;
// ...
{window.location.origin}{resumeUrl}
```

此為 CSR 應用問題較小，但使用 `window.location.origin` 而非 React 慣用的 `import.meta.env.VITE_PUBLIC_URL` 在 Vite 環境下顯得不一致，且若未來有 SSR 改版會直接爆炸。

---

## LOW 問題

### [LOW-1] `webhooks.py` import 放在模組中段違反 PEP 8

**檔案**：`backend/app/api/webhooks.py:86-88`

標有 `# noqa: E402` 且有注解說明，但更好的做法是將 import 移至檔案頂端，或使用條件性延遲 import 在函數內部。

---

### [LOW-2] `_fallback_parse` 函數毫無實作意義，只是一個回傳空列表的佔位函數

**檔案**：`backend/app/api/webhooks.py:121-123`

```python
def _fallback_parse(payload: dict) -> list:
    """測試環境下若 WebhookParser 嚴格驗證失敗，走 raw dict 解析。"""
    return []
```

docstring 說明「測試環境下」，但此函數在生產環境的 exception handler 中也被呼叫。應移除此函數並改為直接 `return []` 或重新拋出例外。

---

### [LOW-3] `ClarificationRequest.session_id` FK 缺少 `ondelete` 策略

**檔案**：`backend/app/models/clarification_request.py:23`

```python
session_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=True
)
```

未設定 `ondelete`，若 `chat_sessions` 記錄被刪除，`clarification_requests.session_id` 會變成懸掛 FK（dangling reference），應加上 `ondelete="SET NULL"`。

---

### [LOW-4] `EventDetail.tsx` 的 `useCallback` dep 不完整

**檔案**：`frontend-admin/src/components/events/EventDetail.tsx:107-118`

這是輕微問題，因為 `getClarificationRequests` 為模組級別的穩定函數引用，實際上不會造成 bug，但建議加上 ESLint `exhaustive-deps` 規則來強制確保 deps 完整。

---

### [LOW-5] `ClarificationModal` 的 `useEffect` dep 包含物件，可能導致不必要的 reset

**檔案**：`frontend-admin/src/components/events/ClarificationModal.tsx:64-71`

```tsx
useEffect(() => {
    if (!open) return;
    // ...
}, [open, latestReport, completeness]);
```

`completeness` 是從父元件傳入的物件，若父元件每次 render 都產生新的物件引用（即使值相同），此 effect 會不斷觸發並重設 `question` 欄位，可能干擾管理員正在輸入的文字。

---

### [LOW-6] `notification_service.py` 對 `daily_limit=0` 的邊界未明確記載

**檔案**：`backend/app/services/notification_service.py:93`

```python
if sent_today >= self._daily_limit:
    raise DailyLimitExceeded(...)
```

若 `CLARIFICATION_DAILY_LIMIT=0`，第一次呼叫就會立即觸發 `DailyLimitExceeded`（`0 >= 0`），等同完全停用推播。這可能是預期的 kill switch 行為，但應在文件或 `config.py` 的 `Field` 說明中明確記載（例如加上 `Field(ge=1, description="設為 0 將停用所有推播")`）。

---

## Review Summary

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 5     | block  |
| HIGH     | 7     | warn   |
| MEDIUM   | 8     | info   |
| LOW      | 6     | note   |

**Verdict: BLOCK — 必須在合併前修正所有 CRITICAL 問題。**

---

## 最優先處理順序

1. **CRITICAL-1**（banana2556 代理伺服器）：所有通報資料與個人資訊可能流向第三方，這是目前最嚴重的資料隱私風險，且若這只是開發用的臨時代理，必須立即確認是否能移除。

2. **CRITICAL-2**（JWT 預設密鑰）：任何知道此預設值的人都能偽造管理員 token，是認證完全失效的漏洞。

3. **CRITICAL-3 + CRITICAL-4**（Webhook 驗簽繞過）：攻擊者可以偽造 Twilio/LINE webhook 事件，任意修改追問狀態或注入惡意訊息。

4. **CRITICAL-5**（`pending_clarification` 合併阻擋）：這是影響核心業務邏輯的功能性 bug，民眾持 session_token 回來補充資訊時，若事件狀態為 `pending_clarification`，整個追問回覆流程會無法正常完成。
