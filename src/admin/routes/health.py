"""Health check endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session
from database.models import BotAppUser
from security import SecurityError, load_master_key
from ops.docker_control import DockerControlError, get_service_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/live")
async def health_live():
    return {"status": "live"}


@router.get("/health/ready")
async def health_ready(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(select(BotAppUser.id).limit(1))
        load_master_key()
        get_service_status()
    except SecurityError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except DockerControlError as e:
        raise HTTPException(status_code=503, detail=f"runtime backend: {e}")
    except Exception:
        raise HTTPException(status_code=503, detail="service not ready")
    return {"status": "ready"}
