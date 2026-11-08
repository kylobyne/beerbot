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
    ChatMemberUpdated,
)
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder
)

import messages
from handlers.ephemeral import send_ephemeral_message
from database import (
    get_leaderboard,
    get_unchecked_drinker_ids,
    set_drinker_membership,
    update_unchecked_drinker_memberships,
    update_user_name,
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

MEMBER_RECONCILIATION_BATCH_SIZE = 5
MEMBER_RECONCILIATION_RETRY_SECONDS = 15 * 60
membership_reconciliation_tasks: dict[int, asyncio.Task] = {}
membership_reconciliation_last_started: dict[int, float] = {}
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


def is_allowed_member(member) -> bool:
    if member.status not in ALLOWED_STATUSES:
        return False
    if member.status == "restricted":
        return bool(member.is_member)
    return True


@router.chat_member()
async def update_drinker_membership(event: ChatMemberUpdated):
    """Keep stored leaderboard membership in sync with Telegram member events."""
    set_drinker_membership(
        event.chat.id,
        event.new_chat_member.user.id,
        is_allowed_member(event.new_chat_member),
    )


async def reconcile_unchecked_members(bot, chat_id: int):
    """Reconcile pre-existing drinker rows outside the /stats response path."""
    try:
        user_ids = get_unchecked_drinker_ids(chat_id)
        failed_checks = 0
        for offset in range(0, len(user_ids), MEMBER_RECONCILIATION_BATCH_SIZE):
            batch = user_ids[offset:offset + MEMBER_RECONCILIATION_BATCH_SIZE]
            results = await asyncio.gather(
                *(bot.get_chat_member(chat_id=chat_id, user_id=user_id) for user_id in batch),
                return_exceptions=True,
            )

            memberships = {}
            for user_id, result in zip(batch, results):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                if isinstance(result, BaseException):
                    failed_checks += 1
                    continue
                memberships[user_id] = is_allowed_member(result)

            update_unchecked_drinker_memberships(chat_id, memberships)

        if failed_checks:
            logging.warning(
                "Could not verify %d leaderboard member(s) in chat %s; they will be retried later",
                failed_checks,
                chat_id,
            )
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.exception("Could not reconcile leaderboard members for chat %s", chat_id)


def schedule_membership_reconciliation(bot, chat_id: int) -> None:
    """Start one throttled cleanup pass after the leaderboard has been sent."""
    task = membership_reconciliation_tasks.get(chat_id)
    if task is not None and not task.done():
        return

    now = time.monotonic()
    last_started = membership_reconciliation_last_started.get(chat_id, 0)
    if now - last_started < MEMBER_RECONCILIATION_RETRY_SECONDS:
        return

    membership_reconciliation_last_started[chat_id] = now
    task = asyncio.create_task(reconcile_unchecked_members(bot, chat_id))
    membership_reconciliation_tasks[chat_id] = task
    task.add_done_callback(
        lambda completed: membership_reconciliation_tasks.pop(chat_id, None)
        if membership_reconciliation_tasks.get(chat_id) is completed
        else None
    )


def get_valid_leaderboard_text(chat_id: int, target_page: int):
    """Build a paginated leaderboard from the locally stored active members."""
    all_db_rows = get_leaderboard(chat_id)
    if not all_db_rows:
        return messages.EMPTY_LEADERBOARD, None

    total_pages = (len(all_db_rows) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
    page = min(max(0, target_page), total_pages - 1)
    start_index = page * ROWS_PER_PAGE
    end_index = start_index + ROWS_PER_PAGE
    page_rows = all_db_rows[start_index:end_index]
    has_next_page = page < total_pages - 1

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
    text, reply_markup = get_valid_leaderboard_text(message.chat.id, 0)

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

    schedule_membership_reconciliation(message.bot, message.chat.id)


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
    text, reply_markup = get_valid_leaderboard_text(chat_id, page)

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
