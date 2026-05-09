from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models import LoyaltyTier, User
from app.schemas import LoyaltyTierCreate, LoyaltyTierOut, LoyaltyTierUpdate

router = APIRouter(prefix="/admin/loyalty-tiers", tags=["admin"])


@router.get("", response_model=list[LoyaltyTierOut])
def list_tiers(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[LoyaltyTier]:
    return db.query(LoyaltyTier).order_by(LoyaltyTier.sort_order.asc()).all()


@router.post("", response_model=LoyaltyTierOut, status_code=status.HTTP_201_CREATED)
def create_tier(
    payload: LoyaltyTierCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> LoyaltyTier:
    row = LoyaltyTier(
        name=payload.name,
        min_predictions_monthly=payload.min_predictions_monthly,
        discount_percent=payload.discount_percent,
        sort_order=payload.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{tier_id}", response_model=LoyaltyTierOut)
def update_tier(
    tier_id: int,
    payload: LoyaltyTierUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> LoyaltyTier:
    row = db.get(LoyaltyTier, tier_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tier not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tier(
    tier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    row = db.get(LoyaltyTier, tier_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tier not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
