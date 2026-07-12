from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import messages


router = Router()



@router.message(Command("start"))
async def command_start(message:Message):

    if message.chat.type == "private":

        await message.answer(
            messages.START_PRIVATE,
            parse_mode="HTML"
        )

    else:

        await message.answer(
            messages.HELP,
            parse_mode="HTML"
        )