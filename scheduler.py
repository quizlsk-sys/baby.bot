from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import (
    get_users_for_brief, get_user, get_idea_by_age, get_events_since,
    update_last_brief_date, get_day_events, update_last_brief_message_id,
    get_events_between,
)
from utils import get_child_age_days, get_user_tz, now_in_user_tz, get_age_params, _format_hm
from ai_helper import generate_briefing
from backup import send_backup
from config import ADMIN_ID


scheduler = AsyncIOScheduler()


def _count_night_wakes(user_id: int, hours: int = 12) -> int:
    since = int((datetime.now() - timedelta(hours=hours)).timestamp())
    events = get_events_since(user_id, since)
    return sum(1 for e in events if e["event_type"] == "night_wake")


def _analyze_night(user_id: int, tz):
    """Возвращает (sleep_min, wake_count, wake_time_str) за последнюю ночь."""
    now_local = datetime.now(tz)
    yesterday_evening = (now_local - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
    today_morning = now_local.replace(hour=11, minute=0, second=0, microsecond=0)
    start_ts = int(yesterday_evening.timestamp())
    end_ts = int(today_morning.timestamp())

    events = get_events_between(user_id, start_ts, end_ts)
    events.sort(key=lambda e: e["timestamp"])

    total_min = 0
    current_start = None
    wake_count = 0
    last_wake_ts = None

    for e in events:
        if e["event_type"] == "sleep_start":
            current_start = e["timestamp"]
        elif e["event_type"] == "sleep_end":
            if current_start:
                total_min += (e["timestamp"] - current_start) // 60
                current_start = None
            last_wake_ts = e["timestamp"]
        elif e["event_type"] == "night_wake":
            wake_count += 1

    if last_wake_ts:
        wake_time_str = datetime.fromtimestamp(last_wake_ts, tz).strftime("%H:%M")
    else:
        wake_time_str = now_local.strftime("%H:%M")

    return total_min, wake_count, wake_time_str


def _get_today_plan_summary(user_id: int, tz):
    """Возвращает (naps_count, first_nap_str, bedtime_str)."""
    age_days = get_child_age_days(user_id)
    wake_min, wake_max, sleep_count, dur_min, dur_max, bedtime_hour = get_age_params(age_days)

    today = datetime.now(tz).date()
    events = get_day_events(user_id, today)
    sleep_ends = [e for e in events if e["event_type"] == "sleep_end"]

    if sleep_ends:
        wake_ts = max(e["timestamp"] for e in sleep_ends)
    else:
        wake_ts = int(datetime.now(tz).timestamp())

    wake_local = datetime.fromtimestamp(wake_ts, tz)
    avg_wake = (wake_min + wake_max) // 2
    first_nap = wake_local + timedelta(minutes=avg_wake)
    bedtime = wake_local.replace(hour=bedtime_hour, minute=0, second=0, microsecond=0)
    if bedtime <= wake_local:
        bedtime = bedtime + timedelta(days=1)

    return sleep_count, first_nap.strftime("%H:%M"), bedtime.strftime("%H:%M")


async def send_brief(bot: Bot, user_id: int):
    user = get_user(user_id)
    if not user:
        return

    tz = get_user_tz(user_id)
    age_days = get_child_age_days(user_id) or 0
    age_months = age_days // 30
    name = user.get("child_name") or "Малыш"

    night_min, wakes, wake_str = _analyze_night(user_id, tz)
    naps_count, first_nap_str, bedtime_str = _get_today_plan_summary(user_id, tz)

    ai_text = generate_briefing(
        child_name=name,
        age_months=age_months,
        night_sleep_min=night_min,
        night_wakes=wakes,
        wake_time_str=wake_str,
        naps_count=naps_count,
        first_nap_str=first_nap_str,
        bedtime_str=bedtime_str,
    )

    if not ai_text:
        ai_text = (
            f"🌙 НОЧЬ\n"
            f"{name} спал {night_min // 60} ч {night_min % 60} мин, "
            f"пробуждений: {wakes}. Подъём в {wake_str}.\n\n"
            f"📅 СЕГОДНЯ\n"
            f"По плану {naps_count} снов, первый около {first_nap_str}, "
            f"укладывание на ночь в {bedtime_str}.\n\n"
            f"🎯 ФОКУС\n"
            f"Следите за признаками усталости и старайтесь укладывать вовремя."
        )

    header = f"☀️ <b>Доброе утро!</b>\n\n"
    body = ai_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    full_message = header + body

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Полезно", callback_data="brief_feedback_good"),
            InlineKeyboardButton(text="👎 Не полезно", callback_data="brief_feedback_bad"),
        ]
    ])

    try:
        msg = await bot.send_message(user_id, full_message, parse_mode="HTML", reply_markup=keyboard)
        update_last_brief_date(user_id, now_in_user_tz(user_id).strftime("%Y-%m-%d"))
        try:
            update_last_brief_message_id(user_id, msg.message_id)
        except Exception:
            pass
    except Exception as e:
        print(f"Ошибка отправки брифинга пользователю {user_id}: {e}")


async def check_briefs(bot: Bot):
    users = get_users_for_brief()
    for u in users:
        try:
            tz = get_user_tz(u["user_id"])
            now_local = datetime.now(tz)
            today_str = now_local.strftime("%Y-%m-%d")
            current_hm = now_local.strftime("%H:%M")

            if u["last_brief_date"] == today_str:
                continue

            if current_hm == u["morning_brief_time"]:
                await send_brief(bot, u["user_id"])
        except Exception as e:
            print(f"Ошибка при проверке брифинга: {e}")


async def daily_backup(bot: Bot):
    if ADMIN_ID == 0:
        return
    print("📦 Запускаю ежедневный бэкап...")
    await send_backup(bot, ADMIN_ID)


def start_brief_scheduler(bot: Bot):
    scheduler.add_job(
        check_briefs,
        "interval",
        seconds=60,
        args=[bot],
        id="brief_checker",
        replace_existing=True,
    )

    if ADMIN_ID:
        scheduler.add_job(
            daily_backup,
            "cron",
            hour=3,
            minute=0,
            args=[bot],
            id="daily_backup",
            replace_existing=True,
        )
        print(f"✅ Планировщик бэкапа запущен (в 03:00 UTC, ID={ADMIN_ID}).")

    scheduler.start()
    print("✅ Планировщик брифингов запущен.")