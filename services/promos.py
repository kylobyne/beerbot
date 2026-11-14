from dataclasses import dataclass
from enum import Enum

import database


class PromoOutcome(Enum):
    ACTIVATED = "activated"
    ALREADY_USED = "already_used"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    USER_RESTRICTED = "user_restricted"


@dataclass(frozen=True)
class PromoActivationResult:
    outcome: PromoOutcome
    reward_type: str | None = None
    reward_amount: int | float | None = None


def redeem_promo(
    chat_id: int,
    user_id: int,
    user_name: str,
    code: str,
) -> PromoActivationResult:
    promo = database.get_promo(code)
    if promo is None:
        return PromoActivationResult(PromoOutcome.NOT_FOUND)

    promo_id = promo[0]
    reward_type = promo[2]
    reward_amount = promo[3]
    time_limited = promo[4]
    expires_at = promo[5]
    duration = promo[6]
    bind_users = promo[10]

    if not promo[14]:
        return PromoActivationResult(PromoOutcome.INVALID)

    if bind_users:
        allowed_users = {int(value.strip()) for value in bind_users.split(",") if value.strip()}
        if user_id not in allowed_users:
            return PromoActivationResult(PromoOutcome.USER_RESTRICTED)

    if time_limited and (
        (expires_at and database.is_expires_at_expired(expires_at))
        or (duration and database.is_duration_expired(duration, promo[12]))
    ):
        return PromoActivationResult(PromoOutcome.INVALID)

    if reward_type not in {"beer", "attempts"}:
        return PromoActivationResult(PromoOutcome.INVALID)

    if database.has_used_promo(promo_id, user_id):
        return PromoActivationResult(PromoOutcome.ALREADY_USED)

    if not database.claim_promo(promo_id, user_id):
        if database.has_used_promo(promo_id, user_id):
            return PromoActivationResult(PromoOutcome.ALREADY_USED)
        return PromoActivationResult(PromoOutcome.INVALID)

    if reward_type == "beer":
        database.add_beer_reward(chat_id, user_id, user_name, reward_amount)
    else:
        database.add_paid_attempts(user_id, reward_amount)

    return PromoActivationResult(
        outcome=PromoOutcome.ACTIVATED,
        reward_type=reward_type,
        reward_amount=reward_amount,
    )
