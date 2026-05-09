from __future__ import annotations

from app.metrics_extra import bump_prediction_completed, bump_prediction_enqueued


def test_metrics_bumps():
    bump_prediction_enqueued()
    bump_prediction_completed("succeeded")
    bump_prediction_completed("failed")
