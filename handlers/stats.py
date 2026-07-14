import html
import time
import math

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery
)
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder
)

import messages
from database import (
    get_leaderboard,
    update_user_name
)
from config import (
    ROWS_PER_PAGE,
    PAGINATION_COOLDOWN_SECONDS
)

router = Router()
_pagination_last = {}


def format_liters(value: float):
    value = round(float(value), 2)
    return (
        f"{value:.2f}"
        .rstrip("0")
        .rstrip(".")
    )


def get_rank_emoji(rank: int):
    return messages.RANK_EMOJIS.get(
        rank,
        str(rank)
    )


def leaderboard_keyboard(page, pages):
    if pages <= 1:
        return None

    builder = InlineKeyboardBuilder()

    if page > 0:
        builder.button(
            text="◀️",
            callback_data=f"beer_top:{page-1}"
        )

    builder.button(
        text=f"{page+1}/{pages}",
        callback_data="beer_top:current"
    )

    if page < pages - 1:
        builder.button(
            text="▶️",
            callback_data=f"beer_top:{page+1}"
        )

    builder.adjust(3)
    return builder.as_markup()


async def get_valid_leaderboard_text(bot, chat_id: int, target_page: int):
    """
    Получает всех игроков из БД, асинхронно проверяет их наличие в чате,
    динамически нарезает на страницы и возвращает (текст, клавиатура).
    """
    # 1. Получаем вообще всех участников из базы данных
    all_db_rows = get_leaderboard(chat_id)
    if not all_db_rows:
        return messages.EMPTY_LEADERBOARD, None

    valid_rows = []
    ALLOWED_STATUSES = ["creator", "administrator", "member"]

    # 2. Фильтруем только тех, кто реально состоит в чате
    for row in all_db_rows:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=row["user_id"])
            if member.status in ALLOWED_STATUSES:
                valid_rows.append(row)
        except Exception:
            # Игнорируем заблокированных или удаленных пользователей
            continue

    if not valid_rows:
        return messages.EMPTY_LEADERBOARD, None

    # 3. Динамически рассчитываем реальное количество страниц по живым юзерам
    total_users = len(valid_rows)
    total_pages = math.ceil(total_users / ROWS_PER_PAGE)

    # Защита от выхода за границы страниц, если кто-то ливнул
    page = max(0, min(target_page, total_pages - 1))

    # 4. Нарезаем массив "живых" пользователей строго под текущую страницу
    start_index = page * ROWS_PER_PAGE
    end_index = start_index + ROWS_PER_PAGE
    page_rows = valid_rows[start_index:end_index]

    # 5. Собираем текст сообщения
    lines = [messages.LEADERBOARD_TITLE.format(page=page + 1, pages=total_pages)]

    for number, row in enumerate(page_rows, start=start_index + 1):
        lines.append(
            messages.LEADERBOARD_ROW.format(
                number=get_rank_emoji(number),
                name=html.escape(row["name"]),
                liters=format_liters(row["total_liters"]),
            )
        )

    full_text = "\n".join(lines) + messages.TEXT_INFO
    keyboard = leaderboard_keyboard(page, total_pages)

    return full_text, keyboard


@router.message(Command("stats"))
async def command_stats(message: Message):
    if message.chat.type == "private":
        await message.reply(
            messages.PRIVATE_DISABLED,
            parse_mode="HTML"
        )
        return

    if message.from_user:
        update_user_name(
            message.chat.id,
            message.from_user.id,
            message.from_user.full_name
        )

    # Генерируем 1-ю страницу топа (индекс 0) с живыми участниками
    text, reply_markup = await get_valid_leaderboard_text(message.bot, message.chat.id, 0)

    await message.answer(
        text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("beer_top:"))
async def leaderboard_pagination(callback: CallbackQuery):
    if not callback.message:
        return

    chat_id = callback.message.chat.id
    value = callback.data.split(":")[1]

    if value == "current":
        await callback.answer("Вы на этой странице", show_alert=False)
        return

    now = time.time()
    last = _pagination_last.get(chat_id, 0)

    if now - last < PAGINATION_COOLDOWN_SECONDS:
        await callback.answer(
            messages.TOO_FAST,
            show_alert=True
        )
        return

    _pagination_last[chat_id] = now

    try:
        page = int(value)
    except ValueError:
        await callback.answer(
            messages.INVALID_PAGE,
            show_alert=True
        )
        return

    if callback.from_user:
        update_user_name(
            chat_id,
            callback.from_user.id,
            callback.from_user.full_name
        )

    # Генерируем запрошенную страницу с живыми участниками
    text, reply_markup = await get_valid_leaderboard_text(callback.message.bot, chat_id, page)

    await callback.message.edit_text(
        text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    await callback.answer()
