"""Heartbeat — мониторинг живучести бота.

Отправляет POST на админку каждые 60 секунд.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import httpx

logger = logging.getLogger("redmine_bot")


def start_heartbeat_task(admin_url: str = "http://admin:8080") -> asyncio.Task:
    """Создаёт и возвращает asyncio.Task для heartbeat.

    Вызывается из main() через asyncio.create_task().
    """
    bot_instance_id = str(uuid.uuid4())
    heartbeat_url = f"{admin_url.rstrip('/')}/api/bot/heartbeat" if admin_url else None

    if heartbeat_url:
        logger.info("📡 Heartbeat: отправка на %s", heartbeat_url)
    else:
        logger.warning("⚠️ Heartbeat отключён (ADMIN_URL не задан)")

    async def _loop():
        if not heartbeat_url:
            return
        async with httpx.AsyncClient(timeout=10) as http:
            while True:
                try:
                    await http.post(
                        heartbeat_url,
                        json={"instance_id": bot_instance_id},
                    )
                except Exception as e:
                    logger.debug("Heartbeat failed: %s", e)
                await asyncio.sleep(60)

    return asyncio.create_task(_loop())
