"""Ops routes: bot control, heartbeat."""

from __future__ import annotations

import json
import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlencode

from database.session import get_session
from database.models import BotAppUser
from ops.docker_control import control_service, get_service_status, DockerControlError

from admin.helpers import (
    _verify_csrf, _client_ip, _rate_limiter, _append_ops_to_events_log,
    _now_utc, DASHBOARD_PATH,
)
from admin.main import _audit_op, _restart_in_background, _truncate_ops_detail

logger = logging.getLogger("redmine_admin")

router = APIRouter(tags=["ops"])


@router.post("/ops/bot/{action}")
async def bot_ops_action(
    request: Request,
    action: str,
    csrf_token: Annotated[str, Form()] = "",
    session: AsyncSession = Depends(get_session),
):
    _verify_csrf(request, csrf_token)
    current = getattr(request.state, "current_user", None)
    if not current or getattr(current, "role", "") != "admin":
        raise HTTPException(403, "Только admin")
    ip = _client_ip(request)
    if not _rate_limiter.hit(f"ops:{ip}:{current.login}", limit=12, window_seconds=60):
        raise HTTPException(429, "Слишком много операций, попробуйте позже")

    allowed = {"start", "stop", "restart"}
    if action not in allowed:
        raise HTTPException(400, "Недопустимое действие")
    actor = current.login
    if action == "restart":
        await _audit_op(session, "BOT_RESTART", "accepted", actor_login=actor, detail="scheduled")
        await session.commit()
        _append_ops_to_events_log(f"Docker bot/restart scheduled by={actor}")
        _restart_in_background(actor)
        return RedirectResponse(f"{DASHBOARD_PATH}?ops=restart_accepted", status_code=303)

    ops_q = f"{action}_error"
    ops_detail_err: str | None = None
    res_ok: dict | None = None
    try:
        res_ok = control_service(action)
        await _audit_op(session, f"BOT_{action.upper()}", "ok", actor_login=actor,
            detail=json.dumps(res_ok, ensure_ascii=False))
        ops_q = f"{action}_ok"
    except DockerControlError as e:
        logger.warning("bot_ops DockerControlError action=%s: %s", action, e)
        ops_detail_err = str(e)
        await _audit_op(session, f"BOT_{action.upper()}", "error", actor_login=actor, detail=str(e)[:2000])
    except Exception as e:
        logger.exception("bot_ops unexpected error action=%s", action)
        ops_detail_err = str(e)
        await _audit_op(session, f"BOT_{action.upper()}", "error", actor_login=actor, detail=str(e)[:2000])
    try:
        await session.commit()
    except Exception:
        logger.exception("bot_ops commit failed action=%s", action)
        await session.rollback()
        return RedirectResponse(f"{DASHBOARD_PATH}?ops=ops_commit_error", status_code=303)
    if action in ("start", "stop"):
        if ops_q == f"{action}_ok":
            r = res_ok or {}
            cid = str(r.get("container_id") or "")
            http_st = r.get("docker_http_status")
            http_part = f" http_status={http_st}" if http_st is not None else ""
            _append_ops_to_events_log(f"Docker bot/{action} ok by={actor} container_id={cid[:20]}{http_part}")
        elif ops_q == f"{action}_error":
            _append_ops_to_events_log(f"Docker bot/{action} failed by={actor}: {_truncate_ops_detail(ops_detail_err or 'unknown', 400)}")
    q: dict[str, str] = {"ops": ops_q}
    if ops_detail_err and ops_q.endswith("_error"):
        q["ops_detail"] = _truncate_ops_detail(ops_detail_err)
    return RedirectResponse(DASHBOARD_PATH + "?" + urlencode(q), status_code=303)


@router.post("/api/bot/heartbeat")
async def bot_heartbeat(session: AsyncSession = Depends(get_session)):
    from database.models import BotHeartbeat
    from sqlalchemy import insert
    stmt = insert(BotHeartbeat).values(
        instance_id=os.getenv("BOT_INSTANCE_ID", "default"),
        heartbeat_at=_now_utc(),
        status="running",
    )
    await session.execute(stmt)
    await session.commit()
    return {"ok": True}


@router.get("/api/bot/status")
async def bot_status():
    try:
        status = get_service_status()
        return {"ok": True, "status": status}
    except DockerControlError as e:
        return {"ok": False, "error": str(e)}
