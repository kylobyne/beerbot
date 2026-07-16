# admin.py

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
import re
from datetime import datetime

from messages import *
import database
from config import admins

router = Router()

# Временное хранилище создания/редактирования промокодов
promo_states = {}

# =====================================
# Проверка админа
# =====================================

def is_admin(user_id: int):
    return user_id in admins

async def check_admin(callback):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return False
    return True

# =====================================
# Валидаторы
# =====================================

def validate_name(name: str) -> str | None:
    """Проверка названия промокода: латиница + цифры, до 16 символов."""
    if not name:
        return "Название не может быть пустым"
    
    if " " in name:
        return PROMO_NAME_SPACE_ERROR
    
    if len(name) > 16:
        return "Название не должно превышать 16 символов"
    
    if not re.match(r'^[a-zA-Z0-9]+$', name):
        return "Название должно содержать только латинские буквы и цифры"
    
    return None

def validate_reward_amount(reward_type: str, amount_str: str) -> tuple[int | float | None, str | None]:
    """
    Проверяет количество награды.
    Пиво: целое или дробное (до 2 знаков после точки).
    Доп. попытки: целое число.
    Возвращает (распарсенное_значение, ошибка).
    """
    if not amount_str:
        return None, "Введите количество"
    
    try:
        if reward_type == "beer":
            amount = float(amount_str)
            if amount <= 0:
                return None, "Количество пива должно быть положительным числом"
            if '.' in amount_str and len(amount_str.split('.')[1]) > 2:
                return None, "Допускается не более двух знаков после точки"
            return amount, None
        
        elif reward_type == "attempts":
            if '.' in amount_str:
                return None, "Количество попыток должно быть целым числом"
            amount = int(amount_str)
            if amount <= 0:
                return None, "Количество попыток должно быть положительным числом"
            return amount, None
        
        else:
            return None, "Неизвестный тип награды"
    
    except ValueError:
        return None, "Введите корректное число"

def validate_time(duration: str) -> str | None:
    """
    Проверка формата времени.
    ДД.ММ.ГГ, ДД.ММ.ГГГГ или 2h, 3h, 2h5s.
    """
    if not duration:
        return "Введите дату или длительность"
    
    duration = duration.strip()
    
    # Формат ДД.ММ.ГГ или ДД.ММ.ГГГГ
    date_patterns = [
        r'^\d{2}\.\d{2}\.\d{2}$',
        r'^\d{2}\.\d{2}\.\d{4}$'
    ]
    
    for pattern in date_patterns:
        if re.match(pattern, duration):
            try:
                if len(duration.split('.')[2]) == 2:
                    datetime.strptime(duration, "%d.%m.%y")
                else:
                    datetime.strptime(duration, "%d.%m.%Y")
                return None
            except ValueError:
                return "Некорректная дата"
    
    # Формат длительности
    duration_pattern = r'^(\d+h)?(\d+m)?(\d+s)?$'
    if re.match(duration_pattern, duration) and duration:
        if any(unit in duration for unit in ['h', 'm', 's']):
            return None
    
    return "Неверный формат. Используйте ДД.ММ.ГГ или 2h, 3h, 2h5s"

def validate_activations(amount_str: str) -> tuple[int | None, str | None]:
    """Проверка количества активаций: целое положительное число."""
    if not amount_str:
        return None, "Введите количество активаций"
    
    try:
        if '.' in amount_str:
            return None, PROMO_NUMBER_ERROR
        amount = int(amount_str)
        if amount <= 0:
            return None, "Количество активаций должно быть положительным числом"
        return amount, None
    except ValueError:
        return None, PROMO_NUMBER_ERROR

def validate_user_id(user_id_str: str) -> tuple[int | None, str | None]:
    """Проверка Telegram user_id: целое число."""
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
# Клавиатуры
# =====================================

