"""Email delivery helpers for practical company workflows."""

from __future__ import annotations

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from typing import Dict

try:
    from ai_company.config import (
        SMTP_FROM_EMAIL,
        SMTP_FROM_NAME,
        SMTP_HOST,
        SMTP_PASSWORD,
        SMTP_PORT,
        SMTP_USERNAME,
        SMTP_USE_SSL,
        SMTP_USE_TLS,
    )
except ImportError:
    from config import (
        SMTP_FROM_EMAIL,
        SMTP_FROM_NAME,
        SMTP_HOST,
        SMTP_PASSWORD,
        SMTP_PORT,
        SMTP_USERNAME,
        SMTP_USE_SSL,
        SMTP_USE_TLS,
    )


class EmailService:
    """Send real emails when SMTP is configured, otherwise queue them safely."""

    def __init__(self) -> None:
        self.host = SMTP_HOST
        self.port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.from_email = SMTP_FROM_EMAIL
        self.from_name = SMTP_FROM_NAME
        self.use_tls = SMTP_USE_TLS
        self.use_ssl = SMTP_USE_SSL

    @property
    def configured(self) -> bool:
        """Whether the service has enough configuration to attempt delivery."""
        return bool(self.host and self.from_email)

    def deliver(self, recipient_email: str, subject: str, body: str) -> Dict[str, str]:
        """Deliver or queue one email."""
        if not self.configured:
            return {
                "status": "queued",
                "delivery_note": "SMTP is not configured. Email stored in outbox only.",
                "sent_at": "",
            }

        message = EmailMessage()
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=30)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=30)
            with server:
                if self.use_tls and not self.use_ssl:
                    server.starttls(context=ssl.create_default_context())
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(message)
            return {
                "status": "sent",
                "delivery_note": "Email delivered through SMTP.",
                "sent_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        except Exception as exc:  # pragma: no cover
            return {
                "status": "failed",
                "delivery_note": f"SMTP delivery failed: {exc}",
                "sent_at": "",
            }
