"""Celery task for parsing content and generating posts."""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Set

from aiogram import Bot
from aiogram.types import URLInputFile
from celery import Task
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from tasks.celery_app import celery_app
from models import Source, UserSettings, Article, Post, ParsingHistory, PostStatus
from core.config import settings, config
from parser import (
    ArticleParser,
    SerpParser,
    fetch_links_from_page,
    fetch_rbc_companies_articles,
    fetch_rss_articles,
)
from ai import ContentAnalyzer, SEOWriter, SEOChecker, SelfReviewer, NanaBananaGenerator
from publisher import UTMInjector
from tasks.publish_task import publish_post


def parse_comma_separated(value: str | None) -> list[str]:
    """Parse comma-separated string into list of strings."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


async def _notify_admin_async(post_id: int) -> None:
    """Send Telegram message to admin with post preview and approval keyboard."""
    from bot.keyboards.approval import get_approval_keyboard

    admin_chat_id = getattr(config, "admin_chat_id", None) or getattr(settings, "admin_chat_id", None)
    bot_token = getattr(config, "telegram_bot_token", None) or getattr(settings, "telegram_bot_token", None)

    if not admin_chat_id or not bot_token:
        logger.warning(
            "notify_admin: admin_chat_id or telegram_bot_token not configured — skipping notification"
        )
        return

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    local_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    bot = Bot(token=bot_token)
    try:
        async with local_session_factory() as db:
            result = await db.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()

        if not post:
            logger.error(f"notify_admin: post {post_id} not found")
            return

        preview = (post.text or "")[:300]
        if len(post.text or "") > 300:
            preview += "..."

        title_line = f"<b>{post.title}</b>\n\n" if post.title else ""
        text = f"📝 <b>Новый пост #{post_id}</b>\n\n{title_line}{preview}"
        keyboard = get_approval_keyboard(post_id)

        if post.image_url:
            await bot.send_photo(
                chat_id=admin_chat_id,
                photo=URLInputFile(post.image_url),
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        logger.success(f"Sent admin notification for post {post_id}")
    except Exception as e:
        logger.error(f"notify_admin: failed to send notification for post {post_id}: {e}")
    finally:
        await bot.session.close()
        await engine.dispose()


def notify_admin(post_id: int) -> None:
    """Send notification to admin about new post ready for review."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_notify_admin_async(post_id))
    finally:
        loop.close()


async def _save_to_history(
    url: str, status: str, error_message: str = None, session_factory=None
) -> None:
    """Save parsing attempt to history."""
    if not session_factory:
        logger.warning("_save_to_history called without session_factory, skipping")
        return
    try:
        async with session_factory() as db:
            history = ParsingHistory(
                url=url,
                status=status,
                error_message=error_message,
            )
            db.add(history)
            await db.commit()
            logger.debug(f"Saved parsing history for {url}: {status}")
    except Exception as e:
        logger.error(f"Failed to save parsing history: {e}")


