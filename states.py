from aiogram.fsm.state import StatesGroup, State


class UserStates(StatesGroup):
    waiting_consent = State()
    waiting_birthday = State()
    waiting_child_name = State()
    waiting_child_name_change = State()
    waiting_manual_time = State()
    waiting_question = State()
    waiting_brief_time = State()