"""Celery task for publishing posts to multiple platforms."""

import asyncio
from datetime import datetime

from aiogram import Bot
from celery import Task
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from aiogram.types import URLInputFile

from tasks.celery_app import celery_app
from models import Post, UserSettings, PostStatus, TargetPlatform
from core.config import settings
from publisher import TelegramPublisher, VCPublisher, RBCPublisher
from core.config import config


def parse_comma_separated(value: str | None) -> list[str]:
    """Parse comma-separated string into list of strings."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def publish_post(self: Task, post_id: int) -> dict:
    """
    Publish post to all configured platforms.
    
    This task:
    1. Fetches the post from database
    2. Gets user settings for publishing channels
    3. Publishes to Telegram channels
    4. Publishes to VC.ru (if configured)
    5. Publishes to RBC Companies (if configured)
    6. Updates post status in database
    
    Args:
        post_id: ID of the post to publish
        
    Returns:
        Dictionary with publishing results
    """
    logger.info(f"Starting publish_post task for post {post_id}")
    
    try:
        # Run async code in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_publish_post_async(post_id))
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"publish_post task failed for post {post_id}: {exc}")
        
        # Retry with exponential backoff
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            countdown = 60 * (2 ** retry_count)
            logger.info(f"Retrying task in {countdown}s (attempt {retry_count + 1}/{self.max_retries})")
            raise self.retry(exc=exc, countdown=countdown)
        else:
            logger.error("Max retries reached, task failed permanently")
            
            # Update post status to failed
            try:
                asyncio.run(_update_post_status(post_id, "failed"))
            except Exception as e:
                logger.error(f"Failed to update post status: {e}")
            
            return {
                "status": "failed",
                "post_id": post_id,
                "error": str(exc),
                "retries": retry_count,
            }


async def _update_post_status(post_id: int, status: str) -> None:
    """Update post status in database. Creates local engine/session for event loop isolation."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    local_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with local_session_factory() as db:
            try:
                result = await db.execute(select(Post).where(Post.id == post_id))
                post = result.scalar_one_or_none()
                if post:
                    post.status = status
                    await db.commit()
            except Exception:
                await db.rollback()
                raise
    finally:
        await engine.dispose()


async def _publish_post_async(post_id: int) -> dict:
    """Async implementation of post publishing."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    local_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        results = {
            "post_id": post_id,
            "telegram": [],
            "vc": False,
            "rbc": False,
            "errors": [],
        }

        # Step 1: Get post from database
        logger.info(f"Fetching post {post_id} from database")
        async with local_session_factory() as db:
            result = await db.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()

        if not post:
            logger.error(f"Post {post_id} not found in database")
            return {
                "status": "error",
                "error": "Post not found",
                **results,
            }

        if post.status == PostStatus.PUBLISHED.value:
            logger.warning(f"Post {post_id} is already published")
            return {
                "status": "skipped",
                "reason": "already_published",
                **results,
            }

        post_title = post.title
        post_text = post.text
        post_image_url = post.image_url

        logger.info(f"Publishing post: {post_title}")

        # Step 2: Get user settings
        async with local_session_factory() as db:
            result = await db.execute(select(UserSettings).limit(1))
            user_settings = result.scalar_one_or_none()

        if not user_settings:
            logger.warning("No user settings found in database")
            # Return early - cannot proceed without settings
            return {
                "status": "error",
                "message": "No user settings configured. Please configure settings in bot first.",
                **results,
            }

        target_platform = getattr(post, "target_platform", None) or "vc"

        # Platform-specific routing: VC = autopost stub, RBC = send draft to admin in TG
        if target_platform == TargetPlatform.RBC.value:
            # RBC: send full post + image to admin for manual publication
            admin_chat_id = getattr(config, "admin_chat_id", None) or getattr(settings, "admin_chat_id", None)
            bot_token = getattr(config, "telegram_bot_token", None) or getattr(settings, "telegram_bot_token", None)
            if not admin_chat_id or not bot_token:
                logger.warning("RBC post: admin_chat_id or telegram_bot_token not configured")
                results["errors"].append("rbc_admin_not_configured")
            else:
                bot = Bot(token=bot_token)
                try:
                    header = "📝 [ЧЕРНОВИК ДЛЯ РБК - РУЧНАЯ ПУБЛИКАЦИЯ]\n\n"
                    full_text = f"{header}<b>{post_title or 'Без заголовка'}</b>\n\n{post_text}"
                    if post_image_url:
                        await bot.send_photo(
                            chat_id=admin_chat_id,
                            photo=URLInputFile(post_image_url),
                            caption=full_text,
                            parse_mode="HTML",
                        )
                    else:
                        await bot.send_message(
                            chat_id=admin_chat_id,
                            text=full_text,
                            parse_mode="HTML",
                        )
                    results["rbc"] = True
                    logger.success(f"RBC draft sent to admin for post {post_id}")
                except Exception as e:
                    logger.error(f"Failed to send RBC draft to admin: {e}")
                    results["errors"].append(f"rbc_draft_error: {e}")
                finally:
                    await bot.session.close()
        else:
            # VC: autoposting stub (to be implemented)
            logger.info("Auto-posting to VC.ru (to be implemented)")
            results["vc"] = False

        # Determine overall result
        has_success = (
            any(r["status"] == "success" for r in results["telegram"])
            or results["vc"]
            or results["rbc"]
        )

        # Step 6: Update post status in database
        async with local_session_factory() as db:
            try:
                result = await db.execute(select(Post).where(Post.id == post_id))
                post = result.scalar_one_or_none()
                if post:
                    if has_success:
                        post.status = PostStatus.PUBLISHED.value
                        post.published_at = datetime.utcnow()
                        logger.success(f"Post {post_id} marked as published")
                    else:
                        post.status = "failed"
                        logger.error(f"Post {post_id} marked as failed (no successful publishes)")
                    await db.commit()
            except Exception:
                await db.rollback()
                raise

        if results["errors"]:
            status = "partial" if has_success else "failed"
        else:
            status = "success"

        logger.info(f"Publishing completed for post {post_id}: {status}")

        return {
            "status": status,
            **results,
        }
    finally:
        await engine.dispose()
