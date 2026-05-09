"""Prometheus counters/metrics helpers shared by API."""

from prometheus_client import Counter

predictions_enqueued_total = Counter(
    "ml_predictions_enqueued_total",
    "Prediction jobs accepted into queue",
)

predictions_completed_total = Counter(
    "ml_predictions_completed_total",
    "Prediction jobs finished",
    ["status"],
)


def bump_prediction_enqueued() -> None:
    predictions_enqueued_total.inc()


def bump_prediction_completed(status: str) -> None:
    predictions_completed_total.labels(status=status).inc()
