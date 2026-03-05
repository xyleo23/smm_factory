from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings


engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)


class Base(DeclarativeBase):
    pass


async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migration: add content column if missing (SQLite has no ADD COLUMN IF NOT EXISTS)
        try:
            await conn.execute(text("ALTER TABLE articles ADD COLUMN content TEXT"))
        except OperationalError as e:
            err = str(e).lower()
            if "duplicate column" not in err and "already exists" not in err:
                raise
