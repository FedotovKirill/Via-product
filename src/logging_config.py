"""Конфигурация structured (JSON) логирования.

Если WANT_JSON_LOG=1 — логи в JSON-формате (для ELK/Loki).
Иначе — стандартный human-readable формат.
"""

from __future__ import annotations

import logging
import os
import sys

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None  # type: ignore[assignment]


def _want_json() -> bool:
    """Проверяет WANT_JSON_LOG=1 в окружении."""
    return os.getenv("WANT_JSON_LOG", "0").strip() == "1"


def setup_json_logging(logger_name: str | None = None) -> None:
    """Настраивает JSON-логирование для root или указанного logger'а.

    Если python-json-logger недоступен — использует стандартный текстовый формат.
    """
    if not _want_json():
        return

    target = logging.getLogger(logger_name) if logger_name else logging.root

    # Удаляем существующие handlers (чтобы не дублировать)
    for handler in target.handlers[:]:
        target.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if jsonlogger is not None:
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    else:
        # Fallback: стандартный формат
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )

    handler.setFormatter(formatter)
    target.addHandler(handler)


def get_log_formatter() -> logging.Formatter:
    """Возвращает подходящий formatter для file handler."""
    if _want_json() and jsonlogger is not None:
        return jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    return logging.Formatter("%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s")
