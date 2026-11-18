from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from backend.models.run import RunRecord
from backend.repositories.run_repository import RunRepository


def record(run_id: str, alert_id: str, status: str = "queued") -> RunRecord:
    now = datetime.now().astimezone()
    return RunRecord(
        run_id=run_id,
        alert_id=alert_id,
        status=status,
        analysis_mode=None,
        state={},
        created_at=now,
        updated_at=now,
    )


def test_repository_crud_active_lookup_and_clear() -> None:
    repository = RunRepository()
    repository.create(record("RUN-1", "ALT-001"))
    assert repository.get("RUN-1").alert_id == "ALT-001"
    assert repository.find_active_by_alert("ALT-001").run_id == "RUN-1"
    repository.update("RUN-1", status="completed")
    assert repository.find_active_by_alert("ALT-001") is None
    assert repository.clear() == 1
    assert repository.get("RUN-1") is None


def test_repository_is_safe_for_concurrent_creates_and_reads() -> None:
    repository = RunRepository()

    def create_and_read(index: int) -> str:
        run_id = f"RUN-{index}"
        repository.create(record(run_id, f"ALT-{index}"))
        return repository.get(run_id).run_id

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create_and_read, range(40)))
    assert len(set(results)) == 40
    assert repository.clear() == 40
