import asyncio
import logging

from aiogram import Bot, Dispatcher

# ДОБАВЛЕНО: Импортируем интервал очистки из конфигурации
from config import TOKEN, DB_CLEAN_INTERVAL
from database import delete_old_pending_invoices
# ШАГ 1: Добавляем admin в импорт (измените имя файла, если оно другое)
from handlers import beer, buy, start, stats, admin, promo


# Фоновая задача для периодической очистки базы данных
async def periodic_db_cleaner():
    """Фоновое задание, которое запускает очистку по интервалу из конфига."""
    while True:
        try:
            delete_old_pending_invoices()
            logging.info("[DB/Background] Автоматическая очистка просроченных инвойсов выполнена.")
        except Exception as e:
            logging.error(f"[DB/Background] Ошибка фоновой очистки: {e}")
        
        # ИЗМЕНЕНО: Используем константу из config.py вместо жесткого числа
        await asyncio.sleep(DB_CLEAN_INTERVAL)


async def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    bot = Bot(TOKEN)
    dp = Dispatcher()

    # ШАГ 2: Регистрируем админский роутер в диспетчере первым
   
    dp.include_router(start.router)
    dp.include_router(beer.router)
    dp.include_router(buy.router)
    dp.include_router(stats.router)
    dp.include_router(promo.router)
    dp.include_router(admin.router)

    # Запускаем фоновую задачу
    asyncio.create_task(periodic_db_cleaner())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
