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
    user = get_user(user_id)
    if user and user.get("timezone"):
        try:
            return ZoneInfo(user["timezone"])
        except Exception:
            pass
    return ZoneInfo("Asia/Krasnoyarsk")


def now_in_user_tz(user_id: int):
    return datetime.now(get_user_tz(user_id))


def to_user_tz(user_id: int, ts: int):
    return datetime.fromtimestamp(ts, get_user_tz(user_id))


def _format_hm(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    if h and m:
        return f"{h} ч {m} мин"
    if h:
        return f"{h} ч"
    return f"{m} мин"


def get_age_params(age_days):
    """Возвращает параметры по возрасту:
    (wake_min, wake_max, sleep_count, dur_min, dur_max, bedtime_hour)."""
    if age_days is None:
        age_days = 180
    if age_days < 90:       # 0–3 мес
        return (45, 90, 5, 30, 90, 21)
    elif age_days < 180:    # 3–6 мес
        return (75, 120, 4, 60, 120, 20)
    elif age_days < 270:    # 6–9 мес
        return (120, 180, 3, 60, 90, 20)
    elif age_days < 365:    # 9–12 мес
        return (180, 240, 2, 60, 90, 20)
    elif age_days < 550:    # 1–1.5 года
        return (210, 270, 2, 90, 120, 20)
    else:                   # 1.5+ года
        return (240, 300, 1, 90, 150, 20)


def get_wake_window(age_days: int):
    """Возвращает (min, max) — окно бодрствования по возрасту."""
    lo, hi, *_ = get_age_params(age_days)
    return (lo, hi)


def get_average_wake_time(user_id: int, days=3):
    age_days = get_child_age_days(user_id)
    lo, hi = get_wake_window(age_days)
    return (lo + hi) // 2


def recalc_schedule(user_id: int, wake_timestamp: int):
    """Пересчёт окна бодрствования после пробуждения."""
    age_days = get_child_age_days(user_id)
    lo, hi = get_wake_window(age_days)

    next_sleep_min = wake_timestamp + lo * 60
    next_sleep_max = wake_timestamp + hi * 60

    dt_min = to_user_tz(user_id, next_sleep_min)
    dt_max = to_user_tz(user_id, next_sleep_max)

    msg = (
        f"💤 Следующее укладывание ориентировочно в "
        f"<b>{dt_min.strftime('%H:%M')} – {dt_max.strftime('%H:%M')}</b>\n"
        f"(через {_format_hm(lo)} – {_format_hm(hi)})\n"
    )
    return msg


def build_day_plan(user_id: int):
    """Строит план дня от последнего пробуждения. Возвращает текст."""
    user = get_user(user_id)
    if not user:
        return "Сначала настрой бота через /start"

    tz = get_user_tz(user_id)
    now_local = datetime.now(tz)
    age_days = get_child_age_days(user_id)
    wake_min, wake_max, sleep_count, dur_min, dur_max, bedtime_hour = get_age_params(age_days)

    # Ищем последнее пробуждение сегодня
    today = now_local.date()
    events = get_day_events(user_id, today)
    sleep_ends = [e for e in events if e["event_type"] == "sleep_end"]
    if sleep_ends:
        wake_ts = max(e["timestamp"] for e in sleep_ends)
    else:
        wake_ts = int(now_local.timestamp())

    wake_local = datetime.fromtimestamp(wake_ts, tz)

    # Средние значения
    avg_wake = (wake_min + wake_max) // 2
    avg_sleep = (dur_min + dur_max) // 2

    name = user.get("child_name") or "Малыш"

    # Время укладывания на ночь (сегодня или завтра)
    bedtime = wake_local.replace(hour=bedtime_hour, minute=0, second=0, microsecond=0)
    if bedtime <= wake_local:
        bedtime = bedtime + timedelta(days=1)

    lines = [f"📅 <b>План дня для {name}</b>\n"]
    lines.append(f"🌅 Подъём: {wake_local.strftime('%H:%M')}")

    cursor = wake_local
    total_sleep_min = 0
    total_awake_min = 0

    for i in range(1, sleep_count + 1):
        nap_start = cursor + timedelta(minutes=avg_wake)
        if nap_start >= bedtime:
            break

        # Бодрствование перед сном
        awake_before = int((nap_start - cursor).total_seconds() // 60)
        lines.append("")
        lines.append(
            f"☀️ Бодрствование: {cursor.strftime('%H:%M')} – "
            f"{nap_start.strftime('%H:%M')} ({_format_hm(awake_before)})"
        )
        total_awake_min += awake_before

        # Сон
        nap_dur = avg_sleep
        nap_end = nap_start + timedelta(minutes=nap_dur)
        if nap_end > bedtime:
            nap_dur = int((bedtime - nap_start).total_seconds() // 60)
            nap_end = bedtime
            if nap_dur < 20:
                break

        lines.append(
            f"😴 <b>Сон {i}:</b> {nap_start.strftime('%H:%M')} – "
            f"{nap_end.strftime('%H:%M')} ({_format_hm(nap_dur)})"
        )
        total_sleep_min += nap_dur
        cursor = nap_end

    # Бодрствование перед ночью
    if cursor < bedtime:
        awake_before_night = int((bedtime - cursor).total_seconds() // 60)
        lines.append("")
        lines.append(
            f"☀️ Бодрствование: {cursor.strftime('%H:%M')} – "
            f"{bedtime.strftime('%H:%M')} ({_format_hm(awake_before_night)})"
        )
        total_awake_min += awake_before_night

    lines.append("")
    lines.append(f"🌙 <b>Укладывание на ночь:</b> {bedtime.strftime('%H:%M')}")
    lines.append("")
    lines.append(
        f"<i>Итого: бодрствование ~{_format_hm(total_awake_min)}, "
        f"дневной сон ~{_format_hm(total_sleep_min)}.</i>"
    )

    return "\n".join(lines)


def generate_stats(user_id: int, days=1):
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
    age_days = get_child_age_days(user_id)
    lo, hi = get_wake_window(age_days)

    msg = f"📊 Статистика за последние {days} дн:\n"
    msg += f"• Всего снов: {num_sleeps}\n"
    if num_sleeps > 0:
        msg += f"• Общая длительность сна: {total_sleep_min / 60:.1f} ч ({total_sleep_min:.0f} мин)\n"
        msg += f"• Средняя длительность сна: {avg_sleep_min:.0f} мин\n"
    msg += f"• Окно бодрствования по возрасту: {_format_hm(lo)} – {_format_hm(hi)}\n"
    msg += f"• Ночные пробуждения: {len(night_wakes)}\n"
    if night_wakes:
        times = [to_user_tz(user_id, e["timestamp"]).strftime("%H:%M") for e in night_wakes]
        msg += f"  (в {', '.join(times)})\n"
    return msg