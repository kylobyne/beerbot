from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

import messages
from services.promos import PromoOutcome, redeem_promo


router = Router()


@router.message(Command("promo"))
async def activate_promo(message: Message) -> None:
    if message.chat.type == "private":
        await message.answer(messages.PRIVATE_DISABLED, parse_mode=ParseMode.HTML)
        return

    if not message.from_user:
        return

    arguments = (message.text or "").split(maxsplit=1)
    if len(arguments) < 2 or not arguments[1].strip():
        await message.answer(messages.PROMO_USAGE, parse_mode=ParseMode.HTML)
        return

    result = redeem_promo(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        user_name=message.from_user.first_name,
        code=arguments[1].strip(),
    )

    if result.outcome is PromoOutcome.NOT_FOUND:
        text = messages.PROMO_NOT_FOUND
    elif result.outcome is PromoOutcome.USER_RESTRICTED:
        text = messages.PROMO_USER_ONLY
    elif result.outcome is PromoOutcome.ALREADY_USED:
        text = messages.PROMO_ALREADY_USED
    elif result.outcome is PromoOutcome.INVALID:
        text = messages.PROMO_NOT_VALID
    else:
        reward_text = (
            f"\n\n+{result.reward_amount} л. пива"
            if result.reward_type == "beer"
            else f"\n\n+{result.reward_amount} доп. попыток"
        )
        text = messages.PROMO_ACTIVATED + reward_text

    await message.answer(text, parse_mode=ParseMode.HTML)
