import logging
import re

# 需遮罩的 query 參數名（大小寫不敏感）。涵蓋 Google Maps `key`、
# 各式 api key / token / 密碼 / 簽章，避免明碼寫進 log（httpx INFO 會印完整 URL）。
_SENSITIVE_PARAMS = (
    "key",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "password",
    "secret",
    "signature",
    "sig",
)

# 比對 `?key=xxx` / `&token=xxx`，僅擷取到值的結尾（下一個 & 或空白/引號前）。
_REDACT_RE = re.compile(
    r"(?i)([?&](?:" + "|".join(_SENSITIVE_PARAMS) + r")=)([^&\s\"']+)"
)

_REDACTED = "***REDACTED***"


def _redact(text: str) -> str:
    """把字串中敏感 query 參數的值換成遮罩標記。"""
    return _REDACT_RE.sub(lambda m: m.group(1) + _REDACTED, text)


class RedactSecretsFilter(logging.Filter):
    """logging filter：遮罩 log 訊息中 URL 的敏感 query 參數值。

    先以 `record.getMessage()` 完成 %-格式化，再對成品字串遮罩，最後把
    結果寫回 `record.msg` 並清空 `record.args`。如此無論金鑰落在 msg 本體或
    args（httpx 把 URL 放在 args）都能一致遮罩。filter 一律回傳 True，只改寫內容不丟棄記錄。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            # 格式化失敗（罕見）就不動記錄，讓原本的 handler 自行處理。
            return True
        redacted = _redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True
