from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models import CreditTransaction, LoyaltyTier, PredictionJob, User
from app.services import billing as billing_svc
from app.services import loyalty as loyalty_svc


def test_discounted_cost_edges():
    from app.services.pricing import discounted_cost

    assert discounted_cost(10, 0) == 10
    assert discounted_cost(10, 100) == 1
    assert discounted_cost(10, 5) == max(1, round(10 * 0.95))
    assert discounted_cost(0, 50) == 0


def test_charge_idempotent_when_tx_exists():
    job_id = uuid.uuid4()
    job = MagicMock(spec=PredictionJob)
    job.id = job_id
    job.base_cost = 10

    user = MagicMock(spec=User)
    user.id = 1
    user.balance_credits = 100

    existing = MagicMock(spec=CreditTransaction)
    existing.amount = -9

    session = MagicMock()
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = existing
    session.execute.return_value = exec_res

    charged = billing_svc.charge_prediction_success(session, job, user, discount_percent=10)
    assert charged == 9
    session.add.assert_not_called()


def test_charge_insufficient():
    job = MagicMock(spec=PredictionJob)
    job.id = uuid.uuid4()
    job.base_cost = 100

    user = MagicMock(spec=User)
    user.id = 1
    user.balance_credits = 1

    session = MagicMock()
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = None
    session.execute.return_value = exec_res

    with pytest.raises(ValueError, match="INSUFFICIENT"):
        billing_svc.charge_prediction_success(session, job, user, discount_percent=0)


def test_security_token_roundtrip(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-at-least-32-bytes-long")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.security import create_access_token, decode_token

    token = create_access_token(42)
    assert decode_token(token) == "42"


def test_pick_tier_for_count():
    bronze = LoyaltyTier(id=1, name="Bronze", min_predictions_monthly=0, discount_percent=0, sort_order=0)
    silver = LoyaltyTier(id=2, name="Silver", min_predictions_monthly=10, discount_percent=5, sort_order=1)
    gold = LoyaltyTier(id=3, name="Gold", min_predictions_monthly=50, discount_percent=10, sort_order=2)

    session = MagicMock(spec=Session)
    session.execute.return_value.scalars.return_value.all.return_value = [bronze, silver, gold]

    assert loyalty_svc.pick_tier_for_count(session, 0).id == 1
    assert loyalty_svc.pick_tier_for_count(session, 10).id == 2
    assert loyalty_svc.pick_tier_for_count(session, 49).id == 2
    assert loyalty_svc.pick_tier_for_count(session, 50).id == 3


def test_discount_for_user_no_tier():
    user = MagicMock(spec=User)
    user.loyalty_tier_id = None
    session = MagicMock(spec=Session)
    assert loyalty_svc.discount_for_user(session, user) == 0


def test_get_base_prediction_cost():
    session = MagicMock(spec=Session)
    session.get.return_value = None
    assert billing_svc.get_base_prediction_cost(session, 10) == 10

    row = MagicMock()
    row.value = "25"
    session.get.return_value = row
    assert billing_svc.get_base_prediction_cost(session, 10) == 25


def test_discount_for_user_with_tier():
    tier = LoyaltyTier(id=2, name="Silver", min_predictions_monthly=10, discount_percent=7, sort_order=1)
    user = MagicMock(spec=User)
    user.loyalty_tier_id = 2
    session = MagicMock(spec=Session)
    session.get.return_value = tier
    assert loyalty_svc.discount_for_user(session, user) == 7