def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_CREATE_PROMO,
                    callback_data="promo_create"
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN_SETTINGS_PROMO,
                    callback_data="promo_settings"
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN_DELETE_PROMO,
                    callback_data="promo_delete"
                )
            ]
        ]
    )

def back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_BACK,
                    callback_data="promo_back",
                    icon_custom_emoji_id="5255964497608217438",
                    style="danger"
                )
            ]
        ]
    )

def final_keyboard(code, edit_mode=False):
    """Клавиатура финального подтверждения."""
    
    name_display = code.get('name', '—')
    
    reward_display = code.get('reward_type', '—')
    if code.get('reward_amount'):
        reward_display += f" ({code['reward_amount']})"
    
    time_display = 'Ограничено' if code.get('time_limited') else 'Без ограничений'
    if code.get('duration'):
        time_display += f": {code['duration']}"
    
    limit_display = str(code.get('max_activations')) if code.get('activation_limited') else 'Без ограничений'
    
    user_display = str(code.get('bind_user')) if code.get('bind_user') else 'Нет'
    
    save_button = InlineKeyboardButton(
        text=BTN_SAVE_CHANGES if edit_mode else BTN_SAVE,
        callback_data="promo_save_changes" if edit_mode else "promo_save",
        icon_custom_emoji_id="5256216509109272955",
        style="success"
    )
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Название: {name_display}",
                    callback_data="edit_name",
                    icon_custom_emoji_id="5281015457002852972"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Награда: {reward_display}",
                    callback_data="edit_reward",
                    icon_custom_emoji_id="5278563335619512182"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Время: {time_display}",
                    callback_data="edit_time",
                    icon_custom_emoji_id="5256137370041879472"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Лимит активаций: {limit_display}",
                    callback_data="edit_limit",
                    icon_custom_emoji_id="5256116200148075808"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Пользователь: {user_display}",
                    callback_data="edit_user",
                    icon_custom_emoji_id="5280472444287616361"
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN_CANCEL,
                    callback_data="promo_cancel",
                    icon_custom_emoji_id="5255933371980223131",
                    style="danger"
                ),
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
    
    await message.answer(
        ADMIN_PANEL,
        reply_markup=admin_keyboard()
    )

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
        "from_final": False,  # ← флаг: перешли ли из финального окна
        "step": "name",
        "name": None,
        "reward_type": None,
        "reward_amount": 0,
        "duration": None,
        "time_limited": 0,
        "max_activations": None,
        "activation_limited": 0,
        "bind_user": None
    }
    
    await callback.message.edit_text(
        PROMO_ENTER_NAME,
        reply_markup=back_keyboard()
    )

# =====================================
# Редактирование параметров (из финального окна)
# =====================================

@router.callback_query(F.data == "edit_name")
async def edit_name(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    # Устанавливаем флаг — пришли из финального окна
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "name"
    
    await callback.message.edit_text(
        PROMO_ENTER_NAME,
        reply_markup=back_keyboard()
    )

@router.callback_query(F.data == "edit_reward")
async def edit_reward(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "reward"
    
    await callback.message.edit_text(
        PROMO_REWARD,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=REWARD_BEER,
                        callback_data="reward_beer"
                    ),
                    InlineKeyboardButton(
                        text=REWARD_ATTEMPTS,
                        callback_data="reward_attempts"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_BACK,
                        callback_data="promo_back",
                        icon_custom_emoji_id="5255964497608217438",
                        style="danger"
                    )
                ]
            ]
        )
    )

@router.callback_query(F.data == "edit_time")
async def edit_time(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "time"
    
    await callback.message.edit_text(
        PROMO_TIME_LIMIT,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да",
                        callback_data="time_yes"
                    ),
                    InlineKeyboardButton(
                        text="Нет",
                        callback_data="time_no"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_BACK,
                        callback_data="promo_back",
                        icon_custom_emoji_id="5255964497608217438",
                        style="danger"
                    )
                ]
            ]
        )
    )