async def _generate_post_for_article(
    *,
    article_id: int,
    article_data: dict,
    user_settings: UserSettings,
    utm_injector: UTMInjector,
    keywords: list[str],
    internal_links: list[str],
    local_session_factory,
    stats: dict,
) -> Optional[int]:
    """
    Run the AI pipeline for a single article and persist the resulting Post.

    Returns the new post_id on success, or None on failure.
    The caller is responsible for updating stats["posts_created"] etc.
    """
    try:
        analysis = await ContentAnalyzer.analyze(
            article_data.get("title", ""),
            article_data.get("content", ""),
        )

        text = await SEOWriter.write(
            analysis=analysis,
            tone=user_settings.tone,
            keywords=keywords,
            llm=user_settings.selected_llm,
        )

        seo_result = SEOChecker.check(text, keywords)
        if not seo_result["passed"]:
            logger.warning(f"SEO check failed for article {article_id}, reviewing...")
            text = await SelfReviewer.review(text, seo_result["issues"])

        text = utm_injector.inject(text, internal_links, user_settings.utm_template)

        image_url = await NanaBananaGenerator.generate(
            title=article_data.get("title", ""),
            topic=article_data.get("title", ""),
        )

        async with local_session_factory() as db:
            try:
                post = Post(
                    article_id=article_id,
                    title=article_data.get("title", "")[:512] or None,
                    text=text,
                    image_url=image_url,
                    status=PostStatus.PENDING.value,
                )
                db.add(post)
                await db.commit()
                await db.refresh(post)
                post_id = post.id

                ar_result = await db.execute(select(Article).where(Article.id == article_id))
                article = ar_result.scalar_one_or_none()
                if article:
                    article.is_processed = True
                    await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.success(f"Created post {post_id} from article {article_id}")
        return post_id

    except Exception as e:
        logger.error(f"_generate_post_for_article failed for article {article_id}: {e}")
        stats["errors"] += 1
        return None


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def parse_and_generate(self: Task) -> dict:
    """
    Full content pipeline: parse articles, generate posts, and publish.

    1. Fetches active sources from database
    2. Collects URLs from sources and SERP keywords
    3. Parses each new article
    4. Generates SEO-optimized content
    5. Creates posts in database
    6. Processes any existing is_processed=False articles from DB
    7. Triggers publishing (if auto-publish enabled) or notifies admin
    """
    logger.info("Starting parse_and_generate task")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_parse_and_generate_async())
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"parse_and_generate task failed: {exc}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(f"Retrying task (attempt {retry_count + 1}/{self.max_retries})")
            raise self.retry(exc=exc, countdown=300 * (2 ** retry_count))
        else:
            logger.error("Max retries reached, task failed permanently")
            return {
                "status": "failed",
                "error": str(exc),
                "retries": retry_count,
            }


