import unittest
from unittest.mock import patch

from services.beer import BeerOutcome, process_beer_command


class BeerServiceTests(unittest.TestCase):
    @patch("services.beer.record_drink_attempt")
    @patch("services.beer.drink")
    @patch("services.beer.is_drink_banned", return_value=False)
    def test_free_attempt_records_success_and_cooldown_delay(
        self,
        is_drink_banned,
        drink,
        record_drink_attempt,
    ):
        drink.return_value = (True, 1.5, 3.5, 12)

        result = process_beer_command(-100, 42, "user", "Test User")

        self.assertEqual(result.outcome, BeerOutcome.FREE_SUCCESS)
        self.assertEqual(result.liters, 1.5)
        self.assertEqual(result.total_liters, 3.5)
        self.assertEqual(result.cooldown_delay_seconds, 12)
        record_drink_attempt.assert_called_once_with(
            -100,
            42,
            "user",
            "Test User",
            "success",
            1.5,
            cooldown_delay_seconds=12,
        )

    @patch("services.beer.record_drink_attempt")
    @patch("services.beer.drink_paid", return_value=(2.0, 7.0))
    @patch("services.beer.use_paid_attempt", return_value=True)
    @patch("services.beer.drink", return_value=(False, 30, 5.0, None))
    @patch("services.beer.is_drink_banned", return_value=False)
    def test_cooldown_consumes_shared_paid_attempt(
        self,
        is_drink_banned,
        drink,
        use_paid_attempt,
        drink_paid,
        record_drink_attempt,
    ):
        result = process_beer_command(-100, 42, "user", "Test User")

        self.assertEqual(result.outcome, BeerOutcome.PAID_SUCCESS)
        self.assertEqual((result.liters, result.total_liters), (2.0, 7.0))
        use_paid_attempt.assert_called_once_with(42)
        drink_paid.assert_called_once_with(-100, 42, "Test User")
        record_drink_attempt.assert_called_once_with(
            -100,
            42,
            "user",
            "Test User",
            "success",
            2.0,
        )

    @patch("services.beer.record_drink_attempt")
    @patch("services.beer.use_paid_attempt", return_value=False)
    @patch("services.beer.drink", return_value=(False, 45, 5.0, None))
    @patch("services.beer.is_drink_banned", return_value=False)
    def test_cooldown_without_paid_attempt_is_recorded(
        self,
        is_drink_banned,
        drink,
        use_paid_attempt,
        record_drink_attempt,
    ):
        result = process_beer_command(-100, 42, "user", "Test User")

        self.assertEqual(result.outcome, BeerOutcome.COOLDOWN)
        self.assertEqual(result.cooldown_seconds, 45)
        record_drink_attempt.assert_called_once_with(
            -100,
            42,
            "user",
            "Test User",
            "cooldown",
        )

    @patch("services.beer.claim_drink_ban_notice", return_value=True)
    @patch("services.beer.remember_drinking_user")
    @patch("services.beer.is_drink_banned", return_value=True)
    def test_ban_notice_is_claimed_once_by_domain_service(
        self,
        is_drink_banned,
        remember_drinking_user,
        claim_drink_ban_notice,
    ):
        result = process_beer_command(-100, 42, "user", "Test User")

        self.assertEqual(result.outcome, BeerOutcome.BANNED)
        self.assertTrue(result.should_notify_ban)
        remember_drinking_user.assert_called_once_with(-100, 42, "user", "Test User")
        claim_drink_ban_notice.assert_called_once_with(-100, 42)


if __name__ == "__main__":
    unittest.main()
