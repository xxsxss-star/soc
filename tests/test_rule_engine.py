from copy import deepcopy
from pathlib import Path

import pytest

from backend.models.evidence import EvidencePackage
from backend.services.data_store import JsonDataStore
from backend.services.evidence_builder import EvidenceBuilder
from backend.services.rule_engine import RuleEngine


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def store() -> JsonDataStore:
    return JsonDataStore(DATA_DIR)


def evaluate(store: JsonDataStore, alert_id: str):
    alert = store.get_alert(alert_id)
    evidence = EvidenceBuilder(store).build(alert)
    return RuleEngine().evaluate(alert, evidence)


def test_all_preset_scenarios_match_expected_rules(store: JsonDataStore) -> None:
    expected = {
        "ALT-001": "R-101",
        "ALT-002": "R-001",
        "ALT-003": "R-003",
        "ALT-004": "R-005",
        "ALT-005": "R-302",
        "ALT-006": "R-301",
        "ALT-007": "R-202",
        "ALT-008": "R-399",
        "ALT-009": "R-399",
    }
    assert {alert_id: evaluate(store, alert_id).matched_rule.rule_id for alert_id in expected} == expected


def test_high_risk_rule_precedes_r101(store: JsonDataStore) -> None:
    alert = store.get_alert("ALT-001")
    package = EvidenceBuilder(store).build(alert)
    behavior = next(item for item in package.items if item.evidence_type == "behavior_context")
    behavior.content["lateral_movement"] = True

    result = RuleEngine().evaluate(alert, package)

    assert result.matched_rule.rule_id == "R-001"
    assert result.decision == "HIGH_RISK"
    assert result.need_ai is False


@pytest.mark.parametrize(
    ("evidence_type", "field", "value"),
    [
        ("asset_context", "asset_type", "employee_workstation"),
        ("approved_activity", "within_approved_time", False),
        ("approved_activity", "within_target_scope", False),
        ("threat_intelligence", "malicious", True),
        ("behavior_context", "payload_download", True),
    ],
)
def test_r101_requires_every_condition(
    store: JsonDataStore, evidence_type: str, field: str, value: object
) -> None:
    alert = store.get_alert("ALT-001")
    package = EvidenceBuilder(store).build(alert)
    item = next(item for item in package.items if item.evidence_type == evidence_type)
    item.content[field] = value

    result = RuleEngine().evaluate(alert, package)

    assert result.matched_rule.rule_id != "R-101"


def test_r302_enters_ai_for_authorized_malicious_conflict(store: JsonDataStore) -> None:
    result = evaluate(store, "ALT-005")
    assert result.matched_rule.rule_id == "R-302"
    assert result.decision == "NEED_AI"
    assert result.need_ai is True


def test_r399_is_default_ai_entry(store: JsonDataStore) -> None:
    result = evaluate(store, "ALT-009")
    assert result.matched_rule.rule_id == "R-399"
    assert result.decision == "NEED_AI"
    assert result.need_ai is True


def test_missing_evidence_is_not_confirmed_as_false_positive(store: JsonDataStore) -> None:
    alert = store.get_alert("ALT-007")
    package = EvidenceBuilder(store).build(alert)
    result = RuleEngine().evaluate(alert, package)
    assert result.matched_rule.rule_id == "R-202"
    assert result.decision == "MANUAL_ENRICHMENT"
    assert result.need_human is True


def test_missing_critical_alert_field_hits_r201(store: JsonDataStore) -> None:
    alert = store.get_alert("ALT-001").model_copy(update={"host_id": ""})
    package = EvidenceBuilder(store).build(store.get_alert("ALT-001"))
    result = RuleEngine().evaluate(alert, package)
    assert result.matched_rule.rule_id == "R-201"
    assert result.decision == "MANUAL_ENRICHMENT"


def test_rule_result_exposes_top_level_evidence_refs(store: JsonDataStore) -> None:
    result = evaluate(store, "ALT-004")
    assert result.evidence_refs == ["EV-001", "EV-003"]
    assert result.evidence_refs == result.matched_rule.evidence_refs
