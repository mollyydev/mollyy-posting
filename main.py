import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


from data.config import BOT_TOKEN
from middlewares.album import AlbumMiddleware
from filters.admin import AdminFilter
from handlers import base, posting, callbacks, admin
from utils.scheduler import start_scheduler

async def main():
    logging.basicConfig(level=logging.INFO)
    bot_properties = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=BOT_TOKEN, default=bot_properties)
    dp = Dispatcher(storage=MemoryStorage())

    # Global Filters
    dp.message.filter(AdminFilter())
    dp.callback_query.filter(AdminFilter())

    # Middleware
    dp.message.middleware(AlbumMiddleware())

    # Routers
    dp.include_router(base.router)
    dp.include_router(posting.router)
    dp.include_router(callbacks.router)
    dp.include_router(admin.router)

    await start_scheduler()

    print("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
