"""Pure pricing helpers for tests and billing."""

from __future__ import annotations


def discounted_cost(base_credits: int, discount_percent: int) -> int:
    if base_credits <= 0:
        return 0
    d = max(0, min(100, discount_percent))
    return max(1, round(base_credits * (100 - d) / 100))
