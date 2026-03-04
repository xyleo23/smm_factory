"""Shared utilities for bot handlers."""

from sqlalchemy import select

from core.database import async_session
from models.settings import UserSettings


async def get_or_create_settings(user_id: int) -> dict:
    """
    Fetch UserSettings for a given user_id, creating defaults if not found.
    Returns a plain dict so it's safe to use after the session closes.
    """
    async with async_session() as db:
        try:
            result = await db.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalars().first()

            if not settings:
                settings = UserSettings(user_id=user_id)
                db.add(settings)
                await db.commit()
                await db.refresh(settings)
            else:
                db.expire_all()
                await db.refresh(settings)

            return {
                "id": settings.id,
                "serp_keywords": [k.strip() for k in settings.serp_keywords.split(",") if k.strip()] if settings.serp_keywords else [],
                "internal_links": [l.strip() for l in settings.internal_links.split(",") if l.strip()] if settings.internal_links else [],
                "utm_template": settings.utm_template,
                "tone": settings.tone,
                "selected_llm": settings.selected_llm,
                "tg_channels": [c.strip() for c in settings.tg_channels.split(",") if c.strip()] if settings.tg_channels else [],
                "is_auto_publish": settings.is_auto_publish,
            }
        except Exception:
            await db.rollback()
            raise


def settings_text(s: dict) -> str:
    """Format settings dict into a human-readable message."""
    auto = "✅ Включена" if s["is_auto_publish"] else "❌ Выключена"
    channels = ", ".join(s["tg_channels"]) if s["tg_channels"] else "не заданы"
    serp = ", ".join(s["serp_keywords"]) if s["serp_keywords"] else "не заданы"
    links = ", ".join(s["internal_links"]) if s["internal_links"] else "не заданы"
    utm = s["utm_template"] or "не задан"
    return (
        f"⚙️ <b>Текущие настройки</b>\n\n"
        f"🎨 Тон: <code>{s['tone']}</code>\n"
        f"🤖 LLM: <code>{s['selected_llm']}</code>\n"
        f"🔄 Автопубликация: {auto}\n"
        f"📡 TG-каналы: {channels}\n"
        f"🔍 SERP-ключи: {serp}\n"
        f"🔗 Внутренние ссылки: {links}\n"
        f"📝 UTM-шаблон: <code>{utm}</code>"
    )
