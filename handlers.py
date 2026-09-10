from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import ReplyKeyboardRemove, Message
from datetime import datetime, timedelta
import re

from database import create_user, get_user, add_event, get_last_event, get_day_events, get_idea_by_age, get_ideas_by_age, answer_question, update_user_brief_time
from states import UserStates
from keyboards import main_keyboard, mood_keyboard, stats_period_keyboard
from utils import get_child_age_days, recalc_schedule, generate_stats

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    if user:
        await message.answer(
            f"С возвращением! Ваш бот готов.\n"
            f"Дата рождения ребёнка: {user['child_birthday']}\n"
            f"Время утреннего брифинга: {user['morning_brief_time']}",
            reply_markup=main_keyboard()
        )
        await state.clear()
    else:
        await message.answer(
            "Привет! Давай настроим бота.\n"
            "Укажи дату рождения ребёнка в формате ГГГГ-ММ-ДД (например, 2024-01-01):"
        )
        await state.set_state(UserStates.waiting_birthday)

@router.message(UserStates.waiting_birthday)
async def process_birthday(message: Message, state: FSMContext):
    text = message.text.strip()
    if not re.match(r'\d{4}-\d{2}-\d{2}', text):
        await message.answer("Пожалуйста, введите дату в формате ГГГГ-ММ-ДД")
        return
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        await message.answer("Неверная дата. Попробуйте ещё раз.")
        return
    user_id = message.from_user.id
    create_user(user_id, text)
    await message.answer(
        f"Отлично! Данные сохранены.\n"
        f"Теперь ты можешь пользоваться ботом. Нажми на кнопку, чтобы отметить сон.",
        reply_markup=main_keyboard()
    )
    await state.clear()

