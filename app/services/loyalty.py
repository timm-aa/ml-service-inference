from __future__ import annotations

from calendar import monthrange
from datetime import datetime

from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import JobStatus, LoyaltyTier, PredictionJob, User


def discount_for_user(session: Session, user: User) -> int:
    if user.loyalty_tier_id is None:
        return 0
    tier = session.get(LoyaltyTier, user.loyalty_tier_id)
    return tier.discount_percent if tier else 0


def count_successful_predictions_in_month(
    session: Session, user_id: int, year: int, month: int
) -> int:
    start = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59)
    q = select(func.count()).select_from(PredictionJob).where(
        and_(
            PredictionJob.user_id == user_id,
            PredictionJob.status == JobStatus.SUCCEEDED,
            PredictionJob.created_at >= start,
            PredictionJob.created_at <= end,
        )
    )
    return int(session.execute(q).scalar_one())


def pick_tier_for_count(session: Session, prediction_count: int) -> Optional[LoyaltyTier]:
    tiers = session.execute(
        select(LoyaltyTier).order_by(LoyaltyTier.min_predictions_monthly.asc())
    ).scalars().all()
    best: Optional[LoyaltyTier] = None
    for tier in tiers:
        if prediction_count >= tier.min_predictions_monthly:
            best = tier
    return best


def recalculate_user_tier_for_previous_month(session: Session, user_id: int) -> None:
    """Assign tier based on successful predictions in the previous calendar month."""
    now = datetime.utcnow()
    month = now.month - 1
    year = now.year
    if month == 0:
        month = 12
        year -= 1
    cnt = count_successful_predictions_in_month(session, user_id, year, month)
    tier = pick_tier_for_count(session, cnt)
    user = session.get(User, user_id)
    if user and tier:
        user.loyalty_tier_id = tier.id


def recalculate_all_users_monthly_tiers(session: Session) -> int:
    users = session.execute(select(User.id)).scalars().all()
    for uid in users:
        recalculate_user_tier_for_previous_month(session, uid)
    return len(users)
