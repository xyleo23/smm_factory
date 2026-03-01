"""Example script to start Celery worker and test tasks."""

import asyncio
from loguru import logger

from core.database import get_db, init_db
from models import Source, UserSettings, Article, Post
from tasks import parse_and_generate, publish_post


def setup_database():
    """Initialize database and create sample data."""
    logger.info("Initializing database...")
    init_db()
    
    with get_db() as db:
        # Check if we already have data
        existing_sources = db.query(Source).count()
        
        if existing_sources == 0:
            logger.info("Creating sample sources...")
            
            # Create sample sources
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
            
            db.commit()
            logger.success(f"Created {len(sources)} sample sources")
        
        # Check if we have user settings
        existing_settings = db.query(UserSettings).count()
        
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
            db.commit()
            logger.success("Created default user settings")


def test_parse_task():
    """Test the parse_and_generate task."""
    logger.info("Testing parse_and_generate task...")
    
    # Call task synchronously for testing
    result = parse_and_generate.apply()
    
    logger.info(f"Task result: {result.get()}")


def test_publish_task():
    """Test the publish_post task."""
    logger.info("Testing publish_post task...")
    
    # Get a pending post
    with get_db() as db:
        post = db.query(Post).filter(Post.status == "pending").first()
        
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
            db.commit()
            db.refresh(post)
            logger.success(f"Created test post with ID {post.id}")
    
    # Call task synchronously for testing
    result = publish_post.apply(args=[post.id])
    
    logger.info(f"Task result: {result.get()}")


def main():
    """Main function."""
    logger.info("""
    ╔════════════════════════════════════════════════════════════╗
    ║              SMM Factory - Celery Worker Setup            ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Setup database
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
