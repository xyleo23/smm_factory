"""SMM Factory — root entry point.

Loads config, initialises the database, wires up all aiogram routers and starts long-polling.
"""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger
from sqlalchemy import select

from core.config import config
from core.database import async_session, init_db
from models.article import Article
from models.post import Post
from models.settings import UserSettings
from models.source import Source

from bot.handlers import main as main_handler
from bot.handlers import settings as settings_handler
from bot.handlers import sources as sources_handler
from bot.handlers import queue as queue_handler
from bot.handlers import stats as stats_handler


async def on_startup(bot: Bot) -> None:
    me = await bot.get_me()
    logger.info("SMM Factory started — @{} (id={}).", me.username, me.id)


async def on_shutdown(bot: Bot) -> None:
    logger.info("SMM Factory shutting down...")
    await bot.session.close()


async def main() -> None:
    token = config.telegram_bot_token
    if not token:
        logger.error(
            "BOT_TOKEN / TELEGRAM_BOT_TOKEN is not set. Add it to your .env file."
        )
        sys.exit(1)

    # Initialise DB tables
    await init_db()

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register routers — more specific handlers first, fallback (main) last
    dp.include_router(settings_handler.router)
    dp.include_router(sources_handler.router)
    dp.include_router(queue_handler.router)
    dp.include_router(stats_handler.router)
    dp.include_router(main_handler.router)

    logger.info("Starting long-polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
