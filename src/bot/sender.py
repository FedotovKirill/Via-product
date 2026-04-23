"""Отправка сообщений в Matrix.

Формирование HTML из Jinja2-шаблона, отправка с retry.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp
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

# ── Таймаут на создание DM-комнаты (секунды) ────────────────────────────────

DM_CREATE_TIMEOUT: int = 60

# ── Пауза между созданиями DM (чтобы не упереться в rate-limit) ─────────────

DM_CREATE_DELAY: float = 5.0

# ── Template ─────────────────────────────────────────────────────────────────

_notification_template = None

# ── Кеш MXID → room_id (загружается из БД при старте) ────────────────────────

_mxid_to_room_cache: dict[str, str] = {}

# ── DB session для сохранения кеша ───────────────────────────────────────────

_db_session = None


def set_db_session(session):
    """Устанавливает DB session для сохранения кеша."""
    global _db_session
    _db_session = session


async def _save_to_db_cache(mxid: str, room_id: str) -> None:
    """Сохраняет DM в БД кеш."""
    if _db_session is None:
        logger.debug("⚠ DB session не установлен, пропускаем сохранение в БД")
        return
    try:
        from bot.dm_cache import save_dm_cache
        await save_dm_cache(_db_session, mxid, room_id)
        logger.debug("💾 Сохранено в БД: %s → %s", mxid, room_id)
    except Exception as e:
        logger.warning("⚠ Не удалось сохранить в БД: %s", e)

# ── Множество MXID, для которых создание DM провалилось в текущем цикле ─────

_dm_failed: set[str] = set()


def init_template(root) -> None:
    """Инициализация Jinja2-шаблона (вызывается один раз при старте)."""
    global _notification_template
    env = Environment(
        loader=FileSystemLoader(str(root / "templates" / "bot")),
        autoescape=False,
    )
    _notification_template = env.get_template("notification.html")


def reset_dm_failed() -> None:
    """Сброс списка неудачных DM (вызывается в начале каждого цикла)."""
    _dm_failed.clear()


async def _load_rooms_via_api(client: "AsyncClient", homeserver: str, access_token: str) -> dict[str, any]:
    """Загружает комнаты через Matrix API и кеширует в client.rooms."""
    room_ids = await _fetch_joined_rooms_via_api(homeserver, access_token)
    rooms_dict = {}
    
    for room_id in room_ids:
        members = await _fetch_room_members_via_api(homeserver, access_token, room_id)
        # Создаём простой объект-заглушку
        class RoomStub:
            def __init__(self, rid, mbrs):
                self.room_id = rid
                self.members = mbrs
                self.users = mbrs
                self.member_count = len(mbrs)
        rooms_dict[room_id] = RoomStub(room_id, members)
    
    logger.info("📦 Загружено %d комнат через API", len(rooms_dict))
    return rooms_dict


async def prewarm_dm_rooms(client: "AsyncClient", mxids: list[str]) -> None:
    """Предварительное создание/поиск DM-комнат для списка MXID.

    Вызывается один раз при старте бота, после первого sync.
    Последовательно (не параллельно), чтобы не упереться в rate-limit homeserver'а.
    """
    to_resolve: list[str] = []
    found_in_cache = 0

    for m in mxids:
        m = (m or "").strip()
        if not m or m.startswith("!"):
            continue
        if not m.startswith("@"):
            m = f"@{m}"
        if m in _mxid_to_room_cache:
            found_in_cache += 1
            logger.info("💾 DM найден в БД: %s → %s", m, _mxid_to_room_cache[m])
            continue
        if m not in to_resolve:
            to_resolve.append(m)

    if not to_resolve:
        logger.info("🔗 Pre-warm DM: все %d комнат уже в кеше", found_in_cache)
        return

    logger.info(
        "🔗 Pre-warm DM: %d в БД кеше, %d нужно резолвить...",
        found_in_cache, len(to_resolve),
    )

    created_count = 0
    found_count = 0
    failed_count = 0
    need_create: list[str] = []

    # Фаза 1: быстрый поиск среди загруженных комнат (без API-вызовов)
    bot_mxid = client.user_id
    for target_mxid in to_resolve:
        room_id = _find_existing_dm(client, target_mxid, bot_mxid)
        if room_id:
            _mxid_to_room_cache[target_mxid] = room_id
            found_count += 1
            logger.info("🔗 DM найден в rooms: %s → %s", target_mxid, room_id)
            # Сохраняем в БД
            await _save_to_db_cache(target_mxid, room_id)
        else:
            need_create.append(target_mxid)

    # Фаза 2: создание недостающих DM — по одному, с паузой
    # ВАЖНО: ошибки не блокируют запуск бота
    for i, target_mxid in enumerate(need_create):
        try:
            room_id = await asyncio.wait_for(
                _create_dm(client, target_mxid),
                timeout=DM_CREATE_TIMEOUT,
            )
            _mxid_to_room_cache[target_mxid] = room_id
            created_count += 1
            logger.info(
                "✅ DM создан (%d/%d): %s → %s",
                i + 1, len(need_create), target_mxid, room_id,
            )
            # Сохраняем в БД
            await _save_to_db_cache(target_mxid, room_id)
        except asyncio.TimeoutError:
            logger.warning("⏱ Pre-warm DM timeout: %s (пропуск)", target_mxid)
            failed_count += 1
        except Exception as e:
            error_msg = str(e)
            # Игнорируем ошибки создания DM — бот продолжит работу
            logger.warning("⚠ Pre-warm DM ошибка (не блокирующая): %s — %s", target_mxid, e)
            failed_count += 1

        # Пауза между созданиями (не после последнего)
        if i < len(need_create) - 1:
            await asyncio.sleep(DM_CREATE_DELAY)

    if failed_count > 0:
        logger.warning(
            "⚠ Pre-warm DM завершён с ошибками: %d найдено, %d создано, %d неудачно. "
            "Бот продолжит работу, DM будут созданы при первой отправке.",
            found_count, created_count, failed_count,
        )
    else:
        logger.info(
            "✅ Pre-warm DM завершён: %d найдено, %d создано (всего %d)",
            found_count, created_count, len(to_resolve),
        )
    # Сбрасываем failed — при первом цикле попробуем ещё раз
    _dm_failed.clear()


async def _fetch_joined_rooms_via_api(homeserver: str, access_token: str) -> list[str]:
    """Получает список комнат через Matrix API напрямую."""
    # Убираем trailing slash если есть
    homeserver = homeserver.rstrip("/")
    
    # Пробуем разные версии API
    for version in ["v3", "r0", "v2"]:
        url = f"{homeserver}/_matrix/client/{version}/joined_rooms"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        logger.debug("🔍 Пробуем API: %s", url)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    logger.debug("📋 API response status: %d", resp.status)
                    if resp.status == 200:
                        data = await resp.json()
                        rooms = data.get("joined_rooms", [])
                        logger.info("📋 API joined_rooms (%s): %d комнат", version, len(rooms))
                        return rooms
                    elif resp.status == 404:
                        logger.debug("⚠ API %s вернул 404, пробуем другую версию", version)
                        continue
                    else:
                        logger.warning("⚠ API joined_rooms (%s): status %d", version, resp.status)
                        # Попробуем прочитать тело ошибки
                        try:
                            error_body = await resp.text()
                            logger.debug("📄 Error body: %s", error_body[:200])
                        except Exception:
                            pass
                        continue
        except Exception as e:
            logger.error("⚠ API joined_rooms (%s) exception: %s", version, e)
            continue
    
    logger.warning("⚠ Не удалось получить joined_rooms ни через одну версию API")
    return []


async def _fetch_room_members_via_api(homeserver: str, access_token: str, room_id: str) -> set[str]:
    """Получает список участников комнаты через Matrix API."""
    url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/members"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    chunk = data.get("chunk", [])
                    members = {m.get("user_id") for m in chunk if m.get("user_id")}
                    logger.debug("📋 API room %s members: %d", room_id, len(members))
                    return members
                else:
                    logger.debug("⚠ API room members: status %d", resp.status)
                    return set()
    except Exception as e:
        logger.debug("⚠ API room members error: %s", e)
        return set()


async def _find_dm_via_api(client: "AsyncClient", target_mxid: str, bot_mxid: str) -> str | None:
    """Ищет DM через Matrix API напрямую."""
    # Импортируем из main.py где заполняются переменные при старте
    try:
        from bot.main import ACCESS_TOKEN, HOMESERVER
    except ImportError:
        logger.warning("⚠ Не удалось импортировать HOMESERVER/ACCESS_TOKEN из main")
        return None
    
    homeserver = HOMESERVER
    access_token = ACCESS_TOKEN
    
    if not homeserver or not access_token:
        logger.warning("⚠ Homeserver или access_token пустые")
        return None
    
    # Получаем список комнат
    room_ids = await _fetch_joined_rooms_via_api(homeserver, access_token)
    
    # Для каждой комнаты проверяем участников
    rooms_cache = getattr(client, '_rooms_cache', {})
    for room_id in room_ids:
        members = await _fetch_room_members_via_api(homeserver, access_token, room_id)
        
        # Кешируем в _rooms_cache
        if room_id not in rooms_cache:
            class RoomStub:
                def __init__(self, rid, mbrs):
                    self.room_id = rid
                    self.members = mbrs
                    self.users = mbrs
                    self.member_count = len(mbrs)
            rooms_cache[room_id] = RoomStub(room_id, members)
        
        if target_mxid in members and bot_mxid in members and len(members) == 2:
            logger.info("✅ DM найден через API: %s", room_id)
            return room_id
    
    return None


def _find_existing_dm(client: "AsyncClient", target_mxid: str, bot_mxid: str) -> str | None:
    """Ищет существующую DM-комнату через API (так как client.room_members не существует)."""
    # Быстрая проверка по БД кешу - если есть, возвращаем сразу
    if target_mxid in _mxid_to_room_cache:
        logger.debug("💾 DM найден в памяти: %s → %s", target_mxid, _mxid_to_room_cache[target_mxid])
        return _mxid_to_room_cache[target_mxid]

    return None


async def _create_dm(client: "AsyncClient", target_mxid: str) -> str:
    """Создаёт DM-комнату. Бросает исключение при ошибке."""
    from nio import RoomCreateError, RoomCreateResponse

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.room_create(
                invite=[target_mxid],
                is_direct=True,
            )

            if isinstance(resp, RoomCreateResponse) and resp.room_id:
                return resp.room_id

            # nio может вернуть RoomCreateError с кодом M_LIMIT_EXCEEDED
            if isinstance(resp, RoomCreateError):
                msg = resp.message or ""
                status = getattr(resp, "status_code", None) or ""
                if "LIMIT_EXCEEDED" in msg.upper() or str(status) == "429":
                    retry_ms = 30000  # по умолчанию 30с
                    # Пытаемся достать retry_after_ms из ответа
                    if hasattr(resp, "retry_after_ms") and resp.retry_after_ms:
                        retry_ms = resp.retry_after_ms
                    wait_s = (retry_ms / 1000) + 2  # +2с запас
                    if attempt < max_attempts:
                        logger.warning(
                            "⚠ Rate-limited при создании DM %s (попытка %d/%d), ждём %.0fс...",
                            target_mxid, attempt, max_attempts, wait_s,
                        )
                        await asyncio.sleep(wait_s)
                        continue

                # Другая ошибка при создании — пробуем ещё раз
                logger.debug("⚠ Ошибка создания DM %s: %s (status=%s, попытка %d/%d)",
                            target_mxid, msg, status, attempt, max_attempts)
                if attempt < max_attempts:
                    await asyncio.sleep(3)
                    continue
                raise RuntimeError(f"Не удалось создать DM с {target_mxid}: {msg}")

        except Exception as e:
            logger.debug("⚠ Исключение при создании DM %s (попытка %d/%d): %s",
                        target_mxid, attempt, max_attempts, e)
            if attempt < max_attempts:
                await asyncio.sleep(3)
                continue
            raise

    raise RuntimeError(f"Не удалось создать DM с {target_mxid} после {max_attempts} попыток")

async def _resolve_room_id(client: "AsyncClient", room_or_mxid: str) -> str:
    """Если room_or_mxid — MXID (@user:server), находит или создаёт DM.

    Если это уже room_id (!xxx:server), возвращает как есть.
    Результат кешируется на время жизни процесса.
    """
    room_or_mxid = (room_or_mxid or "").strip()

    # Уже нормальный room_id
    if room_or_mxid.startswith("!"):
        return room_or_mxid

    # Это MXID — нужно найти или создать DM
    target_mxid = room_or_mxid
    if not target_mxid.startswith("@"):
        target_mxid = f"@{target_mxid}"

    # Проверяем кеш
    if target_mxid in _mxid_to_room_cache:
        return _mxid_to_room_cache[target_mxid]

    # Если уже провалилось в этом цикле — не повторяем
    if target_mxid in _dm_failed:
        raise RuntimeError(f"DM с {target_mxid} уже не удался в этом цикле (пропуск)")

    bot_mxid = client.user_id

    # Синхронизируем список комнат (нужен хотя бы один sync)
    if not getattr(client, '_rooms_cache', None):
        logger.info("📡 Matrix sync (первый раз, для поиска DM)...")
        await client.sync(timeout=10000, full_state=True)

    # Дополнительная синхронизация если rooms пустой
    if not getattr(client, '_rooms_cache', None):
        logger.info("📡 Matrix sync (дополнительная синхронизация)...")
        await client.sync(timeout=10000, full_state=True)

    rooms_cache = getattr(client, '_rooms_cache', {})
    logger.info("📊 Matrix rooms debug: _rooms_cache=%d", len(rooms_cache))

    # Ищем существующую DM-комнату через client._rooms_cache
    room_id = _find_existing_dm(client, target_mxid, bot_mxid)
    if room_id:
        logger.info("🔗 DM найден: %s → %s", target_mxid, room_id)
        _mxid_to_room_cache[target_mxid] = room_id
        # Сохраняем в БД
        await _save_to_db_cache(target_mxid, room_id)
        return room_id

    # Fallback: ищем через Matrix API напрямую
    logger.info("🔍 DM не найден в rooms, пробуем API...")
    room_id = await _find_dm_via_api(client, target_mxid, bot_mxid)
    if room_id:
        logger.info("🔗 DM найден через API: %s → %s", target_mxid, room_id)
        _mxid_to_room_cache[target_mxid] = room_id
        return room_id

    logger.warning("⚠ Existing DM not found for %s, attempting to create...", target_mxid)
    # Создаём новую DM с таймаутом
    logger.info("📨 Создаём DM с %s...", target_mxid)
    try:
        new_room_id = await asyncio.wait_for(
            _create_dm(client, target_mxid),
            timeout=DM_CREATE_TIMEOUT,
        )
        logger.info("✅ DM создан: %s → %s", target_mxid, new_room_id)
        _mxid_to_room_cache[target_mxid] = new_room_id
        # Сохраняем в БД
        await _save_to_db_cache(target_mxid, new_room_id)
        return new_room_id
    except asyncio.TimeoutError:
        _dm_failed.add(target_mxid)
        raise RuntimeError(
            f"Таймаут создания DM с {target_mxid} ({DM_CREATE_TIMEOUT}с)"
        )
    except Exception:
        _dm_failed.add(target_mxid)
        raise

async def resolve_room(client: "AsyncClient", room_or_mxid: str) -> str:
    """Публичный хелпер: резолвит MXID → room_id через кеш. Для использования вне sender."""
    return await _resolve_room_id(client, room_or_mxid)

async def send_matrix_message(
    client: "AsyncClient",
    issue: "Issue",
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

    # ── Резолвим MXID → room_id если нужно ──
    resolved_room = await _resolve_room_id(client, room_id)

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

    await room_send_with_retry(client, resolved_room, content)
    logger.info("📨 #%s → %s... (%s)", issue.id, resolved_room[:20], notification_type)


async def send_safe(
    client: "AsyncClient",
    issue: "Issue",
    user_cfg: dict,
    room_id: str,
    notification_type: str,
    extra_text: str = "",
    db_session=None,
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
        # Сохраняем в DLQ для повторной отправки
        if db_session is not None:
            try:
                from database.dlq_repo import enqueue_notification

                payload = {
                    "issue_id": issue.id,
                    "room_id": room_id,
                    "notification_type": notification_type,
                    "extra_text": extra_text,
                }
                await enqueue_notification(
                    db_session,
                    user_redmine_id=user_cfg.get("redmine_id", 0),
                    issue_id=issue.id,
                    room_id=room_id,
                    notification_type=notification_type,
                    payload=payload,
                    error=str(e),
                )
            except Exception as dlq_err:
                logger.error("❌ Не удалось сохранить в DLQ: %s", dlq_err)