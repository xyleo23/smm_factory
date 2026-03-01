"""FSM states for the Telegram bot."""

from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    waiting_serp_keys = State()
    waiting_utm = State()
    waiting_links = State()
    waiting_channels = State()


class SourceStates(StatesGroup):
    waiting_url = State()
    waiting_name = State()
