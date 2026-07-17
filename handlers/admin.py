# admin.py

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
import re
from datetime import datetime, timedelta

from messages import *
import database
from config import admins, PROMOS_PER_PAGE

router = Router()

promo_states = {}

# =====================================
# Проверка админа
# =====================================

def is_admin(user_id: int):
    return user_id in admins

async def check_admin(callback):
    if not is_admin(callback.from_user.id):
        await callback.answer(ADMIN_NO_ACCESS, show_alert=True)
        return False
    return True

# =====================================
# Валидаторы
# =====================================

def validate_name(name: str) -> str | None:
    if not name:
        return VALIDATE_NAME_EMPTY
    if " " in name:
        return PROMO_NAME_SPACE_ERROR
    if len(name) > 16:
        return VALIDATE_NAME_TOO_LONG
    if not re.match(r'^[a-zA-Z0-9]+$', name):
        return VALIDATE_NAME_INVALID_CHARS
    return None

def validate_reward_amount(reward_type: str, amount_str: str) -> tuple[int | float | None, str | None]:
    if not amount_str:
        return None, VALIDATE_REWARD_EMPTY
    try:
        if reward_type == "beer":
            amount = float(amount_str)
            if amount <= 0:
                return None, VALIDATE_BEER_POSITIVE
            if '.' in amount_str and len(amount_str.split('.')[1]) > 2:
                return None, VALIDATE_BEER_DECIMALS
            return amount, None
        elif reward_type == "attempts":
            if '.' in amount_str:
                return None, VALIDATE_ATTEMPTS_INTEGER
            amount = int(amount_str)
            if amount <= 0:
                return None, VALIDATE_ATTEMPTS_POSITIVE
            return amount, None
        else:
            return None, VALIDATE_REWARD_UNKNOWN
    except ValueError:
        return None, VALIDATE_REWARD_NUMBER

def validate_time(duration: str) -> str | None:
    if not duration:
        return VALIDATE_TIME_EMPTY
    duration = duration.strip()
    date_patterns = [
        r'^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$',
        r'^\d{2}\.\d{2}\.\d{2} \d{2}:\d{2}$',
        r'^\d{2}\.\d{2}\.\d{4}$',
        r'^\d{2}\.\d{2}\.\d{2}$'
    ]
    for pattern in date_patterns:
        if re.match(pattern, duration):
            try:
                if ' ' in duration:
                    if len(duration.split('.')[2].split()[0]) == 2:
                        parsed_date = datetime.strptime(duration, "%d.%m.%y %H:%M")
                    else:
                        parsed_date = datetime.strptime(duration, "%d.%m.%Y %H:%M")
                else:
                    if len(duration.split('.')[2]) == 2:
                        parsed_date = datetime.strptime(duration, "%d.%m.%y")
                        parsed_date = parsed_date.replace(hour=23, minute=59)
                    else:
                        parsed_date = datetime.strptime(duration, "%d.%m.%Y")
                        parsed_date = parsed_date.replace(hour=23, minute=59)
                if parsed_date < datetime.now():
                    return VALIDATE_TIME_PAST_DATE
                return None
            except ValueError:
                return VALIDATE_TIME_INVALID_DATE
    duration_pattern = r'^(\d+d)?(\d+h)?(\d+m)?(\d+s)?$'
    if re.match(duration_pattern, duration) and duration:
        if any(unit in duration for unit in ['d', 'h', 'm', 's']):
            return None
    return VALIDATE_TIME_INVALID_FORMAT

def validate_activations(amount_str: str) -> tuple[int | None, str | None]:
    if not amount_str:
        return None, VALIDATE_ACTIVATIONS_EMPTY
    try:
        if '.' in amount_str:
            return None, PROMO_NUMBER_ERROR
        amount = int(amount_str)
        if amount <= 0:
            return None, VALIDATE_ACTIVATIONS_POSITIVE
        return amount, None
    except ValueError:
        return None, PROMO_NUMBER_ERROR

def validate_user_id(user_id_str: str) -> tuple[int | None, str | None]:
    if not user_id_str:
        return None, PROMO_USER_ID_ERROR
    try:
        user_id = int(user_id_str)
        if user_id <= 0:
            return None, PROMO_USER_ID_ERROR
        return user_id, None
    except ValueError:
        return None, PROMO_USER_ID_ERROR

