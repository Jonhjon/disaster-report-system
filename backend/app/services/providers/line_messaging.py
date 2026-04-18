"""LINE Messaging API provider。"""

from __future__ import annotations

import logging
import uuid

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from app.services.notification_service import ProviderResult

logger = logging.getLogger(__name__)


class LineMessagingProvider:
    """透過 LINE Messaging API 對使用者推播訊息。"""

    def __init__(self, channel_access_token: str) -> None:
        self._token = channel_access_token

    def send(self, recipient: str, body: str) -> ProviderResult:
        try:
            configuration = Configuration(access_token=self._token)
            with ApiClient(configuration) as api_client:
                api = MessagingApi(api_client)
                request = PushMessageRequest(
                    to=recipient,
                    messages=[TextMessage(text=body)],
                )
                api.push_message(request)
            return ProviderResult(
                success=True,
                provider_message_id=f"line-{uuid.uuid4().hex[:12]}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LINE push failed: %s", exc)
            return ProviderResult(
                success=False,
                error_message=str(exc),
            )
