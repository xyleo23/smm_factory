"""Celery task for parsing content and generating posts."""

import asyncio
from datetime import datetime
from typing import List, Set

from celery import Task
from loguru import logger
from sqlalchemy import select

from tasks.celery_app import celery_app
from models import Source, UserSettings, Article, Post, ParsingHistory
from core.database import get_db
from parser import ArticleParser, SerpParser, fetch_links_from_page
from ai import ContentAnalyzer, SEOWriter, SEOChecker, SelfReviewer, NanaBananaGenerator
from publisher import UTMInjector
from tasks.publish_task import publish_post


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


def save_to_history(url: str, status: str, error_message: str = None) -> None:
    """
    Save parsing attempt to history.
    
    Args:
        url: URL that was parsed
        status: Status (success, failed, skipped)
        error_message: Optional error message
    """
    try:
        with get_db() as db:
            history = ParsingHistory(
                url=url,
                status=status,
                error_message=error_message,
            )
            db.add(history)
            db.commit()
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
    with get_db() as db:
        sources = db.execute(
            select(Source).where(Source.is_active == True)
        ).scalars().all()
        
        if not sources:
            logger.warning("No active sources found in database")
            return {"status": "skipped", "reason": "no_sources", **stats}
        
        logger.info(f"Found {len(sources)} active sources")
    
    # Step 2: Get user settings
    logger.info("Fetching user settings from database")
    with get_db() as db:
        user_settings = db.execute(
            select(UserSettings).limit(1)
        ).scalar_one_or_none()
        
        if not user_settings:
            logger.warning("No user settings found, using defaults")
            user_settings = UserSettings(
                user_id=1,
                serp_keywords=[],
                internal_links=[],
                utm_template="?utm_source=auto&utm_medium=post",
                tone="professional",
                keywords=[],
                selected_llm="gpt-4",
                tg_channels=[],
                is_auto_publish=False,
            )
    
    # Step 3: Collect URLs from sources
    logger.info("Collecting URLs from sources")
    all_urls: Set[str] = set()
    
    for source in sources:
        try:
            logger.info(f"Fetching links from source: {source.name or source.url}")
            links = await fetch_links_from_page(source.url)
            all_urls.update(links)
            stats["sources_processed"] += 1
            
            # Update last parsed time
            with get_db() as db:
                db_source = db.get(Source, source.id)
                if db_source:
                    db_source.last_parsed_at = datetime.utcnow()
                    db.commit()
                    
        except Exception as e:
            logger.error(f"Error fetching links from {source.url}: {e}")
            stats["errors"] += 1
            continue
    
    # Step 4: Collect URLs from SERP keywords
    if user_settings.serp_keywords:
        logger.info(f"Searching SERP for {len(user_settings.serp_keywords)} keywords")
        
        for keyword in user_settings.serp_keywords:
            try:
                serp_urls = await SerpParser.search_all(keyword)
                all_urls.update(serp_urls)
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
    with get_db() as db:
        existing_urls = db.execute(
            select(Article.url).where(Article.url.in_(all_urls))
        ).scalars().all()
        existing_urls_set = set(existing_urls)
    
    new_urls = all_urls - existing_urls_set
    logger.info(f"Found {len(new_urls)} new URLs to process ({len(existing_urls_set)} already in database)")
    
    # Step 6: Process each new URL
    utm_injector = UTMInjector()
    
    for url in new_urls:
        try:
            logger.info(f"Processing URL: {url}")
            
            # Parse article
            html = await ArticleParser.fetch_html(url)
            if not html:
                logger.warning(f"Failed to fetch HTML for {url}")
                save_to_history(url, "failed", "Could not fetch HTML")
                stats["errors"] += 1
                continue
            
            article_data = ArticleParser.parse_article(html, url)
            if not article_data:
                logger.warning(f"Failed to parse article from {url}")
                save_to_history(url, "failed", "Could not parse article")
                stats["errors"] += 1
                continue
            
            # Save article to database
            with get_db() as db:
                article = Article(
                    url=url,
                    title=article_data.get("title"),
                    content=article_data.get("content"),
                    is_processed=False,
                )
                db.add(article)
                db.commit()
                db.refresh(article)
                article_id = article.id
            
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
                keywords=user_settings.keywords,
                llm=user_settings.selected_llm,
            )
            
            # Check SEO
            seo_result = SEOChecker.check(text, user_settings.keywords)
            
            # Review if SEO check failed
            if not seo_result["passed"]:
                logger.warning(f"SEO check failed for article {article_id}, reviewing...")
                text = await SelfReviewer.review(text, seo_result["issues"])
            
            # Inject UTM parameters
            text = utm_injector.inject(
                text,
                user_settings.internal_links,
                user_settings.utm_template,
            )
            
            # Generate image
            image_url = await NanaBananaGenerator.generate(
                title=article_data.get("title", ""),
                topic=article_data.get("title", ""),
            )
            
            # Save post to database
            with get_db() as db:
                post = Post(
                    article_id=article_id,
                    title=article_data.get("title"),
                    text=text,
                    image_url=image_url,
                    status="pending",
                )
                db.add(post)
                db.commit()
                db.refresh(post)
                post_id = post.id
                
                # Mark article as processed
                article = db.get(Article, article_id)
                if article:
                    article.is_processed = True
                    article.processed_at = datetime.utcnow()
                    db.commit()
            
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
            
            save_to_history(url, "success")
            
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            save_to_history(url, "failed", str(e))
            stats["errors"] += 1
            continue
    
    logger.success(f"Parse and generate task completed: {stats}")
    return {"status": "completed", **stats}
