"""Pydantic-схемы для API response'ов админки.

Используются для валидации и автодокументации (OpenAPI/Swagger).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Общие responses ──────────────────────────────────────────────────────────


class OkResponse(BaseModel):
    """Стандартный ответ об успехе."""

    ok: bool = True


class ErrorResponse(BaseModel):
    """Ответ об ошибке."""

    ok: Literal[False] = False
    error: str = Field(..., description="Описание ошибки")


# ── Health ───────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Ответ health-check endpoint'ов."""

    status: str = Field(..., description="Статус: ok, live, ready")


# ── Service / Ops ────────────────────────────────────────────────────────────


class ServiceControlRequest(BaseModel):
    """Запрос на управление сервисом (start/stop/restart)."""

    action: Literal["start", "stop", "restart"] = Field(..., description="Действие над сервисом")


class ServiceStatusResponse(BaseModel):
    """Статус бота."""

    ok: bool = True
    status: str = Field(..., description="Статус: running, stopped, restarting, unknown, error")
    uptime: str | None = Field(None, description="Uptime в читаемом формате")
    started_at: str | None = Field(None, description="Время запуска ISO-8601")
    errors: int = Field(0, description="Количество ошибок в текущем цикле")


class ServiceControlResponse(BaseModel):
    """Результат управления сервисом."""

    ok: bool
    status: str | None = Field(None, description="Новый статус (если успешно)")
    error: str | None = Field(None, description="Ошибка (если неуспешно)")


# ── DB Config ────────────────────────────────────────────────────────────────


class DbConfigResponse(BaseModel):
    """Конфигурация БД из .env (masked)."""

    ok: Literal[True] = True
    postgres_user: str
    postgres_db: str
    postgres_password: str = Field(..., description="Замаскированный пароль")
    app_master_key: str = Field(..., description="Замаскированный мастер-ключ")


class RegenerateDbRequest(BaseModel):
    """Запрос на регенерацию DB credentials."""

    target: Literal["postgres_password", "master_key", "all"] = Field(
        ..., description="Что регенерировать"
    )


class RegenerateDbResponse(BaseModel):
    """Результат регенерации."""

    ok: bool
    updated_fields: list[str] = Field(default_factory=list, description="Обновлённые поля")
    error: str | None = None


# ── Redmine Lookup ───────────────────────────────────────────────────────────


class RedmineUserLookupResponse(BaseModel):
    """Ответ поиска пользователя в Redmine."""

    ok: bool
    id: int | None = None
    firstname: str | None = None
    lastname: str | None = None
    mail: str | None = None
    error: str | None = None


# ── Matrix Test Message ─────────────────────────────────────────────────────


class TestMessageRequest(BaseModel):
    """Запрос на отправку тестового сообщения."""

    room_id: str = Field(..., description="Matrix room ID")
    message: str | None = Field("Тестовое сообщение от Via", description="Текст сообщения")


class TestMessageResponse(BaseModel):
    """Результат отправки тестового сообщения."""

    ok: bool
    event_id: str | None = Field(None, description="Matrix event ID (если успешно)")
    error: str | None = None


# ── Catalog ──────────────────────────────────────────────────────────────────


class CatalogSaveRequest(BaseModel):
    """Запрос на сохранение каталога (уведомления/версии)."""

    catalog: Literal["notify", "versions"] = Field(..., description="Тип каталога")
    items: list[str] = Field(..., description="Список элементов")


# ── Bot Status ───────────────────────────────────────────────────────────────


class BotStatusResponse(BaseModel):
    """Статус бота для UI."""

    status: str = Field(..., description="running / stopped / restarting / unknown")
    uptime: str | None = None
    started_at: str | None = None
    errors: int = 0
    last_check: str | None = Field(None, description="Последняя проверка ISO-8601")
