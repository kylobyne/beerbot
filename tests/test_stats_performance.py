import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.stats import get_valid_leaderboard_text


class StatsMembershipTests(unittest.IsolatedAsyncioTestCase):
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
