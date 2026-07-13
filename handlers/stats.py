import html
import time

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



def format_liters(value:float):

    value = round(float(value),2)

    return (
        f"{value:.2f}"
        .rstrip("0")
        .rstrip(".")
    )



def get_rank_emoji(rank:int):

    return messages.RANK_EMOJIS.get(
        rank,
        str(rank)
    )



def leaderboard_text(rows, page, pages):
    if not rows:
        return (messages.EMPTY_LEADERBOARD, page, pages)

    lines = [messages.LEADERBOARD_TITLE.format(page=page + 1, pages=pages)]
    start = page * ROWS_PER_PAGE

    for number, row in enumerate(rows, start=start + 1):
        lines.append(
            messages.LEADERBOARD_ROW.format(
                number=get_rank_emoji(number),
                name=html.escape(row["name"]),
                liters=format_liters(row["total_liters"]),
            )
        )

    # Объединяем строки таблицы и в конец добавляем TEXT_INFO
    full_text = "\n".join(lines) + messages.TEXT_INFO

    return (full_text, page, pages)


def leaderboard_keyboard(
    page,
    pages
):

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



    if page < pages-1:

        builder.button(
            text="▶️",
            callback_data=f"beer_top:{page+1}"
        )


    builder.adjust(3)


    return builder.as_markup()





@router.message(Command("stats"))
async def command_stats(message:Message):


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



    rows,pages = get_leaderboard(
        message.chat.id,
        0
    )


    text, page, pages = leaderboard_text(
        rows,
        0,
        pages
    )



    await message.answer(
        text,
        reply_markup=leaderboard_keyboard(
            page,
            pages
        ),
        parse_mode="HTML"
    )





@router.callback_query(
    F.data.startswith("beer_top:")
)
async def leaderboard_pagination(
    callback:CallbackQuery
):

    if not callback.message:
        return



    chat_id = callback.message.chat.id



    now=time.time()


    last = _pagination_last.get(
        chat_id,
        0
    )


    if now-last < PAGINATION_COOLDOWN_SECONDS:

        await callback.answer(
            messages.TOO_FAST,
            show_alert=True
        )

        return



    _pagination_last[chat_id]=now



    value = callback.data.split(":")[1]



    if value=="current":

        await callback.answer()

        return



    try:

        page=int(value)

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



    rows,pages = get_leaderboard(
        chat_id,
        page
    )


    text,page,pages = leaderboard_text(
        rows,
        page,
        pages
    )


    await callback.message.edit_text(
        text,
        reply_markup=leaderboard_keyboard(
            page,
            pages
        ),
        parse_mode="HTML"
    )


    await callback.answer()