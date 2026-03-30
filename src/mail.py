"""SMTP sender and health checks for admin password reset flow."""

from __future__ import annotations

import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
import os


@dataclass
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    use_tls: bool
    use_starttls: bool
    mock_mode: bool


@dataclass
class SmtpHealth:
    ok: bool
    detail: str
    checked_at: float


_SMTP_HEALTH_CACHE: SmtpHealth | None = None
_SMTP_HEALTH_TTL_SECONDS = int(os.getenv("SMTP_HEALTH_TTL_SECONDS", "300"))


def load_smtp_settings() -> SmtpSettings:
    return SmtpSettings(
        host=(os.getenv("SMTP_HOST") or "").strip(),
        port=int(os.getenv("SMTP_PORT", "587")),
        username=(os.getenv("SMTP_USERNAME") or "").strip(),
        password=(os.getenv("SMTP_PASSWORD") or "").strip(),
        sender=(os.getenv("SMTP_SENDER") or "").strip(),
        use_tls=(os.getenv("SMTP_USE_TLS", "0").strip().lower() in ("1", "true", "yes", "on")),
        use_starttls=(os.getenv("SMTP_USE_STARTTLS", "1").strip().lower() in ("1", "true", "yes", "on")),
        mock_mode=(os.getenv("SMTP_MOCK", "0").strip().lower() in ("1", "true", "yes", "on")),
    )


def _smtp_connect(settings: SmtpSettings):
    timeout = int(os.getenv("SMTP_TIMEOUT_SECONDS", "8"))
    if settings.use_tls:
        context = ssl.create_default_context()
        client = smtplib.SMTP_SSL(settings.host, settings.port, timeout=timeout, context=context)
    else:
        client = smtplib.SMTP(settings.host, settings.port, timeout=timeout)
    client.ehlo()
    if settings.use_starttls and not settings.use_tls:
        context = ssl.create_default_context()
        client.starttls(context=context)
        client.ehlo()
    if settings.username and settings.password:
        client.login(settings.username, settings.password)
    return client


def check_smtp_health(force: bool = False) -> SmtpHealth:
    global _SMTP_HEALTH_CACHE
    now = time.time()
    if not force and _SMTP_HEALTH_CACHE and (now - _SMTP_HEALTH_CACHE.checked_at) < _SMTP_HEALTH_TTL_SECONDS:
        return _SMTP_HEALTH_CACHE
    settings = load_smtp_settings()
    if settings.mock_mode:
        _SMTP_HEALTH_CACHE = SmtpHealth(ok=True, detail="smtp mock mode", checked_at=now)
        return _SMTP_HEALTH_CACHE
    if not settings.host:
        _SMTP_HEALTH_CACHE = SmtpHealth(ok=False, detail="smtp host is empty", checked_at=now)
        return _SMTP_HEALTH_CACHE
    try:
        client = _smtp_connect(settings)
        client.quit()
        _SMTP_HEALTH_CACHE = SmtpHealth(ok=True, detail="smtp auth ok", checked_at=now)
    except Exception as e:
        _SMTP_HEALTH_CACHE = SmtpHealth(ok=False, detail=f"smtp check failed: {type(e).__name__}", checked_at=now)
    return _SMTP_HEALTH_CACHE


def send_reset_email(to_email: str, reset_url: str) -> tuple[bool, str]:
    settings = load_smtp_settings()
    if settings.mock_mode:
        return True, "mock"
    if not settings.host or not settings.sender:
        return False, "smtp not configured"
    try:
        msg = EmailMessage()
        msg["Subject"] = "Сброс пароля админ-панели"
        msg["From"] = settings.sender
        msg["To"] = to_email
        msg.set_content(
            "Вы запросили сброс пароля.\n"
            f"Перейдите по ссылке: {reset_url}\n"
            "Если это были не вы, проигнорируйте письмо."
        )
        client = _smtp_connect(settings)
        client.send_message(msg)
        client.quit()
        return True, "sent"
    except Exception as e:
        return False, f"send failed: {type(e).__name__}"


def mask_email(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        local_masked = local[:1] + "***"
    else:
        local_masked = local[:2] + "***"
    return f"{local_masked}@{domain}"

