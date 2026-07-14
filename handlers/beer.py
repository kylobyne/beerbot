import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import messages

from config import COOLDOWN_SECONDS

from database import (
    drink,
    drink_paid,
    use_paid_attempt
)


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



    # Запрет в личных сообщениях
    if message.chat.type == "private":

        await message.reply(
            messages.PRIVATE_DISABLED,
            parse_mode="HTML"
        )

        return



    name = message.from_user.full_name


    success, value, total_liters = drink(
        message.chat.id,
        message.from_user.id,
        name
    )



    # Если обычный КД ещё идёт
    if not success:


        # Проверяем купленные попытки

        if use_paid_attempt(
            message.from_user.id
        ):


            value, total_liters = drink_paid(
                message.chat.id,
                message.from_user.id,
                name
            )


            await message.reply(
                messages.DRINK_NEXT.format(
                    name=html.escape(name),
                    liters=format_liters(value),
                    total_liters=format_liters(
                        total_liters
                    ),
                    minutes=0,
                    seconds=0
                ),
                parse_mode="HTML"
            )


            return



        minutes, seconds = divmod(
            int(value),
            60
        )


        await message.reply(
            messages.COOLDOWN_EARLY.format(
                name=html.escape(name),
                minutes=minutes,
                seconds=seconds,
                total_liters=format_liters(
                    total_liters
                )
            ),
            parse_mode="HTML"
        )

        return



    minutes, seconds = divmod(
        COOLDOWN_SECONDS,
        60
    )


    await message.reply(
        messages.DRINK_NEXT.format(
            name=html.escape(name),
            liters=format_liters(value),
            total_liters=format_liters(
                total_liters
            ),
            minutes=minutes,
            seconds=seconds
        ),
        parse_mode="HTML"
    )