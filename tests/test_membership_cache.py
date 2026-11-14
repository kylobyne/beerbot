import unittest
from types import SimpleNamespace
from unittest.mock import patch

from handlers.mod import handle_chat_member_update


class ChatMemberMembershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_member_status_updates_are_persisted(self):
        for status, expected in (("member", True), ("left", False), ("kicked", False)):
            with self.subTest(status=status):
                event = SimpleNamespace(
                    new_chat_member=SimpleNamespace(
                        user=SimpleNamespace(id=42),
                        status=status,
                    ),
                    chat=SimpleNamespace(id=-100123),
                    from_user=SimpleNamespace(id=7),
                    bot=None,
                )
                with (
                    patch("handlers.mod.database.set_drinker_membership") as set_membership,
                    patch("handlers.mod.database.get_mod_permissions", return_value={}),
                ):
                    await handle_chat_member_update(event)

                set_membership.assert_called_once_with(-100123, 42, expected)


if __name__ == "__main__":
    unittest.main()
