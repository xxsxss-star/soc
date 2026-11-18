from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Any

from backend.models.run import RunRecord


class RunRepository:
    """Thread-safe in-memory run storage for the single-process Demo."""

    _TERMINAL_STATUSES = {"completed", "failed"}

    def __init__(self) -> None:
        self._records: dict[str, RunRecord] = {}
        self._lock = RLock()

    def create(self, record: RunRecord) -> None:
        with self._lock:
            if record.run_id in self._records:
                raise ValueError(f"run already exists: {record.run_id}")
            self._records[record.run_id] = record.model_copy(deep=True)

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            record = self._records.get(run_id)
            return record.model_copy(deep=True) if record else None

    def update(self, run_id: str, **changes: Any) -> RunRecord:
        with self._lock:
            current = self._records.get(run_id)
            if current is None:
                raise KeyError(run_id)
            changes["updated_at"] = datetime.now().astimezone()
            updated = current.model_copy(update=changes, deep=True)
            self._records[run_id] = updated
            return updated.model_copy(deep=True)

    def find_active_by_alert(self, alert_id: str) -> RunRecord | None:
        with self._lock:
            for record in self._records.values():
                if record.alert_id == alert_id and record.status not in self._TERMINAL_STATUSES:
                    return record.model_copy(deep=True)
            return None

    def clear(self) -> int:
        with self._lock:
            count = len(self._records)
            self._records.clear()
            return count
