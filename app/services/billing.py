from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CreditTransaction,
    PredictionJob,
    TransactionType,
    User,
)
from app.services.pricing import discounted_cost


def get_base_prediction_cost(session: Session, default: int) -> int:
    from app.models import BillingConfig

    row = session.get(BillingConfig, "prediction_base_cost_credits")
    if row is None:
        return default
    try:
        return max(1, int(row.value))
    except ValueError:
        return default


def charge_prediction_success(
    session: Session,
    job: PredictionJob,
    user: User,
    discount_percent: int,
) -> int:
    """
    Atomically charge credits for a succeeded job. Idempotent: unique (reference_type, reference_id).
    Returns credits charged.
    """
    base = job.base_cost
    cost = discounted_cost(base, discount_percent)
    ref_id = str(job.id)

    existing = session.execute(
        select(CreditTransaction).where(
            CreditTransaction.reference_type == "prediction_job",
            CreditTransaction.reference_id == ref_id,
        )
    ).scalar_one_or_none()
    if existing:
        return abs(existing.amount)

    if user.balance_credits < cost:
        raise ValueError("INSUFFICIENT_CREDITS")

    user.balance_credits -= cost
    tx = CreditTransaction(
        user_id=user.id,
        amount=-cost,
        balance_after=user.balance_credits,
        tx_type=TransactionType.PREDICTION_CHARGE,
        reference_type="prediction_job",
        reference_id=ref_id,
    )
    session.add(tx)
    job.credits_charged = cost
    job.discount_percent_applied = discount_percent
    session.flush()
    return cost


def credit_payment(
    session: Session,
    user: User,
    amount: int,
    external_ref: str,
) -> CreditTransaction:
    if amount <= 0:
        raise ValueError("Amount must be positive")
    user.balance_credits += amount
    tx = CreditTransaction(
        user_id=user.id,
        amount=amount,
        balance_after=user.balance_credits,
        tx_type=TransactionType.PAYMENT_CREDIT,
        reference_type="payment",
        reference_id=external_ref[:64],
    )
    session.add(tx)
    try:
        session.flush()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("Duplicate payment reference") from e
    return tx
