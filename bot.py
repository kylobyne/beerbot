import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import TOKEN

from handlers import (
    start,
    beer,
    stats
)



async def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    bot = Bot(TOKEN)


    dp = Dispatcher()


    dp.include_router(start.router)
    dp.include_router(beer.router)
    dp.include_router(stats.router)



    await dp.start_polling(bot)




if __name__ == "__main__":

    asyncio.run(main())