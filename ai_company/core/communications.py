"""Email delivery helpers for practical company workflows."""

from __future__ import annotations

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from typing import Dict

import requests

try:
    from ai_company.config import (
        EMAIL_PROVIDER,
        BREVO_API_KEY,
        BREVO_API_URL,
        BREVO_FROM_EMAIL,
        BREVO_FROM_NAME,
        REQUEST_TIMEOUT,
        RESEND_API_KEY,
        RESEND_API_URL,
        RESEND_FROM_EMAIL,
        RESEND_FROM_NAME,
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
        EMAIL_PROVIDER,
        BREVO_API_KEY,
        BREVO_API_URL,
        BREVO_FROM_EMAIL,
        BREVO_FROM_NAME,
        REQUEST_TIMEOUT,
        RESEND_API_KEY,
        RESEND_API_URL,
        RESEND_FROM_EMAIL,
        RESEND_FROM_NAME,
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
        self.provider = EMAIL_PROVIDER.strip().lower()
        self.brevo_api_key = BREVO_API_KEY
        self.brevo_api_url = BREVO_API_URL
        self.brevo_from_email = BREVO_FROM_EMAIL
        self.brevo_from_name = BREVO_FROM_NAME
        self.resend_api_key = RESEND_API_KEY
        self.resend_api_url = RESEND_API_URL
        self.resend_from_email = RESEND_FROM_EMAIL
        self.resend_from_name = RESEND_FROM_NAME
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
        if self.provider == "brevo":
            return bool(self.brevo_api_key and self.brevo_from_email)
        if self.provider == "resend":
            return bool(self.resend_api_key and self.resend_from_email)
        if self.provider == "smtp":
            return bool(self.host and self.from_email and self.username and self.password)
        return False

    def deliver(self, recipient_email: str, subject: str, body: str, html_body: str = "") -> Dict[str, str]:
        """Deliver or queue one email."""
        if not self.configured:
            return {
                "status": "queued",
                "delivery_note": "No email provider is configured. Email stored in outbox only.",
                "sent_at": "",
            }

        if self.provider == "brevo":
            return self._deliver_via_brevo(recipient_email, subject, body, html_body)

        if self.provider == "resend":
            return self._deliver_via_resend(recipient_email, subject, body, html_body)

        message = EmailMessage()
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

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

    def _deliver_via_brevo(self, recipient_email: str, subject: str, body: str, html_body: str = "") -> Dict[str, str]:
        """Send an email through Brevo's transactional email API."""
        try:
            response = requests.post(
                self.brevo_api_url,
                headers={
                    "api-key": self.brevo_api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "sender": {
                        "name": self.brevo_from_name,
                        "email": self.brevo_from_email,
                    },
                    "to": [{"email": recipient_email}],
                    "subject": subject,
                    "textContent": body,
                    "htmlContent": html_body or "<br>".join(body.splitlines()),
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "status": "sent",
                "delivery_note": (
                    "Email delivered through Brevo. "
                    f"Message id: {payload.get('messageId', '') or payload.get('message-id', '')}"
                ).strip(),
                "sent_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        except requests.RequestException as exc:
            detail = ""
            if getattr(exc, "response", None) is not None:
                try:
                    detail = exc.response.text
                except Exception:
                    detail = ""
            message = f"Brevo delivery failed: {exc}"
            if detail:
                message = f"{message} | {detail[:220]}"
            return {
                "status": "failed",
                "delivery_note": message,
                "sent_at": "",
            }

    def _deliver_via_resend(self, recipient_email: str, subject: str, body: str, html_body: str = "") -> Dict[str, str]:
        """Send an email through Resend's REST API."""
        from_value = f"{self.resend_from_name} <{self.resend_from_email}>"
        try:
            response = requests.post(
                self.resend_api_url,
                headers={
                    "Authorization": f"Bearer {self.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_value,
                    "to": [recipient_email],
                    "subject": subject,
                    "text": body,
                    "html": html_body or "<br>".join(body.splitlines()),
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "status": "sent",
                "delivery_note": f"Email delivered through Resend. Message id: {payload.get('id', '')}",
                "sent_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        except requests.RequestException as exc:
            return {
                "status": "failed",
                "delivery_note": f"Resend delivery failed: {exc}",
                "sent_at": "",
            }
