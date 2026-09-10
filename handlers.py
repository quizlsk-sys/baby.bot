import os
from gigachat import GigaChat
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from datetime import datetime, timedelta
import re

from database import (
    create_user, get_user, add_event, get_last_event, get_day_events,
    get_idea_by_age, answer_question, get_questions_by_category,
    get_answer_by_id, get_connection, update_user_consent
)
from states import UserStates
from keyboards import (
    main_keyboard, consent_keyboard, sleep_keyboard, mood_keyboard,
    stats_period_keyboard, timezone_keyboard, categories_keyboard,
    questions_keyboard, CATEGORIES
)
from utils import (
    get_child_age_days, recalc_schedule, generate_stats,
    now_in_user_tz, to_user_tz, get_user_tz
)

router = Router()

# ===== ИНИЦИАЛИЗАЦИЯ ИИ =====
# Настраиваем GigaChat, используя ключ из переменных окружения
try:
    giga = GigaChat(
        credentials=os.environ.get("GIGACHAT_API_KEY"),
        verify_ssl_certs=False,
        scope="GIGACHAT_API_PERS"
    )
except Exception as e:
    print(f"Ошибка инициализации GigaChat: {e}")
    giga = None

MAIN_BUTTONS = [
    "😴 Сон", "📊 Статистика",
    "💡 Идея дня", "📚 Полезное",
    "❤️ Моё самочувствие", "🌍 Часовой пояс",
]

# ... (весь код /start, обработки согласия и сна остаётся без изменений) ...

# ===== Полезное (база знаний) =====
@router.message(F.text == "📚 Полезное")
async def ask_question(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(UserStates.waiting_question)
    await message.answer(
        "📚 Полезные материалы для мамы и малыша.\n\n"
        "Выбери категорию или напиши свой вопрос текстом 👇",
        reply_markup=categories_keyboard()
    )

# ... (код category_callback и question_callback остаётся без изменений) ...

# Обработка текстового вопроса (только если это НЕ кнопка меню)
@router.message(UserStates.waiting_question, ~F.text.in_(MAIN_BUTTONS))
async def process_question(message: Message, state: FSMContext):
    user_question = message.text
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user or not user.get("child_birthday"):
        await message.answer("Пожалуйста, сначала укажите дату рождения ребёнка в настройках (/start).")
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

    # Проверяем, инициализирован ли GigaChat
    if giga is None:
        fallback_answer = answer_question(user_question)
        await message.answer(fallback_answer)
        await state.clear()
        return

    try:
        # Отправляем запрос к GigaChat
        response = giga.chat(prompt)
        ai_answer = response.choices[0].message.content
        await message.answer(f"🤖 {ai_answer}")
    except Exception as e:
        print(f"Ошибка GigaChat API: {e}")
        fallback_answer = answer_question(user_question)
        await message.answer(fallback_answer)

    await state.clear()