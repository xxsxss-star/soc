from datetime import timedelta
from pathlib import Path

from backend.models.evidence import EvidenceItem, EvidencePackage
from backend.services.data_store import JsonDataStore


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def make_store() -> JsonDataStore:
    return JsonDataStore(DATA_DIR)


def test_all_json_files_load_and_alert_ids_are_unique() -> None:
    store = make_store()
    alerts = store.list_alerts()
    assert len(alerts) == 9
    assert len({alert.alert_id for alert in alerts}) == len(alerts)


def test_queries_all_four_evidence_types() -> None:
    store = make_store()
    alert = store.get_alert("ALT-001")
    assert alert is not None
    assert store.find_asset(alert.host_id)["asset_type"] == "security_test_server"
    assert store.find_approved_task(
        alert.user, alert.host_id, alert.alert_time, str(alert.dst_ip)
    )["task_id"] == "TASK-001"
    assert store.find_threat_intel(str(alert.dst_ip))["malicious"] is False
    assert store.find_related_events(
        alert.alert_id, alert.host_id, alert.alert_time
    )["alert_id"] == "ALT-001"


def test_approved_task_requires_user_host_time_and_target_scope() -> None:
    store = make_store()
    alert = store.get_alert("ALT-001")
    assert alert is not None
    assert store.find_approved_task(
        alert.user, alert.host_id, alert.alert_time, str(alert.dst_ip)
    ) is not None
    assert store.find_approved_task(
        "wrong-user", alert.host_id, alert.alert_time, str(alert.dst_ip)
    ) is None
    assert store.find_approved_task(
        alert.user, "wrong-host", alert.alert_time, str(alert.dst_ip)
    ) is None
    assert store.find_approved_task(
        alert.user, alert.host_id, alert.alert_time + timedelta(days=1), str(alert.dst_ip)
    ) is None
    assert store.find_approved_task(
        alert.user, alert.host_id, alert.alert_time, "203.0.113.200"
    ) is None


def test_related_events_falls_back_to_host_and_time_window() -> None:
    store = make_store()
    alert = store.get_alert("ALT-009")
    result = store.find_related_events(alert.alert_id, alert.host_id, alert.alert_time)
    assert result is not None
    assert result["alert_id"] is None
    assert result["host_id"] == "HOST-009"


def test_missing_data_returns_none() -> None:
    store = make_store()
    assert store.get_alert("ALT-404") is None
    assert store.find_asset("HOST-404") is None
    assert store.find_threat_intel("192.0.2.254") is None
    assert store.find_related_events(
        "ALT-404", "HOST-404", store.get_alert("ALT-001").alert_time
    ) is None


def test_demo_scenario_cannot_enter_evidence_models() -> None:
    alert = make_store().get_alert("ALT-001")
    package = EvidencePackage(
        alert_id=alert.alert_id,
        items=[EvidenceItem(
            evidence_id="EV-001",
            evidence_type="asset_context",
            source="mock_cmdb",
            observed_at=alert.alert_time,
            content={"asset_type": "security_test_server"},
        )],
    )
    serialized = package.model_dump()
    assert "demo_scenario" not in serialized
    assert "demo_scenario" not in serialized["items"][0]["content"]
