from sqlalchemy import text
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

    # Каждый ALTER TABLE — в своей транзакции (PostgreSQL иначе падает с InFailedSQLTransactionError)
    # content уже есть в БД, не добавляем
    migrations = [
        "ALTER TABLE articles ADD COLUMN is_processed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE articles ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW()",
        "ALTER TABLE posts ADD COLUMN title VARCHAR(512)",
        "ALTER TABLE posts ADD COLUMN published_at TIMESTAMPTZ",
        "ALTER TABLE sources ADD COLUMN last_parsed_at TIMESTAMPTZ",
    ]
    for sql in migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        except Exception as e:
            err = str(e).lower()
            if "already exists" not in err and "duplicate column" not in err:
                raise
