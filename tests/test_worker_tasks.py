from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models import JobStatus, MLModel, PredictionJob, User


@pytest.fixture
def job_id() -> str:
    return str(uuid.uuid4())


def test_run_prediction_job_not_found(job_id: str) -> None:
    with patch("worker.tasks.SessionLocal") as m_local:
        session = MagicMock()
        session.get.return_value = None
        m_local.return_value = session
        from worker.tasks import run_prediction

        run_prediction(job_id)
        session.commit.assert_not_called()
        session.close.assert_called_once()


def test_run_prediction_already_succeeded(job_id: str) -> None:
    job = MagicMock(spec=PredictionJob)
    job.status = JobStatus.SUCCEEDED
    with patch("worker.tasks.SessionLocal") as m_local:
        session = MagicMock()
        session.get.return_value = job
        m_local.return_value = session
        from worker.tasks import run_prediction

        run_prediction(job_id)
        session.commit.assert_not_called()
        session.close.assert_called_once()


def test_run_prediction_user_or_model_missing(job_id: str) -> None:
    job = MagicMock(spec=PredictionJob)
    job.status = JobStatus.PENDING
    job.user_id = 1
    job.model_id = 2
    with patch("worker.tasks.SessionLocal") as m_local:
        session = MagicMock()

        def _get(model, pk):
            if model is PredictionJob:
                return job
            return None

        session.get.side_effect = _get
        m_local.return_value = session
        from worker.tasks import run_prediction

        run_prediction(job_id)
        assert job.status == JobStatus.FAILED
        session.commit.assert_called()
        session.close.assert_called_once()


def test_run_prediction_model_file_missing(job_id: str) -> None:
    job = MagicMock(spec=PredictionJob)
    job.status = JobStatus.PENDING
    job.user_id = 1
    job.model_id = 2
    user = MagicMock(spec=User)
    model_row = MagicMock(spec=MLModel)
    model_row.storage_filename = "missing.pkl"

    with patch("worker.tasks.SessionLocal") as m_local, patch("worker.tasks.os.path.isfile", return_value=False):
        session = MagicMock()

        def _get(model, pk):
            if model is PredictionJob:
                return job
            if model is User and pk == 1:
                return user
            if model is MLModel and pk == 2:
                return model_row
            return None

        session.get.side_effect = _get
        m_local.return_value = session
        from worker.tasks import run_prediction

        run_prediction(job_id)
        assert job.status == JobStatus.FAILED
        session.close.assert_called_once()


def test_run_prediction_predict_raises(job_id: str) -> None:
    job = MagicMock(spec=PredictionJob)
    job.status = JobStatus.PENDING
    job.user_id = 1
    job.model_id = 2
    job.input_features = [1.0, 2.0]
    user = MagicMock(spec=User)
    model_row = MagicMock(spec=MLModel)
    model_row.storage_filename = "x.pkl"

    with patch("worker.tasks.SessionLocal") as m_local, patch(
        "worker.tasks.os.path.isfile", return_value=True
    ), patch("worker.tasks.joblib.load", side_effect=RuntimeError("bad model")):
        session = MagicMock()

        def _get(model, pk):
            if model is PredictionJob:
                return job
            if model is User and pk == 1:
                return user
            if model is MLModel and pk == 2:
                return model_row
            return None

        session.get.side_effect = _get
        m_local.return_value = session
        from worker.tasks import run_prediction

        run_prediction(job_id)
        assert job.status == JobStatus.FAILED
        session.close.assert_called_once()


def test_run_prediction_insufficient_credits_at_charge(job_id: str) -> None:
    job = MagicMock(spec=PredictionJob)
    job.status = JobStatus.PENDING
    job.user_id = 1
    job.model_id = 2
    job.input_features = [1.0, 2.0]
    user = MagicMock(spec=User)
    model_row = MagicMock(spec=MLModel)
    model_row.storage_filename = "x.pkl"
    estimator = MagicMock()
    estimator.predict.return_value = __import__("numpy").array([1])

    with patch("worker.tasks.SessionLocal") as m_local, patch(
        "worker.tasks.os.path.isfile", return_value=True
    ), patch("worker.tasks.joblib.load", return_value=estimator), patch(
        "worker.tasks.discount_for_user", return_value=0
    ), patch(
        "worker.tasks.charge_prediction_success", side_effect=ValueError("INSUFFICIENT_CREDITS")
    ):
        session = MagicMock()

        def _get(model, pk):
            if model is PredictionJob:
                return job
            if model is User and pk == 1:
                return user
            if model is MLModel and pk == 2:
                return model_row
            return None

        session.get.side_effect = _get
        m_local.return_value = session
        from worker.tasks import run_prediction

        run_prediction(job_id)
        assert job.status == JobStatus.FAILED
        session.close.assert_called_once()


def test_run_prediction_success(job_id: str) -> None:
    job = MagicMock(spec=PredictionJob)
    job.status = JobStatus.PENDING
    job.user_id = 1
    job.model_id = 2
    job.input_features = [1.0, 2.0]
    user = MagicMock(spec=User)
    model_row = MagicMock(spec=MLModel)
    model_row.storage_filename = "x.pkl"
    estimator = MagicMock()
    estimator.predict.return_value = __import__("numpy").array([42.0])

    with patch("worker.tasks.SessionLocal") as m_local, patch(
        "worker.tasks.os.path.isfile", return_value=True
    ), patch("worker.tasks.joblib.load", return_value=estimator), patch(
        "worker.tasks.discount_for_user", return_value=10
    ), patch("worker.tasks.charge_prediction_success", return_value=9):
        session = MagicMock()

        def _get(model, pk):
            if model is PredictionJob:
                return job
            if model is User and pk == 1:
                return user
            if model is MLModel and pk == 2:
                return model_row
            return None

        session.get.side_effect = _get
        m_local.return_value = session
        from worker.tasks import run_prediction

        run_prediction(job_id)
        assert job.status == JobStatus.SUCCEEDED
        assert job.result == {"prediction": [42.0]}
        session.close.assert_called_once()


def test_recalculate_loyalty_monthly() -> None:
    with patch("worker.tasks.SessionLocal") as m_local, patch(
        "app.services.loyalty.recalculate_all_users_monthly_tiers", return_value=3
    ) as m_recalc:
        session = MagicMock()
        m_local.return_value = session
        from worker.tasks import recalculate_loyalty_monthly

        n = recalculate_loyalty_monthly()
        assert n == 3
        m_recalc.assert_called_once_with(session)
        session.commit.assert_called_once()
        session.close.assert_called_once()


def test_recalculate_loyalty_monthly_rollback() -> None:
    with patch("worker.tasks.SessionLocal") as m_local, patch(
        "app.services.loyalty.recalculate_all_users_monthly_tiers", side_effect=RuntimeError("db")
    ):
        session = MagicMock()
        m_local.return_value = session
        from worker.tasks import recalculate_loyalty_monthly

        with pytest.raises(RuntimeError):
            recalculate_loyalty_monthly()
        session.rollback.assert_called_once()
        session.close.assert_called_once()
