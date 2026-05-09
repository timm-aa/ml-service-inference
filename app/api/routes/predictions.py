from __future__ import annotations

import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.metrics_extra import bump_prediction_enqueued
from app.models import JobStatus, MLModel, PredictionJob, User
from app.schemas import PredictionCreate, PredictionOut
from app.services.billing import get_base_prediction_cost
from app.services.loyalty import discount_for_user
from app.services.pricing import discounted_cost

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("", response_model=PredictionOut, status_code=status.HTTP_202_ACCEPTED)
def create_prediction(
    payload: PredictionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PredictionJob:
    settings = get_settings()
    model = db.get(MLModel, payload.model_id)
    if model is None or model.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Model not found")

    base = get_base_prediction_cost(db, settings.prediction_base_cost_credits)
    discount = discount_for_user(db, user)
    est = discounted_cost(base, discount)
    if user.balance_credits < est:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: need at least {est}, have {user.balance_credits}",
        )

    job = PredictionJob(
        user_id=user.id,
        model_id=model.id,
        status=JobStatus.PENDING,
        input_features=payload.features,
        base_cost=base,
        discount_percent_applied=discount,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from worker.celery_app import celery_app

    async_result = celery_app.send_task(
        "worker.tasks.run_prediction",
        args=[str(job.id)],
        queue="celery",
    )
    job.celery_task_id = async_result.id
    db.add(job)
    db.commit()
    db.refresh(job)
    bump_prediction_enqueued()
    return job


@router.get("/{job_id}", response_model=PredictionOut)
def get_prediction(
    job_id: uuid_lib.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PredictionJob:
    job = db.get(PredictionJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=list[PredictionOut])
def list_predictions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 50,
) -> list[PredictionJob]:
    q = (
        db.query(PredictionJob)
        .filter(PredictionJob.user_id == user.id)
        .order_by(PredictionJob.created_at.desc())
        .limit(min(limit, 200))
    )
    return q.all()
