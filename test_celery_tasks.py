"""Test script for Celery tasks."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger


def test_imports():
    """Test that all modules can be imported."""
    logger.info("Testing imports...")

    try:
        from core.config import config
        logger.success("✓ core.config imported")

        from models import Source, UserSettings, Article, Post, ParsingHistory
        logger.success("✓ models imported")

        from core.database import async_session, init_db
        logger.success("✓ core.database imported")
        
        from parser import ArticleParser, SerpParser, fetch_links_from_page, fetch_rss_articles
        logger.success("✓ parser modules imported")
        
        from ai import ContentAnalyzer, SEOWriter, SEOChecker, SelfReviewer, NanaBananaGenerator
        logger.success("✓ ai modules imported")
        
        from publisher import TelegramPublisher, VCPublisher, RBCPublisher, UTMInjector
        logger.success("✓ publisher modules imported")
        
        from tasks import celery_app, parse_and_generate, publish_post
        logger.success("✓ tasks imported")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False


def test_config():
    """Test configuration loading."""
    logger.info("Testing configuration...")
    
    try:
        from core.config import config
        
        logger.info(f"Redis URL: {config.redis_url}")
        logger.info(f"Database URL: {config.database_url}")
        logger.info(f"Logs directory: {config.logs_dir}")
        
        # Check if logs directory exists
        if config.logs_dir.exists():
            logger.success("✓ Logs directory exists")
        else:
            logger.warning("! Logs directory does not exist, will be created")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Config test failed: {e}")
        return False


async def _test_db_connection() -> bool:
    """Async helper to test database connection."""
    from core.database import async_session, init_db
    from models import Source
    from sqlalchemy import func, select

    await init_db()
    logger.success("✓ Database tables created")

    async with async_session() as db:
        result = await db.execute(select(func.count()).select_from(Source))
        count = result.scalar() or 0
        logger.info(f"Sources in database: {count}")
        logger.success("✓ Database connection works")
    return True


def test_database():
    """Test database connection."""
    logger.info("Testing database...")

    try:
        return asyncio.run(_test_db_connection())
    except Exception as e:
        logger.error(f"✗ Database test failed: {e}")
        return False


def test_celery_config():
    """Test Celery configuration."""
    logger.info("Testing Celery configuration...")
    
    try:
        from tasks import celery_app
        
        logger.info(f"Broker: {celery_app.conf.broker_url}")
        logger.info(f"Backend: {celery_app.conf.result_backend}")
        logger.info(f"Timezone: {celery_app.conf.timezone}")
        logger.info(f"Task acks late: {celery_app.conf.task_acks_late}")
        
        logger.success("✓ Celery app configured")
        
        # Check registered tasks
        registered_tasks = sorted(celery_app.tasks.keys())
        logger.info(f"Registered tasks ({len(registered_tasks)}):")
        for task in registered_tasks:
            if not task.startswith("celery."):
                logger.info(f"  - {task}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Celery config test failed: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("""
    ╔════════════════════════════════════════════════════════════╗
    ║           SMM Factory - Celery Tasks Test Suite          ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
        ("Celery", test_celery_config),
    ]
    
    results = []
    
    for name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running test: {name}")
        logger.info(f"{'='*60}")
        
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Test Summary")
    logger.info(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        logger.success("\n✅ All tests passed! Ready to start Celery worker.")
        logger.info("\nNext steps:")
        logger.info("1. Start Redis: redis-server")
        logger.info("2. Start worker: celery -A tasks.celery_app worker --loglevel=info")
        logger.info("3. Test task: python -c \"from tasks import parse_and_generate; parse_and_generate.delay()\"")
        return 0
    else:
        logger.error("\n❌ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    logger.add(
        "logs/test_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG"
    )
    
    sys.exit(main())
