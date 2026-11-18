from pathlib import Path

import pytest

from backend.config import Settings
from backend.models.ai_result import AIAnalysisResult, ConfidenceBreakdown, EvidenceReason
from backend.services.ai_analyzer import AIAnalysisError, LiveAIAnalyzer, MockAIAnalyzer
from backend.services.ai_validator import AIValidator
from backend.services.data_store import JsonDataStore
from backend.services.evidence_builder import EvidenceBuilder


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_mock_analyzer_covers_structured_scenarios() -> None:
    store = JsonDataStore(DATA_DIR)
    builder = EvidenceBuilder(store)
    analyzer = MockAIAnalyzer()
    expected = {
        "ALT-008": ("likely_false_positive", 90),
        "ALT-009": ("likely_false_positive", 70),
        "ALT-006": ("likely_true_positive", 92),
        "ALT-005": ("insufficient_evidence", 55),
    }
    for alert_id, (result_name, total) in expected.items():
        alert = store.get_alert(alert_id)
        result = analyzer.analyze(alert, builder.build(alert))
        assert result.suggested_result == result_name
        assert result.confidence.total == total


def test_mock_invalid_reference_is_rejected_by_same_validator() -> None:
    store = JsonDataStore(DATA_DIR)
    alert = store.get_alert("ALT-009").model_copy(update={"alert_id": "ALT-MOCK-INVALID-REF"})
    evidence = EvidenceBuilder(store).build(store.get_alert("ALT-009"))
    candidate = MockAIAnalyzer().analyze(alert, evidence)
    result, errors = AIValidator().validate(candidate, evidence)
    assert result is None
    assert errors == ["unknown_evidence_reference: EV-999"]


def test_mock_invalid_schema_is_rejected_by_same_validator() -> None:
    store = JsonDataStore(DATA_DIR)
    alert = store.get_alert("ALT-009").model_copy(
        update={"alert_id": "ALT-MOCK-INVALID-SCHEMA"}
    )
    evidence = EvidenceBuilder(store).build(store.get_alert("ALT-009"))
    candidate = MockAIAnalyzer().analyze(alert, evidence)
    result, errors = AIValidator().validate(candidate, evidence)
    assert result is None
    assert errors[0].startswith("schema_validation_error:")


@pytest.mark.parametrize(
    "candidate",
    [
        {"suggested_result": "invalid_enum"},
        {
            "suggested_result": "likely_false_positive",
            "confidence": {
                "evidence_completeness": 26,
                "support_strength": 25,
                "evidence_consistency": 25,
                "conclusion_clarity": 25,
                "total": 101,
                "reason": "invalid",
            },
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "missing_evidence": [],
            "recommended_action": "test",
            "summary": "test",
        },
        {
            "suggested_result": "likely_false_positive",
            "confidence": {
                "evidence_completeness": 20,
                "support_strength": 20,
                "evidence_consistency": 20,
                "conclusion_clarity": 20,
                "total": 79,
                "reason": "mismatch",
            },
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "missing_evidence": [],
            "recommended_action": "test",
            "summary": "test",
        },
    ],
)
def test_validator_rejects_schema_enum_range_and_total_errors(candidate: dict) -> None:
    store = JsonDataStore(DATA_DIR)
    evidence = EvidenceBuilder(store).build(store.get_alert("ALT-008"))
    result, errors = AIValidator().validate(candidate, evidence)
    assert result is None
    assert errors and errors[0].startswith("schema_validation_error:")


class FailingResponses:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        raise TimeoutError("model timeout")


class FakeClient:
    def __init__(self) -> None:
        self.responses = FailingResponses()


def test_live_analyzer_retries_once_sanitizes_input_and_never_falls_back() -> None:
    settings = Settings(
        APP_ENV="test",
        AI_MODE="live",
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="test-model",
        AI_MAX_RETRIES=1,
        AI_TIMEOUT_SECONDS=1,
    )
    fake = FakeClient()
    analyzer = LiveAIAnalyzer(settings, client=fake)
    store = JsonDataStore(DATA_DIR)
    alert = store.get_alert("ALT-008")

    with pytest.raises(AIAnalysisError, match="AI_UNAVAILABLE"):
        analyzer.analyze(alert, EvidenceBuilder(store).build(alert))

    assert len(fake.responses.calls) == 2
    sent = fake.responses.calls[0]["input"]
    assert "demo_scenario" not in sent
    assert alert.demo_scenario not in sent
    assert fake.responses.calls[0]["text_format"] is AIAnalysisResult
