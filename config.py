import os

# Пробуем разные имена переменных: сначала BOT_TOKEN, потом baby_bot (как у вас на Render)
BOT_TOKEN = (
    os.environ.get("BOT_TOKEN")
    or os.environ.get("baby_bot")
    or "ВАШ_ТОКЕН_ЗДЕСЬ"
)

# ID администратора — бот будет присылать бэкапы на этот Telegram ID.
# Оставьте 0, пока не узнаете свой ID через команду /myid.
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))