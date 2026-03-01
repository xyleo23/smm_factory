"""Approval keyboard for post moderation."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class PostActionCallback(CallbackData, prefix="post"):
    post_id: int
    action: str  # "approve" | "rewrite" | "delete"


def get_approval_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Return inline keyboard for approving, rewriting or deleting a post."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=PostActionCallback(post_id=post_id, action="approve").pack(),
                ),
                InlineKeyboardButton(
                    text="✏️ Переписать",
                    callback_data=PostActionCallback(post_id=post_id, action="rewrite").pack(),
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=PostActionCallback(post_id=post_id, action="delete").pack(),
                ),
            ]
        ]
    )