async def _parse_and_generate_async() -> dict:
    """Async implementation of the parse and generate pipeline."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    local_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        stats = {
            "sources_processed": 0,
            "urls_collected": 0,
            "articles_parsed": 0,
            "posts_created": 0,
            "posts_published": 0,
            "errors": 0,
        }

        # Step 1: Get active sources from database
        logger.info("Fetching active sources from database")
        async with local_session_factory() as db:
            result = await db.execute(select(Source).where(Source.is_active == True))
            sources = result.scalars().all()

        if not sources:
            logger.warning("No active sources found in database")
            return {"status": "skipped", "reason": "no_sources", **stats}

        logger.info(f"Found {len(sources)} active sources")

        # Step 2: Get user settings (first user or use defaults)
        logger.info("Fetching user settings from database")
        async with local_session_factory() as db:
            result = await db.execute(select(UserSettings).limit(1))
            user_settings = result.scalar_one_or_none()

        if not user_settings:
            logger.warning("No user settings found in database")
            return {
                "status": "error",
                "message": "No user settings configured. Please configure settings in bot first.",
                **stats,
            }

        serp_keywords = parse_comma_separated(user_settings.serp_keywords)
        internal_links = parse_comma_separated(user_settings.internal_links)
        keywords = parse_comma_separated(user_settings.keywords)

        # Step 3: Collect URLs from sources
        logger.info("Collecting URLs from sources")
        all_urls: Set[str] = set()
        url_to_source: Dict[str, int] = {}
        rss_items: List[tuple] = []   # (source_id, article_dict)
        rbc_items: List[tuple] = []   # (source_id, article_dict)

        for source in sources:
            try:
                logger.info(f"Fetching links from source: {source.name or source.url}")
                url_lower = source.url.lower()

                if "rss" in url_lower or "feed" in url_lower or ".xml" in url_lower:
                    articles = await fetch_rss_articles(source.url)
                    for article in articles:
                        art_url = article.get("url", "").strip()
                        if art_url:
                            all_urls.add(art_url)
                            url_to_source[art_url] = source.id
                            rss_items.append((source.id, article))
                elif "companies.rbc.ru/persons" in url_lower or "companies.rbc.ru/id" in url_lower:
                    articles = await fetch_rbc_companies_articles(source.url)
                    for article in articles:
                        art_url = article.get("url", "").strip()
                        if art_url:
                            all_urls.add(art_url)
                            url_to_source[art_url] = source.id
                            rbc_items.append((source.id, article))
                else:
                    links = await fetch_links_from_page(source.url)
                    for link in links:
                        all_urls.add(link)
                        url_to_source[link] = source.id

                stats["sources_processed"] += 1

                # Update last_parsed_at
                async with local_session_factory() as db:
                    try:
                        result = await db.execute(select(Source).where(Source.id == source.id))
                        db_source = result.scalar_one_or_none()
                        if db_source:
                            db_source.last_parsed_at = datetime.utcnow()
                            await db.commit()
                    except Exception:
                        await db.rollback()
                        raise
            except Exception as e:
                logger.error(f"Error fetching links from {source.url}: {e}")
                stats["errors"] += 1
                continue

        # Step 4: Collect URLs from SERP keywords
        if serp_keywords:
            logger.info(f"Searching SERP for {len(serp_keywords)} keywords")
            default_source_id = sources[0].id if sources else None
            for keyword in serp_keywords:
                try:
                    serp_urls = await SerpParser.search_all(keyword)
                    for u in serp_urls:
                        all_urls.add(u)
                        if default_source_id and u not in url_to_source:
                            url_to_source[u] = default_source_id
                except Exception as e:
                    logger.error(f"Error searching for keyword '{keyword}': {e}")
                    stats["errors"] += 1
                    continue

        stats["urls_collected"] = len(all_urls)
        logger.info(f"Collected {len(all_urls)} unique URLs")

        # Step 5: Filter out already existing articles
        utm_injector = UTMInjector()

        if all_urls:
            async with local_session_factory() as db:
                result = await db.execute(
                    select(Article.url).where(Article.url.in_(list(all_urls)))
                )
                existing_urls_set = set(result.scalars().all())

            new_urls = all_urls - existing_urls_set
            logger.info(
                f"Found {len(new_urls)} new URLs to process "
                f"({len(existing_urls_set)} already in database)"
            )

            # Step 5b: Save RSS articles (content already in feed)
            for source_id, article in rss_items:
                art_url = article.get("url", "").strip()
                if art_url not in new_urls:
                    continue
                try:
                    async with local_session_factory() as db:
                        try:
                            result = await db.execute(
                                select(Article.id).where(Article.url == art_url)
                            )
                            if result.scalar_one_or_none():
                                continue
                            art = Article(
                                source_id=source_id,
                                url=art_url,
                                title=article.get("title", "")[:512],
                                text=article.get("content", "") or "",
                                is_processed=False,
                            )
                            db.add(art)
                            await db.commit()
                            logger.info(f"RSS: saved article {art_url[:60]}...")
                        except Exception:
                            await db.rollback()
                            raise
                except Exception as e:
                    logger.error(f"RSS save error for {art_url}: {e}")
                    stats["errors"] += 1

            # Step 5c: Save RBC Companies articles
            for source_id, article in rbc_items:
                art_url = article.get("url", "").strip()
                if art_url not in new_urls:
                    continue
                try:
                    async with local_session_factory() as db:
                        try:
                            result = await db.execute(
                                select(Article.id).where(Article.url == art_url)
                            )
                            if result.scalar_one_or_none():
                                continue
                            art = Article(
                                source_id=source_id,
                                url=art_url,
                                title=article.get("title", "")[:512],
                                text=article.get("content", "") or "",
                                is_processed=False,
                            )
                            db.add(art)
                            await db.commit()
                            logger.info(f"RBC Companies: saved article {art_url[:60]}...")
                        except Exception:
                            await db.rollback()
                            raise
                except Exception as e:
                    logger.error(f"RBC Companies save error for {art_url}: {e}")
                    stats["errors"] += 1

            # Step 6: Process each new URL (fetch HTML → generate post)
            for url in new_urls:
                try:
                    logger.info(f"Processing URL: {url}")

                    article_data = None
                    article_id = None
                    source_id = url_to_source.get(url, sources[0].id if sources else None)

                    # Check if already saved (RSS/RBC path)
                    async with local_session_factory() as db:
                        result = await db.execute(select(Article).where(Article.url == url))
                        existing_article = result.scalar_one_or_none()
                        if existing_article:
                            if existing_article.is_processed:
                                continue
                            article_data = {
                                "title": existing_article.title,
                                "content": existing_article.text,
                            }
                            article_id = existing_article.id

                    if not article_data:
                        html = await ArticleParser.fetch_html(url)
                        if not html:
                            logger.warning(f"Failed to fetch HTML for {url}")
                            await _save_to_history(
                                url, "failed", "Could not fetch HTML", local_session_factory
                            )
                            stats["errors"] += 1
                            continue

                        article_data = ArticleParser.parse_article(html, url)
                        if not article_data:
                            logger.warning(f"Failed to parse article from {url}")
                            await _save_to_history(
                                url, "failed", "Could not parse article", local_session_factory
                            )
                            stats["errors"] += 1
                            continue

                        if not source_id:
                            logger.warning(f"No source_id for {url}, skipping")
                            continue
                        async with local_session_factory() as db:
                            try:
                                article = Article(
                                    source_id=source_id,
                                    url=url,
                                    title=article_data.get("title"),
                                    text=article_data.get("content") or "",
                                    is_processed=False,
                                )
                                db.add(article)
                                await db.commit()
                                await db.refresh(article)
                                article_id = article.id
                            except Exception:
                                await db.rollback()
                                raise

                    stats["articles_parsed"] += 1
                    logger.info(f"Saved article {article_id}: {article_data.get('title')}")

                    post_id = await _generate_post_for_article(
                        article_id=article_id,
                        article_data=article_data,
                        user_settings=user_settings,
                        utm_injector=utm_injector,
                        keywords=keywords,
                        internal_links=internal_links,
                        local_session_factory=local_session_factory,
                        stats=stats,
                    )

                    if post_id is None:
                        await _save_to_history(
                            url, "failed", "Post generation failed", local_session_factory
                        )
                        continue

                    stats["posts_created"] += 1

                    if user_settings.is_auto_publish:
                        publish_post.delay(post_id)
                        stats["posts_published"] += 1
                    else:
                        notify_admin(post_id)

                    await _save_to_history(url, "success", session_factory=local_session_factory)

                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    await _save_to_history(url, "failed", str(e), local_session_factory)
                    stats["errors"] += 1
                    continue

        # Step 7: Process any backlog articles (is_processed=False) that weren't in this run's URLs
        logger.info("Checking for unprocessed articles in the database...")
        async with local_session_factory() as db:
            result = await db.execute(
                select(Article).where(Article.is_processed == False)
            )
            backlog_articles = result.scalars().all()

        if backlog_articles:
            logger.info(f"Found {len(backlog_articles)} unprocessed articles in DB — generating posts")
            for article in backlog_articles:
                try:
                    article_data = {
                        "title": article.title,
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
                        continue

                    stats["posts_created"] += 1

                    if user_settings.is_auto_publish:
                        publish_post.delay(post_id)
                        stats["posts_published"] += 1
                    else:
                        notify_admin(post_id)

                except Exception as e:
                    logger.error(f"Error processing backlog article {article.id}: {e}")
                    stats["errors"] += 1
                    continue
        else:
            logger.info("No unprocessed backlog articles found")

        logger.success(f"Parse and generate task completed: {stats}")
        return {"status": "completed", **stats}
    finally:
        await engine.dispose()
