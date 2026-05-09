from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import LoyaltyTierCreate, PaymentStubIn, PredictionCreate, UserCreate


def test_user_create_password_length():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.co", password="short")


def test_prediction_create():
    p = PredictionCreate(model_id=1, features=[1.0, 2.0])
    assert p.model_id == 1


def test_payment_stub_in():
    p = PaymentStubIn(amount_credits=50, external_payment_id="pay-1", signature="sig")
    assert p.amount_credits == 50


def test_loyalty_tier_create():
    t = LoyaltyTierCreate(name="X", min_predictions_monthly=5, discount_percent=7)
    assert t.discount_percent == 7
