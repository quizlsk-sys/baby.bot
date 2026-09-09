import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from database import init_db, get_user
from handlers import router
from scheduler import schedule_for_user, scheduler
from keyboards import main_keyboard

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)

async def on_startup():
    init_db()
    scheduler.start()
    # Здесь можно добавить всех пользователей из БД, но для простоты пока нет
    # Если вы хотите, чтобы брифинг работал, нужно получить список всех user_id и добавить их в scheduler.
    # Но для первого теста можно временно пропустить.

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())