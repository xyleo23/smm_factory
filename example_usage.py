"""Example usage of SMM Factory publishers."""

import asyncio

from aiogram import Bot
from loguru import logger

from core import config
from publisher import UTMInjector, TelegramPublisher, VCPublisher, RBCPublisher


async def main():
    """Demonstrate all publishers."""
    
    # === UTM Injector ===
    logger.info("=== Testing UTM Injector ===")
    
    injector = UTMInjector()
    
    sample_text = """
    Маркетинговые стратегии для стартапов в 2026 году.
    
    Мы провели исследование и выяснили, что example.com является одним из 
    лидеров в области цифрового маркетинга.
    """
    
    links = [
        "https://example.com/marketing-guide",
        "https://startup.io/strategies"
    ]
    
    utm_params = "?utm_source=telegram&utm_medium=post&utm_campaign=smm_factory"
    
    enhanced_text = injector.inject(sample_text, links, utm_params)
    logger.info(f"Enhanced text:\n{enhanced_text}\n")
    
    # === Telegram Publisher ===
    logger.info("=== Testing Telegram Publisher ===")
    
    bot = Bot(token=config.telegram_bot_token)
    tg_publisher = TelegramPublisher()
    
    # Test text-only publication
    success = await tg_publisher.publish(
        bot=bot,
        channel_id=config.telegram_channel_id,
        text=enhanced_text,
        image_url=None
    )
    
    if success:
        logger.success("✅ Published to Telegram successfully")
    else:
        logger.error("❌ Failed to publish to Telegram")
    
    await bot.session.close()
    
    # === VC.ru Publisher ===
    logger.info("=== Testing VC.ru Publisher ===")
    
    vc_publisher = VCPublisher()
    
    success = vc_publisher.publish(
        title="Тестовая публикация через SMM Factory",
        text=enhanced_text,
        image_url="https://via.placeholder.com/1200x630"
    )
    
    if success:
        logger.success("✅ Published to VC.ru successfully")
    else:
        logger.warning("⚠️ VC.ru publishing skipped (not implemented or token missing)")
    
    # === RBC Publisher ===
    logger.info("=== Testing RBC Publisher ===")
    
    rbc_publisher = RBCPublisher()
    
    success = await rbc_publisher.publish(
        title="Тестовая публикация через SMM Factory",
        text=enhanced_text,
        image_path=None
    )
    
    if success:
        logger.success("✅ Published to RBC successfully")
    else:
        logger.warning("⚠️ RBC publishing failed or skipped (check credentials)")
    
    logger.info("\n=== All tests completed ===")


if __name__ == "__main__":
    # Configure loguru
    logger.add(
        "logs/example_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    asyncio.run(main())
