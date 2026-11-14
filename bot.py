import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeDefault

# ДОБАВЛЕНО: Импортируем интервал очистки из конфигурации
from config import TOKEN, DB_CLEAN_INTERVAL, SQLITE_AUTOBACKUP_ENABLED
from sqlite_backup import periodic_sqlite_backup
from database import delete_old_pending_invoices, deactivate_expired_promos  # ДОБАВЛЕНА deactivate_expired_promos
# ШАГ 1: Добавляем admin в импорт (измените имя файла, если оно другое)
from handlers import beer, buy, start, stats, admin, promo, mod


# Фоновая задача для периодической очистки базы данных
async def periodic_db_cleaner():
    """Фоновое задание, которое запускает очистку по интервалу из конфига."""
    while True:
        try:
            delete_old_pending_invoices()
            deactivate_expired_promos()  # ДОБАВЛЕНО: Деактивация истекших промокодов
            logging.info("[DB/Background] Автоматическая очистка просроченных инвойсов и промокодов выполнена.")
        except Exception as e:
            logging.error(f"[DB/Background] Ошибка фоновой очистки: {e}")
        
        # ИЗМЕНЕНО: Используем константу из config.py вместо жесткого числа
        await asyncio.sleep(DB_CLEAN_INTERVAL)


async def configure_group_commands(bot: Bot):
    group_scope = BotCommandScopeAllGroupChats()
    default_scope = BotCommandScopeDefault()
    default_commands = await bot.get_my_commands(scope=default_scope)
    filtered_default_commands = [
        command for command in default_commands
        if command.command != "admin"
    ]
    if len(filtered_default_commands) != len(default_commands):
        await bot.set_my_commands(filtered_default_commands, scope=default_scope)

    commands = await bot.get_my_commands(scope=group_scope)
    if not commands:
        commands = list(filtered_default_commands)

    if not commands:
        commands = [
            BotCommand(command="start", description="Информация о боте"),
            BotCommand(command="beer", description="Выпить виртуальное пиво"),
            BotCommand(command="buy", description="Купить дополнительные попытки"),
            BotCommand(command="stats", description="Показать рейтинг"),
            BotCommand(command="promo", description="Активировать промокод"),
            BotCommand(command="mod", description="Модерация чата"),
        ]

    commands = [command for command in commands if command.command != "admin"]
    known_commands = {command.command for command in commands}
    for command, description in (
        ("start", "Информация о боте"),
        ("stats", "Показать рейтинг"),
        ("mod", "Модерация чата"),
    ):
        if command not in known_commands:
            commands.append(BotCommand(command=command, description=description))

    commands = [
        BotCommand(
            command=command.command,
            description=command.description,
            is_ephemeral=True if command.command in {"start", "stats", "mod"} else command.is_ephemeral,
        )
        for command in commands
    ]
    await bot.set_my_commands(commands, scope=group_scope)


async def run_polling_with_retry(bot: Bot, dp: Dispatcher) -> None:
    retry_delay = 1
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                close_bot_session=False,
            )
            return
        except TelegramNetworkError:
            logging.exception("Telegram API unavailable; retrying polling in %s seconds", retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)


async def _cancel_background_tasks(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    if not TOKEN:
        raise RuntimeError("Задайте BOT_TOKEN в файле .env")

    bot = Bot(TOKEN)
    dp = Dispatcher()
    try:
        await configure_group_commands(bot)
    except TelegramAPIError:
        logging.exception("Could not update Telegram commands; continuing with long polling")

    # ШАГ 2: Регистрируем админский роутер в диспетчере первым
    dp.include_router(start.router)
    dp.include_router(beer.router)
    dp.include_router(buy.router)
    dp.include_router(stats.router)
    dp.include_router(promo.router)
    dp.include_router(mod.router)
    dp.include_router(admin.router)

    background_tasks = [asyncio.create_task(periodic_db_cleaner())]
    if SQLITE_AUTOBACKUP_ENABLED:
        background_tasks.append(asyncio.create_task(periodic_sqlite_backup()))

    try:
        await run_polling_with_retry(bot, dp)
    finally:
        await _cancel_background_tasks(background_tasks)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
