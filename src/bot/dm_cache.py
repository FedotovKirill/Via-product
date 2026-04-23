"""Кеш DM-комнат в БД."""

from sqlalchemy import Column, Integer, String, DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone


class DmCache:
    """Таблица для кеширования DM-комнат."""
    
    __tablename__ = "bot_dm_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_mxid = Column(String, nullable=False, index=True, unique=True)
    room_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


async def load_dm_cache(session: AsyncSession) -> dict[str, str]:
    """Загружает кеш DM из БД. Возвращает dict {mxid: room_id}."""
    result = await session.execute(select(DmCache))
    cache = {}
    for row in result.scalars():
        cache[row.user_mxid] = row.room_id
    return cache


async def save_dm_cache(session: AsyncSession, mxid: str, room_id: str) -> None:
    """Сохраняет DM-комнату в кеш."""
    from sqlalchemy import update, insert, exists
    
    # Проверяем существует ли запись
    exists_stmt = select(exists().where(DmCache.user_mxid == mxid))
    result = await session.execute(exists_stmt)
    exists_flag = result.scalar()
    
    if exists_flag:
        await session.execute(
            update(DmCache)
            .where(DmCache.user_mxid == mxid)
            .values(room_id=room_id, updated_at=datetime.now(timezone.utc))
        )
    else:
        await session.execute(
            insert(DmCache).values(user_mxid=mxid, room_id=room_id)
        )
    
    await session.commit()


async def init_dm_cache_table(session: AsyncSession) -> None:
    """Создаёт таблицу если не существует."""
    from sqlalchemy import text
    
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_dm_cache (
            id SERIAL PRIMARY KEY,
            user_mxid VARCHAR NOT NULL UNIQUE,
            room_id VARCHAR NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    await session.commit()
