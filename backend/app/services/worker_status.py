"""Premium (Claude Code) worker presence via a heartbeat file.

The worker touches a file; the API reports online/offline from its age. A file
(not a DB row) keeps this off the SQLite write path entirely.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import settings


def touch_heartbeat() -> None:
    path = settings.heartbeat_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(datetime.now(UTC).isoformat())


def worker_status() -> dict:
    path = settings.heartbeat_path
    if not path.exists():
        return {"online": False, "last_seen": None}
    try:
        stamp = path.read_text().strip()
        last = datetime.fromisoformat(stamp)
    except (OSError, ValueError):
        return {"online": False, "last_seen": None}
    age = (datetime.now(UTC) - last).total_seconds()
    return {"online": age <= settings.WORKER_HEARTBEAT_TTL, "last_seen": stamp}