@router.callback_query(F.data == "edit_limit")
async def edit_limit(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "activation"
    
    await callback.message.edit_text(
        PROMO_ACTIVATION_LIMIT,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да",
                        callback_data="activation_yes"
                    ),
                    InlineKeyboardButton(
                        text="Нет",
                        callback_data="activation_no"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_BACK,
                        callback_data="promo_back",
                        icon_custom_emoji_id="5255964497608217438",
                        style="danger"
                    )
                ]
            ]
        )
    )

@router.callback_query(F.data == "edit_user")
async def edit_user(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    promo_states[user_id]["from_final"] = True
    promo_states[user_id]["step"] = "bind"
    
    await callback.message.edit_text(
        PROMO_BIND_USER,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да",
                        callback_data="bind_yes"
                    ),
                    InlineKeyboardButton(
                        text="Нет",
                        callback_data="bind_no"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_BACK,
                        callback_data="promo_back",
                        icon_custom_emoji_id="5255964497608217438",
                        style="danger"
                    )
                ]
            ]
        )
    )

# =====================================
# Выбор награды
# =====================================

@router.callback_query(F.data.startswith("reward_"))
async def reward_select(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    reward = callback.data.replace("reward_", "")
    
    promo_states[user_id]["reward_type"] = reward
    promo_states[user_id]["step"] = "reward_amount"
    
    if reward == "beer":
        prompt = "Введите количество литров пива\n(целое или дробное число, до 2 знаков после точки):"
    else:
        prompt = "Введите количество дополнительных попыток\n(целое число):"
    
    await callback.message.edit_text(
        prompt,
        reply_markup=back_keyboard()
    )

# =====================================
# Получение текста от админа
# =====================================

@router.message()
async def promo_input(message: Message):
    """Обработка текстового ввода на разных шагах."""
    
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
    
    # ========== Шаг: ввод названия ==========
    if state["step"] == "name":
        error = validate_name(text)
        if error:
            await message.answer(error)
            return
        
        state["name"] = text
        
        # Если пришли из финального окна (создание или редактирование) — возвращаемся назад
        if from_final or edit_mode:
            state["from_final"] = False
            await show_final(message, user_id)
            return
        
        # Иначе — продолжаем по шагам создания
        state["step"] = "reward"
        
        await message.answer(
            PROMO_REWARD,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=REWARD_BEER,
                            callback_data="reward_beer"
                        ),
                        InlineKeyboardButton(
                            text=REWARD_ATTEMPTS,
                            callback_data="reward_attempts"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
        return
    
    # ========== Шаг: ввод количества награды ==========
    if state["step"] == "reward_amount":
        reward_type = state.get("reward_type")
        amount, error = validate_reward_amount(reward_type, text)
        
        if error:
            await message.answer(error)
            return
        
        state["reward_amount"] = amount
        
        # Если пришли из финального окна — возвращаемся
        if from_final or edit_mode:
            state["from_final"] = False
            await show_final(message, user_id)
            return
        
        # Иначе — продолжаем
        state["step"] = "time"
        
        await message.answer(
            PROMO_TIME_LIMIT,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Да",
                            callback_data="time_yes"
                        ),
                        InlineKeyboardButton(
                            text="Нет",
                            callback_data="time_no"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
        return
    
    # ========== Шаг: ввод времени ==========
    if state["step"] == "duration":
        error = validate_time(text)
        if error:
            await message.answer(error)
            return
        
        state["duration"] = text
        
        # Если пришли из финального окна — возвращаемся
        if from_final or edit_mode:
            state["from_final"] = False
            await show_final(message, user_id)
            return
        
        # Иначе — продолжаем
        state["step"] = "activation"
        
        await message.answer(
            PROMO_ACTIVATION_LIMIT,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Да",
                            callback_data="activation_yes"
                        ),
                        InlineKeyboardButton(
                            text="Нет",
                            callback_data="activation_no"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
        return
    
    # ========== Шаг: ввод количества активаций ==========
    if state["step"] == "activations":
        amount, error = validate_activations(text)
        if error:
            await message.answer(error)
            return
        
        state["max_activations"] = amount
        
        # Если пришли из финального окна — возвращаемся
        if from_final or edit_mode:
            state["from_final"] = False
            await show_final(message, user_id)
            return
        
        # Иначе — продолжаем
        state["step"] = "bind"
        
        await message.answer(
            PROMO_BIND_USER,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Да",
                            callback_data="bind_yes"
                        ),
                        InlineKeyboardButton(
                            text="Нет",
                            callback_data="bind_no"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
        return
    
    # ========== Шаг: ввод user_id для привязки ==========
    if state["step"] == "user":
        user_id_bind, error = validate_user_id(text)
        if error:
            await message.answer(error)
            return
        
        state["bind_user"] = user_id_bind
        state["from_final"] = False
        
        # Всегда возвращаемся в финальное окно
        await show_final(message, user_id)

# =====================================
# Финальное окно
# =====================================

async def show_final(message_or_callback, user_id):
    data = promo_states[user_id]
    edit_mode = data.get("edit", False)
    
    # Сбрасываем флаг from_final при показе финального окна
    data["from_final"] = False
    
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(
            PROMO_FINAL.format(name=data["name"]),
            reply_markup=final_keyboard(data, edit_mode)
        )
    else:
        await message_or_callback.message.edit_text(
            PROMO_FINAL.format(name=data["name"]),
            reply_markup=final_keyboard(data, edit_mode)
        )

# =====================================
# Ограничение по времени
# =====================================

@router.callback_query(F.data == "time_yes")
async def time_yes(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    promo_states[user_id]["time_limited"] = 1
    promo_states[user_id]["step"] = "duration"
    
    await callback.message.edit_text(
        PROMO_TIME_INPUT,
        reply_markup=back_keyboard()
    )

@router.callback_query(F.data == "time_no")
async def time_no(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    state = promo_states[user_id]
    state["time_limited"] = 0
    state["duration"] = None
    
    # Если редактирование или пришли из финала — сразу в финал
    if state.get("edit") or state.get("from_final"):
        state["from_final"] = False
        await show_final(callback, user_id)
        return
    
    # Иначе — продолжаем по шагам
    state["step"] = "activation"
    
    await callback.message.edit_text(
        PROMO_ACTIVATION_LIMIT,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да",
                        callback_data="activation_yes"
                    ),
                    InlineKeyboardButton(
                        text="Нет",
                        callback_data="activation_no"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_BACK,
                        callback_data="promo_back",
                        icon_custom_emoji_id="5255964497608217438",
                        style="danger"
                    )
                ]
            ]
        )
    )

# =====================================
# Ограничение активаций
# =====================================

@router.callback_query(F.data == "activation_yes")
async def activation_yes(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    promo_states[user_id]["activation_limited"] = 1
    promo_states[user_id]["step"] = "activations"
    
    await callback.message.edit_text(
        PROMO_ACTIVATION_AMOUNT,
        reply_markup=back_keyboard()
    )

@router.callback_query(F.data == "activation_no")
async def activation_no(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    state = promo_states[user_id]
    state["activation_limited"] = 0
    state["max_activations"] = None
    
    # Если редактирование или пришли из финала — сразу в финал
    if state.get("edit") or state.get("from_final"):
        state["from_final"] = False
        await show_final(callback, user_id)
        return
    
    # Иначе — продолжаем
    state["step"] = "bind"
    
    await callback.message.edit_text(
        PROMO_BIND_USER,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да",
                        callback_data="bind_yes"
                    ),
                    InlineKeyboardButton(
                        text="Нет",
                        callback_data="bind_no"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_BACK,
                        callback_data="promo_back",
                        icon_custom_emoji_id="5255964497608217438",
                        style="danger"
                    )
                ]
            ]
        )
    )

# =====================================
# Привязка пользователя
# =====================================

@router.callback_query(F.data == "bind_yes")
async def bind_yes(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    promo_states[user_id]["step"] = "user"
    
    await callback.message.edit_text(
        PROMO_BIND_USER_INPUT,
        reply_markup=back_keyboard()
    )

@router.callback_query(F.data == "bind_no")
async def bind_no(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    promo_states[user_id]["bind_user"] = None
    promo_states[user_id]["from_final"] = False
    
    await show_final(callback, user_id)

# =====================================
# Клавиатура "Ок" после сохранения
# =====================================

def ok_keyboard():
    """Клавиатура с кнопкой Ок для возврата в админ-панель."""
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

# =====================================
# Сохранение промокода
# =====================================

@router.callback_query(F.data == "promo_save")
async def save_promo(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    data = promo_states[user_id]
    
    if not data.get("name") or not data.get("reward_type"):
        await callback.answer(
            "Заполните все обязательные поля",
            show_alert=True
        )
        return
    
    existing = database.get_promo(data["name"])
    if existing:
        await callback.answer(
            "Промокод с таким названием уже существует",
            show_alert=True
        )
        return
    
    database.create_promo(data)
    del promo_states[user_id]
    
    await callback.message.edit_text(
        PROMO_SAVED,
        reply_markup=ok_keyboard()
    )

@router.callback_query(F.data == "promo_save_changes")
async def save_changes(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    data = promo_states[user_id]
    
    if not data.get("reward_type"):
        await callback.answer(
            "Заполните все обязательные поля",
            show_alert=True
        )
        return
    
    database.update_promo(data["old_code"], data)
    del promo_states[user_id]
    
    await callback.message.edit_text(
        PROMO_UPDATED,
        reply_markup=ok_keyboard()
    )
# =====================================
# Отмена создания
# =====================================

@router.callback_query(F.data == "promo_cancel")
async def cancel_promo(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id in promo_states:
        del promo_states[user_id]
    
    await callback.message.edit_text(
        PROMO_CANCELLED,
        reply_markup=admin_keyboard()
    )

# =====================================
# Назад
# =====================================

@router.callback_query(F.data == "promo_back")
async def promo_back(callback: CallbackQuery):
    """
    Кнопка Назад.
    - Если from_final=True или edit=True — возвращает в финальное окно.
    - Если шаг "name" при создании — возвращает в админ-панель.
    - Иначе — возвращает на предыдущий шаг создания.
    """
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id not in promo_states:
        return
    
    state = promo_states[user_id]
    current_step = state.get("step", "")
    edit_mode = state.get("edit", False)
    from_final = state.get("from_final", False)
    
    # Если редактирование или пришли из финала — всегда в финальное окно
    if edit_mode or from_final:
        state["from_final"] = False
        await show_final(callback, user_id)
        return
    
    # ========== Особый случай: шаг "name" при создании — возврат в админ-панель ==========
    if current_step == "name" and not edit_mode:
        del promo_states[user_id]
        await callback.message.edit_text(
            PROMO_CANCELLED,
            reply_markup=admin_keyboard()
        )
        return
    
    # ========== При создании: возврат на шаг назад ==========
    
    if current_step in ("user",):
        state["step"] = "bind"
        await callback.message.edit_text(
            PROMO_BIND_USER,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Да",
                            callback_data="bind_yes"
                        ),
                        InlineKeyboardButton(
                            text="Нет",
                            callback_data="bind_no"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
    
    elif current_step == "bind":
        state["step"] = "activation"
        await callback.message.edit_text(
            PROMO_ACTIVATION_LIMIT,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Да",
                            callback_data="activation_yes"
                        ),
                        InlineKeyboardButton(
                            text="Нет",
                            callback_data="activation_no"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
    
    elif current_step == "activations":
        state["step"] = "activation"
        await callback.message.edit_text(
            PROMO_ACTIVATION_LIMIT,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Да",
                            callback_data="activation_yes"
                        ),
                        InlineKeyboardButton(
                            text="Нет",
                            callback_data="activation_no"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
    
    elif current_step == "activation":
        state["step"] = "time"
        await callback.message.edit_text(
            PROMO_TIME_LIMIT,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Да",
                            callback_data="time_yes"
                        ),
                        InlineKeyboardButton(
                            text="Нет",
                            callback_data="time_no"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
    
    elif current_step == "duration":
        state["step"] = "time"
        await callback.message.edit_text(
            PROMO_TIME_LIMIT,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Да",
                            callback_data="time_yes"
                        ),
                        InlineKeyboardButton(
                            text="Нет",
                            callback_data="time_no"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
    
    elif current_step == "time":
        state["step"] = "reward_amount"
        
        reward_type = state.get("reward_type", "beer")
        if reward_type == "beer":
            prompt = "Введите количество литров пива\n(целое или дробное число, до 2 знаков после точки):"
        else:
            prompt = "Введите количество дополнительных попыток\n(целое число):"
        
        await callback.message.edit_text(
            prompt,
            reply_markup=back_keyboard()
        )
    
    elif current_step == "reward_amount":
        state["step"] = "reward"
        await callback.message.edit_text(
            PROMO_REWARD,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=REWARD_BEER,
                            callback_data="reward_beer"
                        ),
                        InlineKeyboardButton(
                            text=REWARD_ATTEMPTS,
                            callback_data="reward_attempts"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=BTN_BACK,
                            callback_data="promo_back",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
    
    elif current_step == "reward":
        state["step"] = "name"
        await callback.message.edit_text(
            PROMO_ENTER_NAME,
            reply_markup=back_keyboard()
        )
    
    else:
        # Защита: если что-то пошло не так — возврат в админ-панель
        del promo_states[user_id]
        await callback.message.edit_text(
            PROMO_CANCELLED,
            reply_markup=admin_keyboard()
        )
# =====================================
# Список промокодов (пагинация)
# =====================================

PROMOS_PER_PAGE = 10

def promo_list_keyboard(promos, page, total_pages, mode):
    buttons = []
    row = []
    
    for promo in promos:
        button = InlineKeyboardButton(
            text=promo[1],
            callback_data=f"{mode}_select:{promo[1]}"
        )
        row.append(button)
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    pages = []
    
    if page > 1:
        pages.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{mode}_page:{page-1}"
            )
        )
    
    if total_pages > 1:
        pages.append(
            InlineKeyboardButton(
                text=PROMO_PAGE.format(current=page, total=total_pages),
                callback_data="none"
            )
        )
    
    if page < total_pages:
        pages.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{mode}_page:{page+1}"
            )
        )
    
    if pages:
        buttons.append(pages)
    
    buttons.append(
        [
            InlineKeyboardButton(
                text=BTN_RETURN,
                callback_data="admin_return",
                icon_custom_emoji_id="5255964497608217438",
                style="danger"
            )
        ]
    )
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def show_promo_list(callback, page, mode):
    promos = database.get_promos_page(page, PROMOS_PER_PAGE)
    total = database.get_promos_count()
    total_pages = max(1, (total + PROMOS_PER_PAGE - 1) // PROMOS_PER_PAGE)
    
    if not promos:
        await callback.message.edit_text(
            PROMO_NO_FOUND,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=BTN_RETURN,
                            callback_data="admin_return",
                            icon_custom_emoji_id="5255964497608217438",
                            style="danger"
                        )
                    ]
                ]
            )
        )
        return
    
    text = PROMO_SETTINGS_SELECT if mode == "settings" else PROMO_DELETE_SELECT
    
    await callback.message.edit_text(
        text,
        reply_markup=promo_list_keyboard(promos, page, total_pages, mode)
    )

# =====================================
# Настройка промокодов
# =====================================

@router.callback_query(F.data == "promo_settings")
async def promo_settings(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    await show_promo_list(callback, 1, "settings")

@router.callback_query(F.data.startswith("settings_page:"))
async def settings_page(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    page = int(callback.data.split(":")[1])
    await show_promo_list(callback, page, "settings")

@router.callback_query(F.data.startswith("settings_select:"))
async def settings_select(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    code = callback.data.split(":")[1]
    promo = database.get_promo(code)
    
    if not promo:
        return
    
    promo_states[callback.from_user.id] = {
        "edit": True,
        "from_final": False,
        "old_code": code,
        "name": promo[1],
        "reward_type": promo[2],
        "reward_amount": promo[3],
        "time_limited": promo[4],
        "expires_at": promo[5],
        "duration": promo[6],
        "activation_limited": promo[7],
        "max_activations": promo[8],
        "bind_user": promo[10]
    }
    
    await callback.message.edit_text(
        PROMO_EDIT_TITLE.format(name=code),
        reply_markup=final_keyboard(
            promo_states[callback.from_user.id],
            edit_mode=True
        )
    )

# =====================================
# Удаление промокодов
# =====================================

@router.callback_query(F.data == "promo_delete")
async def promo_delete(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    await show_promo_list(callback, 1, "delete")

@router.callback_query(F.data.startswith("delete_page:"))
async def delete_page(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    page = int(callback.data.split(":")[1])
    await show_promo_list(callback, page, "delete")

@router.callback_query(F.data.startswith("delete_select:"))
async def delete_select(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    code = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        PROMO_DELETE_CONFIRM.format(name=code),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=BTN_DELETE,
                        callback_data=f"delete_confirm:{code}",
                        icon_custom_emoji_id="5445267414562389170",
                        style="danger"
                    ),
                    InlineKeyboardButton(
                        text=BTN_BACK,
                        callback_data="delete_cancel",
                        icon_custom_emoji_id="5255964497608217438",
                        style="danger"
                    )
                ]
            ]
        )
    )

@router.callback_query(F.data.startswith("delete_confirm:"))
async def delete_confirm(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    code = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        PROMO_DELETE_SECOND_CONFIRM,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=BTN_CONFIRM_DELETE,
                        callback_data=f"delete_final:{code}",
                        style="success",
                        icon_custom_emoji_id="5454096630372379732"
                    ),
                    InlineKeyboardButton(
                        text=BTN_BACK,
                        callback_data="delete_cancel",
                        icon_custom_emoji_id="5255964497608217438",
                        style="danger"
                    )
                ]
            ]
        )
    )

@router.callback_query(F.data.startswith("delete_final:"))
async def delete_final(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    code = callback.data.split(":")[1]
    database.delete_promo(code)
    
    await callback.message.edit_text(
        PROMO_DELETED,
        reply_markup=ok_keyboard()
    )

@router.callback_query(F.data == "delete_cancel")
async def delete_cancel(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    await show_promo_list(callback, 1, "delete")

# =====================================
# Возврат в админ-панель
# =====================================

@router.callback_query(F.data == "admin_return")
async def admin_return(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    
    user_id = callback.from_user.id
    if user_id in promo_states:
        del promo_states[user_id]
    
    await callback.message.edit_text(
        ADMIN_PANEL,
        reply_markup=admin_keyboard()
    )

# =====================================
# Заглушка для неактивных кнопок
# =====================================

@router.callback_query(F.data == "none")
async def none_callback(callback: CallbackQuery):
    await callback.answer()

# =====================================
# Обработчик неизвестных callback
# =====================================

@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery):
    """Отлавливает все неизвестные callback_data."""
    if not is_admin(callback.from_user.id):
        return
    
    await callback.answer(
        "Действие не распознано. Попробуйте снова.",
        show_alert=True
    )