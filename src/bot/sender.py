"""Отправка сообщений в Matrix.

Формирование HTML из Jinja2-шаблона, отправка с retry.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

from matrix_send import room_send_with_retry
from preferences import can_notify
from utils import safe_html

if TYPE_CHECKING:
    from nio import AsyncClient
    from redminelib.resources import Issue

logger = logging.getLogger("redmine_bot")

# ── Config (заполняется из main.py при старте) ──────────────────────────────

REDMINE_URL: str = ""

# ── Template ─────────────────────────────────────────────────────────────────

_notification_template = None


def init_template(root) -> None:
    """Инициализация Jinja2-шаблона (вызывается один раз при старте)."""
    global _notification_template
    env = Environment(
        loader=FileSystemLoader(str(root / "templates" / "bot")),
        autoescape=False,
    )
    _notification_template = env.get_template("notification.html")


async def send_matrix_message(
    client: AsyncClient,
    issue: Issue,
    room_id: str,
    notification_type: str,
    extra_text: str = "",
) -> None:
    """Формирует и отправляет HTML-сообщение в Matrix через Jinja2-шаблон."""
    from bot.logic import NOTIFICATION_TYPES, get_version_name, plural_days

    global _notification_template
    if _notification_template is None:
        # Ленивая инициализация для тестов
        from pathlib import Path

        _root = Path(__file__).resolve().parent.parent.parent
        env = Environment(
            loader=FileSystemLoader(str(_root / "templates" / "bot")),
            autoescape=False,
        )
        _notification_template = env.get_template("notification.html")

    issue_url = f"{REDMINE_URL}/issues/{issue.id}"
    emoji, title = NOTIFICATION_TYPES.get(notification_type, ("🔔", "Обратите внимание"))

    overdue_text = ""
    if notification_type == "overdue" and issue.due_date:
        from bot.main import today_tz

        days = (today_tz() - issue.due_date).days
        overdue_text = f" (просрочено на {plural_days(days)})"

    version = get_version_name(issue)
    due_date = str(issue.due_date) if issue.due_date else None

    html_body = _notification_template.render(
        emoji=emoji,
        title=title,
        issue_url=issue_url,
        issue_id=issue.id,
        subject=safe_html(issue.subject),
        status=safe_html(issue.status.name),
        priority=safe_html(issue.priority.name),
        version=safe_html(version) if version else None,
        due_date=due_date,
        overdue_text=overdue_text,
        extra_text=extra_text if extra_text else None,
    )

    plain_body = f"{emoji} {title} #{issue.id}: {issue.subject} | Статус: {issue.status.name}"

    content = {
        "msgtype": "m.text",
        "body": plain_body,
        "format": "org.matrix.custom.html",
        "formatted_body": html_body,
    }

    await room_send_with_retry(client, room_id, content)
    logger.info("📨 #%s → %s... (%s)", issue.id, room_id[:20], notification_type)


async def send_safe(
    client: AsyncClient,
    issue: Issue,
    user_cfg: dict,
    room_id: str,
    notification_type: str,
    extra_text: str = "",
) -> None:
    """Обёртка: проверка DND/рабочих часов → отправка с перехватом ошибок."""
    from bot.logic import _cfg_for_room, _issue_priority_name

    cfg = _cfg_for_room(user_cfg, room_id)
    if not can_notify(cfg, priority=_issue_priority_name(issue)):
        logger.debug(
            "Пропуск (время/DND): user %s, #%s, %s",
            user_cfg.get("redmine_id"),
            issue.id,
            notification_type,
        )
        return
    try:
        await send_matrix_message(client, issue, room_id, notification_type, extra_text)
    except Exception as e:
        logger.error("❌ Ошибка отправки #%s → %s: %s", issue.id, room_id[:20], e)
