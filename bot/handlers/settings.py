"""Settings handlers with full FSM for all configurable fields."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy import select

from bot.keyboards.main import get_main_keyboard
from bot.keyboards.settings import get_back_keyboard, get_settings_keyboard
from bot.states import SettingsStates
from bot.utils import get_or_create_settings, settings_text
from models import UserSettings
from core.database import async_session

router = Router(name="settings")

CANCEL_TEXT = "Отправьте /start для возврата в главное меню."


# ── helpers ──────────────────────────────────────────────────────────────────

async def _load_settings_model(user_id: int) -> UserSettings:
    """Return the ORM object (still attached to a fresh session snapshot)."""
    async with async_session() as db:
        try:
            result = await db.execute(
                select(UserSettings).where(UserSettings.id == user_id)
            )
            s = result.scalars().first()
            if s is None:
                s = UserSettings()
                db.add(s)
                await db.commit()
                await db.refresh(s)
            db.expunge(s)
            return s
        except Exception:
            await db.rollback()
            raise


async def _update_settings(user_id: int, **kwargs) -> None:
    """Apply keyword-argument updates to the user's settings row."""
    async with async_session() as db:
        try:
            result = await db.execute(
                select(UserSettings).where(UserSettings.id == user_id)
            )
            s = result.scalars().first()
            if s is None:
                s = UserSettings(**kwargs)
                db.add(s)
            else:
                for key, value in kwargs.items():
                    setattr(s, key, value)
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def _refresh_settings_message(callback: CallbackQuery, user_id: int) -> None:
    """Edit the current message to show updated settings + keyboard."""
    settings_dict = await get_or_create_settings(user_id)
    settings_obj = await _load_settings_model(user_id)
    await callback.message.edit_text(
        text=settings_text(settings_dict),
        reply_markup=get_settings_keyboard(settings_obj),
        parse_mode="HTML",
    )


# ── open settings panel ───────────────────────────────────────────────────────

@router.callback_query(F.data == "settings")
async def cb_open_settings(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    settings_dict = await get_or_create_settings(user_id)
    settings_obj = await _load_settings_model(user_id)

    await callback.message.edit_text(
        text=settings_text(settings_dict),
        reply_markup=get_settings_keyboard(settings_obj),
        parse_mode="HTML",
    )
    await callback.answer()


# ── tone ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("set_tone:"))
async def cb_set_tone(callback: CallbackQuery) -> None:
    tone = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    await _update_settings(user_id, tone=tone)
    await _refresh_settings_message(callback, user_id)
    await callback.answer(f"Тон изменён: {tone}")


# ── LLM ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("set_llm:"))
async def cb_set_llm(callback: CallbackQuery) -> None:
    llm = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    await _update_settings(user_id, selected_llm=llm)
    await _refresh_settings_message(callback, user_id)
    await callback.answer(f"LLM изменена: {llm}")


# ── auto-publish toggle ────────────────────────────────────────────────────────

@router.callback_query(F.data == "toggle_autopublish")
async def cb_toggle_autopublish(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    settings_dict = await get_or_create_settings(user_id)
    new_value = not settings_dict["is_auto_publish"]
    await _update_settings(user_id, is_auto_publish=new_value)
    await _refresh_settings_message(callback, user_id)
    status = "включена ✅" if new_value else "выключена ❌"
    await callback.answer(f"Автопубликация {status}")


# ── SERP keys ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "set_serp_keys")
async def cb_ask_serp_keys(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.waiting_serp_keys)
    await state.update_data(settings_message_id=callback.message.message_id)
    await callback.message.answer(
        "🔍 <b>Введите SERP-ключи</b> через запятую:\n\n"
        "<i>Пример: SMM агентство, продвижение в соцсетях, контент-маркетинг</i>\n\n"
        f"{CANCEL_TEXT}",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("settings"),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_serp_keys)
async def msg_serp_keys(message: Message, state: FSMContext) -> None:
    keywords = [k.strip() for k in message.text.split(",") if k.strip()]
    user_id = message.from_user.id
    await _update_settings(user_id, serp_keywords=keywords)
    await state.clear()
    logger.info(f"User {user_id} set SERP keywords: {keywords}")

    settings_dict = await get_or_create_settings(user_id)
    settings_obj = await _load_settings_model(user_id)
    await message.answer(
        text=f"✅ Сохранено {len(keywords)} ключей.\n\n" + settings_text(settings_dict),
        reply_markup=get_settings_keyboard(settings_obj),
        parse_mode="HTML",
    )


# ── UTM template ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "set_utm")
async def cb_ask_utm(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.waiting_utm)
    await callback.message.answer(
        "📝 <b>Введите UTM-шаблон</b> строкой:\n\n"
        "<i>Пример: ?utm_source=tg&amp;utm_medium=post&amp;utm_campaign=smm</i>\n\n"
        f"{CANCEL_TEXT}",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("settings"),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_utm)
async def msg_utm(message: Message, state: FSMContext) -> None:
    utm = message.text.strip()
    user_id = message.from_user.id
    await _update_settings(user_id, utm_template=utm)
    await state.clear()
    logger.info(f"User {user_id} set UTM template: {utm}")

    settings_dict = await get_or_create_settings(user_id)
    settings_obj = await _load_settings_model(user_id)
    await message.answer(
        text=f"✅ UTM-шаблон сохранён.\n\n" + settings_text(settings_dict),
        reply_markup=get_settings_keyboard(settings_obj),
        parse_mode="HTML",
    )


# ── internal links ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "set_links")
async def cb_ask_links(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.waiting_links)
    await callback.message.answer(
        "🔗 <b>Введите внутренние ссылки</b> через запятую:\n\n"
        "<i>Пример: https://example.com/page1, https://example.com/page2</i>\n\n"
        f"{CANCEL_TEXT}",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("settings"),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_links)
async def msg_links(message: Message, state: FSMContext) -> None:
    links = [lnk.strip() for lnk in message.text.split(",") if lnk.strip()]
    user_id = message.from_user.id
    await _update_settings(user_id, internal_links=links)
    await state.clear()
    logger.info(f"User {user_id} set internal links: {links}")

    settings_dict = await get_or_create_settings(user_id)
    settings_obj = await _load_settings_model(user_id)
    await message.answer(
        text=f"✅ Сохранено {len(links)} ссылок.\n\n" + settings_text(settings_dict),
        reply_markup=get_settings_keyboard(settings_obj),
        parse_mode="HTML",
    )


# ── TG channels ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "set_channels")
async def cb_ask_channels(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsStates.waiting_channels)
    await callback.message.answer(
        "📡 <b>Введите TG-каналы</b> через запятую (@username или числовой id):\n\n"
        "<i>Пример: @mychannel, -100123456789</i>\n\n"
        f"{CANCEL_TEXT}",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("settings"),
    )
    await callback.answer()


@router.message(SettingsStates.waiting_channels)
async def msg_channels(message: Message, state: FSMContext) -> None:
    channels = [ch.strip() for ch in message.text.split(",") if ch.strip()]
    user_id = message.from_user.id
    await _update_settings(user_id, tg_channels=channels)
    await state.clear()
    logger.info(f"User {user_id} set TG channels: {channels}")

    settings_dict = await get_or_create_settings(user_id)
    settings_obj = await _load_settings_model(user_id)
    await message.answer(
        text=f"✅ Сохранено {len(channels)} каналов.\n\n" + settings_text(settings_dict),
        reply_markup=get_settings_keyboard(settings_obj),
        parse_mode="HTML",
    )
