"""Settings keyboard with current values displayed."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models.settings import UserSettings

TONES: dict[str, str] = {
    "professional": "Проф.",
    "friendly": "Дружелюбный",
    "casual": "Неформальный",
    "expert": "Экспертный",
    "creative": "Креативный",
}

LLMS: list[str] = ["gpt-4o", "gpt-4", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet"]


def get_settings_keyboard(settings: UserSettings) -> InlineKeyboardMarkup:
    """Build settings keyboard showing current values with ✅ on active options."""
    buttons: list[list[InlineKeyboardButton]] = []

    # Tone selection — first 3 on one row, last 2 on next
    tone_keys = list(TONES.keys())
    tone_row_1 = [
        InlineKeyboardButton(
            text=f"{'✅ ' if settings.tone == t else ''}{TONES[t]}",
            callback_data=f"set_tone:{t}",
        )
        for t in tone_keys[:3]
    ]
    tone_row_2 = [
        InlineKeyboardButton(
            text=f"{'✅ ' if settings.tone == t else ''}{TONES[t]}",
            callback_data=f"set_tone:{t}",
        )
        for t in tone_keys[3:]
    ]
    buttons.append(tone_row_1)
    if tone_row_2:
        buttons.append(tone_row_2)

    # LLM selection — 3 per row
    llm_row_1 = [
        InlineKeyboardButton(
            text=f"{'✅ ' if settings.selected_llm == llm else ''}{llm}",
            callback_data=f"set_llm:{llm}",
        )
        for llm in LLMS[:3]
    ]
    llm_row_2 = [
        InlineKeyboardButton(
            text=f"{'✅ ' if settings.selected_llm == llm else ''}{llm}",
            callback_data=f"set_llm:{llm}",
        )
        for llm in LLMS[3:]
    ]
    buttons.append(llm_row_1)
    if llm_row_2:
        buttons.append(llm_row_2)

    # Auto-publish toggle
    auto_label = "🔄 Автопубликация: ✅ Вкл" if settings.is_auto_publish else "🔄 Автопубликация: ❌ Выкл"
    buttons.append([InlineKeyboardButton(text=auto_label, callback_data="toggle_autopublish")])

    # Input fields
    buttons.append([InlineKeyboardButton(text="🔍 Задать SERP-ключи", callback_data="set_serp_keys")])
    buttons.append([InlineKeyboardButton(text="📝 Задать UTM-шаблон", callback_data="set_utm")])
    buttons.append([InlineKeyboardButton(text="🔗 Задать внутренние ссылки", callback_data="set_links")])
    buttons.append([InlineKeyboardButton(text="📡 Задать TG-каналы", callback_data="set_channels")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard(callback_data: str = "back_to_main") -> InlineKeyboardMarkup:
    """Single back-button keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data)]]
    )