# =====================================
# Вспомогательные функции для времени
# =====================================

def parse_duration_to_datetime(duration: str, created_at: datetime = None) -> datetime | None:
    """Парсит duration (дата или длительность) и возвращает datetime истечения."""
    if not duration:
        return None
    if created_at is None:
        created_at = datetime.now()
    duration = duration.strip()

    # Пробуем дату
    date_patterns = [
        (r'^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$', "%d.%m.%Y %H:%M"),
        (r'^\d{2}\.\d{2}\.\d{2} \d{2}:\d{2}$', "%d.%m.%y %H:%M"),
        (r'^\d{2}\.\d{2}\.\d{4}$', "%d.%m.%Y"),
        (r'^\d{2}\.\d{2}\.\d{2}$', "%d.%m.%y")
    ]
    for pattern, fmt in date_patterns:
        if re.match(pattern, duration):
            try:
                expiry = datetime.strptime(duration, fmt)
                if ' ' not in duration:  # только дата → конец дня
                    expiry = expiry.replace(hour=23, minute=59, second=59)
                return expiry
            except ValueError:
                return None

    # Длительность
    days = hours = minutes = seconds = 0
    d_match = re.search(r'(\d+)d', duration)
    h_match = re.search(r'(\d+)h', duration)
    m_match = re.search(r'(\d+)m', duration)
    s_match = re.search(r'(\d+)s', duration)
    if d_match: days = int(d_match.group(1))
    if h_match: hours = int(h_match.group(1))
    if m_match: minutes = int(m_match.group(1))
    if s_match: seconds = int(s_match.group(1))
    return created_at + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

def calculate_remaining(expiry: datetime) -> str:
    """Возвращает 'Осталось X дней, Y часов, Z минут' с опусканием нулей."""
    now = datetime.now()
    if expiry <= now:
        return "Истекло"
    delta = expiry - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} д.")
    if hours > 0:
        parts.append(f"{hours} ч.")
    if minutes > 0:
        parts.append(f"{minutes} мин.")
    if not parts:  # меньше минуты
        parts.append(f"{seconds} сек.")
    return "Осталось " + ", ".join(parts)

def format_expiry(expiry: datetime) -> str:
    """Форматирует дату в 'До: ДД.ММ.ГГГГ ЧЧ:ММ'."""
    return f"До {expiry.strftime('%d.%m.%Y %H:%M')}"

# =====================================
# Клавиатуры
# =====================================

def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Создание промокодов",
                    callback_data="promo_create",
                    style="success",
                    icon_custom_emoji_id="5454096630372379732"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Настройка промокодов",
                    callback_data="promo_settings",
                    style="primary",
                    icon_custom_emoji_id="5283080550293211714"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Удаление промокодов",
                    callback_data="promo_delete",
                    style="danger",
                    icon_custom_emoji_id="5255933371980223131"
                )
            ]
        ]
    )

def back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data="promo_back",
                    icon_custom_emoji_id="5255964497608217438",
                    style="danger"
                )
            ]
        ]
    )

def ok_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Ок",
                    callback_data="admin_return",
                    icon_custom_emoji_id="5256216509109272955",
                    style="success"
                )
            ]
        ]
    )

