from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_keyboard():
    buttons = [
        [KeyboardButton(text="😴 Уснул сейчас"), KeyboardButton(text="👶 Проснулся сейчас")],
        [KeyboardButton(text="⏰ Уснул 15 мин назад"), KeyboardButton(text="⏰ Проснулся 15 мин назад")],
        [KeyboardButton(text="⏰ Уснул 30 мин назад"), KeyboardButton(text="⏰ Проснулся 30 мин назад")],
        [KeyboardButton(text="⌨️ Ввести время вручную"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="💡 Идея дня"), KeyboardButton(text="📚 Полезное")],
        [KeyboardButton(text="❤️ Моё самочувствие"), KeyboardButton(text="🌍 Часовой пояс")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def mood_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🟢 Хорошо", callback_data="mood_good")],
        [InlineKeyboardButton(text="🟡 Средне", callback_data="mood_medium")],
        [InlineKeyboardButton(text="🔴 Плохо", callback_data="mood_bad")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stats_period_keyboard():
    buttons = [
        [InlineKeyboardButton(text="За сегодня", callback_data="stats_today")],
        [InlineKeyboardButton(text="За 3 дня", callback_data="stats_3days")],
        [InlineKeyboardButton(text="За неделю", callback_data="stats_week")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def timezone_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Красноярск (UTC+7)", callback_data="tz_Asia/Krasnoyarsk")],
        [InlineKeyboardButton(text="Москва (UTC+3)", callback_data="tz_Europe/Moscow")],
        [InlineKeyboardButton(text="Новосибирск (UTC+7)", callback_data="tz_Asia/Novosibirsk")],
        [InlineKeyboardButton(text="Иркутск (UTC+8)", callback_data="tz_Asia/Irkutsk")],
        [InlineKeyboardButton(text="Владивосток (UTC+10)", callback_data="tz_Asia/Vladivostok")],
        [InlineKeyboardButton(text="Калининград (UTC+2)", callback_data="tz_Europe/Kaliningrad")],
        [InlineKeyboardButton(text="Екатеринбург (UTC+5)", callback_data="tz_Asia/Yekaterinburg")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ===== База знаний: категории =====
CATEGORIES = {
    "сон": "😴 Сон",
    "прикорм": "🍎 Прикорм",
    "здоровье": "🩺 Здоровье",
    "развитие": "🧠 Развитие",
    "уход": "🧴 Уход",
    "мама": "❤️ Мама",
}


def categories_keyboard():
    buttons = []
    row = []
    for key, label in CATEGORIES.items():
        row.append(InlineKeyboardButton(text=label, callback_data=f"cat_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def questions_keyboard(questions):
    buttons = []
    for q in questions:
        title = q["title"]
        if len(title) > 60:
            title = title[:57] + "..."
        buttons.append([InlineKeyboardButton(text=title, callback_data=f"q_{q['id']}")])
    buttons.append([InlineKeyboardButton(text="◀️ К категориям", callback_data="cat_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)