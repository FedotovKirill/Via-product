"""Глобальное состояние конфигурации бота.

Заполняется из main.py при старте (загрузка из БД).
Используется processor.py и scheduler.py.
"""

from __future__ import annotations

# Пользователи бота (загружаются из БД)
USERS: list[dict] = []

# Маршрутизация: статус → Matrix room
STATUS_ROOM_MAP: dict[str, str] = {}

# Маршрутизация: версия → Matrix room (глобальный)
VERSION_ROOM_MAP: dict[str, str] = {}
