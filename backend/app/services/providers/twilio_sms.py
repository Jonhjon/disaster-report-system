"""Twilio SMS provider。"""

from __future__ import annotations

import logging

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from app.services.notification_service import ProviderResult

logger = logging.getLogger(__name__)


class TwilioSMSProvider:
    """透過 Twilio REST API 發送 SMS。"""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number
        self._client: TwilioClient | None = None

    def _get_client(self) -> TwilioClient:
        if self._client is None:
            self._client = TwilioClient(self._account_sid, self._auth_token)
        return self._client

    def send(self, recipient: str, body: str) -> ProviderResult:
        try:
            message = self._get_client().messages.create(
                from_=self._from_number,
                to=recipient,
                body=body,
            )
            return ProviderResult(
                success=True,
                provider_message_id=message.sid,
            )
        except TwilioRestException as exc:
            logger.warning("Twilio send failed: %s", exc)
            return ProviderResult(
                success=False,
                error_message=f"Twilio {exc.status}: {exc.msg}",
            )
        except Exception as exc:  # noqa: BLE001 - 保底，避免外部錯誤穿透
            logger.exception("Twilio unexpected error")
            return ProviderResult(
                success=False,
                error_message=str(exc),
            )
