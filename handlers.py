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
    delete_last_event, delete_sleep, update_user_child_name,
    get_last_sleep_start,
)
from states import UserStates
from keyboards import (
    main_keyboard, consent_keyboard, name_skip_keyboard,
    sleep_main_keyboard, sleep_day_keyboard, sleep_night_keyboard,
    sleep_list_keyboard, mood_keyboard, stats_period_keyboard,
    timezone_keyboard, categories_keyboard, questions_keyboard, CATEGORIES,
    brief_menu_keyboard, zodiac_keyboard, ZODIAC_SIGNS,
)
from utils import (
    get_child_age_days, recalc_schedule, generate_stats,
    now_in_user_tz, to_user_tz, get_user_tz,
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
def _child_name(user) -> str:
    if user and user.get("child_name"):
        return user["child_name"]
    return "Малыш"


def _format_hm(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    if h and m:
        return f"{h} ч {m} мин"
    if h:
        return f"{h} ч"
    return f"{m} мин"


def _collect_sleeps(user_id: int):
    today = now_in_user_tz(user_id).date()
    events = get_day_events(user_id, today)
    events = [e for e in events if e["event_type"] in ("sleep_start", "sleep_end")]
    events.sort(key=lambda e: e["timestamp"])

    sleeps = []
    current = None
    for e in events:
        if e["event_type"] == "sleep_start":
            if current is not None:
                sleeps.append(current)
            current = {"start_id": e["id"], "start": e["timestamp"], "end": None, "end_id": None}
        elif e["event_type"] == "sleep_end":
            if current is not None:
                current["end"] = e["timestamp"]
                current["end_id"] = e["id"]
                sleeps.append(current)
                current = None
            else:
                sleeps.append({"start_id": None, "start": None, "end": e["timestamp"], "end_id": e["id"]})
    if current is not None:
        sleeps.append(current)
    return sleeps


def _is_night(start_ts, tz):
    if start_ts is None:
        return False
    h = datetime.fromtimestamp(start_ts, tz).hour
    return h >= 20 or h < 5


def _format_sleeps_list(user_id: int, sleeps):
    tz = get_user_tz(user_id)
    if not sleeps:
        return "📋 Снов за сегодня пока нет."

    lines = ["📋 <b>Сны за сегодня:</b>\n"]
    for i, s in enumerate(sleeps, 1):
        st = s.get("start")
        en = s.get("end")
        night = _is_night(st, tz)

        if st and en:
            start_str = datetime.fromtimestamp(st, tz).strftime("%H:%M")
            end_str = datetime.fromtimestamp(en, tz).strftime("%H:%M")
            dur = (en - st) // 60
            h, m = dur // 60, dur % 60
            dur_str = f"{h} ч {m} мин" if h else f"{m} мин"
            kind = "🌙 ночной" if night else "☀️ дневной"
            lines.append(f"{i}. {kind}: {start_str} – {end_str} ({dur_str})")
        elif st and not en:
            start_str = datetime.fromtimestamp(st, tz).strftime("%H:%M")
            kind = "🌙 ночной" if night else "☀️ дневной"
            lines.append(f"{i}. {kind}: заснул в {start_str} (ещё спит)")
        elif en and not st:
            end_str = datetime.fromtimestamp(en, tz).strftime("%H:%M")
            lines.append(f"{i}. Проснулся в {end_str}")
    return "\n".join(lines)


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


# ===== Инструкция при старте =====
async def send_welcome_instructions(message: Message, user=None):
    name = _child_name(user) if user else "Малыш"
    text = (
        f"🎉 Отлично, всё настроено!\n\n"
        f"📋 <b>Что можно настроить:</b>\n\n"
        f"1️⃣ <b>🌍 Часовой пояс</b>\n"
        f"Проверь, что стоит твой город — чтобы все отметки сна и брифинг "
        f"приходили в правильное время.\n\n"
        f"2️⃣ <b>🌅 Утренний брифинг</b>\n"
        f"Каждое утро бот присылает персональное сообщение: "
        f"приветствие, идею для занятия с {name}, пожелание и гороскоп.\n"
        f"👉 Кнопка «🌅 Брифинг» внизу.\n\n"
        f"💡 <b>Остальные кнопки:</b>\n"
        f"😴 <b>Сон</b> — отметить сон {name}: дневной / ночной / пробуждение\n"
        f"📊 <b>Статистика</b> — сны за день, 3 дня или неделю\n"
        f"💡 <b>Идея дня</b> — случайная идея для занятия\n"
        f"📚 <b>Полезное</b> — ответы на вопросы\n"
        f"❤️ <b>Самочувствие</b> — отметка настроения\n\n"
        f"Хорошего дня! 🌸"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())


# ===== /start =====
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)

    if user and user.get("consent_given"):
        # Если имя ещё не задано — спросим
        if not user.get("child_name"):
            await message.answer(
                "Как зовут малыша? Это нужно для персональных сообщений "
                "(например, «Мишка проснулся в 7:20»).\n\n"
                "Напиши имя одним словом или нажми «Пропустить»:",
                reply_markup=name_skip_keyboard()
            )
            await state.set_state(UserStates.waiting_child_name_change)
            return
        await send_welcome_instructions(message, user)
        await state.clear()
    else:
        await message.answer(
            "👋 Привет! Я бот-помощник для мам.\n\n"
            "Прежде чем начать, мне нужно получить ваше согласие на обработку персональных данных. "
            "Это необходимо для корректной работы бота.\n\n"
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
        await send_welcome_instructions(callback.message, user)
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

    await message.answer(
        "А как зовут малыша? Напиши имя одним словом "
        "(например, «Миша») — или нажми «Пропустить».",
        reply_markup=name_skip_keyboard()
    )
    await state.set_state(UserStates.waiting_child_name)


@router.message(UserStates.waiting_child_name, ~F.text.in_(MAIN_BUTTONS))
async def process_child_name(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) > 40:
        await message.answer("Слишком длинное имя. Попробуй короче.")
        return
    user_id = message.from_user.id
    update_user_child_name(user_id, text)
    user = get_user(user_id)
    await send_welcome_instructions(message, user)
    await state.clear()


@router.callback_query(F.data == "name_skip")
async def process_name_skip(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    update_user_child_name(user_id, "")
    user = get_user(user_id)
    await callback.message.edit_text("Хорошо, буду называть просто «Малыш». ✅")
    await send_welcome_instructions(callback.message, user)
    await state.clear()
    await callback.answer()


# ===== Изменение имени из /start =====
@router.message(UserStates.waiting_child_name_change, ~F.text.in_(MAIN_BUTTONS))
async def process_child_name_change(message: Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id
    if len(text) > 40:
        await message.answer("Слишком длинное имя.")
        return
    update_user_child_name(user_id, text)
    user = get_user(user_id)
    await message.answer(f"Запомнил! Буду звать {text}. ✅")
    await send_welcome_instructions(message, user)
    await state.clear()


# ===== СОН: главное меню =====
@router.message(F.text == "😴 Сон")
async def sleep_menu(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала настрой бота через /start")
        return
    await message.answer(
        "😴 <b>Раздел «Сон»</b>\n\n"
        "Выбери, что отметить:",
        parse_mode="HTML",
        reply_markup=sleep_main_keyboard()
    )


@router.callback_query(F.data == "sleep_back")
async def cb_sleep_back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "😴 <b>Раздел «Сон»</b>\n\n"
        "Выбери, что отметить:",
        parse_mode="HTML",
        reply_markup=sleep_main_keyboard()
    )
    await callback.answer()


# ===== ДНЕВНОЙ СОН =====
@router.callback_query(F.data == "sleep_day_menu")
async def cb_day_menu(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    name = _child_name(user)
    await callback.message.edit_text(
        f"☀️ <b>Дневной сон {name}</b>\n\n"
        f"Отметь начало или конец дневного сна:",
        parse_mode="HTML",
        reply_markup=sleep_day_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "day_start_now")
async def cb_day_start_now(callback: types.CallbackQuery):
    await _record_sleep(callback, "sleep_start", 0, is_night=False, minutes_ago=0)


@router.callback_query(F.data == "day_start_15")
async def cb_day_start_15(callback: types.CallbackQuery):
    await _record_sleep(callback, "sleep_start", 15, is_night=False, minutes_ago=15)


@router.callback_query(F.data == "day_start_30")
async def cb_day_start_30(callback: types.CallbackQuery):
    await _record_sleep(callback, "sleep_start", 30, is_night=False, minutes_ago=30)


@router.callback_query(F.data == "day_end_now")
async def cb_day_end_now(callback: types.CallbackQuery):
    await _record_sleep(callback, "sleep_end", 0, is_night=False, minutes_ago=0)


@router.callback_query(F.data == "day_end_15")
async def cb_day_end_15(callback: types.CallbackQuery):
    await _record_sleep(callback, "sleep_end", 15, is_night=False, minutes_ago=15)


@router.callback_query(F.data == "day_end_30")
async def cb_day_end_30(callback: types.CallbackQuery):
    await _record_sleep(callback, "sleep_end", 30, is_night=False, minutes_ago=30)


# ===== НОЧНОЙ СОН =====
@router.callback_query(F.data == "sleep_night_menu")
async def cb_night_menu(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    name = _child_name(user)
    await callback.message.edit_text(
        f"🌙 <b>Ночной сон {name}</b>\n\n"
        f"Вечером — «Заснул вечером», утром — «Проснулся утром».",
        parse_mode="HTML",
        reply_markup=sleep_night_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "night_start_now")
async def cb_night_start_now(callback: types.CallbackQuery):
    await _record_sleep(callback, "sleep_start", 0, is_night=True, minutes_ago=0)


@router.callback_query(F.data == "night_end_now")
async def cb_night_end_now(callback: types.CallbackQuery):
    await _record_sleep(callback, "sleep_end", 0, is_night=True, minutes_ago=0)


# ===== Вспомогательная функция записи сна =====
async def _record_sleep(callback: types.CallbackQuery, event_type: str, minutes_ago: int, is_night: bool = False, **_):
    user_id = callback.from_user.id
    user = get_user(user_id)
    if not user:
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return

    name = _child_name(user)
    ts = int((datetime.now() - timedelta(minutes=minutes_ago)).timestamp())
    local = to_user_tz(user_id, ts).strftime('%H:%M')
    kind = "🌙 ночной сон" if is_night else "☀️ дневной сон"

    add_event(user_id, event_type, ts)

    if event_type == "sleep_start":
        text = (
            f"✅ {name} заснул в <b>{local}</b> ({kind}).\n\n"
            f"Когда проснётся — отметь «Проснулся»."
        )
        await callback.message.edit_text(text, parse_mode="HTML")
    else:
        # Найти последний sleep_start и посчитать длительность
        last_start = get_last_sleep_start(user_id)
        duration_str = ""
        if last_start:
            dur_min = (ts - last_start["timestamp"]) // 60
            if dur_min > 0:
                duration_str = f"\n😴 {name} поспал: {_format_hm(dur_min)}."

        schedule_text = recalc_schedule(user_id, ts)
        text = (
            f"✅ {name} проснулся в <b>{local}</b> ({kind}).{duration_str}\n\n"
            f"{schedule_text}"
        )
        await callback.message.edit_text(text, parse_mode="HTML")

    await callback.answer()


# ===== НОЧНОЕ ПРОБУЖДЕНИЕ =====
@router.callback_query(F.data == "night_wake")
async def cb_night_wake(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    if not user:
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    name = _child_name(user)
    now = int(datetime.now().timestamp())
    add_event(user_id, "night_wake", now)
    local = now_in_user_tz(user_id).strftime('%H:%M')

    from datetime import timedelta as td
    from database import get_events_since
    since = int((datetime.now() - td(hours=12)).timestamp())
    events = get_events_since(user_id, since)
    count = sum(1 for e in events if e["event_type"] == "night_wake")

    await callback.message.edit_text(
        f"🌙 Записал: <b>{name} проснулся ночью в {local}</b>.\n"
        f"Сегодня уже {count} пробуждени{'е' if count == 1 else 'я' if 2 <= count <= 4 else 'й'}.",
        parse_mode="HTML"
    )
    await callback.answer()


# ===== СПИСОК СНОВ ЗА СЕГОДНЯ + УДАЛЕНИЕ =====
@router.callback_query(F.data == "sleep_list")
async def cb_sleep_list(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return

    sleeps = _collect_sleeps(user_id)
    text = _format_sleeps_list(user_id, sleeps)

    if not sleeps:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=sleep_main_keyboard()
        )
    else:
        text += "\n\n<i>Нажми на кнопку ниже, чтобы удалить ненужный сон.</i>"
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=sleep_list_keyboard(sleeps)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("del_sleep:"))
async def cb_delete_sleep(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Ошибка.", show_alert=True)
        return

    start_id = None if parts[1] == "none" else int(parts[1])
    end_id = None if parts[2] == "none" else int(parts[2])

    delete_sleep(user_id, start_id, end_id)

    sleeps = _collect_sleeps(user_id)
    text = "🗑 Сон удалён.\n\n" + _format_sleeps_list(user_id, sleeps)

    if not sleeps:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=sleep_main_keyboard()
        )
    else:
        text += "\n\n<i>Нажми на кнопку ниже, чтобы удалить ненужный сон.</i>"
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=sleep_list_keyboard(sleeps)
        )
    await callback.answer("Удалено")


# ===== ОТМЕНА ПОСЛЕДНЕГО =====
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


# ===== РУЧНОЙ ВВОД =====
@router.callback_query(F.data == "sleep_manual")
async def cb_sleep_manual(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not get_user(user_id):
        await callback.answer("Сначала настрой бота через /start", show_alert=True)
        return
    await callback.message.edit_text(
        "⌨️ Введи время в формате ЧЧ:ММ (например, 14:30).\n\n"
        "Укажи действие:\n"
        "• <b>'уснул 14:30'</b> — начало сна\n"
        "• <b>'проснулся 14:30'</b> — конец сна",
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
    user = get_user(user_id)
    name = _child_name(user)
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
            f"✅ {name} заснул в <b>{local_str}</b>.",
            parse_mode="HTML"
        )
    else:
        last_start = get_last_sleep_start(user_id)
        duration_str = ""
        if last_start:
            dur_min = (ts - last_start["timestamp"]) // 60
            if dur_min > 0:
                duration_str = f"\n😴 {name} поспал: {_format_hm(dur_min)}."
        schedule_text = recalc_schedule(user_id, ts)
        await message.answer(
            f"✅ {name} проснулся в <b>{local_str}</b>.{duration_str}\n\n{schedule_text}",
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
    now_local = now_in_user_tz(message.from_user.id).strftime('%H:%M')
    await message.answer(
        f"🌍 <b>Часовой пояс</b>\n\n"
        f"Сейчас у тебя <b>{now_local}</b>\n"
        f"Пояс в настройках: {user['timezone']}\n\n"
        f"Если время не совпадает с твоими часами — выбери свой город ниже:",
        parse_mode="HTML",
        reply_markup=timezone_keyboard()
    )


@router.callback_query(F.data.startswith("tz_"))
async def timezone_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tz = callback.data.replace("tz_", "", 1)
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
        f"Сейчас у тебя: <b>{now_local}</b>\n\n"
        f"Сравни с часами на телефоне. Если совпадает — всё верно. 🌸",
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