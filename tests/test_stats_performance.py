import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.stats import (
    command_stats,
    get_valid_leaderboard_text,
    stats_last_requests,
    stats_last_warnings,
)


class StatsMembershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_stats_cooldown_is_per_user_in_the_same_chat(self):
        stats_last_requests.clear()
        stats_last_warnings.clear()
        self.addCleanup(stats_last_requests.clear)
        self.addCleanup(stats_last_warnings.clear)

        def make_message(user_id):
            return SimpleNamespace(
                from_user=SimpleNamespace(id=user_id, full_name=f"User {user_id}"),
                chat=SimpleNamespace(id=-100, type="supergroup"),
                bot=SimpleNamespace(),
                ephemeral_message_id=None,
            )

        with (
            patch("handlers.stats.time.monotonic", side_effect=[100.0, 101.0, 102.0]),
            patch("handlers.stats.update_user_name"),
            patch("handlers.stats.get_valid_leaderboard_text", new_callable=AsyncMock) as get_text,
            patch("handlers.stats.send_ephemeral_message", new_callable=AsyncMock),
        ):
            get_text.return_value = ("leaderboard", None)
            await command_stats(make_message(1))
            await command_stats(make_message(2))
            await command_stats(make_message(1))

        self.assertEqual(get_text.await_count, 2)
        self.assertEqual(set(stats_last_requests), {(-100, 1), (-100, 2)})

    async def test_only_unchecked_members_are_requested_from_telegram(self):
        rows = [
            {
                "user_id": 1,
                "name": "Current",
                "total_liters": 10.0,
                "is_member": 1,
                "membership_checked": 1,
            },
            {
                "user_id": 2,
                "name": "Former",
                "total_liters": 8.0,
                "is_member": 0,
                "membership_checked": 1,
            },
            {
                "user_id": 3,
                "name": "Legacy",
                "total_liters": 6.0,
                "is_member": 1,
                "membership_checked": 0,
            },
        ]
        bot = SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member"))
        )
        with (
            patch("handlers.stats.get_leaderboard", return_value=rows),
            patch("handlers.stats.update_unchecked_drinker_memberships") as update_memberships,
        ):
            text, keyboard = await get_valid_leaderboard_text(bot, -100, 0)

        self.assertIn("Current", text)
        self.assertIn("Legacy", text)
        self.assertNotIn("Former", text)
        self.assertIsNone(keyboard)
        bot.get_chat_member.assert_awaited_once_with(chat_id=-100, user_id=3)
        update_memberships.assert_called_once_with(-100, {3: True})


if __name__ == "__main__":
    unittest.main()