def final_keyboard(code, edit_mode=False):
    name_display = code.get('name', '—')

    reward_display = code.get('reward_type', '—')
    if code.get('reward_amount'):
        reward_display += f" ({code['reward_amount']})"

    # Время
    time_display = 'Без ограничений'
    if code.get('time_limited'):
        duration = code.get('duration')
        if edit_mode and duration == code.get('old_duration'):
            # Показываем оставшееся время
            created_at = code.get('created_at')
            expiry = parse_duration_to_datetime(duration, created_at)
            if expiry:
                time_display = calculate_remaining(expiry)
        else:
            # Создание или изменено → "До: ..."
            created_at = code.get('created_at')
            expiry = parse_duration_to_datetime(duration, created_at)
            if expiry:
                time_display = format_expiry(expiry)

    # Лимит активаций
    if code.get('activation_limited'):
        max_act = code.get('max_activations', 0)
        if edit_mode:
            used = code.get('used_count', 0)
            limit_display = f"{used}/{max_act}"
        else:
            limit_display = f"{max_act}"
    else:
        limit_display = 'Без ограничений'

    # Пользователи
    bind_users = code.get('bind_users', '')
    if isinstance(bind_users, list):
        user_display = ", ".join(str(uid) for uid in bind_users) if bind_users else 'Нет'
    elif bind_users:
        user_display = bind_users
    else:
        user_display = 'Нет'

    save_button = InlineKeyboardButton(
        text="Сохранить изменения" if edit_mode else "Сохранить промокод",
        callback_data="promo_save_changes" if edit_mode else "promo_save",
        icon_custom_emoji_id="5256216509109272955",
        style="success"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Название: {name_display}", callback_data="edit_name", icon_custom_emoji_id="5281015457002852972")],
            [InlineKeyboardButton(text=f"Награда: {reward_display}", callback_data="edit_reward", icon_custom_emoji_id="5278563335619512182")],
            [InlineKeyboardButton(text=f"Время: {time_display}", callback_data="edit_time", icon_custom_emoji_id="5256137370041879472")],
            [InlineKeyboardButton(text=f"Активаций: {limit_display}", callback_data="edit_limit", icon_custom_emoji_id="5256116200148075808")],
            [InlineKeyboardButton(text=f"Пользователи: {user_display}", callback_data="edit_user", icon_custom_emoji_id="5280472444287616361")],
            [
                InlineKeyboardButton(text="Отменить", callback_data="promo_cancel", icon_custom_emoji_id="5255933371980223131", style="danger"),
                save_button
            ]
        ]
    )

# =====================================
# /admin
# =====================================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.chat.type != "private":
        return
    if not is_admin(message.from_user.id):
        return
    await message.answer(ADMIN_PANEL, reply_markup=admin_keyboard(), parse_mode=ParseMode.HTML)

# =====================================
# Создание промокода
# =====================================

@router.callback_query(F.data == "promo_create")
async def create_promo(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    user_id = callback.from_user.id
    promo_states[user_id] = {
        "edit": False,
        "from_final": False,
        "step": "name",
        "name": None,
        "reward_type": None,
        "reward_amount": 0,
        "duration": None,
        "time_limited": 0,
        "max_activations": None,
        "activation_limited": 0,
        "bind_users": None,
        "created_at": None,
        "used_count": 0,
        "promo_id": None,
        "old_duration": None
    }
    await callback.message.edit_text(PROMO_ENTER_NAME, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

# =====================================
# Редактирование параметров (из финального окна)
# =====================================

@router.callback_query(F.data == "edit_name")
async def edit_name(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "name"
    await callback.message.edit_text(PROMO_ENTER_NAME, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "edit_reward")
async def edit_reward(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "reward"
    await callback.message.edit_text(PROMO_REWARD, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=REWARD_BEER, callback_data="reward_beer"),
         InlineKeyboardButton(text=REWARD_ATTEMPTS, callback_data="reward_attempts")],
        [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
    ]), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "edit_time")
async def edit_time(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "time"
    await callback.message.edit_text(PROMO_TIME_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="time_yes"),
         InlineKeyboardButton(text="Нет", callback_data="time_no")],
        [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
    ]), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "edit_limit")
async def edit_limit(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "activation"
    await callback.message.edit_text(PROMO_ACTIVATION_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="activation_yes"),
         InlineKeyboardButton(text="Нет", callback_data="activation_no")],
        [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
    ]), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "edit_user")
