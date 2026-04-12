"""DB credentials management endpoints.

GET  /settings/db-config
POST /settings/db-config/regenerate
"""

from __future__ import annotations

import logging
import secrets as _secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from admin.helpers import _verify_csrf
from database.session import get_session
from mail import mask_identifier

logger = logging.getLogger("admin")

router = APIRouter(tags=["db-config"])

_ENV_FILE_PATH = Path("/app/.env")


def _load_db_config_from_env() -> dict[str, str]:
    """Читает DB credentials из .env файла."""
    if not _ENV_FILE_PATH.exists():
        return {
            "postgres_user": "bot",
            "postgres_db": "via",
            "postgres_password": "",
            "app_master_key": "",
        }

    config = {}
    for line in _ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()

    return {
        "postgres_user": config.get("POSTGRES_USER", "bot"),
        "postgres_db": config.get("POSTGRES_DB", "via"),
        "postgres_password": config.get("POSTGRES_PASSWORD", ""),
        "app_master_key": config.get("APP_MASTER_KEY", ""),
    }


def _update_env_file(updates: dict[str, str]) -> None:
    """Обновляет переменные в .env файле с file-locking."""
    from admin.env_manager import update_env_file_with_lock

    update_env_file_with_lock(updates)


@router.get("/settings/db-config", response_class=JSONResponse)
async def get_db_config(request: Request, session: AsyncSession = Depends(get_session)):
    """Возвращает текущие DB credentials из .env (только для admin)."""
    user = getattr(request.state, "current_user", None)
    if not user or getattr(user, "role", "") != "admin":
        raise HTTPException(403, "Только admin")

    config = _load_db_config_from_env()
    return {
        "ok": True,
        "postgres_user": config["postgres_user"],
        "postgres_db": config["postgres_db"],
        "postgres_password": config["postgres_password"],
        "app_master_key": config["app_master_key"],
    }


@router.post("/settings/db-config/regenerate", response_class=JSONResponse)
async def regenerate_db_config(
    request: Request,
    regenerate_password: Annotated[str, Form()] = "1",
    regenerate_key: Annotated[str, Form()] = "1",
    csrf_token: Annotated[str, Form()] = "",
    session: AsyncSession = Depends(get_session),
):
    """Генерирует новые credentials и обновляет .env."""
    _verify_csrf(request, csrf_token)
    user = getattr(request.state, "current_user", None)
    if not user or getattr(user, "role", "") != "admin":
        raise HTTPException(403, "Только admin")

    current_config = _load_db_config_from_env()
    updates = {}

    if regenerate_password in ("1", "true", "yes", "on"):
        updates["POSTGRES_PASSWORD"] = _secrets.token_urlsafe(32)

    if regenerate_key in ("1", "true", "yes", "on"):
        updates["APP_MASTER_KEY"] = _secrets.token_urlsafe(32)

    if not updates:
        raise HTTPException(400, "Нечего перегенерировать")

    _update_env_file(updates)

    # Обновляем пароль в PostgreSQL
    if "POSTGRES_PASSWORD" in updates:
        try:
            await session.execute(
                text("ALTER USER :username WITH PASSWORD :password"),
                {
                    "username": current_config["postgres_user"],
                    "password": updates["POSTGRES_PASSWORD"],
                },
            )
            await session.commit()
        except Exception as e:
            _update_env_file(
                {
                    k: current_config[k.replace("POSTGRES_", "").lower()]
                    for k in updates
                    if k in current_config
                }
            )
            raise HTTPException(500, f"Не удалось обновить пароль в PostgreSQL: {e}") from e

    logger.info(
        "db_credentials_regenerated actor=%s regenerated=%s",
        mask_identifier(user.login),
        list(updates.keys()),
    )

    return {
        "ok": True,
        "message": "Credentials обновлены. Перезапустите контейнеры: docker compose restart postgres bot admin",
        "regenerated": list(updates.keys()),
        "new_postgres_password": updates.get("POSTGRES_PASSWORD", ""),
        "new_app_master_key": updates.get("APP_MASTER_KEY", ""),
    }
