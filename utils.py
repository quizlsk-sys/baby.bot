from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from database import get_user, get_day_events, add_event, get_events_since, get_events_between


def get_child_age_days(user_id: int):
    user = get_user(user_id)
    if not user or not user["child_birthday"]:
        return None
    birth = datetime.strptime(user["child_birthday"], "%Y-%m-%d").date()
    return (date.today() - birth).days


def get_user_tz(user_id: int):
    """Возвращает ZoneInfo с часовым поясом пользователя (или Красноярск по умолчанию)."""
    user = get_user(user_id)
    if user and user.get("timezone"):
        try:
            return ZoneInfo(user["timezone"])
        except Exception:
            pass
    return ZoneInfo("Asia/Krasnoyarsk")


def now_in_user_tz(user_id: int):
    """Текущее время в часовом поясе пользователя."""
    return datetime.now(get_user_tz(user_id))


def to_user_tz(user_id: int, ts: int):
    """Преобразует unix timestamp в datetime в часовом поясе пользователя."""
    return datetime.fromtimestamp(ts, get_user_tz(user_id))


def get_average_wake_time(user_id: int, days=3):
    """Простая эвристика по возрасту."""
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
    """Пересчёт режима после пробуждения. Все времена — в часовом поясе пользователя."""
    age_days = get_child_age_days(user_id)
    avg_wake = get_average_wake_time(user_id)
    next_sleep = wake_timestamp + avg_wake * 60
    next_sleep_dt = to_user_tz(user_id, next_sleep)
    hour = next_sleep_dt.hour
    if 19 <= hour or hour < 6:
        sleep_duration = 540  # ночной сон ~9 часов
    else:
        sleep_duration = 90   # дневной сон ~1.5 часа
    wake_after_next = next_sleep + sleep_duration * 60
    wake_after_next_dt = to_user_tz(user_id, wake_after_next)
    wake_local = to_user_tz(user_id, wake_timestamp)

    msg = (
        f"🔄 Режим пересчитан на основе пробуждения в {wake_local.strftime('%H:%M')}\n"
        f"⏳ Рекомендуемое бодрствование: {avg_wake} мин.\n"
        f"💤 Следующий сон: ~ {next_sleep_dt.strftime('%H:%M')}\n"
        f"🌙 Ожидаемое пробуждение: ~ {wake_after_next_dt.strftime('%H:%M')}\n"
    )
    if hour >= 18:
        msg += "\n🌆 Вечернее время, следующий сон, вероятно, ночной."
    return msg


def generate_stats(user_id: int, days=1):
    """Статистика за последние days дней (включая сегодня). Время — в часовом поясе пользователя."""
    now = datetime.now()
    start_date = now - timedelta(days=days - 1)
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
        msg += f"• Общая длительность сна: {total_sleep_min / 60:.1f} ч ({total_sleep_min:.0f} мин)\n"
        msg += f"• Средняя длительность сна: {avg_sleep_min:.0f} мин\n"
    msg += f"• Среднее бодрствование: {avg_wake} мин\n"
    msg += f"• Ночные пробуждения: {len(night_wakes)}\n"
    if night_wakes:
        times = [to_user_tz(user_id, e["timestamp"]).strftime("%H:%M") for e in night_wakes]
        msg += f"  (в {', '.join(times)})\n"
    return msg