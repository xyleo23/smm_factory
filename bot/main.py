"""Bot entry-point: initialise Dispatcher, register all routers, start polling."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from core.config import config
from core.database import init_db

from bot.handlers import main as main_handler
from bot.handlers import settings as settings_handler
from bot.handlers import sources as sources_handler
from bot.handlers import queue as queue_handler
from bot.handlers import stats as stats_handler


async def main() -> None:
    if not config.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Add it to your .env file."
        )

    # Ensure DB tables exist
    init_db()

    bot = Bot(
        token=config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Register routers (order matters — more specific first)
    dp.include_router(settings_handler.router)
    dp.include_router(sources_handler.router)
    dp.include_router(queue_handler.router)
    dp.include_router(stats_handler.router)
    dp.include_router(main_handler.router)  # fallback last

    logger.info("Starting SMM Factory bot (long polling)...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
