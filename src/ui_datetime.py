"""
Единый формат даты и времени в UI панели: ДД.ММ.ГГГГ ЧЧ:ММ:СС в BOT_TIMEZONE,
без микросекунд и без суффикса часового пояса в строке.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


def bot_display_timezone() -> ZoneInfo:
    name = (os.getenv("BOT_TIMEZONE") or "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def format_datetime_ui(value: Any) -> str:
    """Для Jinja-фильтра `dt_ui`: datetime из БД (aware UTC) → локальная строка панели."""
    if value is None:
        return "—"
    if not isinstance(value, datetime):
        return "—"
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(bot_display_timezone())
    return local.strftime("%d.%m.%Y %H:%M:%S")
