"""SMTP email provider。"""

from __future__ import annotations

import logging
import smtplib
import uuid
from email.message import EmailMessage

from app.services.notification_service import ProviderResult

logger = logging.getLogger(__name__)


class SMTPEmailProvider:
    """透過 SMTP 寄送 plain text 追問郵件。"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_address: str,
        subject: str = "通報中心追問通知",
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from = from_address
        self._subject = subject

    def send(self, recipient: str, body: str) -> ProviderResult:
        try:
            msg = EmailMessage()
            msg["Subject"] = self._subject
            msg["From"] = self._from
            msg["To"] = recipient
            msg.set_content(body)

            with smtplib.SMTP(self._host, self._port) as smtp:
                smtp.starttls()
                if self._user and self._password:
                    smtp.login(self._user, self._password)
                smtp.send_message(msg)

            return ProviderResult(
                success=True,
                provider_message_id=f"smtp-{uuid.uuid4().hex[:12]}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("SMTP send failed: %s", exc)
            return ProviderResult(
                success=False,
                error_message=str(exc),
            )
