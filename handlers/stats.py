import html
import logging
import time
import asyncio

from aiogram import Router, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
)
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder
)

import messages
from handlers.ephemeral import send_ephemeral_message
from database import (
    get_leaderboard,
    update_user_name,
    update_unchecked_drinker_memberships,
)
from config import (
    ROWS_PER_PAGE,
    ALLOWED_STATUSES,
    STATS_COOLDOWN_SECONDS,
)
from handlers.Middleware import CooldownMiddleware # Импортируем middleware

# Создаем роутер ОДИН раз
router = Router()
# Подключаем к нему middleware
router.callback_query.middleware(CooldownMiddleware()) 

MEMBER_CHECK_BATCH_SIZE = 20
MEMBER_LOOKAHEAD_BATCH_SIZE = 5
stats_last_requests: dict[int, float] = {}
stats_last_warnings: dict[int, float] = {}


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


def leaderboard_keyboard(chat_id: int, page: int, has_next_page: bool):
    if page == 0 and not has_next_page:
        return None

    builder = InlineKeyboardBuilder()

    if page > 0:
        builder.button(
            text="◀️",
            callback_data=f"beer_top:{chat_id}:{page-1}",
            style="success"
        )

    builder.button(
        text=f"{page + 1}/…" if has_next_page else f"{page + 1}/{page + 1}",
        callback_data=f"beer_top:{chat_id}:current"
    )

    if has_next_page:
        builder.button(
            text="▶️",
            callback_data=f"beer_top:{chat_id}:{page+1}",
            style="success"
        )

    builder.adjust(3)
    return builder.as_markup()


async def get_valid_leaderboard_text(bot, chat_id: int, target_page: int):
    """Reconcile legacy membership rows, then render the requested page."""
    all_db_rows = get_leaderboard(chat_id)
    if not all_db_rows:
        return messages.EMPTY_LEADERBOARD, None

    async def check_member(row):
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=row["user_id"])
        except TelegramAPIError:
            return row["user_id"], None
        return row["user_id"], member.status in ALLOWED_STATUSES

    async def reconcile_batch(batch):
        unchecked_rows = [row for row in batch if not row["membership_checked"]]
        if not unchecked_rows:
            return [row for row in batch if row["is_member"]]

        checked = await asyncio.gather(*(check_member(row) for row in unchecked_rows))
        membership_updates = {
            user_id: is_member
            for user_id, is_member in checked
            if is_member is not None
        }
        update_unchecked_drinker_memberships(chat_id, membership_updates)

        is_member_by_id = dict(checked)
        return [
            row
            for row in batch
            if (
                bool(row["is_member"])
                if row["membership_checked"]
                else is_member_by_id.get(row["user_id"]) is True
            )
        ]

    target_page = max(0, target_page)
    start_index = target_page * ROWS_PER_PAGE
    page_end = start_index + ROWS_PER_PAGE
    valid_rows = []
    next_offset = 0
    for offset in range(0, len(all_db_rows), MEMBER_CHECK_BATCH_SIZE):
        batch = all_db_rows[offset:offset + MEMBER_CHECK_BATCH_SIZE]
        valid_rows.extend(await reconcile_batch(batch))
        next_offset = offset + len(batch)
        if len(valid_rows) >= page_end:
            break

    lookahead_offset = next_offset if len(valid_rows) == page_end else len(all_db_rows)
    for offset in range(lookahead_offset, len(all_db_rows), MEMBER_LOOKAHEAD_BATCH_SIZE):
        batch = all_db_rows[offset:offset + MEMBER_LOOKAHEAD_BATCH_SIZE]
        valid_rows.extend(await reconcile_batch(batch))
        if len(valid_rows) > page_end:
            break
    if not valid_rows:
        return messages.EMPTY_LEADERBOARD, None

    page = min(target_page, (len(valid_rows) - 1) // ROWS_PER_PAGE)
    start_index = page * ROWS_PER_PAGE
    end_index = start_index + ROWS_PER_PAGE
    page_rows = valid_rows[start_index:end_index]
    has_next_page = len(valid_rows) > end_index
    total_pages = "…" if has_next_page else page + 1

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
    keyboard = leaderboard_keyboard(chat_id, page, has_next_page)

    return full_text, keyboard


@router.message(Command("stats"))
async def command_stats(message: Message):
    if not message.from_user:
        return

    if message.chat.type == "private":
        await message.answer(messages.PRIVATE_DISABLED, parse_mode="HTML")
        return

    now = time.monotonic()
    last_request = stats_last_requests.get(message.chat.id)
    if last_request is not None and now - last_request < STATS_COOLDOWN_SECONDS:
        last_warning = stats_last_warnings.get(message.chat.id)
        if last_warning is None or now - last_warning >= STATS_COOLDOWN_SECONDS:
            stats_last_warnings[message.chat.id] = now
            try:
                await send_ephemeral_message(
                    bot=message.bot,
                    chat_id=message.chat.id,
                    receiver_user_id=message.from_user.id,
                    text=messages.STATS_TOO_FAST,
                    reply_to_ephemeral_id=message.ephemeral_message_id,
                )
            except TelegramAPIError:
                logging.exception(
                    "Could not send /stats cooldown response to user %s",
                    message.from_user.id,
                )
        return

    stats_last_requests[message.chat.id] = now

    update_user_name(
        message.chat.id,
        message.from_user.id,
        message.from_user.full_name
    )
    text, reply_markup = await get_valid_leaderboard_text(message.bot, message.chat.id, 0)

    try:
        await send_ephemeral_message(
            bot=message.bot,
            chat_id=message.chat.id,
            receiver_user_id=message.from_user.id,
            text=text,
            reply_markup=reply_markup,
            reply_to_ephemeral_id=message.ephemeral_message_id,
        )
    except TelegramAPIError:
        logging.exception("Could not send ephemeral /stats response to user %s", message.from_user.id)
        return



@router.callback_query(F.data.startswith("beer_top:"))
async def leaderboard_pagination(callback: CallbackQuery):
    if not callback.message:
        return

    parts = callback.data.split(":")
    if len(parts) == 3:
        try:
            chat_id = int(parts[1])
        except ValueError:
            await callback.answer(messages.INVALID_PAGE, show_alert=True)
            return
        value = parts[2]
    else:
        chat_id = callback.message.chat.id
        value = parts[1]

    if value == "current":
        await callback.answer("Вы на этой странице", show_alert=False)
        return

    # --- ВСЯ СТАРАЯ ПРОВЕРКА ВРЕМЕНИ И СЛОВАРЬ УДАЛЕНЫ ОТСЮДА ---

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

    # Генерируем запрошенную страницу
    text, reply_markup = await get_valid_leaderboard_text(callback.message.bot, chat_id, page)

    ephemeral_message_id = getattr(callback.message, "ephemeral_message_id", None)
    if ephemeral_message_id is not None:
        await callback.bot.edit_ephemeral_message_text(
            chat_id=chat_id,
            receiver_user_id=callback.from_user.id,
            ephemeral_message_id=ephemeral_message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    await callback.answer()