async def edit_user(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "bind"
    await callback.message.edit_text(
        "Введите Telegram user_id пользователей через запятую\nНапример: 123456, 789012",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="bind_yes"),
             InlineKeyboardButton(text="Нет", callback_data="bind_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]),
        parse_mode=ParseMode.HTML
    )

# =====================================
# Выбор награды
# =====================================

@router.callback_query(F.data.startswith("reward_"))
async def reward_select(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    reward = callback.data.replace("reward_", "")
    promo_states[user_id]["reward_type"] = reward
    promo_states[user_id]["step"] = "reward_amount"
    prompt = PROMPT_BEER_AMOUNT if reward == "beer" else PROMPT_ATTEMPTS_AMOUNT
    await callback.message.edit_text(prompt, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

# =====================================
# Обновление списка привязанных пользователей
# =====================================

async def refresh_bind_users_if_needed(state, user_id):
    """Обновляет список привязанных пользователей, исключая уже активировавших."""
    if state.get("bind_users") and state.get("promo_id"):
        db = database.promo_connect()
        cursor = db.cursor()
        cursor.execute("SELECT user_id FROM promo_uses WHERE promo_id=?", (state["promo_id"],))
        used = {row[0] for row in cursor.fetchall()}
        db.close()
        original = state["bind_users"]
        if isinstance(original, list):
            state["bind_users"] = [uid for uid in original if uid not in used]
        elif isinstance(original, str):
            ids = [int(x.strip()) for x in original.split(",") if x.strip()]
            filtered = [uid for uid in ids if uid not in used]
            state["bind_users"] = filtered if filtered else None

# =====================================
# Получение текста от админа
# =====================================

@router.message()
async def promo_input(message: Message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if user_id not in promo_states:
        return
    if message.text and message.text.startswith("/"):
        return

    state = promo_states[user_id]
    text = message.text.strip() if message.text else ""
    from_final = state.get("from_final", False)
    edit_mode = state.get("edit", False)

    if state["step"] == "name":
        error = validate_name(text)
        if error:
            await message.answer(error, parse_mode=ParseMode.HTML)
            return
        state["name"] = text
        if from_final or edit_mode:
            state["from_final"] = False
            await show_final(message, user_id)
            return
        state["step"] = "reward"
        await message.answer(PROMO_REWARD, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=REWARD_BEER, callback_data="reward_beer"),
             InlineKeyboardButton(text=REWARD_ATTEMPTS, callback_data="reward_attempts")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
        return

    if state["step"] == "reward_amount":
        reward_type = state.get("reward_type")
        amount, error = validate_reward_amount(reward_type, text)
        if error:
            await message.answer(error, parse_mode=ParseMode.HTML)
            return
        state["reward_amount"] = amount
        if from_final or edit_mode:
            state["from_final"] = False
            await show_final(message, user_id)
            return
        state["step"] = "time"
        await message.answer(PROMO_TIME_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="time_yes"),
             InlineKeyboardButton(text="Нет", callback_data="time_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
        return

    if state["step"] == "duration":
        error = validate_time(text)
        if error:
            await message.answer(error, parse_mode=ParseMode.HTML)
            return
        state["duration"] = text
        if from_final or edit_mode:
            state["from_final"] = False
            await show_final(message, user_id)
            return
        state["step"] = "activation"
        await message.answer(PROMO_ACTIVATION_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="activation_yes"),
             InlineKeyboardButton(text="Нет", callback_data="activation_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
        return

    if state["step"] == "activations":
        amount, error = validate_activations(text)
        if error:
            await message.answer(error, parse_mode=ParseMode.HTML)
            return
        state["max_activations"] = amount
        if from_final or edit_mode:
            state["from_final"] = False
            await show_final(message, user_id)
            return
        state["step"] = "bind"
        await message.answer(PROMO_BIND_USER, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="bind_yes"),
             InlineKeyboardButton(text="Нет", callback_data="bind_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
        return

    if state["step"] == "user":
        user_ids = []
        for part in text.split(","):
            part = part.strip()
            if part:
                uid, error = validate_user_id(part)
                if error:
                    await message.answer(error, parse_mode=ParseMode.HTML)
                    return
                user_ids.append(uid)
        state["bind_users"] = user_ids
        if edit_mode:
            await refresh_bind_users_if_needed(state, user_id)
        state["from_final"] = False
        await show_final(message, user_id)
        return

# =====================================
# Финальное окно
# =====================================

async def show_final(message_or_callback, user_id):
    data = promo_states[user_id]
    edit_mode = data.get("edit", False)
    if edit_mode and data.get("bind_users"):
        await refresh_bind_users_if_needed(data, user_id)
    data["from_final"] = False

    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(
            PROMO_FINAL.format(name=data["name"]),
            reply_markup=final_keyboard(data, edit_mode),
            parse_mode=ParseMode.HTML
        )
    else:
        await message_or_callback.message.edit_text(
            PROMO_FINAL.format(name=data["name"]),
            reply_markup=final_keyboard(data, edit_mode),
            parse_mode=ParseMode.HTML
        )

# =====================================
# Ограничение по времени
# =====================================

@router.callback_query(F.data == "time_yes")
async def time_yes(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    promo_states[user_id]["time_limited"] = 1
    promo_states[user_id]["step"] = "duration"
    await callback.message.edit_text(PROMO_TIME_INPUT, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "time_no")
async def time_no(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    state = promo_states[user_id]
    state["time_limited"] = 0
    state["duration"] = None
    if state.get("edit") or state.get("from_final"):
        state["from_final"] = False
        await show_final(callback, user_id)
        return
    state["step"] = "activation"
    await callback.message.edit_text(PROMO_ACTIVATION_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="activation_yes"),
         InlineKeyboardButton(text="Нет", callback_data="activation_no")],
        [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
    ]), parse_mode=ParseMode.HTML)

# =====================================
# Ограничение активаций
# =====================================

@router.callback_query(F.data == "activation_yes")
async def activation_yes(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    promo_states[user_id]["activation_limited"] = 1
    promo_states[user_id]["step"] = "activations"
    await callback.message.edit_text(PROMO_ACTIVATION_AMOUNT, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "activation_no")
async def activation_no(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    state = promo_states[user_id]
    state["activation_limited"] = 0
    state["max_activations"] = None
    if state.get("edit") or state.get("from_final"):
        state["from_final"] = False
        await show_final(callback, user_id)
        return
    state["step"] = "bind"
    await callback.message.edit_text(PROMO_BIND_USER, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="bind_yes"),
         InlineKeyboardButton(text="Нет", callback_data="bind_no")],
        [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
    ]), parse_mode=ParseMode.HTML)

# =====================================
# Привязка пользователей
# =====================================

@router.callback_query(F.data == "bind_yes")
async def bind_yes(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    promo_states[user_id]["step"] = "user"
    await callback.message.edit_text(PROMO_BIND_USER_INPUT, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "bind_no")
async def bind_no(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    promo_states[user_id]["bind_users"] = None
    promo_states[user_id]["from_final"] = False
    await show_final(callback, user_id)

# =====================================
# Сохранение промокода
# =====================================

@router.callback_query(F.data == "promo_save")
async def save_promo(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    data = promo_states[user_id]
    if not data.get("name") or not data.get("reward_type"):
        await callback.answer(SAVE_ERROR_EMPTY_FIELDS, show_alert=True)
        return
    existing = database.get_promo(data["name"])
    if existing:
        await callback.answer(SAVE_ERROR_DUPLICATE, show_alert=True)
        return
    database.create_promo(data)
    del promo_states[user_id]
    await callback.message.edit_text(PROMO_SAVED, reply_markup=ok_keyboard(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "promo_save_changes")
async def save_changes(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id not in promo_states: return
    data = promo_states[user_id]
    if not data.get("reward_type"):
        await callback.answer(SAVE_ERROR_EMPTY_FIELDS, show_alert=True)
        return
    database.update_promo(data["old_code"], data)
    del promo_states[user_id]
    await callback.message.edit_text(PROMO_UPDATED, reply_markup=ok_keyboard(), parse_mode=ParseMode.HTML)

# =====================================
# Отмена создания
# =====================================

@router.callback_query(F.data == "promo_cancel")
async def cancel_promo(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id in promo_states:
        del promo_states[user_id]
    await callback.message.edit_text(PROMO_CANCELLED, reply_markup=admin_keyboard(), parse_mode=ParseMode.HTML)

# =====================================
# Назад (возврат на предыдущий шаг)
# =====================================

@router.callback_query(F.data == "promo_back")
async def promo_back(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    user_id = callback.from_user.id
    if user_id not in promo_states:
        await callback.answer(UNKNOWN_CALLBACK, show_alert=True)
        return

    state = promo_states[user_id]
    current_step = state.get("step", "")
    edit_mode = state.get("edit", False)
    from_final = state.get("from_final", False)

    # Если мы были в режиме редактирования отдельного параметра, возвращаемся в финальное окно
    if edit_mode or from_final:
        state["from_final"] = False
        await show_final(callback, user_id)
        return

    # Далее стандартная логика пошагового создания
    if current_step == "name":
        del promo_states[user_id]
        await callback.message.edit_text(PROMO_CANCELLED, reply_markup=admin_keyboard(), parse_mode=ParseMode.HTML)
        return

    if current_step == "user":
        state["step"] = "bind"
        await callback.message.edit_text(PROMO_BIND_USER, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="bind_yes"),
             InlineKeyboardButton(text="Нет", callback_data="bind_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
    elif current_step == "bind":
        state["step"] = "activation"
        await callback.message.edit_text(PROMO_ACTIVATION_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="activation_yes"),
             InlineKeyboardButton(text="Нет", callback_data="activation_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
    elif current_step == "activations":
        state["step"] = "activation"
        await callback.message.edit_text(PROMO_ACTIVATION_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="activation_yes"),
             InlineKeyboardButton(text="Нет", callback_data="activation_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
    elif current_step == "activation":
        state["step"] = "time"
        await callback.message.edit_text(PROMO_TIME_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="time_yes"),
             InlineKeyboardButton(text="Нет", callback_data="time_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
    elif current_step == "duration":
        state["step"] = "time"
        await callback.message.edit_text(PROMO_TIME_LIMIT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="time_yes"),
             InlineKeyboardButton(text="Нет", callback_data="time_no")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
    elif current_step == "time":
        state["step"] = "reward_amount"
        prompt = PROMPT_BEER_AMOUNT if state.get("reward_type") == "beer" else PROMPT_ATTEMPTS_AMOUNT
        await callback.message.edit_text(prompt, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)
    elif current_step == "reward_amount":
        state["step"] = "reward"
        await callback.message.edit_text(PROMO_REWARD, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=REWARD_BEER, callback_data="reward_beer"),
             InlineKeyboardButton(text=REWARD_ATTEMPTS, callback_data="reward_attempts")],
            [InlineKeyboardButton(text="Назад", callback_data="promo_back", icon_custom_emoji_id="5255964497608217438", style="danger")]
        ]), parse_mode=ParseMode.HTML)
    elif current_step == "reward":
        state["step"] = "name"
        await callback.message.edit_text(PROMO_ENTER_NAME, reply_markup=back_keyboard(), parse_mode=ParseMode.HTML)
    else:
        del promo_states[user_id]
        await callback.message.edit_text(PROMO_CANCELLED, reply_markup=admin_keyboard(), parse_mode=ParseMode.HTML)

# =====================================
# Список промокодов (пагинация)
# =====================================

def promo_list_keyboard(promos, page, total_pages, mode):
    buttons = []
    row = []
    for promo in promos:
        display_text = promo[1]
        if mode == "delete" and not promo[14]:
            display_text += " (НР)"
        button = InlineKeyboardButton(text=display_text, callback_data=f"{mode}_select:{promo[1]}")
        row.append(button)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    pages = []
    if page > 1:
        pages.append(InlineKeyboardButton(text="⬅️", callback_data=f"{mode}_page:{page-1}"))
    if total_pages > 1:
        pages.append(InlineKeyboardButton(text=PROMO_PAGE.format(current=page, total=total_pages), callback_data="none"))
    if page < total_pages:
        pages.append(InlineKeyboardButton(text="➡️", callback_data=f"{mode}_page:{page+1}"))
    if pages:
        buttons.append(pages)
    buttons.append([InlineKeyboardButton(text="ВЕРНУТЬСЯ", callback_data="admin_return", icon_custom_emoji_id="5255964497608217438", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def show_promo_list(callback, page, mode):
    if mode == "settings":
        promos = database.get_active_promos_page(page, PROMOS_PER_PAGE)
        total = database.get_active_promos_count()
    else:
        promos = database.get_all_promos_page(page, PROMOS_PER_PAGE)
        total = database.get_all_promos_count()
    total_pages = max(1, (total + PROMOS_PER_PAGE - 1) // PROMOS_PER_PAGE)
    if not promos:
        await callback.message.edit_text(PROMO_NO_FOUND, reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="ВЕРНУТЬСЯ", callback_data="admin_return", icon_custom_emoji_id="5255964497608217438", style="danger")]]
        ), parse_mode=ParseMode.HTML)
        return
    text = PROMO_SETTINGS_SELECT if mode == "settings" else PROMO_DELETE_SELECT
    await callback.message.edit_text(text, reply_markup=promo_list_keyboard(promos, page, total_pages, mode), parse_mode=ParseMode.HTML)

# =====================================
# Настройка промокодов
# =====================================

@router.callback_query(F.data == "promo_settings")
async def promo_settings(callback: CallbackQuery):
    if not await check_admin(callback): return
    await show_promo_list(callback, 1, "settings")

@router.callback_query(F.data.startswith("settings_page:"))
async def settings_page(callback: CallbackQuery):
    if not await check_admin(callback): return
    page = int(callback.data.split(":")[1])
    await show_promo_list(callback, page, "settings")

@router.callback_query(F.data.startswith("settings_select:"))
async def settings_select(callback: CallbackQuery):
    if not await check_admin(callback): return
    code = callback.data.split(":")[1]
    promo = database.get_promo(code)
    if not promo:
        return

    promo_id = promo[0]
    used_count = promo[9] if promo[9] is not None else 0
    bind_users_raw = promo[10]
    created_at_str = promo[12]
    old_duration = promo[6]

    db = database.promo_connect()
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM promo_uses WHERE promo_id=?", (promo_id,))
    used_users = {row[0] for row in cursor.fetchall()}
    db.close()

    filtered_bind = None
    if bind_users_raw:
        ids = [int(x.strip()) for x in bind_users_raw.split(",") if x.strip()]
        filtered = [uid for uid in ids if uid not in used_users]
        filtered_bind = filtered if filtered else None

    created_at = None
    if created_at_str:
        try:
            created_at = datetime.strptime(created_at_str, "%d.%m.%Y %H:%M")
        except ValueError:
            pass

    promo_states[callback.from_user.id] = {
        "edit": True,
        "from_final": False,
        "old_code": code,
        "name": promo[1],
        "reward_type": promo[2],
        "reward_amount": promo[3],
        "time_limited": promo[4],
        "expires_at": promo[5],
        "duration": old_duration,
        "activation_limited": promo[7],
        "max_activations": promo[8],
        "used_count": used_count,
        "bind_users": filtered_bind,
        "created_at": created_at,
        "promo_id": promo_id,
        "old_duration": old_duration
    }

    await callback.message.edit_text(
        PROMO_EDIT_TITLE.format(name=code),
        reply_markup=final_keyboard(promo_states[callback.from_user.id], edit_mode=True),
        parse_mode=ParseMode.HTML
    )

# =====================================
# Удаление промокодов
# =====================================

@router.callback_query(F.data == "promo_delete")
async def promo_delete(callback: CallbackQuery):
    if not await check_admin(callback): return
    await show_promo_list(callback, 1, "delete")

@router.callback_query(F.data.startswith("delete_page:"))
async def delete_page(callback: CallbackQuery):
    if not await check_admin(callback): return
    page = int(callback.data.split(":")[1])
    await show_promo_list(callback, page, "delete")

@router.callback_query(F.data.startswith("delete_select:"))
async def delete_select(callback: CallbackQuery):
    if not await check_admin(callback): return
    code = callback.data.split(":")[1]
    await callback.message.edit_text(PROMO_DELETE_CONFIRM.format(name=code), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Удалить", callback_data=f"delete_confirm:{code}", icon_custom_emoji_id="5445267414562389170", style="danger"),
         InlineKeyboardButton(text="Назад", callback_data="delete_cancel", icon_custom_emoji_id="5255964497608217438", style="success")]
    ]), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("delete_confirm:"))
async def delete_confirm(callback: CallbackQuery):
    if not await check_admin(callback): return
    code = callback.data.split(":")[1]
    await callback.message.edit_text(PROMO_DELETE_SECOND_CONFIRM, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Точно уверен", callback_data=f"delete_final:{code}", style="success", icon_custom_emoji_id="5454096630372379732"),
         InlineKeyboardButton(text="Назад", callback_data="delete_cancel", icon_custom_emoji_id="5255964497608217438", style="danger")]
    ]), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("delete_final:"))
async def delete_final(callback: CallbackQuery):
    if not await check_admin(callback): return
    code = callback.data.split(":")[1]
    database.delete_promo(code)
    await callback.message.edit_text(PROMO_DELETED, reply_markup=ok_keyboard(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "delete_cancel")
async def delete_cancel(callback: CallbackQuery):
    if not await check_admin(callback): return
    await show_promo_list(callback, 1, "delete")

# =====================================
# Возврат в админ-панель
# =====================================

@router.callback_query(F.data == "admin_return")
async def admin_return(callback: CallbackQuery):
    if not await check_admin(callback): return
    user_id = callback.from_user.id
    if user_id in promo_states:
        del promo_states[user_id]
    await callback.message.edit_text(ADMIN_PANEL, reply_markup=admin_keyboard(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "none")
async def none_callback(callback: CallbackQuery):
    await callback.answer()

@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer(UNKNOWN_CALLBACK, show_alert=True)