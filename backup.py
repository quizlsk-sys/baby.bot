import os
import shutil
from datetime import datetime

from aiogram import Bot
from aiogram.types import FSInputFile

from database import DB_NAME


async def send_backup(bot: Bot, admin_id: int):
    """Копирует файл БД и отправляет его в Telegram администратору."""
    if admin_id == 0:
        print("⚠️ ADMIN_ID не задан, бэкап пропущен.")
        return

    if not os.path.exists(DB_NAME):
        try:
            await bot.send_message(admin_id, "❌ Файл базы данных не найден.")
        except Exception as e:
            print(f"Ошибка отправки сообщения о бэкапе: {e}")
        return

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_name = f"baby_bot_{date_str}.db"

    try:
        shutil.copy(DB_NAME, backup_name)
        doc = FSInputFile(backup_name)
        await bot.send_document(
            admin_id,
            doc,
            caption=(
                f"📦 Бэкап базы данных\n"
                f"📅 {date_str}\n\n"
                f"Сохрани этот файл — из него можно восстановить данные."
            )
        )
        print(f"✅ Бэкап отправлен администратору ({backup_name}).")
    except Exception as e:
        print(f"Ошибка отправки бэкапа: {e}")
    finally:
        if os.path.exists(backup_name):
            try:
                os.remove(backup_name)
            except Exception:
                pass