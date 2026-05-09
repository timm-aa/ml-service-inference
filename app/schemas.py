from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models import JobStatus, TransactionType, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    role: UserRole
    balance_credits: int
    loyalty_tier_id: Optional[int]

    model_config = {"from_attributes": True}


class MLModelCreate(BaseModel):
    name: str = Field(max_length=255)


class MLModelOut(BaseModel):
    id: int
    name: str
    owner_id: int
    storage_filename: str

    model_config = {"from_attributes": True}


class PredictionCreate(BaseModel):
    model_id: int
    features: List[float]


class PredictionOut(BaseModel):
    id: UUID
    status: JobStatus
    model_id: int
    base_cost: int
    discount_percent_applied: Optional[int] = None
    credits_charged: Optional[int] = None
    result: Optional[Union[dict[str, Any], list[Any]]] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceOut(BaseModel):
    balance_credits: int


class TransactionOut(BaseModel):
    id: int
    amount: int
    balance_after: int
    tx_type: TransactionType
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentStubIn(BaseModel):
    """Simulated payment gateway callback."""

    amount_credits: int = Field(gt=0)
    external_payment_id: str = Field(max_length=128)
    signature: str


class LoyaltyTierCreate(BaseModel):
    name: str = Field(max_length=64)
    min_predictions_monthly: int = Field(ge=0)
    discount_percent: int = Field(ge=0, le=100)
    sort_order: int = 0


class LoyaltyTierOut(BaseModel):
    id: int
    name: str
    min_predictions_monthly: int
    discount_percent: int
    sort_order: int

    model_config = {"from_attributes": True}


class LoyaltyTierUpdate(BaseModel):
    name: Optional[str] = None
    min_predictions_monthly: Optional[int] = Field(default=None, ge=0)
    discount_percent: Optional[int] = Field(default=None, ge=0, le=100)
    sort_order: Optional[int] = None


class AnalyticsSummary(BaseModel):
    total_predictions: int
    successful_predictions: int
    total_credits_spent: int
    predictions_last_7_days: int
