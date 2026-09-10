from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_keyboard():
    buttons = [
        [KeyboardButton(text="😴 Уснул сейчас"), KeyboardButton(text="👶 Проснулся сейчас")],
        [KeyboardButton(text="⏰ Уснул 15 мин назад"), KeyboardButton(text="⏰ Проснулся 15 мин назад")],
        [KeyboardButton(text="⏰ Уснул 30 мин назад"), KeyboardButton(text="⏰ Проснулся 30 мин назад")],
        [KeyboardButton(text="⌨️ Ввести время вручную"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="💡 Идея дня"), KeyboardButton(text="❓ Задать вопрос")],
        [KeyboardButton(text="❤️ Моё самочувствие"), KeyboardButton(text="🌍 Часовой пояс")],
        [KeyboardButton(text="⚙️ Настройки")],
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
    """Клавиатура с популярными часовыми поясами России."""
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