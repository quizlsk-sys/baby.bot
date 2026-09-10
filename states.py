from aiogram.fsm.state import StatesGroup, State


class UserStates(StatesGroup):
    waiting_consent = State()
    waiting_birthday = State()
    waiting_manual_time = State()
    waiting_question = State()