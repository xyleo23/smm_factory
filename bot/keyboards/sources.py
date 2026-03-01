"""Sources management keyboard."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models import Source


class SourceActionCallback(CallbackData, prefix="src"):
    source_id: int
    action: str  # "toggle" | "delete"


def get_sources_keyboard(sources: list[Source]) -> InlineKeyboardMarkup:
    """Build sources list keyboard with toggle and delete buttons."""
    buttons: list[list[InlineKeyboardButton]] = []

    for source in sources:
        status = "✅" if source.is_active else "❌"
        name = (source.name or source.url)[:35]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {name}",
                    callback_data=SourceActionCallback(
                        source_id=source.id, action="toggle"
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=SourceActionCallback(
                        source_id=source.id, action="delete"
                    ).pack(),
                ),
            ]
        )

    buttons.append(
        [InlineKeyboardButton(text="➕ Добавить источник", callback_data="add_source")]
    )
    buttons.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
