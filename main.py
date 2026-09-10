import asyncio
import logging
import os
from threading import Thread
from flask import Flask, Response
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import router
from scheduler import start_brief_scheduler

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)

flask_app = Flask(__name__)

@flask_app.route('/ping')
def ping():
    return Response("pong", status=200)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def on_startup():
    print("Инициализация базы данных...")
    init_db()
    print("Запуск планировщика брифингов...")
    start_brief_scheduler(bot)

async def main():
    await on_startup()

    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    print(f"✅ Flask-сервер запущен на порту {os.environ.get('PORT', 10000)}")

    print("🚀 Запускаем бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())