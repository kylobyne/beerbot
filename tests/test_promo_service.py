import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
from services.promos import PromoOutcome, redeem_promo


class PromoServiceTests(unittest.TestCase):
    def run_with_promo(self, promo, *, user_id=42, code="CODE"):
        with (
            patch("services.promos.database.get_promo", return_value=promo),
            patch("services.promos.database.claim_promo", return_value=True) as claim,
            patch("services.promos.database.has_used_promo", return_value=False),
            patch("services.promos.database.add_beer_reward") as add_beer,
            patch("services.promos.database.add_paid_attempts") as add_attempts,
            patch("services.promos.database.is_expires_at_expired", return_value=False),
            patch("services.promos.database.is_duration_expired", return_value=False),
        ):
            result = redeem_promo(-100, user_id, "Test User", code)
        return result, claim, add_beer, add_attempts

    def promo_row(
        self,
        *,
        reward_type="beer",
        bind_users=None,
        time_limited=0,
        expires_at=None,
        duration=None,
        activation_limited=0,
        max_activations=None,
        active=1,
    ):
        return (
            5,
            "CODE",
            reward_type,
            3,
            time_limited,
            expires_at,
            duration,
            activation_limited,
            max_activations,
            0,
            bind_users,
            1,
            100,
            100,
            active,
        )

    def test_restricted_user_cannot_redeem(self):
        result, claim, add_beer, add_attempts = self.run_with_promo(
            self.promo_row(bind_users="7, 8"),
        )

        self.assertEqual(result.outcome, PromoOutcome.USER_RESTRICTED)
        claim.assert_not_called()
        add_beer.assert_not_called()
        add_attempts.assert_not_called()

    def test_expired_promo_cannot_be_claimed(self):
        promo = self.promo_row(time_limited=1, expires_at=50)
        with (
            patch("services.promos.database.get_promo", return_value=promo),
            patch("services.promos.database.is_expires_at_expired", return_value=True),
            patch("services.promos.database.claim_promo") as claim,
        ):
            result = redeem_promo(-100, 42, "Test User", "CODE")

        self.assertEqual(result.outcome, PromoOutcome.INVALID)
        claim.assert_not_called()

    def test_beer_reward_is_applied_to_the_redeeming_chat(self):
        result, claim, add_beer, add_attempts = self.run_with_promo(self.promo_row())

        self.assertEqual(result.outcome, PromoOutcome.ACTIVATED)
        add_beer.assert_called_once_with(-100, 42, "Test User", 3)
        add_attempts.assert_not_called()

    def test_paid_attempt_reward_is_global(self):
        result, claim, add_beer, add_attempts = self.run_with_promo(
            self.promo_row(reward_type="attempts"),
        )

        self.assertEqual(result.outcome, PromoOutcome.ACTIVATED)
        add_attempts.assert_called_once_with(42, 3)
        add_beer.assert_not_called()

    def test_claim_enforces_user_and_total_activation_limits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            promo_path = Path(temp_dir) / "promo.sqlite3"
            with patch.object(database, "PROMO_DB", promo_path):
                database.create_promo_database()
                database.create_promo({
                    "name": "LIMITED",
                    "reward_type": "beer",
                    "reward_amount": 1,
                    "activation_limited": 1,
                    "max_activations": 1,
                })
                promo = database.get_promo("LIMITED")

                self.assertTrue(database.claim_promo(promo[0], user_id=42))
                self.assertFalse(database.claim_promo(promo[0], user_id=42))
                self.assertFalse(database.claim_promo(promo[0], user_id=43))

                refreshed = database.get_promo("LIMITED")
                self.assertEqual(refreshed[9], 1)
                self.assertEqual(refreshed[14], 0)

    def test_expired_promo_claim_is_not_recorded_and_promo_is_deactivated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            promo_path = Path(temp_dir) / "promo.sqlite3"
            with patch.object(database, "PROMO_DB", promo_path):
                database.create_promo_database()
                with patch.object(database, "now_timestamp", return_value=200):
                    database.create_promo({
                        "name": "EXPIRED",
                        "reward_type": "beer",
                        "reward_amount": 1,
                        "time_limited": 1,
                        "expires_at": 100,
                    })
                    promo = database.get_promo("EXPIRED")
                    self.assertFalse(database.claim_promo(promo[0], user_id=42))

                refreshed = database.get_promo("EXPIRED")
                self.assertEqual(refreshed[9], 0)
                self.assertEqual(refreshed[14], 0)


if __name__ == "__main__":
    unittest.main()
