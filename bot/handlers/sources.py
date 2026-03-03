"""Sources management handlers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy import select

from bot.keyboards.sources import SourceActionCallback, get_sources_keyboard
from bot.states import SourceStates
from models import Source
from core.database import async_session

router = Router(name="sources")


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_sources() -> list[dict]:
    """Return all sources as plain dicts (session-safe)."""
    async with async_session() as db:
        result = await db.execute(
            select(Source).order_by(Source.created_at.desc())
        )
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "url": r.url,
                "name": r.name,
                "is_active": r.is_active,
            }
            for r in rows
        ]


def _sources_text(sources: list[dict]) -> str:
    if not sources:
        return "🔗 <b>Источники</b>\n\nСписок источников пуст. Добавьте первый!"
    lines = [f"🔗 <b>Источники</b> ({len(sources)}):\n"]
    for s in sources:
        icon = "✅" if s["is_active"] else "❌"
        name = s["name"] or s["url"]
        lines.append(f"{icon} {name}")
    return "\n".join(lines)


async def _source_exists(url: str) -> bool:
    async with async_session() as db:
        result = await db.execute(select(Source).where(Source.url == url))
        row = result.scalar_one_or_none()
        return row is not None


# ── list sources ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "sources")
async def cb_sources(callback: CallbackQuery) -> None:
    sources_dicts = await _get_sources()

    # Build ORM-like objects for the keyboard (just need id + is_active + name + url)
    class _SourceProxy:
        def __init__(self, d: dict):
            self.id = d["id"]
            self.url = d["url"]
            self.name = d["name"]
            self.is_active = d["is_active"]

    proxies = [_SourceProxy(s) for s in sources_dicts]

    await callback.message.edit_text(
        text=_sources_text(sources_dicts),
        reply_markup=get_sources_keyboard(proxies),  # type: ignore[arg-type]
        parse_mode="HTML",
    )
    await callback.answer()


async def _refresh_sources(callback: CallbackQuery) -> None:
    """Re-render the sources list in the current message."""
    sources_dicts = await _get_sources()

    class _SourceProxy:
        def __init__(self, d: dict):
            self.id = d["id"]
            self.url = d["url"]
            self.name = d["name"]
            self.is_active = d["is_active"]

    proxies = [_SourceProxy(s) for s in sources_dicts]
    await callback.message.edit_text(
        text=_sources_text(sources_dicts),
        reply_markup=get_sources_keyboard(proxies),  # type: ignore[arg-type]
        parse_mode="HTML",
    )


# ── toggle / delete ───────────────────────────────────────────────────────────

@router.callback_query(SourceActionCallback.filter(F.action == "toggle"))
async def cb_source_toggle(callback: CallbackQuery, callback_data: SourceActionCallback) -> None:
    source_id = callback_data.source_id
    async with async_session() as db:
        try:
            result = await db.execute(select(Source).where(Source.id == source_id))
            source = result.scalar_one_or_none()
            if source:
                source.is_active = not source.is_active
                await db.commit()
                status = "активирован ✅" if source.is_active else "деактивирован ❌"
                logger.info(f"Source {source_id} {status}")
                await callback.answer(f"Источник {status}")
            else:
                await callback.answer("Источник не найден")
        except Exception:
            await db.rollback()
            raise

    await _refresh_sources(callback)


@router.callback_query(SourceActionCallback.filter(F.action == "delete"))
async def cb_source_delete(callback: CallbackQuery, callback_data: SourceActionCallback) -> None:
    source_id = callback_data.source_id
    async with async_session() as db:
        try:
            result = await db.execute(select(Source).where(Source.id == source_id))
            source = result.scalar_one_or_none()
            if source:
                db.delete(source)
                await db.commit()
                logger.info(f"Source {source_id} deleted")
                await callback.answer("Источник удалён 🗑")
            else:
                await callback.answer("Источник не найден")
        except Exception:
            await db.rollback()
            raise

    await _refresh_sources(callback)


# ── add source (FSM) ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "add_source")
async def cb_add_source(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SourceStates.waiting_url)
    await callback.message.answer(
        "🔗 <b>Добавление источника</b>\n\n"
        "Введите URL источника (например, https://example.com/blog):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SourceStates.waiting_url)
async def msg_source_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip()

    if not url.startswith(("http://", "https://")):
        await message.answer(
            "❌ Некорректный URL. Укажите адрес, начинающийся с http:// или https://"
        )
        return

    if await _source_exists(url):
        await message.answer(
            f"⚠️ Источник <code>{url}</code> уже существует в базе.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    await state.update_data(url=url)
    await state.set_state(SourceStates.waiting_name)
    await message.answer(
        "📛 Введите название источника (или отправьте <code>-</code> чтобы пропустить):",
        parse_mode="HTML",
    )


@router.message(SourceStates.waiting_name)
async def msg_source_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    url: str = data["url"]
    name_input = message.text.strip()
    name = None if name_input == "-" else name_input

    async with async_session() as db:
        try:
            source = Source(url=url, name=name, is_active=True)
            db.add(source)
            await db.commit()
            await db.refresh(source)
            source_id = source.id
        except Exception:
            await db.rollback()
            raise

    await state.clear()
    logger.info(f"Added source {source_id}: {name or url}")

    sources_dicts = await _get_sources()

    class _SourceProxy:
        def __init__(self, d: dict):
            self.id = d["id"]
            self.url = d["url"]
            self.name = d["name"]
            self.is_active = d["is_active"]

    proxies = [_SourceProxy(s) for s in sources_dicts]
    await message.answer(
        text=f"✅ Источник добавлен!\n\n" + _sources_text(sources_dicts),
        reply_markup=get_sources_keyboard(proxies),  # type: ignore[arg-type]
        parse_mode="HTML",
    )
