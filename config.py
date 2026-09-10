import os

# Токен бота
BOT_TOKEN = os.environ.get("BOT_TOKEN") or "ВАШ_ТОКЕН_ЗДЕСЬ"

# ID администратора — бот будет присылать бэкапы на этот Telegram ID.
# Оставьте 0, пока не узнаете свой ID через команду /myid.
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))