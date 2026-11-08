import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MOD_ADMINS_PAGE_SIZE, MOD_AUDIT_PAGE_SIZE, MOD_HISTORY_PAGE_SIZE
import database
from handlers.ephemeral import send_ephemeral_message
import messages
from time_utils import format_timestamp


router = Router()

PERMISSIONS = {
    "audit": "Просмотр аудита",
    "ban": "Ограничение питья",
    "history": "Просмотр истории питья",
}
ADMIN_STATUSES = {"creator", "administrator"}


async def member_status(bot, chat_id: int, user_id: int) -> str | None:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except TelegramAPIError:
        return None

    if member.status not in ADMIN_STATUSES:
        database.clear_mod_permissions(chat_id, user_id)

    return member.status


async def has_permission(bot, chat_id: int, user_id: int, permission: str) -> bool:
    status = await member_status(bot, chat_id, user_id)
    if status == "creator":
        return True
    if status != "administrator":
        return False
    return database.get_mod_permissions(chat_id, user_id).get(permission, False)


async def is_owner(bot, chat_id: int, user_id: int) -> bool:
    return await member_status(bot, chat_id, user_id) == "creator"


@router.chat_member()
async def clear_permissions_after_demotion(event: ChatMemberUpdated):
    target_id = event.new_chat_member.user.id
    if event.new_chat_member.status in ADMIN_STATUSES:
        return

    existing_permissions = database.get_mod_permissions(event.chat.id, target_id)
    if not existing_permissions:
        return

    status = await member_status(event.bot, event.chat.id, target_id)
    if status is None or status in ADMIN_STATUSES:
        return

    database.record_mod_audit(
        event.chat.id,
        event.from_user.id,
        "permissions_cleared_after_demotion",
        target_id,
    )


async def delete_command_message(message: Message):
    if message.ephemeral_message_id is not None:
        return
    try:
        await message.delete()
    except TelegramAPIError:
        logging.warning("Could not delete /mod command in chat %s", message.chat.id)


async def answer_ephemerally(
    message: Message,
    text: str,
    reply_markup=None,
):
    if not message.from_user:
        return

    try:
        await send_ephemeral_message(
            bot=message.bot,
            chat_id=message.chat.id,
            receiver_user_id=message.from_user.id,
            text=text,
            reply_markup=reply_markup,
            reply_to_ephemeral_id=message.ephemeral_message_id,
        )
    except TelegramAPIError:
        logging.exception("Could not send ephemeral /mod response in chat %s", message.chat.id)


