from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from aiogram import Bot

from database import (
    get_users_for_brief, get_user, get_idea_by_age, get_events_since,
    update_last_brief_date
)
from utils import get_child_age_days, get_user_tz, now_in_user_tz
from ai_helper import generate_text


scheduler = AsyncIOScheduler()


def _count_night_wakes(user_id: int, hours: int = 12) -> int:
    """Считает, сколько раз ребёнок просыпался за последние N часов (ночь)."""
    since = int((datetime.now() - timedelta(hours=hours)).timestamp())
    events = get_events_since(user_id, since)
    return sum(1 for e in events if e["event_type"] == "sleep_end")


async def send_brief(bot: Bot, user_id: int):
    """Формирует и отправляет утренний брифинг через GigaChat."""
    user = get_user(user_id)
    if not user:
        return

    age_days = get_child_age_days(user_id) or 0
    age_months = age_days // 30
    zodiac = user.get("zodiac") or "не указан"
    night_wakes = _count_night_wakes(user_id, hours=12)
    fallback_idea = get_idea_by_age(age_days)

    prompt = (
        f"Составь короткое утреннее сообщение для мамы малыша. Используй ТЁПЛЫЙ, дружелюбный тон на русском языке.\n\n"
        f"Данные:\n"
        f"- Возраст ребёнка: примерно {age_months} мес.\n"
        f"- Знак зодиака мамы: {zodiac}\n"
        f"- Количество ночных пробуждений ребёнка: {night_wakes}\n\n"
        f"В сообщении должно быть 4 части (каждую начинай с эмодзи):\n"
        f"1. ☀️ Короткое тёплое приветствие.\n"
        f"2. 💡 Одна конкретная идея для игры/развития с ребёнком на сегодня (с учётом возраста).\n"
        f"3. 💛 Пожелание или слова поддержки маме на день.\n"
        f"4. ♈ Короткий шуточный гороскоп на день для указанного знака зодиака (1–2 предложения).\n\n"
        f"Не используй заголовки и markdown-разметку, только текст. Общая длина — не более 900 символов."
    )

    text = generate_text(prompt)

    if text:
        message = f"🌅 Доброе утро!\n\n{text}"
    else:
        # Резервный вариант, если GigaChat недоступен
        message = (
            f"🌅 Доброе утро!\n\n"
            f"☀️ Пусть сегодняшний день будет спокойным и радостным.\n\n"
            f"💡 Идея на сегодня: {fallback_idea}\n\n"
            f"💛 Не забывай отдыхать, когда малыш спит.\n\n"
            f"♈ Хорошего дня!"
        )

    try:
        await bot.send_message(user_id, message)
        update_last_brief_date(user_id, now_in_user_tz(user_id).strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"Ошибка отправки брифинга пользователю {user_id}: {e}")


async def check_briefs(bot: Bot):
    """Проверяет всех пользователей: кому пора отправить брифинг."""
    users = get_users_for_brief()
    for u in users:
        try:
            tz = get_user_tz(u["user_id"])
            now_local = datetime.now(tz)
            today_str = now_local.strftime("%Y-%m-%d")
            current_hm = now_local.strftime("%H:%M")

            # Уже отправляли сегодня?
            if u["last_brief_date"] == today_str:
                continue

            # Время совпадает? (проверка с точностью до минуты)
            if current_hm == u["morning_brief_time"]:
                await send_brief(bot, u["user_id"])
        except Exception as e:
            print(f"Ошибка при проверке брифинга: {e}")


def start_brief_scheduler(bot: Bot):
    """Запускает фоновую проверку раз в минуту."""
    scheduler.add_job(
        check_briefs,
        "interval",
        seconds=60,
        args=[bot],
        id="brief_checker",
        replace_existing=True,
    )
    scheduler.start()
    print("✅ Планировщик брифингов запущен.")