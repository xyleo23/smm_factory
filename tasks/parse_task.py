"""Celery task for parsing content and generating posts."""

import asyncio
from datetime import datetime
from typing import Dict, List, Set

from celery import Task
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from tasks.celery_app import celery_app
from models import Source, UserSettings, Article, Post, ParsingHistory, PostStatus
from core.config import settings
from parser import ArticleParser, SerpParser, fetch_links_from_page, fetch_rss_articles
from ai import ContentAnalyzer, SEOWriter, SEOChecker, SelfReviewer, NanaBananaGenerator
from publisher import UTMInjector
from tasks.publish_task import publish_post


def parse_comma_separated(value: str | None) -> list[str]:
    """Parse comma-separated string into list of strings."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def notify_admin(post_id: int) -> None:
    """
    Send notification to admin about new post ready for review.
    
    Args:
        post_id: ID of the post ready for review
    """
    # TODO: Implement bot notification
    # - Send message to admin via Telegram bot
    # - Include post preview and approve/reject buttons
    logger.info(f"TODO: Send notification to admin for post {post_id}")


async def _save_to_history(
    url: str, status: str, error_message: str = None, session_factory=None
) -> None:
    """
    Save parsing attempt to history.

    Args:
        url: URL that was parsed
        status: Status (success, failed, skipped)
        error_message: Optional error message
        session_factory: Session factory for the current event loop (required)
    """
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


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def parse_and_generate(self: Task) -> dict:
    """
    Full content pipeline: parse articles, generate posts, and publish.
    
    This is the main Celery task that:
    1. Fetches active sources from database
    2. Collects URLs from sources and SERP keywords
    3. Parses each article
    4. Generates SEO-optimized content
    5. Creates posts in database
    6. Triggers publishing (if auto-publish enabled)
    
    Returns:
        Dictionary with statistics about the run
    """
    logger.info("Starting parse_and_generate task")
    
    try:
        # Run async code in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_parse_and_generate_async())
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"parse_and_generate task failed: {exc}")
        
        # Retry with exponential backoff
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
            result = await db.execute(
                select(Source).where(Source.is_active == True)
            )
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
            # Return early - cannot proceed without settings
            return {
                "status": "error",
                "message": "No user settings configured. Please configure settings in bot first.",
                **stats,
            }

        # Parse user settings string fields to lists
        serp_keywords = parse_comma_separated(user_settings.serp_keywords)
        internal_links = parse_comma_separated(user_settings.internal_links)
        keywords = parse_comma_separated(user_settings.keywords)

        # Step 3: Collect URLs from sources
        logger.info("Collecting URLs from sources")
        all_urls: Set[str] = set()
        url_to_source: Dict[str, int] = {}
        rss_items: List[tuple] = []  # (source_id, article_dict)

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
                else:
                    links = await fetch_links_from_page(source.url)
                    for link in links:
                        all_urls.add(link)
                        url_to_source[link] = source.id

                stats["sources_processed"] += 1

                # Update last parsed time
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

        if not all_urls:
            logger.warning("No URLs collected")
            return {"status": "completed", **stats}

        # Step 5: Filter out already existing articles
        async with local_session_factory() as db:
            result = await db.execute(
                select(Article.url).where(Article.url.in_(list(all_urls)))
            )
            existing_urls = result.scalars().all()
            existing_urls_set = set(existing_urls)

        new_urls = all_urls - existing_urls_set
        logger.info(f"Found {len(new_urls)} new URLs to process ({len(existing_urls_set)} already in database)")

        # Step 5b: Save RSS articles (content already in feed, no per-article fetch)
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
                            content=article.get("content", "") or "",
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

        # Step 6: Process each new URL
        utm_injector = UTMInjector()

        for url in new_urls:
            try:
                logger.info(f"Processing URL: {url}")

                article_data = None
                article_id = None
                source_id = url_to_source.get(url, sources[0].id if sources else None)

                # Try to load from DB first (RSS articles already saved with content)
                async with local_session_factory() as db:
                    result = await db.execute(select(Article).where(Article.url == url))
                    existing_article = result.scalar_one_or_none()
                    if existing_article:
                        if existing_article.is_processed:
                            continue
                        article_data = {
                            "title": existing_article.title,
                            "content": existing_article.content,
                        }
                        article_id = existing_article.id

                if not article_data:
                    # Fetch and parse (non-RSS flow)
                    html = await ArticleParser.fetch_html(url)
                    if not html:
                        logger.warning(f"Failed to fetch HTML for {url}")
                        await _save_to_history(url, "failed", "Could not fetch HTML", local_session_factory)
                        stats["errors"] += 1
                        continue

                    article_data = ArticleParser.parse_article(html, url)
                    if not article_data:
                        logger.warning(f"Failed to parse article from {url}")
                        await _save_to_history(url, "failed", "Could not parse article", local_session_factory)
                        stats["errors"] += 1
                        continue

                    # Save article to database
                    if not source_id:
                        logger.warning(f"No source_id for {url}, skipping")
                        continue
                    async with local_session_factory() as db:
                        try:
                            article = Article(
                                source_id=source_id,
                                url=url,
                                title=article_data.get("title"),
                                content=article_data.get("content"),
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

                # Analyze content
                analysis = await ContentAnalyzer.analyze(
                    article_data.get("title", ""),
                    article_data.get("content", ""),
                )

                # Generate SEO-optimized text
                text = await SEOWriter.write(
                    analysis=analysis,
                    tone=user_settings.tone,
                    keywords=keywords,
                    llm=user_settings.selected_llm,
                )

                # Check SEO
                seo_result = SEOChecker.check(text, keywords)

                # Review if SEO check failed
                if not seo_result["passed"]:
                    logger.warning(f"SEO check failed for article {article_id}, reviewing...")
                    text = await SelfReviewer.review(text, seo_result["issues"])

                # Inject UTM parameters
                text = utm_injector.inject(
                    text,
                    internal_links,
                    user_settings.utm_template,
                )

                # Generate image
                image_url = await NanaBananaGenerator.generate(
                    title=article_data.get("title", ""),
                    topic=article_data.get("title", ""),
                )

                # Save post to database
                async with local_session_factory() as db:
                    try:
                        post = Post(
                            article_id=article_id,
                            title=article_data.get("title"),
                            text=text,
                            image_url=image_url,
                            status=PostStatus.PENDING.value,
                        )
                        db.add(post)
                        await db.commit()
                        await db.refresh(post)
                        post_id = post.id

                        # Mark article as processed
                        ar_result = await db.execute(select(Article).where(Article.id == article_id))
                        article = ar_result.scalar_one_or_none()
                        if article:
                            article.is_processed = True
                            article.processed_at = datetime.utcnow()
                            await db.commit()
                    except Exception:
                        await db.rollback()
                        raise

                stats["posts_created"] += 1
                logger.success(f"Created post {post_id} from article {article_id}")

                # Publish or notify
                if user_settings.is_auto_publish:
                    logger.info(f"Auto-publishing post {post_id}")
                    publish_post.delay(post_id)
                    stats["posts_published"] += 1
                else:
                    logger.info(f"Notifying admin about post {post_id}")
                    notify_admin(post_id)

                await _save_to_history(url, "success", session_factory=local_session_factory)

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                await _save_to_history(url, "failed", str(e), local_session_factory)
                stats["errors"] += 1
                continue

        logger.success(f"Parse and generate task completed: {stats}")
        return {"status": "completed", **stats}
    finally:
        await engine.dispose()
