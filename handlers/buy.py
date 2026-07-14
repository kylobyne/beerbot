import html
import json
import time
import uuid
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


from config import BUY_OPTIONS, INVOICE_LIFETIME # Здесь COOLDOWN_TIME больше не нужен, он внутри Middleware.py
from database import (
    add_paid_attempts, 
    get_paid_attempts, 
    create_invoice, 
    get_invoice_status, 
    mark_invoice_as_paid
)
import messages
# Импортируем ваш созданный класс из соседнего файла Middleware.py
from handlers.Middleware import CooldownMiddleware 

router = Router()
# Теперь эта строка отработает без ошибок:
router.callback_query.middleware(CooldownMiddleware())


@router.message(Command("buy"))
async def command_buy(message: Message):
    builder = InlineKeyboardBuilder()

    for key, item in BUY_OPTIONS.items():
        button_text = f"{item['attempts']} попыток - ⭐{item['stars']}"

        # Если это тариф на 10 попыток, создаем кнопку с премиум-эмодзи
        if item["attempts"] == 10:
            builder.add(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"buy:{key}",
                    icon_custom_emoji_id="5440539497383087970",  # ID вашего премиум-эмодзи
                )
            )
        else:
            # Для остальных тарифов используем привычный метод
            builder.button(text=button_text, callback_data=f"buy:{key}")

    name = message.from_user.full_name if message.from_user else "Игрок"
    builder.adjust(1)

    await message.answer(
        messages.BUY_MENU.format(name=html.escape(name)),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )

@router.callback_query(F.data.startswith("buy:"))
async def buy_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Неверный формат данных", show_alert=True)
        return

    value = parts[1]

    if value not in BUY_OPTIONS:
        await callback.answer("Ошибка покупки", show_alert=True)
        return

    item = BUY_OPTIONS[value]

    # Генерируем уникальный UUID для транзакции
    invoice_id = str(uuid.uuid4())
    now = int(time.time())

    # 1. Регистрируем инвойс в базе данных со статусом 'pending'
    create_invoice(invoice_id=invoice_id, user_id=callback.from_user.id, created_at=now)

    # 2. Формируем безопасный JSON-словарь для payload
    payload_data = {
        "invoice_id": invoice_id,
        "attempts": item["attempts"],
        "chat_id": callback.message.chat.id,
        "created_at": now
    }

    # 3. Отправляем инвойс пользователю
    await callback.message.answer_invoice(
        title="Активации",
        description=f"Оплата {item['attempts']} активаций",
        payload=json.dumps(payload_data),  # Упаковываем словарь в строку JSON
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Telegram Stars", amount=item["stars"])],
    )

    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    try:
        # Распаковываем JSON из payload
        payload = json.loads(query.invoice_payload)
        invoice_id = payload.get("invoice_id")
        created_at = payload.get("created_at")

        if not invoice_id or not created_at:
            await query.answer(ok=False, error_message="Критическая ошибка данных платежа.")
            return

        # Проверка 1: Контролируем срок действия инвойса (10 минут)
        if int(time.time()) - created_at > INVOICE_LIFETIME:
            await query.answer(
                ok=False, 
                error_message="Срок действия счета истек (10 мин). Создайте новый инвойс."
            )
            return

        # Проверка 2: Проверяем актуальный статус инвойса в базе данных
        status = get_invoice_status(invoice_id)
        if status == "paid":
            await query.answer(ok=False, error_message="Этот счет уже был успешно оплачен.")
            return
        elif status is None:
            await query.answer(ok=False, error_message="Счет не найден в системе бота.")
            return

        # Если проверки пройдены, подтверждаем платеж в Telegram
        await query.answer(ok=True)

    except (json.JSONDecodeError, Exception):
        await query.answer(ok=False, error_message="Ошибка валидации структуры платежа.")


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    if not message.from_user:
        return

    try:
        # Безопасно извлекаем структурированные данные из JSON-строки
        payload = json.loads(message.successful_payment.invoice_payload)
        invoice_id = payload.get("invoice_id")
        attempts = int(payload.get("attempts"))
        target_chat_id = int(payload.get("chat_id"))
    except (json.JSONDecodeError, ValueError, TypeError):
        return

    # Защита от дубликатов (Идемпотентность):
    # Метод переведет статус в 'paid' только если он до этого был 'pending'.
    # Если вернулось False — значит этот инвойс уже обработан ранее, выходим.
    if not mark_invoice_as_paid(invoice_id):
        return

    # Запись начисления в БД
    add_paid_attempts(message.from_user.id, attempts)
    total_attempts = get_paid_attempts(message.from_user.id)

    name = message.from_user.full_name

    # Отправляем сообщение строго в исходный чат, где была оплата
    try:
        await message.bot.send_message(
            chat_id=target_chat_id,
            text=messages.BUY_SUCCESS.format(
                name=html.escape(name),
                attempts=attempts,
                total_attempts=total_attempts,
            ),
            parse_mode="HTML",
        )
    except Exception:
        # Если бота кикнули из группы пока шла оплата, отправим в ЛС как резерв
        await message.answer(
            text=messages.BUY_SUCCESS.format(
                name=html.escape(name),
                attempts=attempts,
                total_attempts=total_attempts,
            ),
            parse_mode="HTML",
        )
