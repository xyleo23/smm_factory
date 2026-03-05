"""
Одноразовый скрипт: перепарсинг статей из БД (очистка от мусора навигации).

Для статей с мусором в text (напр. "Войти / Создать аккаунт", "Поделиться на РБК")
скрипт заново скачивает HTML, парсит через ArticleParser и обновляет article.text.
После этого устанавливает is_processed=False, чтобы посты перегенерировались.

Usage:
    python scripts/reparse_articles.py [--limit N] [--dry-run]

    docker compose exec celery_worker python scripts/reparse_articles.py
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from models import Article
from parser.article_parser import ArticleParser


JUNK_INDICATORS = [
    "Войти",
    "Создать аккаунт",
    "Поделиться новостью",
    "Поделиться на РБК",
]


def has_junk(text: str) -> bool:
    """Проверяет, содержит ли текст типичный мусор навигации."""
    if not text or len(text) < 100:
        return False
    t = text.strip()
    return any(ind in t for ind in JUNK_INDICATORS)


async def _run(limit: int | None, dry_run: bool, reparse_all: bool = False) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            q = select(Article).where(Article.url != "")
            if limit:
                q = q.limit(limit)
            result = await db.execute(q)
            articles = result.scalars().all()

        if not articles:
            logger.info("Нет статей для перепарсинга")
            return

        logger.info(f"Найдено {len(articles)} статей. dry_run={dry_run}")

        updated = 0
        for art in articles:
            if not reparse_all and not has_junk(art.text):
                continue
            if has_junk(art.text):
                logger.info(f"Статья {art.id} содержит мусор, перепарсим: {art.url[:60]}...")
            else:
                logger.info(f"Статья {art.id} (--all): {art.url[:60]}...")

            try:
                html = await ArticleParser.fetch_html(art.url)
                if not html:
                    logger.warning(f"Не удалось загрузить HTML для {art.id}")
                    continue

                parsed = ArticleParser.parse_article(html, art.url)
                if not parsed or not parsed.get("content"):
                    logger.warning(f"Не удалось распарсить статью {art.id}")
                    continue

                new_text = parsed["content"]
                if len(new_text) < 100:
                    logger.warning(f"Слишком короткий текст после парсинга {art.id}, пропуск")
                    continue

                if dry_run:
                    logger.info(
                        f"[DRY-RUN] Обновил бы статью {art.id}: {len(art.text)} -> {len(new_text)} символов"
                    )
                    updated += 1
                    continue

                async with session_factory() as db:
                    r = await db.execute(select(Article).where(Article.id == art.id))
                    a = r.scalar_one_or_none()
                    if a:
                        a.text = new_text
                        a.is_processed = False
                        await db.commit()
                        updated += 1
                        logger.success(f"Статья {art.id} обновлена, is_processed=False")
            except Exception as e:
                logger.error(f"Ошибка при перепарсинге статьи {art.id}: {e}")

        logger.success(f"Готово. Обновлено статей: {updated}")
    finally:
        await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser(description="Перепарсинг статей из БД")
    ap.add_argument("--limit", type=int, default=None, help="Макс. число статей")
    ap.add_argument("--all", action="store_true", help="Перепарсить все статьи (не только с мусором)")
    ap.add_argument("--dry-run", action="store_true", help="Не писать в БД")
    args = ap.parse_args()
    asyncio.run(_run(limit=args.limit, dry_run=args.dry_run, reparse_all=args.all))


if __name__ == "__main__":
    main()