async def edit_ephemerally(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
):
    message = callback.message
    if not message:
        await callback.answer("Сообщение меню недоступно.", show_alert=True)
        return

    ephemeral_id = getattr(message, "ephemeral_message_id", None)
    try:
        if ephemeral_id is not None:
            await callback.bot.edit_ephemeral_message_text(
                chat_id=message.chat.id,
                receiver_user_id=callback.from_user.id,
                ephemeral_message_id=ephemeral_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        else:
            await send_ephemeral_message(
                bot=callback.bot,
                chat_id=message.chat.id,
                receiver_user_id=callback.from_user.id,
                text=text,
                reply_markup=reply_markup,
                callback_query_id=callback.id,
                replace_callback_query_message=True,
            )
        await callback.answer()
    except TelegramAPIError:
        logging.exception("Could not update ephemeral /mod menu")
        await callback.answer("Не удалось обновить меню.", show_alert=True)


def main_keyboard(permissions: dict[str, bool], owner: bool):
    builder = InlineKeyboardBuilder()
    if owner or permissions.get("audit"):
        builder.button(text="Журнал аудита", callback_data="mod:audit")
    if owner:
        builder.button(text="Настройки прав", callback_data="mod:admins")
    builder.adjust(1)
    return builder.as_markup() if builder.buttons else None


async def render_main(callback: CallbackQuery):
    message = callback.message
    if not message:
        await callback.answer("Сообщение меню недоступно.", show_alert=True)
        return

    chat_id = message.chat.id
    user_id = callback.from_user.id
    status = await member_status(callback.bot, chat_id, user_id)
    if status not in ADMIN_STATUSES:
        await callback.answer("Только администраторы чата могут открыть /mod.", show_alert=True)
        return

    owner = status == "creator"
    permissions = database.get_mod_permissions(chat_id, user_id)
    text = (
        "<b>Модерация чата</b>\n\n"
        "<code>/mod history</code> — история питья пользователя\n"
        "<code>/mod ban</code> — запретить пить\n"
        "<code>/mod unban</code> — снять запрет\n\n"
        "Цель можно указать ответом на сообщение, числовым ID или username."
    )
    await edit_ephemerally(
        callback,
        text,
        main_keyboard(permissions, owner),
    )


async def current_admins(bot, chat_id: int):
    try:
        members = await bot.get_chat_administrators(chat_id)
    except TelegramAPIError:
        return None
    return [
        member.user
        for member in members
        if member.status == "administrator" and not member.user.is_bot
    ]


async def render_admins(callback: CallbackQuery, page: int = 0):
    message = callback.message
    if not message:
        await callback.answer("Сообщение меню недоступно.", show_alert=True)
        return

    chat_id = message.chat.id
    user_id = callback.from_user.id
    if not await is_owner(callback.bot, chat_id, user_id):
        await callback.answer("Настраивать права может только владелец чата.", show_alert=True)
        return

    admins = await current_admins(callback.bot, chat_id)
    if admins is None:
        await callback.answer("Не удалось загрузить список администраторов.", show_alert=True)
        return

    total_pages = max(1, (len(admins) + MOD_ADMINS_PAGE_SIZE - 1) // MOD_ADMINS_PAGE_SIZE)
    page = min(max(0, page), total_pages - 1)
    page_admins = admins[page * MOD_ADMINS_PAGE_SIZE:(page + 1) * MOD_ADMINS_PAGE_SIZE]

    builder = InlineKeyboardBuilder()
    for admin in page_admins:
        builder.button(
            text=admin.full_name,
            callback_data=f"mod:admin:{admin.id}:{page}",
        )
    navigation_buttons = 0
    if page > 0:
        builder.button(text="◀️", callback_data=f"mod:admins:{page - 1}")
        navigation_buttons += 1
    if page < total_pages - 1:
        builder.button(text="▶️", callback_data=f"mod:admins:{page + 1}")
        navigation_buttons += 1
    builder.button(text="Назад", callback_data="mod:main")
    row_sizes = [1] * len(page_admins)
    if navigation_buttons:
        row_sizes.append(navigation_buttons)
    row_sizes.append(1)
    builder.adjust(*row_sizes)
    await edit_ephemerally(
        callback,
        f"<b>Права администраторов</b> · стр. {page + 1}/{total_pages}\nВыберите администратора чата:",
        builder.as_markup(),
    )


async def render_admin_permissions(
    callback: CallbackQuery,
    target_id: int,
    admins_page: int = 0,
):
    message = callback.message
    if not message:
        await callback.answer("Сообщение меню недоступно.", show_alert=True)
        return

    chat_id = message.chat.id
    if not await is_owner(callback.bot, chat_id, callback.from_user.id):
        await callback.answer("Настраивать права может только владелец чата.", show_alert=True)
        return

    if await member_status(callback.bot, chat_id, target_id) != "administrator":
        await callback.answer("Пользователь больше не администратор этого чата.", show_alert=True)
        return

    permissions = database.get_mod_permissions(chat_id, target_id)
    builder = InlineKeyboardBuilder()
    for key, label in PERMISSIONS.items():
        enabled = permissions.get(key, False)
        builder.button(
            text=f"{label}: {'ВКЛ' if enabled else 'ВЫКЛ'}",
            callback_data=f"mod:toggle:{target_id}:{key}:{admins_page}",
        )
    builder.button(text="К списку", callback_data=f"mod:admins:{admins_page}")
    builder.adjust(1)
    await edit_ephemerally(
        callback,
        f"<b>Права администратора</b>\nID: <code>{target_id}</code>",
        builder.as_markup(),
    )


def history_text(
    target_id: int,
    rows,
    accuracy: float | None,
    pattern_match: float | None,
    pattern_samples: int,
    page: int,
    total_pages: int,
):
    page_label = f" · стр. {page + 1}/{total_pages}" if total_pages > 1 else ""
    if rows:
        name = html.escape(rows[0]["full_name"])
        lines = [
            f"<b>История питья за 48 часов · {name}</b> · ID <code>{target_id}</code>{page_label}",
            "",
        ]
        for row in rows:
            happened_at = format_timestamp(row["created_at"], "%d.%m %H:%M:%S")
            lines.append(f"{happened_at} · {row['liters']:.1f} л.")
    else:
        lines = [f"<b>История питья за 48 часов</b> · ID <code>{target_id}</code>", "Успешных попыток нет.", ""]

    if lines[-1] != "":
        lines.append("")

    if pattern_match is None:
        lines.append(
            "Совпадение ритма AutoFarm за 7 дней: недостаточно данных "
            f"(нужно не менее {database.PATTERN_MIN_INTERVALS + 1} успешных бесплатных попыток)."
        )
    else:
        lines.append(
            f"Совпадение ритма AutoFarm за 7 дней: {round(pattern_match)}% "
            f"({pattern_samples} интервалов). Оценка учитывает повторяющийся интервал "
            "случайную добавку по умолчанию до 30 минут и нарастающую задержку; "
            "это эвристика, не доказательство использования плагина."
        )

    builder = InlineKeyboardBuilder()
    navigation_buttons = 0
    if page > 0:
        builder.button(
            text="◀️",
            callback_data=f"mod:history:{target_id}:{page - 1}",
        )
        navigation_buttons += 1
    if page < total_pages - 1:
        builder.button(
            text="▶️",
            callback_data=f"mod:history:{target_id}:{page + 1}",
        )
        navigation_buttons += 1
    builder.button(
        text=f"Аккуратность: {round(accuracy)}%" if accuracy is not None else "Аккуратность: нет данных",
        callback_data=f"mod:accuracy:{target_id}",
    )
    if navigation_buttons:
        builder.adjust(navigation_buttons, 1)
    else:
        builder.adjust(1)
    return "\n".join(lines), builder.as_markup()


def build_history_page(chat_id: int, target_id: int, page: int):
    requested_page = max(0, page)
    rows, _, successes = database.get_drink_history(
        chat_id,
        target_id,
        limit=MOD_HISTORY_PAGE_SIZE,
        offset=requested_page * MOD_HISTORY_PAGE_SIZE,
    )
    total_pages = max(1, (successes + MOD_HISTORY_PAGE_SIZE - 1) // MOD_HISTORY_PAGE_SIZE)
    page = min(requested_page, total_pages - 1)
    if page != requested_page:
        rows, _, successes = database.get_drink_history(
            chat_id,
            target_id,
            limit=MOD_HISTORY_PAGE_SIZE,
            offset=page * MOD_HISTORY_PAGE_SIZE,
        )

    accuracy, _ = database.get_drink_accuracy(chat_id, target_id)
    pattern_match, pattern_samples = database.get_drink_pattern_match(
        chat_id,
        target_id,
    )
    return history_text(
        target_id,
        rows,
        accuracy,
        pattern_match,
        pattern_samples,
        page,
        total_pages,
    )


async def render_audit_page(callback: CallbackQuery, page: int):
    message = callback.message
    if not message:
        await callback.answer("Сообщение меню недоступно.", show_alert=True)
        return

    chat_id = message.chat.id
    page = max(0, page)
    entries = database.get_mod_audit(
        chat_id,
        limit=MOD_AUDIT_PAGE_SIZE,
        offset=page * MOD_AUDIT_PAGE_SIZE,
    )
    if not entries and page > 0:
        page = 0
        entries = database.get_mod_audit(chat_id, limit=MOD_AUDIT_PAGE_SIZE)

    total_groups = int(entries[0]["total_groups"]) if entries else 0
    total_pages = max(1, (total_groups + MOD_AUDIT_PAGE_SIZE - 1) // MOD_AUDIT_PAGE_SIZE)
    page = min(page, total_pages - 1)
    lines = [f"<b>Журнал аудита</b> · стр. {page + 1}/{total_pages}", ""]
    for entry in entries:
        happened_at = format_timestamp(entry["created_at"], "%d.%m %H:%M:%S")
        target = f" · цель <code>{entry['target_id']}</code>" if entry["target_id"] else ""
        details = f" · {html.escape(entry['details'])}" if entry["details"] else ""
        repeat = f" (x{entry['repeat_count']})" if entry["repeat_count"] > 1 else ""
        lines.append(
            f"{happened_at} · <code>{entry['actor_id']}</code> · "
            f"{html.escape(entry['action'])}{target}{details}{repeat}"
        )
    if not entries:
        lines.append("Записей пока нет.")

    builder = InlineKeyboardBuilder()
    navigation_buttons = 0
    if page > 0:
        builder.button(text="◀️", callback_data=f"mod:audit:{page - 1}")
        navigation_buttons += 1
    if page < total_pages - 1:
        builder.button(text="▶️", callback_data=f"mod:audit:{page + 1}")
        navigation_buttons += 1
    builder.button(text="Назад", callback_data="mod:main")
    row_sizes = [navigation_buttons] if navigation_buttons else []
    row_sizes.append(1)
    builder.adjust(*row_sizes)
    await edit_ephemerally(callback, "\n".join(lines), builder.as_markup())


def parse_target(message: Message, argument: str | None):
    if argument:
        value = argument.strip()
        if value.isdigit():
            return int(value), None
        if value.startswith("@") or value.isalnum() or "_" in value:
            return database.resolve_drinking_user(message.chat.id, value), value
        return None, value

    replied_user = message.reply_to_message.from_user if message.reply_to_message else None
    if replied_user:
        return replied_user.id, replied_user.full_name
    return None, None


async def command_mod(message: Message):
    if not message.from_user:
        return

    if message.chat.type == "private":
        await message.answer(messages.PRIVATE_DISABLED, parse_mode="HTML")
        return

    await delete_command_message(message)

    status = await member_status(message.bot, message.chat.id, message.from_user.id)
    if status not in ADMIN_STATUSES:
        await answer_ephemerally(message, "Только администраторы чата могут открыть /mod.")
        return

    parts = (message.text or "").split()
    subcommand = parts[1].lower() if len(parts) > 1 else "menu"
    target_argument = parts[2] if len(parts) > 2 else None

    if subcommand == "menu":
        await answer_ephemerally(
            message,
            "<b>Модерация чата</b>\n\n"
            "<code>/mod history</code> — история питья\n"
            "<code>/mod ban</code> — запретить пить\n"
            "<code>/mod unban</code> — снять запрет\n\n"
            "Цель: ответом на сообщение, числовым ID или username.",
            main_keyboard(
                database.get_mod_permissions(message.chat.id, message.from_user.id),
                status == "creator",
            ),
        )
        return

    permission = {"history": "history", "ban": "ban", "unban": "ban"}.get(subcommand)
    if permission is None:
        await answer_ephemerally(message, "Используйте /mod, /mod history, /mod ban или /mod unban.")
        return

    if not await has_permission(message.bot, message.chat.id, message.from_user.id, permission):
        await answer_ephemerally(message, "У вас нет актуального разрешения на это действие.")
        return

    target_id, target_label = parse_target(message, target_argument)
    if target_id is None:
        if target_label:
            await answer_ephemerally(message, f"Не удалось найти <code>{html.escape(target_label)}</code> в этом чате.")
        else:
            await answer_ephemerally(message, "Укажите цель ответом на сообщение, ID или username.")
        return

    if subcommand == "history":
        database.record_mod_audit(message.chat.id, message.from_user.id, "view_history", target_id)
        text, keyboard = build_history_page(message.chat.id, target_id, 0)
        await answer_ephemerally(message, text, keyboard)
        return

    if subcommand == "ban":
        changed = database.ban_drinking(message.chat.id, target_id, message.from_user.id)
        action = "ban" if changed else "ban_existing"
        response = "Пользователю запрещено пить в этом чате." if changed else "Пользователю уже запрещено пить в этом чате."
    else:
        changed = database.unban_drinking(message.chat.id, target_id)
        action = "unban" if changed else "unban_missing"
        response = "Запрет на питьё снят в этом чате." if changed else "В этом чате запрета не было."

    database.record_mod_audit(message.chat.id, message.from_user.id, action, target_id)
    await answer_ephemerally(message, response)


@router.message(Command("mod"))
async def mod_command(message: Message):
    await command_mod(message)


@router.callback_query(F.data.startswith("mod:"))
async def mod_callback(callback: CallbackQuery):
    message = callback.message
    if not message:
        await callback.answer("Сообщение меню недоступно.", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    chat_id = message.chat.id
    user_id = callback.from_user.id

    if action == "main":
        await render_main(callback)
        return

    if action == "audit":
        if not await has_permission(callback.bot, chat_id, user_id, "audit"):
            await callback.answer("У вас нет актуального разрешения на просмотр аудита.", show_alert=True)
            return
        if len(parts) == 2:
            database.record_mod_audit(chat_id, user_id, "view_audit")
            page = 0
        elif len(parts) == 3 and parts[2].isdigit():
            page = int(parts[2])
        else:
            await callback.answer("Страница журнала некорректна.", show_alert=True)
            return
        await render_audit_page(callback, page)
        return

    if action == "admins":
        if len(parts) == 2:
            page = 0
        elif len(parts) == 3 and parts[2].isdigit():
            page = int(parts[2])
        else:
            await callback.answer("Страница списка некорректна.", show_alert=True)
            return
        await render_admins(callback, page)
        return

    if action == "admin" and len(parts) in {3, 4} and parts[2].isdigit():
        admins_page = int(parts[3]) if len(parts) == 4 and parts[3].isdigit() else 0
        if len(parts) == 4 and not parts[3].isdigit():
            await callback.answer("Страница списка некорректна.", show_alert=True)
            return
        await render_admin_permissions(callback, int(parts[2]), admins_page)
        return

    if action == "toggle" and len(parts) in {4, 5} and parts[2].isdigit() and parts[3] in PERMISSIONS:
        if not await is_owner(callback.bot, chat_id, user_id):
            await callback.answer("Настраивать права может только владелец чата.", show_alert=True)
            return

        admins_page = int(parts[4]) if len(parts) == 5 and parts[4].isdigit() else 0
        if len(parts) == 5 and not parts[4].isdigit():
            await callback.answer("Страница списка некорректна.", show_alert=True)
            return

        target_id = int(parts[2])
        if await member_status(callback.bot, chat_id, target_id) != "administrator":
            await callback.answer("Пользователь больше не администратор этого чата.", show_alert=True)
            return

        permission = parts[3]
        current = database.get_mod_permissions(chat_id, target_id).get(permission, False)
        database.set_mod_permission(chat_id, target_id, permission, not current, user_id)
        database.record_mod_audit(
            chat_id,
            user_id,
            "permission_changed",
            target_id,
            f"{permission}={'on' if not current else 'off'}",
        )
        await render_admin_permissions(callback, target_id, admins_page)
        return

    if action == "history" and len(parts) == 4 and parts[2].isdigit() and parts[3].isdigit():
        if not await has_permission(callback.bot, chat_id, user_id, "history"):
            await callback.answer("У вас нет актуального разрешения на просмотр истории.", show_alert=True)
            return
        text, keyboard = build_history_page(chat_id, int(parts[2]), int(parts[3]))
        await edit_ephemerally(callback, text, keyboard)
        return

    if action == "accuracy" and len(parts) == 3 and parts[2].isdigit():
        if not await has_permission(callback.bot, chat_id, user_id, "history"):
            await callback.answer("У вас нет актуального разрешения на просмотр истории.", show_alert=True)
            return
        target_id = int(parts[2])
        accuracy, samples = database.get_drink_accuracy(chat_id, target_id)
        if accuracy is None:
            await callback.answer("Пока недостаточно данных об успешных попытках после cooldown.", show_alert=True)
            return
        await callback.answer(
            f"Аккуратность по времени: {round(accuracy)}% по {samples} попыткам за 48 часов.",
            show_alert=True,
        )
        return

    await callback.answer("Действие не распознано.", show_alert=True)
