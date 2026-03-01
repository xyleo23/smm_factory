"""Main menu keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Return the main menu inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
            [InlineKeyboardButton(text="🔗 Источники", callback_data="sources")],
            [InlineKeyboardButton(text="📥 Очередь", callback_data="queue")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton(text="▶️ Запустить парсинг", callback_data="run_parse")],
        ]
    )
