from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import CreditTransaction, User
from app.schemas import BalanceOut, PaymentStubIn, TransactionOut
from app.services.billing import credit_payment

router = APIRouter(prefix="/billing", tags=["billing"])


def verify_payment_hmac(secret: str, external_id: str, amount: int, signature: str) -> bool:
    msg = f"{external_id}:{amount}".encode()
    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.get("/balance", response_model=BalanceOut)
def balance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    db.refresh(user)
    return {"balance_credits": user.balance_credits}


@router.get("/transactions", response_model=list[TransactionOut])
def transactions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 100,
) -> list[CreditTransaction]:
    q = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(min(limit, 500))
    )
    return q.all()


@router.post("/payment-callback", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def payment_stub(
    payload: PaymentStubIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CreditTransaction:
    settings = get_settings()
    if not verify_payment_hmac(
        settings.payment_webhook_secret,
        payload.external_payment_id,
        payload.amount_credits,
        payload.signature,
    ):
        raise HTTPException(status_code=401, detail="Invalid payment signature")
    try:
        tx = credit_payment(db, user, payload.amount_credits, payload.external_payment_id)
        db.commit()
        db.refresh(tx)
        return tx
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
