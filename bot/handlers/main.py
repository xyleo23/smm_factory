"""Main menu handlers: /start, run_parse, back_to_main."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from bot.keyboards.main import get_main_keyboard
from bot.utils import get_or_create_settings, settings_text
from tasks.parse_task import parse_and_generate

router = Router(name="main")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start — show current settings and the main keyboard."""
    await state.clear()

    user_id = message.from_user.id
    settings = get_or_create_settings(user_id)

    await message.answer(
        text=settings_text(settings),
        reply_markup=get_main_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "run_parse")
async def cb_run_parse(callback: CallbackQuery) -> None:
    """Launch the parse_and_generate Celery task."""
    try:
        parse_and_generate.delay()
        await callback.message.edit_text(
            "🚀 Парсинг запущен! Жду статьи...",
            reply_markup=get_main_keyboard(),
        )
    except Exception as exc:
        logger.error(f"Failed to start parse_and_generate: {exc}")
        await callback.message.edit_text(
            "❌ Не удалось запустить парсинг. Проверьте, что Celery worker запущен.",
            reply_markup=get_main_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to the main menu, clearing any active FSM state."""
    await state.clear()

    user_id = callback.from_user.id
    settings = get_or_create_settings(user_id)

    await callback.message.edit_text(
        text=settings_text(settings),
        reply_markup=get_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
