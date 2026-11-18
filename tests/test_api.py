import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def client():
    settings = Settings(
        APP_ENV="test",
        AI_MODE="mock",
        DEMO_NODE_DELAY_MS=0,
        DATA_DIR=DATA_DIR,
    )
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def wait_for_status(
    client: TestClient,
    run_id: str,
    statuses: set[str] = {"completed", "waiting_human", "failed"},
    timeout: float = 3,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in statuses:
            return payload
        time.sleep(0.01)
    pytest.fail(f"run {run_id} did not reach {statuses}")


def test_alerts_and_health_return_200_without_secrets(client: TestClient) -> None:
    alerts = client.get("/api/v1/alerts")
    assert alerts.status_code == 200
    assert len(alerts.json()["items"]) == 9
    assert all(item["status"] == "ready" for item in alerts.json()["items"])

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "ai_mode": "mock",
        "data_loaded": True,
        "alert_count": 9,
    }
    assert "api_key" not in health.text.lower()


def test_create_returns_202_and_poll_returns_completed_results(client: TestClient) -> None:
    created = client.post("/api/v1/runs", json={"alert_id": "ALT-008"})
    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "queued"
    assert body["poll_url"] == f"/api/v1/runs/{body['run_id']}"

    result = wait_for_status(client, body["run_id"])
    assert result["status"] == "completed"
    assert result["evidence_package"] is not None
    assert result["rule_result"]["matched_rule"]["rule_id"] == "R-399"
    assert result["ai_result"]["confidence"]["total"] == 90
    assert result["decision"]["action"] == "confirm_false_positive_by_ai"
    assert [event["node"] for event in result["timeline"]][-1] == "persist_result"


def test_missing_alert_and_run_use_unified_404_errors(client: TestClient) -> None:
    missing_alert = client.post("/api/v1/runs", json={"alert_id": "ALT-404"})
    assert missing_alert.status_code == 404
    assert missing_alert.json()["error"]["code"] == "ALERT_NOT_FOUND"
    assert "details" in missing_alert.json()["error"]

    missing_run = client.get("/api/v1/runs/RUN-404")
    assert missing_run.status_code == 404
    assert missing_run.json()["error"]["code"] == "RUN_NOT_FOUND"

    invalid_request = client.post("/api/v1/runs", json={})
    assert invalid_request.status_code == 422
    assert invalid_request.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert "details" in invalid_request.json()["error"]


def test_duplicate_active_alert_returns_409(client: TestClient) -> None:
    first = client.post("/api/v1/runs", json={"alert_id": "ALT-002"})
    assert first.status_code == 202
    waiting = wait_for_status(client, first.json()["run_id"])
    assert waiting["status"] == "waiting_human"

    duplicate = client.post("/api/v1/runs", json={"alert_id": "ALT-002"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ACTIVE_RUN_EXISTS"
    assert duplicate.json()["error"]["details"]["run_id"] == first.json()["run_id"]


@pytest.mark.parametrize(
    "decision",
    ["confirm_false_positive", "confirm_true_positive", "continue_investigation"],
)
def test_human_decision_supported_and_audited(client: TestClient, decision: str) -> None:
    created = client.post("/api/v1/runs", json={"alert_id": "ALT-002"}).json()
    wait_for_status(client, created["run_id"])
    response = client.post(
        f"/api/v1/runs/{created['run_id']}/human-decision",
        json={"decision": decision, "comment": "analyst checked evidence"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["human_decision"]["decision"] == decision
    assert response.json()["human_decision"]["comment"] == "analyst checked evidence"
    assert response.json()["human_decision"]["submitted_at"]

    polled = client.get(f"/api/v1/runs/{created['run_id']}").json()
    assert polled["status"] == "completed"
    assert polled["analysis_mode"] == "manual"
    assert polled["human_decision"]["decision"] == decision


def test_repeated_or_invalid_state_human_decision_returns_409(client: TestClient) -> None:
    waiting_run = client.post("/api/v1/runs", json={"alert_id": "ALT-002"}).json()
    wait_for_status(client, waiting_run["run_id"])
    endpoint = f"/api/v1/runs/{waiting_run['run_id']}/human-decision"
    payload = {"decision": "continue_investigation", "comment": "first submission"}
    assert client.post(endpoint, json=payload).status_code == 200
    repeated = client.post(endpoint, json=payload)
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "INVALID_RUN_STATE"

    completed_run = client.post("/api/v1/runs", json={"alert_id": "ALT-001"}).json()
    wait_for_status(client, completed_run["run_id"])
    invalid = client.post(
        f"/api/v1/runs/{completed_run['run_id']}/human-decision",
        json={"decision": "confirm_false_positive", "comment": "not allowed"},
    )
    assert invalid.status_code == 409


def test_reset_clears_runs_and_restores_alerts_without_modifying_data(client: TestClient) -> None:
    alerts_file = DATA_DIR / "alerts.json"
    before = alerts_file.read_bytes()
    created = client.post("/api/v1/runs", json={"alert_id": "ALT-002"}).json()
    wait_for_status(client, created["run_id"])

    reset = client.post("/api/v1/demo/reset")
    assert reset.status_code == 200
    assert reset.json()["alerts_reset"] == 9
    assert reset.json()["runs_removed"] == 1
    assert client.get(f"/api/v1/runs/{created['run_id']}").status_code == 404
    assert all(
        item["status"] == "ready"
        for item in client.get("/api/v1/alerts").json()["items"]
    )
    assert alerts_file.read_bytes() == before
