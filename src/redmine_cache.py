"""Кэширование запросов к Redmine.

Использует TTLCache из cachetools для снижения нагрузки на Redmine API.
Кэшируются только read-only запросы (users), но НЕ issue.filter() —
задачи должны быть всегда актуальными.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cachetools import TTLCache

logger = logging.getLogger("redmine_bot")

# ── Кэши ─────────────────────────────────────────────────────────────────────

# Один пользователь по ID — TTL 5 минут, до 500 записей
_redmine_user_cache: TTLCache = TTLCache(maxsize=500, ttl=300)

# Поиск пользователей по имени — TTL 3 минуты, до 100 запросов
_redmine_search_cache: TTLCache = TTLCache(maxsize=100, ttl=180)

# ── Публичные функции ────────────────────────────────────────────────────────


def fetch_redmine_user_by_id(
    redmine_user_id: int, redmine_url: str, redmine_key: str
) -> tuple[dict | None, str | None]:
    """GET /users/:id.json с кэшированием.

    Возвращает (user_dict, None) или (None, error_code).
    """
    if not redmine_url or not redmine_key:
        return None, "not_configured"

    cache_key = f"user:{redmine_user_id}"
    cached = _redmine_user_cache.get(cache_key)
    if cached is not None:
        return cached, None

    url = f"{redmine_url.rstrip('/')}/users/{redmine_user_id}.json"
    req = Request(url, headers={"X-Redmine-API-Key": redmine_key})
    try:
        with urlopen(req, timeout=5.0) as r:
            payload = json.loads(r.read().decode("utf-8", errors="replace"))
        u = payload.get("user") if isinstance(payload, dict) else None
        if not isinstance(u, dict):
            return None, "bad_response"
        _redmine_user_cache[cache_key] = u
        return u, None
    except HTTPError as e:
        if e.code == 404:
            return None, "not_found"
        return None, f"http_{e.code}"
    except URLError:
        return None, "timeout"
    except Exception:
        logger.exception("Redmine user fetch error (id=%d)", redmine_user_id)
        return None, "error"


def search_redmine_users(
    query: str, redmine_url: str, redmine_key: str, limit: int = 20
) -> list[dict]:
    """GET /users.json?name=... с кэшированием.

    Возвращает список пользователей или пустой список при ошибке.
    """
    if not redmine_url or not redmine_key:
        return []

    cache_key = f"search:{query}:{limit}"
    cached = _redmine_search_cache.get(cache_key)
    if cached is not None:
        return cached

    params = urlencode({"name": query, "limit": str(limit)})
    url = f"{redmine_url.rstrip('/')}/users.json?{params}"
    req = Request(url, headers={"X-Redmine-API-Key": redmine_key})
    try:
        with urlopen(req, timeout=5.0) as r:
            payload = json.loads(r.read().decode("utf-8", errors="replace"))
        items = payload.get("users") if isinstance(payload, dict) else []
        result = items if isinstance(items, list) else []
        _redmine_search_cache[cache_key] = result
        return result
    except (HTTPError, URLError):
        return []
    except Exception:
        logger.exception("Redmine search error (q=%s)", query)
        return []


def check_redmine_access(redmine_url: str, redmine_key: str) -> tuple[bool, str | None]:
    """GET /users/current.json — проверка подключения (без кэширования ошибок).

    Возвращает (True, None) если доступно, или (False, error_message).
    Успешный результат кэшируется на 60 секунд.
    """
    if not redmine_url or not redmine_key:
        return False, "Redmine: укажите URL и API-ключ."

    cache_key = "access_check"
    cached = _redmine_user_cache.get(cache_key)
    if cached is not None:
        return cached

    # Проверка на нелатинские символы
    try:
        redmine_key.encode("ascii")
    except UnicodeEncodeError:
        logger.error("Redmine key contains non-ASCII chars")
        return False, "Redmine: API-ключ содержит недопустимые символы (нужен только английский)."

    target_url = f"{redmine_url.rstrip('/')}/users/current.json"
    req = Request(target_url, headers={"X-Redmine-API-Key": redmine_key})
    try:
        with urlopen(req, timeout=6.0) as r:
            if r.status != 200:
                return False, f"Redmine: HTTP {r.status}."
        _redmine_user_cache[cache_key] = (True, None)
        return True, None
    except HTTPError as e:
        return False, f"Redmine: HTTP {e.code}."
    except URLError:
        return False, "Redmine: нет ответа (URL/сеть)."
    except Exception as e:
        logger.error("Redmine UNEXPECTED ERROR: %s", e, exc_info=True)
        return False, f"Redmine: ошибка ({e})."


# ── Утилиты ──────────────────────────────────────────────────────────────────


def clear_redmine_caches() -> None:
    """Очистить все кэши Redmine (например, после смены credentials)."""
    _redmine_user_cache.clear()
    _redmine_search_cache.clear()
    logger.info("Redmine caches cleared")


def get_redmine_cache_stats() -> dict[str, Any]:
    """Возвращает статистику кэшей (для диагностики)."""
    return {
        "user_cache_size": len(_redmine_user_cache),
        "user_cache_maxsize": _redmine_user_cache.maxsize,
        "search_cache_size": len(_redmine_search_cache),
        "search_cache_maxsize": _redmine_search_cache.maxsize,
    }
