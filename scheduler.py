from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from aiogram import Bot
import asyncio
from database import get_user, get_day_events, get_idea_by_age
from utils import get_child_age_days, generate_stats

scheduler = AsyncIOScheduler()

async def send_morning_brief(bot: Bot, user_id: int):
    user = get_user(user_id)
    if not user:
        return
    now = datetime.now()
    night_start = now - timedelta(hours=12)
    night_events = get_day_events(user_id, night_start.date())
    night_wakes = [e for e in night_events if e["event_type"] == "night_wake"]
    age_days = get_child_age_days(user_id)
    if age_days is None:
        age_days = 0
    idea = get_idea_by_age(age_days)
    yesterday_stats = generate_stats(user_id, days=1)
    msg = (
        f"🌅 Доброе утро! Вот твой утренний брифинг:\n"
        f"• Ночных пробуждений: {len(night_wakes)}\n"
        f"• Возраст ребёнка: {age_days} дней\n"
        f"• Идея на сегодня: {idea}\n"
        f"• Краткая статистика за последний день:\n{yesterday_stats}\n"
        f"Не забывай заботиться о себе! ❤️"
    )
    await bot.send_message(user_id, msg)

def schedule_for_user(user_id: int, brief_time: str, bot: Bot):
    hour, minute = map(int, brief_time.split(':'))
    trigger = CronTrigger(hour=hour, minute=minute)
    scheduler.add_job(send_morning_brief, trigger, args=[bot, user_id], id=f"brief_{user_id}", replace_existing=True)