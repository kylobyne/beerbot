from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import EphemeralMessageParameters, Message, ReplyParameters


async def send_ephemeral_message(
    bot: Bot,
    chat_id: int,
    receiver_user_id: int,
    text: str,
    reply_markup=None,
    reply_to_ephemeral_id: int | None = None,
    callback_query_id: str | None = None,
    replace_callback_query_message: bool | None = None,
):
    parameters = EphemeralMessageParameters(
        receiver_user_id=receiver_user_id,
        callback_query_id=callback_query_id,
        replace_callback_query_message=replace_callback_query_message,
    )

    if reply_to_ephemeral_id is not None:
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                ephemeral_message_parameters=parameters,
                reply_parameters=ReplyParameters(
                    ephemeral_message_id=reply_to_ephemeral_id,
                ),
            )
        except TelegramBadRequest as error:
            if "REPLY_TO_INVALID" not in str(error):
                raise

    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        ephemeral_message_parameters=parameters,
    )