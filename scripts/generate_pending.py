"""
One-shot script: generate posts for all articles with is_processed=False.

Usage (inside the celery_worker container):
    python scripts/generate_pending.py

Or from the host:
    docker compose exec celery_worker python scripts/generate_pending.py

The script re-uses the same AI pipeline as the main Celery task but runs
directly (no broker required) so you can process the existing backlog
without waiting for the next scheduled run.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on the path when running from scripts/ sub-dir
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from models import Article, UserSettings
from publisher import UTMInjector
from tasks.parse_task import (
    _generate_post_for_article,
    notify_admin,
    parse_comma_separated,
)
from tasks.publish_task import publish_post


async def _run() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    local_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # Fetch user settings
        async with local_session_factory() as db:
            result = await db.execute(select(UserSettings).limit(1))
            user_settings = result.scalar_one_or_none()

        if not user_settings:
            logger.error(
                "No user settings found. Please /start the bot and configure settings first."
            )
            return

        keywords = parse_comma_separated(user_settings.keywords)
        internal_links = parse_comma_separated(user_settings.internal_links)
        utm_injector = UTMInjector()

        # Fetch all unprocessed articles
        async with local_session_factory() as db:
            result = await db.execute(
                select(Article).where(Article.is_processed == False)
            )
            articles = result.scalars().all()

        if not articles:
            logger.info("No unprocessed articles found — nothing to do.")
            return

        logger.info(f"Found {len(articles)} unprocessed articles. Starting generation...")

        stats = {"created": 0, "errors": 0}

        for article in articles:
            logger.info(f"Processing article {article.id}: {article.title[:80] if article.title else '(no title)'}")

            if not article.text or not article.text.strip():
                logger.warning(f"Article {article.id} has empty text, skipping")
                stats["errors"] += 1
                continue

            article_data = {
                "title": article.title or "",
                "content": article.text,
            }

            post_id = await _generate_post_for_article(
                article_id=article.id,
                article_data=article_data,
                user_settings=user_settings,
                utm_injector=utm_injector,
                keywords=keywords,
                internal_links=internal_links,
                local_session_factory=local_session_factory,
                stats=stats,
            )

            if post_id is None:
                logger.warning(f"Post generation failed for article {article.id}")
                continue

            stats["created"] += 1
            logger.success(f"Created post {post_id} for article {article.id}")

            if user_settings.is_auto_publish:
                publish_post.delay(post_id)
                logger.info(f"Post {post_id} queued for auto-publish")
            else:
                notify_admin(post_id)
                logger.info(f"Admin notified about post {post_id}")

        logger.success(
            f"Done. Posts created: {stats['created']}, errors: {stats['errors']}"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_run())
