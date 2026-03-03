"""Queue (pending posts) handlers with approval flow."""

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, URLInputFile
from loguru import logger
from sqlalchemy import select

from bot.keyboards.approval import PostActionCallback, get_approval_keyboard
from bot.keyboards.main import get_main_keyboard
from models import Post
from core.database import async_session
from tasks.publish_task import publish_post

router = Router(name="queue")

PREVIEW_LENGTH = 300


# ── queue list ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "queue")
async def cb_queue(callback: CallbackQuery, bot: Bot) -> None:
    async with async_session() as db:
        result = await db.execute(
            select(Post)
            .where(Post.status == "pending")
            .order_by(Post.created_at.desc())
            .limit(5)
        )
        posts = result.scalars().all()
        posts_data = [
            {
                "id": p.id,
                "title": p.title,
                "text": p.text,
                "image_url": p.image_url,
                "article_id": p.article_id,
            }
            for p in posts
        ]

    if not posts_data:
        await callback.message.edit_text(
            "📥 <b>Очередь пуста</b>\n\nНет постов, ожидающих одобрения.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📥 <b>Очередь</b> — последние {len(posts_data)} постов:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()

    chat_id = callback.message.chat.id
    for post in posts_data:
        preview = (post["text"] or "")[:PREVIEW_LENGTH]
        if len(post["text"] or "") > PREVIEW_LENGTH:
            preview += "..."

        title_line = f"<b>{post['title']}</b>\n\n" if post["title"] else ""
        caption = f"{title_line}{preview}"

        try:
            if post["image_url"]:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=URLInputFile(post["image_url"]),
                    caption=caption,
                    reply_markup=get_approval_keyboard(post["id"]),
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    reply_markup=get_approval_keyboard(post["id"]),
                    parse_mode="HTML",
                )
        except Exception as exc:
            logger.error(f"Failed to send post {post['id']} preview: {exc}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Не удалось загрузить превью поста #{post['id']}\n\n{caption}",
                reply_markup=get_approval_keyboard(post["id"]),
                parse_mode="HTML",
            )


# ── approve ───────────────────────────────────────────────────────────────────

@router.callback_query(PostActionCallback.filter(F.action == "approve"))
async def cb_approve(callback: CallbackQuery, callback_data: PostActionCallback) -> None:
    post_id = callback_data.post_id
    async with async_session() as db:
        try:
            result = await db.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            if post is None:
                await callback.answer("Пост не найден")
                return
            post.status = "approved"
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    try:
        publish_post.delay(post_id)
        logger.info(f"Post {post_id} approved and queued for publishing")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("✅ Отправлено на публикацию!")
    except Exception as exc:
        logger.error(f"Failed to queue publish_post for {post_id}: {exc}")
        await callback.answer("❌ Ошибка при постановке в очередь публикации")


# ── rewrite ───────────────────────────────────────────────────────────────────

@router.callback_query(PostActionCallback.filter(F.action == "rewrite"))
async def cb_rewrite(callback: CallbackQuery, callback_data: PostActionCallback) -> None:
    post_id = callback_data.post_id
    article_id = None
    async with async_session() as db:
        try:
            result = await db.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            if post is None:
                await callback.answer("Пост не найден")
                return
            article_id = post.article_id
            post.status = "rejected"
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    if article_id:
        try:
            from tasks.parse_task import parse_and_generate  # noqa: PLC0415
            # Re-trigger full pipeline; in a real app you'd have a
            # dedicated rewrite_post task that targets a single article_id.
            parse_and_generate.delay()
            logger.info(f"Rewrite triggered for post {post_id} (article {article_id})")
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("✏️ Отправлен на переписку!")
        except Exception as exc:
            logger.error(f"Failed to trigger rewrite for post {post_id}: {exc}")
            await callback.answer("❌ Ошибка при запуске перегенерации")
    else:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("✏️ Пост отклонён (нет связанной статьи для перегенерации)")


# ── delete ────────────────────────────────────────────────────────────────────

@router.callback_query(PostActionCallback.filter(F.action == "delete"))
async def cb_delete(callback: CallbackQuery, callback_data: PostActionCallback) -> None:
    post_id = callback_data.post_id
    async with async_session() as db:
        try:
            result = await db.execute(select(Post).where(Post.id == post_id))
            post = result.scalar_one_or_none()
            if post:
                post.status = "rejected"
                await db.commit()
                logger.info(f"Post {post_id} rejected/deleted by user")
        except Exception:
            await db.rollback()
            raise

    await callback.message.delete()
    await callback.answer("🗑 Пост удалён")
