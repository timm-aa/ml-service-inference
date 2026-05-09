from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import CreditTransaction, JobStatus, PredictionJob, TransactionType, User
from app.schemas import AnalyticsSummary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalyticsSummary:
    total = int(
        db.execute(
            select(func.count()).select_from(PredictionJob).where(PredictionJob.user_id == user.id)
        ).scalar_one()
    )
    ok = int(
        db.execute(
            select(func.count())
            .select_from(PredictionJob)
            .where(
                PredictionJob.user_id == user.id,
                PredictionJob.status == JobStatus.SUCCEEDED,
            )
        ).scalar_one()
    )
    spent_rows = db.execute(
        select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
            CreditTransaction.user_id == user.id,
            CreditTransaction.tx_type == TransactionType.PREDICTION_CHARGE,
        )
    ).scalar_one()
    spent = abs(int(spent_rows))

    week_ago = datetime.utcnow() - timedelta(days=7)
    last7 = int(
        db.execute(
            select(func.count())
            .select_from(PredictionJob)
            .where(
                PredictionJob.user_id == user.id,
                PredictionJob.created_at >= week_ago,
            )
        ).scalar_one()
    )

    return AnalyticsSummary(
        total_predictions=total,
        successful_predictions=ok,
        total_credits_spent=spent,
        predictions_last_7_days=last7,
    )
