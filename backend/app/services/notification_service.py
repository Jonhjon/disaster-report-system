"""Notification service：統一封裝 SMS/LINE/Email 推播 provider。

各 provider 只需實作 `send(recipient, body) -> ProviderResult`。
`NotificationService` 以 channel 字串路由到對應 provider，並提供 daily limit 檢查。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderResult:
    """單次推播結果。"""

    success: bool
    provider_message_id: str | None = None
    error_message: str | None = None


class NotificationProvider(Protocol):
    """推播 provider 介面。"""

    def send(self, recipient: str, body: str) -> ProviderResult: ...


class DailyLimitExceeded(Exception):
    """當日已達 CLARIFICATION_DAILY_LIMIT。"""


class NotificationService:
    """依 channel 路由到對應 provider，並提供每日上限檢查。"""

    def __init__(
        self,
        providers: dict[str, NotificationProvider],
        daily_limit: int = 500,
        retry_delay: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        self._providers = dict(providers)
        self._daily_limit = daily_limit
        self._retry_delay = retry_delay
        self._max_retries = max_retries

    @property
    def enabled_channels(self) -> list[str]:
        return sorted(self._providers.keys())

    def send(self, channel: str, recipient: str, body: str) -> ProviderResult:
        provider = self._providers.get(channel)
        if provider is None:
            return ProviderResult(
                success=False,
                error_message=f"channel '{channel}' 尚未設定 provider",
            )

        attempts = self._max_retries + 1  # 初次 + 重試次數
        last_result = ProviderResult(success=False, error_message="not attempted")
        for i in range(attempts):
            last_result = provider.send(recipient, body)
            if last_result.success:
                return last_result
            # 最後一次仍失敗就直接回傳
            if i < attempts - 1:
                logger.info(
                    "channel=%s 送出失敗（%s），%.1fs 後重試",
                    channel, last_result.error_message, self._retry_delay,
                )
                time.sleep(self._retry_delay)
        return last_result

    def check_daily_limit(self, db) -> None:
        """查今日 sent 數量，超過上限時 raise DailyLimitExceeded。"""
        from app.models import ClarificationRequest

        start_of_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tomorrow = start_of_day + timedelta(days=1)
        sent_today = (
            db.query(ClarificationRequest)
            .filter(ClarificationRequest.sent_at >= start_of_day)
            .filter(ClarificationRequest.sent_at < tomorrow)
            .count()
        )
        if sent_today >= self._daily_limit:
            raise DailyLimitExceeded(
                f"今日已達每日追問上限 ({sent_today}/{self._daily_limit})"
            )


def build_notification_service(settings) -> NotificationService:
    """依 settings 有哪些憑證決定啟用哪些 provider。"""
    providers: dict[str, NotificationProvider] = {}

    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER:
        from app.services.providers.twilio_sms import TwilioSMSProvider

        providers["sms"] = TwilioSMSProvider(
            account_sid=settings.TWILIO_ACCOUNT_SID,
            auth_token=settings.TWILIO_AUTH_TOKEN,
            from_number=settings.TWILIO_FROM_NUMBER,
        )

    if settings.LINE_CHANNEL_ACCESS_TOKEN:
        from app.services.providers.line_messaging import LineMessagingProvider

        providers["line"] = LineMessagingProvider(
            channel_access_token=settings.LINE_CHANNEL_ACCESS_TOKEN,
        )

    if settings.SMTP_HOST and settings.SMTP_FROM_ADDRESS:
        from app.services.providers.smtp_email import SMTPEmailProvider

        providers["email"] = SMTPEmailProvider(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            from_address=settings.SMTP_FROM_ADDRESS,
        )

    return NotificationService(
        providers=providers,
        daily_limit=settings.CLARIFICATION_DAILY_LIMIT,
    )
