import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message

from handlers.ephemeral import send_ephemeral_message
import messages


router = Router()



@router.message(Command("start"))
async def command_start(message: Message):
    if not message.from_user:
        return

    if message.chat.type == "private":
        await message.answer(messages.START_PRIVATE, parse_mode="HTML")
        return

    ephemeral_message_id = message.ephemeral_message_id
    if ephemeral_message_id is None:
        try:
            await message.delete()
        except TelegramAPIError:
            logging.warning("Could not delete /start message %s", message.message_id)

    help_text = messages.HELP
    try:
        member = await message.bot.get_chat_member(
            message.chat.id,
            message.from_user.id,
        )
        if member.status in {"creator", "administrator"}:
            help_text += f"\n{messages.MOD_HELP}"
    except TelegramAPIError:
        logging.warning(
            "Could not check /start caller status in chat %s",
            message.chat.id,
        )

    try:
        await send_ephemeral_message(
            bot=message.bot,
            chat_id=message.chat.id,
            receiver_user_id=message.from_user.id,
            text=help_text,
            reply_to_ephemeral_id=ephemeral_message_id,
        )
    except TelegramAPIError:
        logging.exception("Could not send ephemeral /start response to user %s", message.from_user.id)
