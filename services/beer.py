from dataclasses import dataclass
from enum import Enum

from database import (
    claim_drink_ban_notice,
    drink,
    drink_paid,
    is_drink_banned,
    record_drink_attempt,
    remember_drinking_user,
    use_paid_attempt,
)


class BeerOutcome(Enum):
    BANNED = "banned"
    COOLDOWN = "cooldown"
    FREE_SUCCESS = "free_success"
    PAID_SUCCESS = "paid_success"


@dataclass(frozen=True)
class BeerCommandResult:
    outcome: BeerOutcome
    liters: float | None = None
    total_liters: float | None = None
    cooldown_seconds: float | None = None
    cooldown_delay_seconds: float | None = None
    should_notify_ban: bool = False


def process_beer_command(
    chat_id: int,
    user_id: int,
    username: str | None,
    full_name: str,
) -> BeerCommandResult:
    if is_drink_banned(chat_id, user_id):
        remember_drinking_user(chat_id, user_id, username, full_name)
        return BeerCommandResult(
            outcome=BeerOutcome.BANNED,
            should_notify_ban=claim_drink_ban_notice(chat_id, user_id),
        )

    succeeded, value, total_liters, cooldown_delay = drink(chat_id, user_id, full_name)
    if succeeded:
        record_drink_attempt(
            chat_id,
            user_id,
            username,
            full_name,
            "success",
            value,
            cooldown_delay_seconds=cooldown_delay,
        )
        return BeerCommandResult(
            outcome=BeerOutcome.FREE_SUCCESS,
            liters=value,
            total_liters=total_liters,
            cooldown_delay_seconds=cooldown_delay,
        )

    if use_paid_attempt(user_id):
        liters, updated_total = drink_paid(chat_id, user_id, full_name)
        record_drink_attempt(
            chat_id,
            user_id,
            username,
            full_name,
            "success",
            liters,
        )
        return BeerCommandResult(
            outcome=BeerOutcome.PAID_SUCCESS,
            liters=liters,
            total_liters=updated_total,
        )

    record_drink_attempt(chat_id, user_id, username, full_name, "cooldown")
    return BeerCommandResult(
        outcome=BeerOutcome.COOLDOWN,
        total_liters=total_liters,
        cooldown_seconds=value,
    )
