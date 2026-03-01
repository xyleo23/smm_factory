"""Keyboards package for the Telegram bot."""

from bot.keyboards.main import get_main_keyboard
from bot.keyboards.settings import get_settings_keyboard, get_back_keyboard
from bot.keyboards.approval import get_approval_keyboard, PostActionCallback
from bot.keyboards.sources import get_sources_keyboard, SourceActionCallback

__all__ = [
    "get_main_keyboard",
    "get_settings_keyboard",
    "get_back_keyboard",
    "get_approval_keyboard",
    "PostActionCallback",
    "get_sources_keyboard",
    "SourceActionCallback",
]
