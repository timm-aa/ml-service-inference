from __future__ import annotations

import logging
import os
from uuid import UUID

import joblib
import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.metrics_extra import bump_prediction_completed
from app.models import JobStatus, MLModel, PredictionJob, User
from app.services.billing import charge_prediction_success
from app.services.loyalty import discount_for_user

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session() -> Session:
    return SessionLocal()


@celery_app.task(name="worker.tasks.run_prediction")
def run_prediction(job_id: str) -> None:
    session = _session()
    try:
        job = session.get(PredictionJob, UUID(job_id))
        if job is None:
            logger.warning("Job %s not found", job_id)
            return
        if job.status == JobStatus.SUCCEEDED:
            return

        job.status = JobStatus.PROCESSING
        session.commit()

        user = session.get(User, job.user_id)
        model_row = session.get(MLModel, job.model_id)
        if user is None or model_row is None:
            job.status = JobStatus.FAILED
            job.error_message = "User or model missing"
            session.commit()
            bump_prediction_completed("failed")
            return

        settings = get_settings()
        path = os.path.join(settings.model_storage_path, model_row.storage_filename)
        if not os.path.isfile(path):
            job.status = JobStatus.FAILED
            job.error_message = "Model file missing on disk"
            session.commit()
            bump_prediction_completed("failed")
            return

        try:
            estimator = joblib.load(path)
            X = np.asarray(job.input_features, dtype=float).reshape(1, -1)
            raw = estimator.predict(X)
            out = raw.tolist()
        except Exception as e:
            logger.exception("Predict failed")
            job.status = JobStatus.FAILED
            job.error_message = str(e)[:2000]
            session.commit()
            bump_prediction_completed("failed")
            return

        session.refresh(user)
        discount = discount_for_user(session, user)
        try:
            charge_prediction_success(session, job, user, discount)
        except ValueError:
            job.status = JobStatus.FAILED
            job.error_message = "Insufficient credits at billing time"
            session.commit()
            bump_prediction_completed("failed")
            return

        job.result = {"prediction": out}
        job.status = JobStatus.SUCCEEDED
        session.commit()
        bump_prediction_completed("succeeded")
    except Exception:
        logger.exception("Unhandled in run_prediction")
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="worker.tasks.recalculate_loyalty_monthly")
def recalculate_loyalty_monthly() -> int:
    from app.services.loyalty import recalculate_all_users_monthly_tiers

    session = _session()
    try:
        n = recalculate_all_users_monthly_tiers(session)
        session.commit()
        return n
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
