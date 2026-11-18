from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import RLock
from uuid import uuid4

from backend.models.run import HumanDecisionRecord, RunRecord
from backend.repositories.run_repository import RunRepository
from backend.services.data_store import JsonDataStore
from backend.workflow.graph import AlertWorkflow


class AlertNotFoundError(LookupError):
    pass


class ActiveRunExistsError(RuntimeError):
    def __init__(self, record: RunRecord) -> None:
        self.record = record
        super().__init__(f"active run already exists: {record.run_id}")


class RunNotFoundError(LookupError):
    pass


class InvalidRunStateError(RuntimeError):
    pass


class RunService:
    def __init__(
        self,
        *,
        data_store: JsonDataStore,
        workflow: AlertWorkflow,
        repository: RunRepository | None = None,
        max_workers: int = 2,
    ) -> None:
        self.data_store = data_store
        self.workflow = workflow
        self.repository = repository or RunRepository()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="alertlens")
        self._lock = RLock()
        self._generation = 0
        self._alert_statuses = {alert.alert_id: "ready" for alert in data_store.list_alerts()}

    def list_alerts_with_status(self) -> list[tuple[object, str]]:
        with self._lock:
            return [
                (alert, self._alert_statuses.get(alert.alert_id, "ready"))
                for alert in self.data_store.list_alerts()
            ]

    def create_run(self, alert_id: str) -> RunRecord:
        with self._lock:
            if self.data_store.get_alert(alert_id) is None:
                raise AlertNotFoundError(alert_id)
            active = self.repository.find_active_by_alert(alert_id)
            if active is not None:
                raise ActiveRunExistsError(active)
            now = datetime.now().astimezone()
            run_id = f"RUN-{uuid4().hex[:12]}"
            record = RunRecord(
                run_id=run_id,
                alert_id=alert_id,
                status="queued",
                analysis_mode=None,
                state=AlertWorkflow.initial_state(alert_id, run_id),
                created_at=now,
                updated_at=now,
            )
            self.repository.create(record)
            self._alert_statuses[alert_id] = "processing"
            generation = self._generation
            self._executor.submit(self._execute_workflow, run_id, alert_id, generation)
            return record

    def _execute_workflow(self, run_id: str, alert_id: str, generation: int) -> None:
        try:
            for state in self.workflow.stream(alert_id, run_id):
                if not self._update_if_current(run_id, generation, state):
                    return
        except Exception as exc:
            failure_state = {
                "run_id": run_id,
                "alert_id": alert_id,
                "status": "failed",
                "errors": [f"workflow_execution_error: {type(exc).__name__}: {exc}"],
                "timeline": [],
            }
            self._update_if_current(run_id, generation, failure_state)

    def _update_if_current(self, run_id: str, generation: int, state: dict) -> bool:
        with self._lock:
            if generation != self._generation or self.repository.get(run_id) is None:
                return False
            status = state.get("status", "failed")
            self.repository.update(
                run_id,
                status=status,
                analysis_mode=state.get("analysis_mode"),
                state=dict(state),
            )
            alert_id = state.get("alert_id")
            if alert_id:
                self._alert_statuses[alert_id] = self._alert_status_from_run(status)
            return True

    @staticmethod
    def _alert_status_from_run(status: str) -> str:
        if status == "waiting_human":
            return "waiting_human"
        if status in {"completed", "failed"}:
            return status
        return "processing"

    def get_run(self, run_id: str) -> RunRecord:
        record = self.repository.get(run_id)
        if record is None:
            raise RunNotFoundError(run_id)
        return record

    def submit_human_decision(
        self, run_id: str, decision: str, comment: str
    ) -> tuple[RunRecord, HumanDecisionRecord]:
        with self._lock:
            record = self.repository.get(run_id)
            if record is None:
                raise RunNotFoundError(run_id)
            if record.status != "waiting_human":
                raise InvalidRunStateError(
                    f"run {run_id} is {record.status}, expected waiting_human"
                )
            submitted = HumanDecisionRecord(
                decision=decision,
                comment=comment,
                submitted_at=datetime.now().astimezone(),
            )
            state = dict(record.state)
            state["human_decision"] = submitted
            state["status"] = "completed"
            state["analysis_mode"] = "manual"
            updated = self.repository.update(
                run_id,
                status="completed",
                analysis_mode="manual",
                state=state,
            )
            self._alert_statuses[record.alert_id] = "completed"
            return updated, submitted

    def reset(self) -> tuple[int, int]:
        with self._lock:
            self._generation += 1
            removed = self.repository.clear()
            self._alert_statuses = {
                alert.alert_id: "ready" for alert in self.data_store.list_alerts()
            }
            return len(self._alert_statuses), removed

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
