from __future__ import annotations

import os


def test_celery_beat_schedule_present(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv(
        "DATABASE_URL_SYNC",
        os.getenv("DATABASE_URL_SYNC", "postgresql://x:y@localhost:5432/z"),
    )
    from app.config import get_settings

    get_settings.cache_clear()
    from worker.celery_app import celery_app

    assert "loyalty-recalculate-monthly" in celery_app.conf.beat_schedule
