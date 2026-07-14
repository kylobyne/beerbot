import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

from config import COOLDOWN_TIME, PAGINATION_COOLDOWN_SECONDS
import messages

class CooldownMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        super().__init__()
        # Универсальный кэш: {id_для_проверки: timestamp}
        self.user_cooldowns: Dict[Any, float] = {}

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if not event.data or not event.message:
            return await handler(event, data)

        current_time = time.time()
        
        cooldown_duration = 0
        alert_text = ""
        target_id = None  # Сюда запишем либо user_id, либо chat_id

        # 1. Если это кнопка покупки звезд
        if event.data.startswith("buy:"):
            cooldown_duration = COOLDOWN_TIME
            alert_text = getattr(messages, "BUY_COOLDOWN", "Пожалуйста, подождите {remaining} сек. перед следующей покупкой.")
            # ДЛЯ ПОКУПКИ: Идентификация по уникальному ID пользователя
            target_id = event.from_user.id
        
        # 2. Если это стрелочки пагинации статистики
        elif event.data.startswith("beer_top:"):
            if event.data.endswith(":current"):
                return await handler(event, data)
                
            cooldown_duration = PAGINATION_COOLDOWN_SECONDS
            alert_text = messages.TOO_FAST 
            # ДЛЯ СТАТИСТИКИ: Идентификация по ID текущего чата (группы)
            target_id = event.message.chat.id
            
        else:
            # Другие кнопки пропускаем без задержек
            return await handler(event, data)

        # Автоматическая очистка старых записей из памяти текущего файла (RAM)
        self.user_cooldowns = {
            tid: ts for tid, ts in self.user_cooldowns.items() 
            if current_time - ts < cooldown_duration
        }

        # Проверяем КД по вычисленному target_id (user_id или chat_id)
        last_click = self.user_cooldowns.get(target_id, 0)
        
        if current_time - last_click < cooldown_duration:
            remaining = int(cooldown_duration - (current_time - last_click))
            
            if "{remaining}" in alert_text:
                text_to_show = alert_text.format(remaining=remaining)
            else:
                text_to_show = f"{alert_text} ({remaining} сек.)"

            await event.answer(text_to_show, show_alert=True)
            return  # Блокируем обработку кнопки

        # Запоминаем успешное нажатие для данного ID
        self.user_cooldowns[target_id] = current_time
        return await handler(event, data)
