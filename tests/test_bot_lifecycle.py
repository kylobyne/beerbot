import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetMe

from bot import _cancel_background_tasks, run_polling_with_retry


class PollingRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_network_failure_retries_polling_with_backoff(self):
        bot = MagicMock()
        bot.delete_webhook = AsyncMock(return_value=True)
        dispatcher = MagicMock()
        dispatcher.resolve_used_update_types.return_value = ["message"]
        dispatcher.start_polling = AsyncMock(
            side_effect=[
                TelegramNetworkError(method=GetMe(), message="offline"),
                None,
            ]
        )

        with (
            patch("bot.asyncio.sleep", new_callable=AsyncMock) as sleep,
            patch("bot.logging.exception"),
        ):
            await run_polling_with_retry(bot, dispatcher)

        self.assertEqual(sleep.await_args_list, [call(1)])
        self.assertEqual(bot.delete_webhook.await_count, 2)
        bot.delete_webhook.assert_awaited_with(drop_pending_updates=False)
        self.assertEqual(dispatcher.start_polling.await_count, 2)
        dispatcher.start_polling.assert_awaited_with(
            bot,
            allowed_updates=["message"],
            close_bot_session=False,
        )

    async def test_background_tasks_are_cancelled_and_joined(self):
        cleanup_finished = asyncio.Event()

        async def background_task():
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_finished.set()

        task = asyncio.create_task(background_task())
        await asyncio.sleep(0)

        await _cancel_background_tasks([task])

        self.assertTrue(task.cancelled())
        self.assertTrue(cleanup_finished.is_set())


if __name__ == "__main__":
    unittest.main()
