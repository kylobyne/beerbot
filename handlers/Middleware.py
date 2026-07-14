import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

from config import COOLDOWN_TIME, PAGINATION_COOLDOWN_SECONDS
import messages

class CooldownMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        super().__init__()
        self.cooldowns: Dict[str, Dict[int, float]] = {
            "buy": {},
            "beer_top": {}
        }

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if not event.data:
            return await handler(event, data)

        user_id = event.from_user.id
        current_time = time.time()
        
        action_type = None
        cooldown_duration = 0
        alert_text = ""

        if event.data.startswith("buy:"):
            action_type = "buy"
            cooldown_duration = COOLDOWN_TIME
            # Используем значение из messages, если оно там есть, либо дефолт
            alert_text = getattr(messages, "BUY_COOLDOWN", "Пожалуйста, подождите {remaining} сек. перед следующей покупкой.")
        
        elif event.data.startswith("beer_top:"):
            if event.data.endswith(":current"):
                return await handler(event, data)
                
            action_type = "beer_top"
            cooldown_duration = PAGINATION_COOLDOWN_SECONDS
            alert_text = messages.TOO_FAST 

        if action_type:
            # ОЧИСТКА ПАМЯТИ (Периодически удаляем старых пользователей из кэша, чтобы не забивать RAM)
            # Удаляем записи, которые старше, чем текущее время минус кулдаун
            self.cooldowns[action_type] = {
                uid: ts for uid, ts in self.cooldowns[action_type].items() 
                if current_time - ts < cooldown_duration
            }

            last_click = self.cooldowns[action_type].get(user_id, 0)
            
            if current_time - last_click < cooldown_duration:
                remaining = int(cooldown_duration - (current_time - last_click))
                
                # Умное форматирование: проверяем, ждет ли строка переменную {remaining}
                if "{remaining}" in alert_text:
                    text_to_show = alert_text.format(remaining=remaining)
                else:
                    # Если в messages.TOO_FAST нет секунд, просто дописываем их в скобках для удобства
                    text_to_show = f"{alert_text} ({remaining} сек.)"

                await event.answer(text_to_show, show_alert=True)
                return

            self.cooldowns[action_type][user_id] = current_time

        return await handler(event, data)
