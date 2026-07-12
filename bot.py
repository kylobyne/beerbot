import asyncio
import html
import logging
import os
import random
import re
import sqlite3
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

import messages


load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Задайте BOT_TOKEN в файле .env")

COOLDOWN_SECONDS = 60 * 60
ROWS_PER_PAGE = 20
DATABASE_DIRECTORY = Path("sqlite3")
DATABASE_DIRECTORY.mkdir(exist_ok=True)

router = Router()
PAGINATION_COOLDOWN_SECONDS = 1
_pagination_last: dict[int, float] = {}



def database_path(chat_id: int) -> Path:
    """Возвращает путь к отдельной БД этого чата."""
    # chat_id приходит от Telegram как integer; regex оставлен как защита имени файла.
    safe_chat_id = re.sub(r"[^0-9-]", "", str(chat_id))
    return DATABASE_DIRECTORY / f"chat_{safe_chat_id}.sqlite3"


def get_connection(chat_id: int) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(chat_id))
    connection.row_factory = sqlite3.Row

    # Создаём таблицу с хранением в литрах. При обнаружении старой колонки
    # с миллилитрами выполняется перенос значений и удаление старой колонки.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS drinkers (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            total_liters REAL NOT NULL DEFAULT 0,
            last_drink INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    # Миграция схемы: перенос значений в `total_liters` и перестройка таблицы без `total_ml`.
    cur = connection.execute("PRAGMA table_info(drinkers)")
    cols = [r[1] for r in cur.fetchall()]

    # Если присутствует только старый столбец с миллилитрами, создаём столбец с литрами
    # и заполняем его значениями.
    if "total_ml" in cols and "total_liters" not in cols:
        connection.execute("ALTER TABLE drinkers ADD COLUMN total_liters REAL NOT NULL DEFAULT 0")
        connection.execute("UPDATE drinkers SET total_liters = total_ml / 1000.0 WHERE total_ml IS NOT NULL")
        connection.commit()
        # обновим список колонок
        cur = connection.execute("PRAGMA table_info(drinkers)")
        cols = [r[1] for r in cur.fetchall()]

    # При наличии `total_ml` перестроим таблицу без этой колонки.
    if "total_ml" in cols:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS drinkers_new (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                total_liters REAL NOT NULL DEFAULT 0,
                last_drink INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Скопируем данные, используя total_liters если есть, иначе пересчитаем из total_ml
        connection.execute(
            """
            INSERT OR REPLACE INTO drinkers_new (user_id, name, total_liters, last_drink)
            SELECT user_id, name,
                COALESCE(total_liters, (CASE WHEN total_ml IS NOT NULL THEN total_ml / 1000.0 ELSE 0 END)),
                last_drink
            FROM drinkers
            """
        )
        connection.execute("DROP TABLE drinkers")
        connection.execute("ALTER TABLE drinkers_new RENAME TO drinkers")
        connection.commit()

    return connection


def drink(chat_id: int, user_id: int, name: str) -> tuple[bool, float, float]:
    """Пытается выдать пиво. Возвращает (успех, число секунд ожидания или литров, общее количество литров)."""
    now = int(time.time())
    with get_connection(chat_id) as connection:
        row = connection.execute(
            "SELECT last_drink, name, total_liters FROM drinkers WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            remaining = COOLDOWN_SECONDS - (now - row["last_drink"])
            if remaining > 0:
                if row["name"] != name:
                    connection.execute(
                        "UPDATE drinkers SET name = ? WHERE user_id = ?",
                        (name, user_id),
                    )
                return False, float(remaining), float(row["total_liters"])
        amount_liters = round(random.randint(1, 50) / 10.0, 2)  # от 0.1 до 5.0 литров
        connection.execute(
            """
            INSERT INTO drinkers (user_id, name, total_liters, last_drink)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                total_liters = ROUND(drinkers.total_liters + excluded.total_liters, 2),
                last_drink = excluded.last_drink
            """,
            (user_id, name, amount_liters, now),
        )
        total_liters = connection.execute(
            "SELECT ROUND(total_liters, 2) FROM drinkers WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    return True, amount_liters, float(total_liters)


def get_leaderboard(chat_id: int, page: int) -> tuple[list[sqlite3.Row], int]:
    with get_connection(chat_id) as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM drinkers WHERE total_liters >= 0.1"
        ).fetchone()[0]
        pages = max(1, (total + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
        page = max(0, min(page, pages - 1))
        rows = connection.execute(
            """
            SELECT user_id, name, total_liters FROM drinkers
            WHERE total_liters >= 0.1
            ORDER BY total_liters DESC, name COLLATE NOCASE ASC
            LIMIT ? OFFSET ?
            """,
            (ROWS_PER_PAGE, page * ROWS_PER_PAGE),
        ).fetchall()
    return rows, pages


def update_user_name(chat_id: int, user_id: int, name: str) -> None:
    with get_connection(chat_id) as connection:
        connection.execute(
            "UPDATE drinkers SET name = ? WHERE user_id = ?",
            (name, user_id),
        )
        connection.commit()


def format_liters(value: float) -> str:
    value = round(float(value), 2)
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    return formatted


def get_rank_emoji(rank: int) -> str:
    """Возвращает эмодзи для топ-3 из messages.RANK_EMOJIS, или номер как строку для остальных."""
    return messages.RANK_EMOJIS.get(rank, str(rank))


def leaderboard_text(rows: list[dict], page: int, pages: int) -> tuple[str, int, int]:
    page = max(0, min(page, pages - 1))
    if not rows:
        return messages.EMPTY_LEADERBOARD, page, pages

    lines = [messages.LEADERBOARD_TITLE.format(page=page + 1, pages=pages)]
    start_number = page * ROWS_PER_PAGE
    for number, row in enumerate(rows, start=start_number + 1):
        # `total_liters` уже хранит значение в литрах
        rank_display = get_rank_emoji(number)
        lines.append(messages.LEADERBOARD_ROW.format(
            number=rank_display,
            name=html.escape(row["name"]),
            liters=format_liters(row["total_liters"]),
        ))
    return "\n".join(lines), page, pages


def leaderboard_keyboard(page: int, pages: int):
    if pages <= 1:
        return None
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="◀️", callback_data=f"beer_top:{page - 1}")
    builder.button(text=f"{page + 1}/{pages}", callback_data="beer_top:current")
    if page < pages - 1:
        builder.button(text="▶️", callback_data=f"beer_top:{page + 1}")
    builder.adjust(3)
    return builder.as_markup()


@router.message(Command("start"))
async def command_start(message: Message) -> None:
    # Отдельный обработчик для /start: в личных сообщениях показываем специальный текст,
    # в группах — общую справку.
    if message.chat.type == "private":
        await message.answer(messages.START_PRIVATE, parse_mode="HTML")
    else:
        await message.answer(messages.HELP, parse_mode="HTML")


@router.message(Command("beer"))
async def command_beer(message: Message) -> None:
    if not message.from_user:
        return
    # Запрет в личных сообщениях
    if message.chat.type == "private":
        await message.reply(messages.PRIVATE_DISABLED, parse_mode="HTML")
        return
    name = message.from_user.full_name
    success, value, total_liters = drink(message.chat.id, message.from_user.id, name)
    if not success:
        minutes, seconds = divmod(int(value), 60)
        await message.reply(messages.COOLDOWN_EARLY.format(minutes=minutes, seconds=seconds), parse_mode="HTML")
        return
    # Успешно выпил — показываем объём и время до следующей попытки
    minutes, seconds = divmod(COOLDOWN_SECONDS, 60)
    await message.reply(
        messages.DRINK_NEXT.format(
            name=name,
            liters=format_liters(value),
            total_liters=format_liters(total_liters),
            minutes=minutes,
            seconds=seconds,
        ),
        parse_mode="HTML"
    )


@router.message(Command("stats"))
async def command_top(message: Message) -> None:
    # Запрет в личных сообщениях
    if message.chat.type == "private":
        await message.reply(messages.PRIVATE_DISABLED, parse_mode="HTML")
        return
    if message.from_user:
        update_user_name(message.chat.id, message.from_user.id, message.from_user.full_name)
    rows, pages = get_leaderboard(message.chat.id, 0)
    rows = [
        {"user_id": row["user_id"], "name": row["name"], "total_liters": row["total_liters"]}
        for row in rows
    ]
    text, page, pages = leaderboard_text(rows, 0, pages)
    await message.answer(text, reply_markup=leaderboard_keyboard(page, pages), parse_mode="HTML")


@router.callback_query(F.data.startswith("beer_top:"))
async def leaderboard_pagination(callback: CallbackQuery) -> None:
    if not callback.message or not callback.data:
        return
    # Ограничение переключения страниц: 1 секунда на чат
    chat = callback.message.chat
    if chat:
        chat_id = chat.id
        now = time.time()
        last = _pagination_last.get(chat_id, 0)
        if now - last < PAGINATION_COOLDOWN_SECONDS:
            await callback.answer(messages.TOO_FAST, show_alert=True)
            return
        _pagination_last[chat_id] = now
    requested_page = callback.data.removeprefix("beer_top:")
    if requested_page == "current":
        await callback.answer()
        return
    try:
        page = int(requested_page)
    except ValueError:
        await callback.answer(messages.INVALID_PAGE, show_alert=True)
        return

    if callback.from_user:
        update_user_name(callback.message.chat.id, callback.from_user.id, callback.from_user.full_name)
    rows, pages = get_leaderboard(callback.message.chat.id, page)
    rows = [
        {"user_id": row["user_id"], "name": row["name"], "total_liters": row["total_liters"]}
        for row in rows
    ]
    text, page, pages = leaderboard_text(rows, page, pages)
    await callback.message.edit_text(text, reply_markup=leaderboard_keyboard(page, pages), parse_mode="HTML")
    await callback.answer()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bot = Bot(TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
