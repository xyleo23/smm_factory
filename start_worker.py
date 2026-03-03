"""Example script to start Celery worker and test tasks."""

import asyncio
from loguru import logger
from sqlalchemy import func, select

from core.database import async_session, init_db
from models import Source, UserSettings, Article, Post
from tasks import parse_and_generate, publish_post


async def _setup_database() -> None:
    """Initialize database and create sample data."""
    logger.info("Initializing database...")
    await init_db()

    async with async_session() as db:
        try:
            # Check if we already have data
            r_sources = await db.execute(select(func.count()).select_from(Source))
            existing_sources = r_sources.scalar() or 0

            if existing_sources == 0:
                logger.info("Creating sample sources...")

                sources = [
                    Source(
                        url="https://vc.ru/marketing",
                        name="VC.ru Marketing",
                        is_active=True,
                    ),
                    Source(
                        url="https://habr.com/ru/all/",
                        name="Habr All Posts",
                        is_active=True,
                    ),
                ]

                for source in sources:
                    db.add(source)

                await db.commit()
                logger.success(f"Created {len(sources)} sample sources")

            # Check if we have user settings
            r_settings = await db.execute(select(func.count()).select_from(UserSettings))
            existing_settings = r_settings.scalar() or 0

            if existing_settings == 0:
                logger.info("Creating default user settings...")

                settings = UserSettings(
                    user_id=1,
                    serp_keywords=["маркетинг", "smm", "контент-маркетинг"],
                    internal_links=[
                        "https://example.com/blog",
                        "https://example.com/services",
                    ],
                    utm_template="?utm_source=telegram&utm_medium=post&utm_campaign=auto",
                    tone="professional",
                    keywords=["маркетинг", "smm", "контент"],
                    selected_llm="gpt-4",
                    tg_channels=["@your_channel"],
                    is_auto_publish=False,
                )

                db.add(settings)
                await db.commit()
                logger.success("Created default user settings")
        except Exception:
            await db.rollback()
            raise


def setup_database() -> None:
    """Synchronous wrapper for database setup."""
    asyncio.run(_setup_database())


def test_parse_task() -> None:
    """Test the parse_and_generate task."""
    logger.info("Testing parse_and_generate task...")

    result = parse_and_generate.apply()
    logger.info(f"Task result: {result.get()}")


async def _get_or_create_test_post() -> int:
    """Get a pending post or create one. Returns post_id."""
    async with async_session() as db:
        try:
            result = await db.execute(
                select(Post).where(Post.status == "pending").limit(1)
            )
            post = result.scalar_one_or_none()

            if not post:
                logger.warning("No pending posts found")
                logger.info("Creating a test post...")

                post = Post(
                    title="Test Post",
                    text="# Test Post\n\nThis is a test post created by the worker script.",
                    image_url="https://via.placeholder.com/1200x630",
                    status="pending",
                )
                db.add(post)
                await db.commit()
                await db.refresh(post)
                logger.success(f"Created test post with ID {post.id}")

            return post.id
        except Exception:
            await db.rollback()
            raise


def test_publish_task() -> None:
    """Test the publish_post task."""
    logger.info("Testing publish_post task...")

    post_id = asyncio.run(_get_or_create_test_post())

    result = publish_post.apply(args=[post_id])
    logger.info(f"Task result: {result.get()}")


def main() -> None:
    """Main function."""
    logger.info("""
    ╔════════════════════════════════════════════════════════════╗
    ║              SMM Factory - Celery Worker Setup            ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    setup_database()

    logger.info("""
    ✅ Database setup complete!

    To start the Celery worker, run:

        celery -A tasks.celery_app worker --loglevel=info

    To schedule periodic tasks, also run the beat scheduler:

        celery -A tasks.celery_app beat --loglevel=info

    Or run both together:

        celery -A tasks.celery_app worker --beat --loglevel=info

    To test tasks manually:

        python -c "from tasks import parse_and_generate; parse_and_generate.delay()"

    To monitor tasks:

        celery -A tasks.celery_app flower

    Make sure Redis is running first:

        redis-server

    Or using Docker:

        docker run -d -p 6379:6379 redis:7-alpine
    """)


if __name__ == "__main__":
    logger.add(
        "logs/worker_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )

    main()
