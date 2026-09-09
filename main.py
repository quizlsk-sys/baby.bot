import asyncio
import logging
from aiohttp import web
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

async def handle_ping(request):
    return web.Response(text="pong")

async def on_startup():
    init_db()
    scheduler.start()
    # здесь можно добавить расписание для пользователей

async def main():
    await on_startup()
    # Веб-сервер для пинга
    app = web.Application()
    app.router.add_get('/ping', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("Web server started on port 10000")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())