"""Statistics handler — last 7 days summary."""

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import func, select

from bot.keyboards.main import get_main_keyboard
from models import Article, Post, Source
from core.database import async_session

router = Router(name="stats")


@router.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery) -> None:
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    async with async_session() as db:
        # Articles parsed in the last 7 days
        r1 = await db.execute(
            select(func.count()).select_from(Article).where(
                Article.parsed_at >= seven_days_ago
            )
        )
        articles_count: int = r1.scalar() or 0

        # Posts generated in the last 7 days
        r2 = await db.execute(
            select(func.count()).select_from(Post).where(
                Post.created_at >= seven_days_ago
            )
        )
        posts_count: int = r2.scalar() or 0

        # Published posts
        r3 = await db.execute(
            select(func.count()).select_from(Post).where(
                Post.created_at >= seven_days_ago,
                Post.status == "published",
            )
        )
        published_count: int = r3.scalar() or 0

        # Rejected posts
        r4 = await db.execute(
            select(func.count()).select_from(Post).where(
                Post.created_at >= seven_days_ago,
                Post.status == "rejected",
            )
        )
        rejected_count: int = r4.scalar() or 0

        # Currently pending
        r5 = await db.execute(
            select(func.count()).select_from(Post).where(Post.status == "pending")
        )
        pending_count: int = r5.scalar() or 0

        # Top-3 sources by article count over last 7 days
        r6 = await db.execute(
            select(Source.name, Source.url, func.count(Article.id).label("cnt"))
            .join(Article, Source.id == Article.source_id)
            .where(Article.parsed_at >= seven_days_ago)
            .group_by(Source.id, Source.name, Source.url)
            .order_by(func.count(Article.id).desc())
            .limit(3)
        )
        top_sources = r6.all()

    if top_sources:
        top_lines = "\n".join(
            f"  {i + 1}. {name or url}: {cnt} стат."
            for i, (name, url, cnt) in enumerate(top_sources)
        )
    else:
        top_lines = "  Нет данных"

    text = (
        "📊 <b>Статистика за 7 дней:</b>\n\n"
        f"• Спарсено статей: <b>{articles_count}</b>\n"
        f"• Сгенерировано постов: <b>{posts_count}</b>\n"
        f"• Опубликовано: <b>{published_count}</b>\n"
        f"• Отклонено: <b>{rejected_count}</b>\n"
        f"• Ожидают одобрения: <b>{pending_count}</b>\n\n"
        f"🏆 <b>Топ-3 источника:</b>\n{top_lines}"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
