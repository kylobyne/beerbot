import messages
import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery
)

from config import BUY_OPTIONS

from database import add_paid_attempts, get_paid_attempts


router = Router()

@router.message(Command("buy"))
async def command_buy(message: Message):

    from aiogram.utils.keyboard import InlineKeyboardBuilder


    builder = InlineKeyboardBuilder()


    for key, item in BUY_OPTIONS.items():

        builder.button(
            text=f"{item['attempts']} попыток - ⭐{item['stars']}",
            callback_data=f"buy:{key}"
        )


    builder.adjust(1)


    await message.answer(
    messages.BUY_MENU,
    reply_markup=builder.as_markup(),
    parse_mode="HTML"
    )




@router.callback_query(
    F.data.startswith("buy:")
)
async def buy_callback(
    callback: CallbackQuery
):

    value = callback.data.split(":")[1]


    if value not in BUY_OPTIONS:

        await callback.answer(
            "Ошибка покупки",
            show_alert=True
        )

        return



    item = BUY_OPTIONS[value]


    await callback.message.answer_invoice(
        title="Активации",

        description=(
            f"Оплата {item['attempts']} активаций"
        ),

        payload=f"paid_attempts:{item['attempts']}",

        provider_token="",

        currency="XTR",

        prices=[
            LabeledPrice(
                label="Telegram Stars",
                amount=item["stars"]
            )
        ]
    )


    await callback.answer()





@router.pre_checkout_query()
async def process_pre_checkout(
    query: PreCheckoutQuery
):

    await query.answer(
        ok=True
    )





@router.message(
    F.successful_payment
)
async def successful_payment(
    message: Message
):
    name = message.from_user.full_name
    payload = (
        message.successful_payment.invoice_payload
    )


    if not payload.startswith(
        "paid_attempts:"
    ):
        return



    attempts = int(
        payload.split(":")[1]
    )


    add_paid_attempts(
        message.from_user.id,
        attempts
    )


    total_attempts = get_paid_attempts(
        message.from_user.id
    )


    await message.answer(
        messages.BUY_SUCCESS.format(
            name=html.escape(name),
            attempts=attempts,
            total_attempts=total_attempts
        ),
        parse_mode="HTML"
    )