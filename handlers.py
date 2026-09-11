from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from datetime import datetime, timedelta
import re

from config import ADMIN_ID
from backup import send_backup
from database import (
    create_user, get_user, add_event, get_last_event, get_day_events,
    get_idea_by_age, answer_question, get_questions_by_category,
    get_answer_by_id, get_connection, update_user_consent,
    update_user_brief_time, update_user_zodiac, update_user_brief_enabled,
    delete_last_event,
)
from states import UserStates
from keyboards import (
    main_keyboard, consent_keyboard, sleep_keyboard, mood_keyboard,
    stats_period_keyboard, timezone_keyboard, categories_keyboard,
    questions_keyboard, CATEGORIES,
    brief_menu_keyboard, zodiac_keyboard, ZODIAC_SIGNS,
)
from utils import (
    get_child_age_days, recalc_schedule, generate_stats,
    now_in_user_tz, to_user_tz, get_user_tz
)
from ai_helper import generate_text

router = Router()

MAIN_BUTTONS = [
    "😴 Сон", "📊 Статистика",
    "💡 Идея дня", "📚 Полезное",
    "🌅 Брифинг", "❤️ Моё самочувствие",
    "🌍 Часовой пояс",
]


# ===== Вспомогательные функции =====
def format_birthday_display(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        return datetime.strptime(iso_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    except (ValueError, TypeError):
        return iso_str


# ===== Служебные команды =====
@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(
        f"🆔 Ваш Telegram ID: {message.from_user.id}\n\n"
        f"Скопируйте это число и добавьте его на Render как переменную окружения "
        f"ADMIN_ID, чтобы получать ежедневные бэкапы базы данных."
    )


@router.message(Command("backup"))
async def cmd_backup(message: Message):
    user_id = message.from_user.id
    if ADMIN_ID and user_id != ADMIN_ID:
        await message.answer("❌ Команда доступна только администратору.")
        return
    if ADMIN_ID == 0:
        await message.answer(
            f"⚠️ ADMIN_ID не настроен на сервере.\n\n"
            f"Ваш ID: {user_id}\n\n"
            f"Добавьте переменную окружения ADMIN_ID на Render, чтобы получать бэкапы."
        )
        return
    await message.answer("📦 Создаю бэкап...")
    await send_backup(message.bot, ADMIN_ID)


@router.message(Command("delete_me"))
async def cmd_delete_me(message: Message, state: FSMContext):
    user_id = message.from_user.id
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await message.answer(
        "🗑 Все ваши данные удалены из базы бота.\n\n"
        "Согласие отозвано. Если захотите снова воспользоваться ботом — "
        "просто отправьте /start.",
        reply_markup=None
    )
    await state.clear()


# ===== Вспомогательная функция: инструкция =====
async def send_welcome_instructions(message: Message):
    text = (
        "🎉 Отлично, всё настроено!\n\n"
        "📋 <b>Что можно настроить (по желанию):</b>\n\n"
        "1️⃣ <b>🌍 Часовой пояс</b>\n"
        "По умолчанию стоит Красноярск. Если ты в другом городе — "
        "нажми «🌍 Часовой пояс» и выбери свой, чтобы все отметки сна и брифинг "
        "приходили в правильное время.\n\n"
        "2️⃣ <b>🌅 Утренний брифинг</b>\n"
        "Каждое утро бот будет присылать тёплое персональное сообщение: "
        "приветствие, идею для занятия с малышом, пожелание и гороскоп.\n"
        "👉 Нажми кнопку «🌅 Брифинг» внизу → там можно:\n"
        "   • Включить/выключить\n"
        "   • Выбрать удобное время (например, 08:00)\n"
        "   • Указать свой знак зодиака\n\n"
        "💡 <b>Остальные кнопки:</b>\n"
        "😴 <b>Сон</b> — отметки: заснул / проснулся / 🌙 ночное пробуждение\n"
        "📊 <b>Статистика</b> — сны за день, 3 дня или неделю\n"
        "💡 <b>Идея дня</b> — случайная идея для занятия с малышом\n"
        "📚 <b>Полезное</b> — ответы на вопросы (сон, прикорм, здоровье…)\n"
        "❤️ <b>Самочувствие</b> — отмечай своё настроение\n\n"
        "Хорошего дня! 🌸"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())


# ===== /start =====
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)

    if user and user.get("consent_given"):
        await send_welcome_instructions(message)
        await state.clear()
    else:
        await message.answer(
            "👋 Привет! Я бот-помощник для мам.\n\n"
            "Прежде чем начать, мне нужно получить ваше согласие на обработку персональных данных. "
            "Это необходимо для корректной работы бота (например, чтобы сохранять дату рождения ребёнка).\n\n"
            "Пожалуйста, ознакомьтесь с политикой конфиденциальности и подтвердите согласие:",
            reply_markup=consent_keyboard()
        )
        await state.set_state(UserStates.waiting_consent)


@router.callback_query(F.data == "consent_agree")
async def process_consent_agree(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = get_user(user_id)

    if not user:
        create_user(user_id, "1970-01-01")

    update_user_consent(user_id, True)

    user = get_user(user_id)
    if not user or user["child_birthday"] == "1970-01-01":
        await callback.message.edit_text(
            "Отлично! Спасибо за согласие. ✅\n\n"
            "Теперь укажите дату рождения ребёнка в формате ДД-ММ-ГГГГ (например, 15-01-2024):"
        )
        await state.set_state(UserStates.waiting_birthday)
    else:
        await callback.message.edit_text("Спасибо! Согласие получено. ✅")
        await send_welcome_instructions(callback.message)
        await state.clear()

    await callback.answer()


@router.callback_query(F.data == "consent_decline")
async def process_consent_decline(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "❌ Вы отказались от обработки персональных данных.\n\n"
        "К сожалению, без этого я не смогу работать. Если передумаете, отправьте /start заново."
    )
    await callback.answer()
    await state.clear()


# ===== Дата рождения (формат ДД-ММ-ГГГГ) =====
@router.message(UserStates.waiting_birthday)
async def process_birthday(message: Message, state: FSMContext):
    text = message.text.strip()

    if not re.match(r'^\d{2}-\d{2}-\d{4}$', text):
        await message.answer("Пожалуйста, введи дату в формате ДД-ММ-ГГГГ (например, 15-01-2024)")
        return

    try:
        parsed = datetime.strptime(text, "%d-%m-%Y")
    except ValueError:
        await message.answer("Неверная дата. Попробуй ещё раз в формате ДД-ММ-ГГГГ")
        return

    iso_str = parsed.strftime("%Y-%m-%d")

    user_id = message.from_user.id
    user = get_user(user_id)

    if user:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET child_birthday = ? WHERE user_id = ?", (iso_str, user_id))
        conn.commit()
        conn.close()
    else:
        create_user(user_id, iso_str)
        update_user_consent(user_id, True)

    await send_welcome_instructions(message)
    await state.clear()


# ===== Сон =====
@router.message(F.text == "😴 Сон")
async def sleep_menu(message: Message, state: FSMContext):
    await state.clear()
    if not get_user(message.from_user.id):
        await message.answer("Сначала настрой бота через /start")
        return
    await message.answer(
        "Что отметить?\n\n"
        "😴 <b>Заснул</b> — начало сна\n"
        "👶 <b>Проснулся</b> — конец сна\n"
        "🌙 <b>Ночное пробуждение</b> — проснулся ночью и снова уснул",
        parse_mode="HTML",
        reply_markup=sleep_keyboard()
    )


@router.callback_query(F.data == "sleep_start_now")
async def cb_sleep_start_now(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    now = int(datetime.now().timestamp())
    add_event(user_id, "sleep_start", now)
    local = now_in_user_tz(user_id).strftime('%H:%M')
    await callback.message.edit_text(
        f"✅ Записал: <b>заснул в {local}</b>.\n\n"
        f"Когда проснётся — нажми «😴 Сон» → «👶 Проснулся».",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "sleep_end_now")
async def cb_sleep_end_now(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    now = int(datetime.now().timestamp())
    add_event(user_id, "sleep_end", now)
    local = now_in_user_tz(user_id).strftime('%H:%M')
    schedule_text = recalc_schedule(user_id, now)
    await callback.message.edit_text(
        f"✅ Записал: <b>проснулся в {local}</b>.\n\n{schedule_text}",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "sleep_start_15")
async def cb_sleep_start_15(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    ts = int((datetime.now() - timedelta(minutes=15)).timestamp())
    add_event(user_id, "sleep_start", ts)
    local = to_user_tz(user_id, ts).strftime('%H:%M')
    await callback.message.edit_text(
        f"✅ Записал: <b>заснул в {local}</b> (15 минут назад).\n\n"
        f"Когда проснётся — нажми «😴 Сон» → «👶 Проснулся».",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "sleep_end_15")
async def cb_sleep_end_15(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    ts = int((datetime.now() - timedelta(minutes=15)).timestamp())
    add_event(user_id, "sleep_end", ts)
    local = to_user_tz(user_id, ts).strftime('%H:%M')
    schedule_text = recalc_schedule(user_id, ts)
    await callback.message.edit_text(
        f"✅ Записал: <b>проснулся в {local}</b> (15 минут назад).\n\n{schedule_text}",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "sleep_start_30")
async def cb_sleep_start_30(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    ts = int((datetime.now() - timedelta(minutes=30)).timestamp())
    add_event(user_id, "sleep_start", ts)
    local = to_user_tz(user_id, ts).strftime('%H:%M')
    await callback.message.edit_text(
        f"✅ Записал: <b>заснул в {local}</b> (30 минут назад).\n\n"
        f"Когда проснётся — нажми «😴 Сон» → «👶 Проснулся».",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "sleep_end_30")
async def cb_sleep_end_30(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    ts = int((datetime.now() - timedelta(minutes=30)).timestamp())
    add_event(user_id, "sleep_end", ts)
    local = to_user_tz(user_id, ts).strftime('%H:%M')
    schedule_text = recalc_schedule(user_id, ts)
    await callback.message.edit_text(
        f"✅ Записал: <b>проснулся в {local}</b> (30 минут назад).\n\n{schedule_text}",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "night_wake")
async def cb_night_wake(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    now = int(datetime.now().timestamp())
    add_event(user_id, "night_wake", now)
    local = now_in_user_tz(user_id).strftime('%H:%M')

    from datetime import timedelta as td
    from database import get_events_since
    since = int((datetime.now() - td(hours=12)).timestamp())
    events = get_events_since(user_id, since)
    count = sum(1 for e in events if e["event_type"] == "night_wake")

    await callback.message.edit_text(
        f"🌙 Записал: <b>ночное пробуждение в {local}</b>.\n"
        f"Сегодня уже {count} пробуждени{'е' if count == 1 else 'я' if 2 <= count <= 4 else 'й'}.\n\n"
        f"Если хотите отметить ещё — снова нажмите «😴 Сон».",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "sleep_undo")
async def cb_sleep_undo(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    last = delete_last_event(user_id)
    if not last:
        await callback.message.edit_text("❌ Нечего отменять — нет последних записей.")
        await callback.answer()
        return

    type_ru = {
        "sleep_start": "засыпание",
        "sleep_end": "пробуждение",
        "night_wake": "ночное пробуждение",
        "mom_mood": "самочувствие",
    }.get(last["event_type"], last["event_type"])
    local = to_user_tz(user_id, last["timestamp"]).strftime('%H:%M')

    await callback.message.edit_text(
        f"↩️ Отменил последнее действие:\n"
        f"«{type_ru} в {local}» больше не учитывается."
    )
    await callback.answer()


@router.callback_query(F.data == "sleep_manual")
async def cb_sleep_manual(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    await callback.message.edit_text(
        "Введи время в формате ЧЧ:ММ (например, 14:30).\n\n"
        "Укажи, что это:\n"
        "• <b>'уснул 14:30'</b> — если это начало сна\n"
        "• <b>'проснулся 14:30'</b> — если это конец сна",
        parse_mode="HTML"
    )
    await state.set_state(UserStates.waiting_manual_time)
    await callback.answer()


@router.message(UserStates.waiting_manual_time, ~F.text.in_(MAIN_BUTTONS))
async def process_manual_time(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    match = re.match(r'(уснул|проснулся)\s+(\d{1,2}:\d{2})', text)
    if not match:
        await message.answer("Не понял. Напиши, например: 'уснул 14:30' или 'проснулся 10:15'")
        return
    event_type = "sleep_start" if match.group(1) == "уснул" else "sleep_end"
    time_str = match.group(2)
    user_id = message.from_user.id
    try:
        tz = get_user_tz(user_id)
        today = now_in_user_tz(user_id).date()
        h, m = map(int, time_str.split(':'))
        dt = datetime(today.year, today.month, today.day, h, m, tzinfo=tz)
        ts = int(dt.timestamp())
    except ValueError:
        await message.answer("Неверный формат времени. Используй ЧЧ:ММ")
        return
    add_event(user_id, event_type, ts)

    local_str = to_user_tz(user_id, ts).strftime('%H:%M')

    if event_type == "sleep_start":
        await message.answer(
            f"✅ Записал: <b>заснул в {local_str}</b>.\n\n"
            f"Когда проснётся — нажми «😴 Сон» → «👶 Проснулся».",
            parse_mode="HTML"
        )
    else:
        schedule_text = recalc_schedule(user_id, ts)
        await message.answer(
            f"✅ Записал: <b>проснулся в {local_str}</b>.\n\n{schedule_text}",
            parse_mode="HTML"
        )
    await state.clear()


# ===== Статистика =====
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
    days = {"today": 1, "3days": 3, "week": 7}.get(period, 1)
    stats_text = generate_stats(user_id, days)
    await callback.message.answer(stats_text)
    await callback.answer()


# ===== Идея дня =====
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
    idea = get_idea_by_age(age_days)
    await message.answer(f"💡 Идея дня:\n\n{idea}")


# ===== Полезное =====
@router.message(F.text == "📚 Полезное")
async def ask_question(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(UserStates.waiting_question)
    await message.answer(
        "📚 Полезные материалы для мамы и малыша.\n\n"
        "Выбери категорию или напиши свой вопрос текстом 👇",
        reply_markup=categories_keyboard()
    )


@router.callback_query(F.data.startswith("cat_"))
async def category_callback(callback: types.CallbackQuery):
    data = callback.data.replace("cat_", "", 1)

    if data == "back":
        await callback.message.edit_text(
            "📚 Полезные материалы для мамы и малыша.\n\n"
            "Выбери категорию или напиши свой вопрос текстом 👇",
            reply_markup=categories_keyboard()
        )
        await callback.answer()
        return

    category = data
    questions = get_questions_by_category(category)
    if not questions:
        await callback.answer("В этой категории пока нет вопросов.", show_alert=True)
        return

    label = CATEGORIES.get(category, category)
    await callback.message.edit_text(
        f"{label} — выбери вопрос:",
        reply_markup=questions_keyboard(questions)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("q_"))
async def question_callback(callback: types.CallbackQuery):
    try:
        q_id = int(callback.data.replace("q_", "", 1))
    except ValueError:
        await callback.answer("Ошибка.", show_alert=True)
        return
    answer = get_answer_by_id(q_id)
    await callback.message.answer(f"💬 {answer}")
    await callback.answer()


@router.message(UserStates.waiting_question, ~F.text.in_(MAIN_BUTTONS))
async def process_question(message: Message, state: FSMContext):
    user_question = message.text
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user or not user.get("child_birthday"):
        await message.answer("Пожалуйста, сначала укажите дату рождения ребёнка (/start).")
        await state.clear()
        return

    age_days = get_child_age_days(user_id)
    age_months = age_days // 30 if age_days is not None else "неизвестно"

    prompt = (
        f"Ты — дружелюбный и заботливый помощник для мам. "
        f"Твоя задача — давать полезные и безопасные советы по уходу за ребёнком. "
        f"Возраст ребёнка пользователя: примерно {age_months} месяцев. "
        f"Отвечай кратко, по делу и с эмпатией. "
        f"Если вопрос касается здоровья, всегда добавляй, что это не заменяет консультацию врача. "
        f"Вот вопрос мамы: '{user_question}'"
    )

    ai_answer = generate_text(prompt)
    if ai_answer:
        await message.answer(f"🤖 {ai_answer}")
    else:
        await message.answer(answer_question(user_question))

    await state.clear()


# ===== Самочувствие мамы =====
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
    await callback.message.answer(f"Спасибо, отметил: {mood}")
    await callback.answer()
    if "плохо" in mood:
        await callback.message.answer("Помни: отдых мамы важен. Постарайся найти 15 минут для себя, пока малыш спит.")


# ===== Часовой пояс =====
@router.message(F.text == "🌍 Часовой пояс")
async def timezone_menu(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала настрой бота через /start")
        return
    await message.answer(
        f"🌍 <b>Текущий часовой пояс:</b> {user['timezone']}\n\n"
        f"⚠️ Если он не совпадает с твоим городом — все отметки сна и брифинг "
        f"будут приходить в неправильное время. Выбери свой 👇",
        parse_mode="HTML",
        reply_markup=timezone_keyboard()
    )


@router.callback_query(F.data.startswith("tz_"))
async def timezone_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data.replace("tz_", "", 1)

    if data == "check":
        user = get_user(user_id)
        if user:
            await callback.message.edit_text(
                f"🌍 Текущий часовой пояс: {user['timezone']}\n\n"
                f"Если всё верно — можешь пользоваться ботом. Если нет — выбери свой:",
                reply_markup=timezone_keyboard()
            )
        await callback.answer()
        return

    tz = data
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (tz, user_id))
    conn.commit()
    conn.close()

    tz_names = {
        "Asia/Krasnoyarsk": "Красноярск (UTC+7)",
        "Europe/Moscow": "Москва (UTC+3)",
        "Asia/Novosibirsk": "Новосибирск (UTC+7)",
        "Asia/Irkutsk": "Иркутск (UTC+8)",
        "Asia/Vladivostok": "Владивосток (UTC+10)",
        "Europe/Kaliningrad": "Калининград (UTC+2)",
        "Asia/Yekaterinburg": "Екатеринбург (UTC+5)",
    }
    label = tz_names.get(tz, tz)

    now_local = now_in_user_tz(user_id).strftime('%H:%M')

    await callback.message.edit_text(
        f"✅ Часовой пояс изменён на: <b>{label}</b>\n\n"
        f"Сейчас у тебя: <b>{now_local}</b>\n"
        f"Если это совпадает с часами на телефоне — всё верно. 🌸",
        parse_mode="HTML"
    )
    await callback.answer()


# ===== БРИФИНГ =====
@router.message(F.text == "🌅 Брифинг")
async def brief_menu(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала настрой бота через /start")
        return

    zodiac_label = ""
    if user["zodiac"]:
        zodiac_label = ZODIAC_SIGNS.get(user["zodiac"], user["zodiac"])

    await message.answer(
        f"🌅 Утренний брифинг\n\n"
        f"Статус: {'включён ✅' if user['brief_enabled'] else 'выключен 🔕'}\n"
        f"Время: {user['morning_brief_time']}\n"
        f"Знак зодиака: {zodiac_label or 'не указан'}\n\n"
        f"Каждое утро бот будет присылать тёплое персональное сообщение: "
        f"приветствие, идею дня, пожелание и гороскоп.",
        reply_markup=brief_menu_keyboard(
            user["brief_enabled"],
            user["morning_brief_time"],
            zodiac_label or ""
        )
    )


@router.callback_query(F.data == "brief_toggle")
async def brief_toggle(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return
    new_state = not user["brief_enabled"]
    update_user_brief_enabled(user_id, new_state)
    await callback.message.edit_text(
        f"{'✅ Брифинг включён' if new_state else '🔕 Брифинг выключен'}.\n\n"
        f"Время: {user['morning_brief_time']}",
        reply_markup=brief_menu_keyboard(new_state, user["morning_brief_time"], ZODIAC_SIGNS.get(user["zodiac"], ""))
    )
    await callback.answer()


@router.callback_query(F.data == "brief_change_time")
async def brief_change_time(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⏰ Введи новое время брифинга в формате ЧЧ:ММ (например, 07:30)."
    )
    await state.set_state(UserStates.waiting_brief_time)
    await callback.answer()


@router.message(UserStates.waiting_brief_time, ~F.text.in_(MAIN_BUTTONS))
async def process_brief_time(message: Message, state: FSMContext):
    text = message.text.strip()
    if not re.match(r'^\d{2}:\d{2}$', text):
        await message.answer("Неверный формат. Напиши, например: 07:30")
        return
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await message.answer("Неверное время. Попробуй снова.")
        return
    user_id = message.from_user.id
    update_user_brief_time(user_id, text)
    await message.answer(f"✅ Время брифинга изменено на {text}")
    await state.clear()


@router.callback_query(F.data == "brief_change_zodiac")
async def brief_change_zodiac(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "♈ Выбери свой знак зодиака:",
        reply_markup=zodiac_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("zod_"))
async def zodiac_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    key = callback.data.replace("zod_", "", 1)
    update_user_zodiac(user_id, key)
    label = ZODIAC_SIGNS.get(key, key)
    user = get_user(user_id)
    await callback.message.edit_text(
        f"✅ Знак зодиака сохранён: {label}",
        reply_markup=brief_menu_keyboard(
            user["brief_enabled"], user["morning_brief_time"], label
        )
    )
    await callback.answer()


@router.callback_query(F.data == "brief_back")
async def brief_back(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return
    zodiac_label = ZODIAC_SIGNS.get(user["zodiac"], "") if user["zodiac"] else ""
    await callback.message.edit_text(
        f"🌅 Утренний брифинг\n\n"
        f"Статус: {'включён ✅' if user['brief_enabled'] else 'выключен 🔕'}\n"
        f"Время: {user['morning_brief_time']}\n"
        f"Знак зодиака: {zodiac_label or 'не указан'}",
        reply_markup=brief_menu_keyboard(user["brief_enabled"], user["morning_brief_time"], zodiac_label)
    )
    await callback.answer()