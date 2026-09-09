from datetime import datetime, date, timedelta
from database import get_user, get_day_events, add_event, get_events_since

def get_child_age_days(user_id: int):
    user = get_user(user_id)
    if not user or not user["child_birthday"]:
        return None
    birth = datetime.strptime(user["child_birthday"], "%Y-%m-%d").date()
    return (date.today() - birth).days

def get_average_wake_time(user_id: int, days=3):
    # Простая эвристика по возрасту
    age_days = get_child_age_days(user_id)
    if age_days is None:
        return 120
    if age_days < 60:
        return 60
    elif age_days < 120:
        return 90
    elif age_days < 180:
        return 120
    elif age_days < 270:
        return 150
    else:
        return 180

def recalc_schedule(user_id: int, wake_timestamp: int):
    age_days = get_child_age_days(user_id)
    avg_wake = get_average_wake_time(user_id)
    next_sleep = wake_timestamp + avg_wake * 60
    next_sleep_dt = datetime.fromtimestamp(next_sleep)
    hour = next_sleep_dt.hour
    if 19 <= hour or hour < 6:
        sleep_duration = 540
    else:
        sleep_duration = 90
    wake_after_next = next_sleep + sleep_duration * 60
    wake_after_next_dt = datetime.fromtimestamp(wake_after_next)
    msg = (
        f"🔄 Режим пересчитан на основе пробуждения в {datetime.fromtimestamp(wake_timestamp).strftime('%H:%M')}\n"
        f"⏳ Рекомендуемое бодрствование: {avg_wake} мин.\n"
        f"💤 Следующий сон: ~ {next_sleep_dt.strftime('%H:%M')}\n"
        f"🌙 Ожидаемое пробуждение: ~ {wake_after_next_dt.strftime('%H:%M')}\n"
    )
    if hour >= 18:
        msg += "\n🌆 Вечернее время, следующий сон, вероятно, ночной."
    return msg

def generate_stats(user_id: int, days=1):
    now = datetime.now()
    start_date = now - timedelta(days=days-1)
    start_ts = int(start_date.replace(hour=0, minute=0, second=0).timestamp())
    end_ts = int(now.timestamp())
    events = get_events_between(user_id, start_ts, end_ts)
    sleeps = []
    current_sleep = None
    for e in events:
        if e["event_type"] == "sleep_start":
            current_sleep = {"start": e["timestamp"]}
        elif e["event_type"] == "sleep_end" and current_sleep:
            current_sleep["end"] = e["timestamp"]
            sleeps.append(current_sleep)
            current_sleep = None
    total_sleep_min = sum((s["end"] - s["start"]) for s in sleeps) / 60 if sleeps else 0
    avg_sleep_min = total_sleep_min / len(sleeps) if sleeps else 0
    night_wakes = [e for e in events if e["event_type"] == "night_wake"]
    num_sleeps = len(sleeps)
    avg_wake = get_average_wake_time(user_id)
    msg = f"📊 Статистика за последние {days} дн:\n"
    msg += f"• Всего снов: {num_sleeps}\n"
    if num_sleeps > 0:
        msg += f"• Общая длительность сна: {total_sleep_min/60:.1f} ч ({total_sleep_min:.0f} мин)\n"
        msg += f"• Средняя длительность сна: {avg_sleep_min:.0f} мин\n"
    msg += f"• Среднее бодрствование: {avg_wake} мин\n"
    msg += f"• Ночные пробуждения: {len(night_wakes)}\n"
    if len(night_wakes) > 0:
        times = [datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M") for e in night_wakes]
        msg += f"  (в {', '.join(times)})\n"
    return msg