@router.message(F.text == "😴 Уснул сейчас")
async def sleep_start_now(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("Сначала настрой бота через /start")
        return
    now = int(datetime.now().timestamp())
    add_event(user_id, "sleep_start", now)
    await message.answer(f"✅ Отметил: уснул в {datetime.now().strftime('%H:%M')}")

@router.message(F.text == "👶 Проснулся сейчас")
async def sleep_end_now(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("Сначала настрой бота через /start")
        return
    now = int(datetime.now().timestamp())
    add_event(user_id, "sleep_end", now)
    schedule_text = recalc_schedule(user_id, now)
    await message.answer(f"✅ Отметил: проснулся в {datetime.now().strftime('%H:%M')}\n\n{schedule_text}")

@router.message(F.text == "⏰ Уснул 15 мин назад")
async def sleep_start_15(message: Message):
    user_id = message.from_user.id
    if not get_user(user_id):
        await message.answer("Сначала настрой бота через /start")
        return
    ts = int((datetime.now() - timedelta(minutes=15)).timestamp())
    add_event(user_id, "sleep_start", ts)
    await message.answer(f"✅ Отметил: уснул в {datetime.fromtimestamp(ts).strftime('%H:%M')}")

@router.message(F.text == "⏰ Проснулся 15 мин назад")
async def sleep_end_15(message: Message):
    user_id = message.from_user.id
    if not get_user(user_id):
        await message.answer("Сначала настрой бота через /start")
        return
    ts = int((datetime.now() - timedelta(minutes=15)).timestamp())
    add_event(user_id, "sleep_end", ts)
    schedule_text = recalc_schedule(user_id, ts)
    await message.answer(f"✅ Отметил: проснулся в {datetime.fromtimestamp(ts).strftime('%H:%M')}\n\n{schedule_text}")

@router.message(F.text == "⏰ Уснул 30 мин назад")
async def sleep_start_30(message: Message):
    user_id = message.from_user.id
    if not get_user(user_id):
        await message.answer("Сначала настрой бота через /start")
        return
    ts = int((datetime.now() - timedelta(minutes=30)).timestamp())
    add_event(user_id, "sleep_start", ts)
    await message.answer(f"✅ Отметил: уснул в {datetime.fromtimestamp(ts).strftime('%H:%M')}")

@router.message(F.text == "⏰ Проснулся 30 мин назад")
async def sleep_end_30(message: Message):
    user_id = message.from_user.id
    if not get_user(user_id):
        await message.answer("Сначала настрой бота через /start")
        return
    ts = int((datetime.now() - timedelta(minutes=30)).timestamp())
    add_event(user_id, "sleep_end", ts)
    schedule_text = recalc_schedule(user_id, ts)
    await message.answer(f"✅ Отметил: проснулся в {datetime.fromtimestamp(ts).strftime('%H:%M')}\n\n{schedule_text}")

@router.message(F.text == "⌨️ Ввести время вручную")
async def manual_time(message: Message, state: FSMContext):
    await message.answer("Введите время в формате ЧЧ:ММ (например, 14:30).\n"
                         "Укажите, что это: 'уснул' или 'проснулся' — например, 'уснул 14:30'")
    await state.set_state(UserStates.waiting_manual_time)

@router.message(UserStates.waiting_manual_time)
async def process_manual_time(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    match = re.match(r'(уснул|проснулся)\s+(\d{1,2}:\d{2})', text)
    if not match:
        await message.answer("Не понял. Напиши, например: 'уснул 14:30' или 'проснулся 10:15'")
        return
    event_type = "sleep_start" if match.group(1) == "уснул" else "sleep_end"
    time_str = match.group(2)
    try:
        now = datetime.now()
        dt = datetime.strptime(f"{now.date().isoformat()} {time_str}", "%Y-%m-%d %H:%M")
        ts = int(dt.timestamp())
    except ValueError:
        await message.answer("Неверный формат времени. Используй ЧЧ:ММ")
        return
    user_id = message.from_user.id
    add_event(user_id, event_type, ts)
    await message.answer(f"✅ Отметил: {event_type} в {time_str}")
    if event_type == "sleep_end":
        schedule_text = recalc_schedule(user_id, ts)
        await message.answer(schedule_text)
    await state.clear()

@router.message(F.text == "📊 Статистика")
async def stats_request(message: Message):
    await message.answer("Выбери период:", reply_markup=stats_period_keyboard())

@router.callback_query(F.data.startswith("stats_"))
async def stats_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    period = callback.data.split("_")[1]
    if period == "today":
        days = 1
    elif period == "3days":
        days = 3
    elif period == "week":
        days = 7
    else:
        days = 1
    stats_text = generate_stats(user_id, days)
    await callback.message.answer(stats_text)
    await callback.answer()

@router.message(F.text == "💡 Идея дня")
async def idea_of_day(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("Сначала настрой бота через /start")
        return
    age_days = get_child_age_days(user_id)
    if age_days is None:
        await message.answer("Не могу определить возраст. Проверь дату рождения.")
        return
    ideas = get_ideas_by_age(age_days, limit=5)
    if not ideas:
        await message.answer("Для этого возраста пока нет идей. Но вот совет: проводите время на свежем воздухе!")
        return
    response = "💡 Вот несколько идей для бодрствования:\n\n"
    for i, idea in enumerate(ideas, 1):
        response += f"{i}. {idea}\n"
    await message.answer(response)

@router.message(F.text == "❓ Задать вопрос")
async def ask_question(message: Message, state: FSMContext):
    await message.answer("Напиши свой вопрос одним сообщением (например, про прикорм или сон).")
    await state.set_state(UserStates.waiting_question)

@router.message(UserStates.waiting_question)
async def process_question(message: Message, state: FSMContext):
    question = message.text
    answer = answer_question(question)
    await message.answer(answer)
    await state.clear()

@router.message(F.text == "❤️ Моё самочувствие")
async def mom_mood(message: Message):
    await message.answer("Как ты себя чувствуешь?", reply_markup=mood_keyboard())

@router.callback_query(F.data.startswith("mood_"))
async def mood_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    mood_map = {"good": "🟢 хорошо", "medium": "🟡 средне", "bad": "🔴 плохо"}
    mood = mood_map.get(callback.data.split("_")[1], "неизвестно")
    ts = int(datetime.now().timestamp())
    add_event(user_id, "mom_mood", ts, note=mood)
    await callback.message.answer(f"Спасибо, отметила: {mood}")
    await callback.answer()
    if "плохо" in mood:
        await callback.message.answer("Помни, что отдых мамы важен. Постарайся найти 15 минут для себя, пока малыш спит.")

@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("Сначала настрой бота через /start")
        return
    current_brief = user['morning_brief_time']
    await message.answer(
        f"Текущее время утреннего брифинга: {current_brief}\n"
        f"Чтобы изменить, отправь новое время в формате ЧЧ:ММ (например, 09:00)"
    )

@router.message(F.text.regexp(r'^\d{2}:\d{2}$'))
async def change_brief_time(message: Message):
    user_id = message.from_user.id
    if not get_user(user_id):
        await message.answer("Сначала настрой бота через /start")
        return
    new_time = message.text
    try:
        datetime.strptime(new_time, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Используй ЧЧ:ММ")
        return
    update_user_brief_time(user_id, new_time)
    await message.answer(f"Время брифинга изменено на {new_time}")