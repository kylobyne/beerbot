# promo.py

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from messages import *
import database

router = Router()

# =====================================
# /promo ПРОМОКОД
# =====================================

@router.message(Command("promo"))
async def activate_promo(message: Message):
    # Только в группах
    if message.chat.type == "private":
        await message.answer(
            PRIVATE_DISABLED,
            parse_mode=ParseMode.HTML
        )
        return
    
    # Проверяем, что передан код
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            PROMO_USAGE,
            parse_mode=ParseMode.HTML
        )
        return
    
    promo_code = args[1].strip()
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    chat_id = message.chat.id
    
    # Получаем промокод из базы
    promo = database.get_promo(promo_code)
    
    # 1. Промокод вообще не существует
    if not promo:
        await message.answer(
            PROMO_NOT_FOUND,   # <-- новое сообщение
            parse_mode=ParseMode.HTML
        )
        return
    
    # promo: (id, code, reward_type, reward_amount, time_limited, expires_at, duration,
    #         activation_limited, max_activations, used_count, bind_users, created_by,
    #         created_at, updated_at, active)
    
    promo_id = promo[0]
    reward_type = promo[2]
    reward_amount = promo[3]
    time_limited = promo[4]
    expires_at = promo[5]
    duration = promo[6]
    activation_limited = promo[7]
    max_activations = promo[8]
    used_count = promo[9]
    bind_users = promo[10]
    active = promo[14]
    
    # 2. Промокод деактивирован (вручную или автоматически)
    if not active:
        await message.answer(
            PROMO_NOT_VALID,
            parse_mode=ParseMode.HTML
        )
        return
    
    # 3. Привязка к пользователям
    if bind_users:
        allowed_users = [int(uid.strip()) for uid in bind_users.split(",") if uid.strip()]
        if user_id not in allowed_users:
            await message.answer(
                PROMO_USER_ONLY,
                parse_mode=ParseMode.HTML
            )
            return
    
    # 4. Лимит активаций
    if activation_limited and used_count >= max_activations:
        await message.answer(
            PROMO_NOT_VALID,
            parse_mode=ParseMode.HTML
        )
        return
    
    # 5. Время действия по expires_at
    if time_limited and expires_at:
        if not is_expires_at_valid(expires_at):
            await message.answer(
                PROMO_NOT_VALID,
                parse_mode=ParseMode.HTML
            )
            return
    
    # 6. Время действия по длительности (duration)
    if time_limited and duration:
        if not is_duration_valid(promo):
            await message.answer(
                PROMO_NOT_VALID,
                parse_mode=ParseMode.HTML
            )
            return
    
    # 7. Пользователь уже активировал этот промокод
    if database.has_used_promo(promo_id, user_id):
        await message.answer(
            PROMO_ALREADY_USED,
            parse_mode=ParseMode.HTML
        )
        return
    
    # Активация промокода
    database.use_promo(promo_id, user_id)
    
    # Выдача награды
    if reward_type == "beer":
        database.add_beer_reward(chat_id, user_id, user_name, reward_amount)
        await message.answer(
            PROMO_ACTIVATED + f"\n\n+{reward_amount} л. пива",
            parse_mode=ParseMode.HTML
        )
    elif reward_type == "attempts":
        database.add_paid_attempts(user_id, reward_amount)
        await message.answer(
            PROMO_ACTIVATED + f"\n\n+{reward_amount} доп. попыток",
            parse_mode=ParseMode.HTML
        )

# =====================================
# Проверка даты истечения (expires_at)
# =====================================

def is_expires_at_valid(expires_at: int | None) -> bool:
    return not database.is_expires_at_expired(expires_at)

# =====================================
# Проверка длительности промокода
# =====================================

def is_duration_valid(promo) -> bool:
    duration = promo[6]
    created_at = promo[12]
    return not database.is_duration_expired(duration, created_at)