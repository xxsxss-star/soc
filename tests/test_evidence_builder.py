from pathlib import Path

from backend.services.data_store import JsonDataStore
from backend.services.evidence_builder import EvidenceBuilder


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_builds_evidence_in_fixed_slots_without_demo_scenario() -> None:
    store = JsonDataStore(DATA_DIR)
    alert = store.get_alert("ALT-001")
    package = EvidenceBuilder(store).build(alert)

    assert [item.evidence_id for item in package.items] == [
        "EV-001", "EV-002", "EV-003", "EV-004"
    ]
    assert [item.evidence_type for item in package.items] == [
        "asset_context", "approved_activity", "threat_intelligence", "behavior_context"
    ]
    assert package.missing_evidence == []
    assert package.retrieval_errors == []
    assert "demo_scenario" not in package.model_dump_json()


def test_missing_evidence_is_listed_and_not_fabricated() -> None:
    store = JsonDataStore(DATA_DIR)
    package = EvidenceBuilder(store).build(store.get_alert("ALT-007"))

    assert package.items == []
    assert package.missing_evidence == [
        "asset_context_not_found",
        "approved_activity_not_found",
        "threat_intelligence_not_found",
        "behavior_context_not_found",
    ]


def test_query_exception_is_isolated_in_retrieval_errors() -> None:
    store = JsonDataStore(DATA_DIR)
    alert = store.get_alert("ALT-001")
    store.find_asset = lambda _host_id: (_ for _ in ()).throw(RuntimeError("cmdb down"))

    package = EvidenceBuilder(store).build(alert)

    assert "asset_context_retrieval_error: RuntimeError: cmdb down" in package.retrieval_errors
    assert "EV-001" not in {item.evidence_id for item in package.items}
    assert "asset_context_not_found" not in package.missing_evidence
    assert {item.evidence_id for item in package.items} == {"EV-002", "EV-003", "EV-004"}
