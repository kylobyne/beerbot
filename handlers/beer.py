import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import messages

from config import COOLDOWN_SECONDS
from services.beer import BeerOutcome, process_beer_command


router = Router()



def format_liters(value: float) -> str:

    value = round(float(value), 2)

    return (
        f"{value:.2f}"
        .rstrip("0")
        .rstrip(".")
    )



@router.message(Command("beer"))
async def command_beer(message: Message):
    if not message.from_user:
        return

    if message.chat.type == "private":
        await message.reply(
            messages.PRIVATE_DISABLED,
            parse_mode="HTML",
        )
        return

    name = message.from_user.full_name
    username = message.from_user.username
    result = process_beer_command(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        username=username,
        full_name=name,
    )

    if result.outcome is BeerOutcome.BANNED:
        if result.should_notify_ban:
            await message.reply(messages.DRINKING_BANNED, parse_mode="HTML")
        return

    if result.outcome is BeerOutcome.COOLDOWN:
        minutes, seconds = divmod(int(result.cooldown_seconds or 0), 60)
        await message.reply(
            messages.COOLDOWN_EARLY.format(
                name=html.escape(name),
                minutes=minutes,
                seconds=seconds,
                total_liters=format_liters(result.total_liters or 0),
            ),
            parse_mode="HTML",
        )
        return

    cooldown = COOLDOWN_SECONDS if result.outcome is BeerOutcome.FREE_SUCCESS else 0
    minutes, seconds = divmod(cooldown, 60)

    await message.reply(
        messages.DRINK_NEXT.format(
            name=html.escape(name),
            liters=format_liters(result.liters or 0),
            total_liters=format_liters(result.total_liters or 0),
            minutes=minutes,
            seconds=seconds,
        ),
        parse_mode="HTML",
    )