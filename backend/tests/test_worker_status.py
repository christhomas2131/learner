"""Worker heartbeat / presence."""

from __future__ import annotations

from app.core.config import settings
from app.services.worker_status import touch_heartbeat, worker_status


def test_offline_without_heartbeat_then_online_after_touch():
    path = settings.heartbeat_path
    if path.exists():
        path.unlink()
    assert worker_status()["online"] is False

    touch_heartbeat()
    status = worker_status()
    assert status["online"] is True and status["last_seen"]

    path.unlink()
