"""Transactional email delivery helpers."""

from __future__ import annotations

from datetime import datetime

import httpx

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    """Raised when a transactional email cannot be delivered."""


class EmailService:
    def can_send(self) -> bool:
        provider = settings.email_provider.strip().lower()
        if provider == "resend":
            return bool(settings.resend_api_key.strip() and settings.email_from.strip())
        return False

    def send_login_code(self, to_email: str, code: str, expires_at: datetime) -> None:
        provider = settings.email_provider.strip().lower()
        if provider == "resend":
            self._send_resend_login_code(to_email, code, expires_at)
            return
        raise EmailDeliveryError("email_provider_not_configured")

    def _send_resend_login_code(self, to_email: str, code: str, expires_at: datetime) -> None:
        api_key = settings.resend_api_key.strip()
        sender = settings.email_from.strip()
        if not api_key or not sender:
            raise EmailDeliveryError("resend_not_configured")

        text = (
            f"Your Distilled TI login code is {code}. "
            f"It expires at {expires_at.isoformat()}. "
            "If you did not request this code, ignore this email."
        )
        html = f"""
        <div style="font-family:Arial,sans-serif;line-height:1.6;color:#1d2520">
          <h2>Distilled TI 登录验证码</h2>
          <p>你的验证码是：</p>
          <p style="font-size:28px;font-weight:700;letter-spacing:0.18em">{code}</p>
          <p>验证码将在 {expires_at.isoformat()} 过期。</p>
          <p>如果不是你本人操作，可以忽略这封邮件。</p>
        </div>
        """

        try:
            with httpx.Client(timeout=settings.email_timeout_seconds, follow_redirects=False) as client:
                response = client.post(
                    f"{settings.resend_base_url.rstrip('/')}/emails",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": sender,
                        "to": [to_email],
                        "subject": "你的 Distilled TI 登录验证码",
                        "html": html,
                        "text": text,
                    },
                )
                response.raise_for_status()
        except Exception as exc:  # pragma: no cover - covered with httpx mock objects in tests
            raise EmailDeliveryError(f"resend_send_failed:{exc}") from exc


email_service = EmailService()
