from pathlib import Path

import pytest

from backend.config import Settings
from backend.models.ai_result import AIAnalysisResult, ConfidenceBreakdown, EvidenceReason
from backend.services.ai_analyzer import MockAIAnalyzer
from backend.services.data_store import JsonDataStore
from backend.workflow.graph import AlertWorkflow


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        APP_ENV="test",
        AI_MODE="mock",
        DEMO_NODE_DELAY_MS=0,
        DATA_DIR=DATA_DIR,
        AI_FALSE_POSITIVE_THRESHOLD=85,
    )


class CountingAnalyzer:
    def __init__(self, delegate=None) -> None:
        self.delegate = delegate or MockAIAnalyzer()
        self.calls = 0

    def analyze(self, alert, evidence):
        self.calls += 1
        return self.delegate.analyze(alert, evidence)


class InvalidReferenceAnalyzer:
    def analyze(self, alert, evidence):
        return AIAnalysisResult(
            suggested_result="likely_false_positive",
            confidence=ConfidenceBreakdown(
                evidence_completeness=25,
                support_strength=25,
                evidence_consistency=20,
                conclusion_clarity=20,
                total=90,
                reason="invalid reference test",
            ),
            supporting_evidence=[EvidenceReason(evidence_id="EV-999", reason="invalid")],
            recommended_action="test",
            summary="test",
        )


class FailingAnalyzer:
    def analyze(self, alert, evidence):
        raise TimeoutError("AI timed out")


class FixedFalsePositiveAnalyzer:
    def __init__(self, total: int) -> None:
        self.total = total

    def analyze(self, alert, evidence):
        quotient, remainder = divmod(self.total, 4)
        scores = [quotient] * 4
        for index in range(remainder):
            scores[index] += 1
        return AIAnalysisResult(
            suggested_result="likely_false_positive",
            confidence=ConfidenceBreakdown(
                evidence_completeness=scores[0],
                support_strength=scores[1],
                evidence_consistency=scores[2],
                conclusion_clarity=scores[3],
                total=self.total,
                reason="R-302 threshold acceptance test",
            ),
            supporting_evidence=[EvidenceReason(evidence_id="EV-002", reason="有效授权")],
            contradicting_evidence=[EvidenceReason(evidence_id="EV-003", reason="恶意情报")],
            recommended_action="按阈值路由",
            summary="R-302 冲突证据的固定验收输出",
        )


def workflow(settings: Settings, analyzer=None) -> AlertWorkflow:
    return AlertWorkflow(
        data_store=JsonDataStore(DATA_DIR),
        ai_analyzer=analyzer or MockAIAnalyzer(),
        settings=settings,
    )


def test_rule_confirmed_path_does_not_call_ai(settings: Settings) -> None:
    analyzer = CountingAnalyzer()
    state = workflow(settings, analyzer).run("ALT-001")
    assert analyzer.calls == 0
    assert state["status"] == "completed"
    assert state["final_action"] == "confirm_false_positive_by_rule"
    assert "analyze_with_ai" not in [event.node for event in state["timeline"]]


def test_high_risk_path_does_not_call_ai(settings: Settings) -> None:
    analyzer = CountingAnalyzer()
    state = workflow(settings, analyzer).run("ALT-002")
    assert analyzer.calls == 0
    assert state["status"] == "waiting_human"
    assert state["final_action"] == "high_priority_manual_investigation"


def test_need_ai_path_calls_ai(settings: Settings) -> None:
    analyzer = CountingAnalyzer()
    state = workflow(settings, analyzer).run("ALT-008")
    assert analyzer.calls == 1
    assert state["analysis_mode"] == "ai"


@pytest.mark.parametrize(
    ("confidence", "expected_status", "expected_action", "need_human"),
    [
        (90, "completed", "confirm_false_positive_by_ai", False),
        (70, "waiting_human", "manual_review", True),
    ],
)
def test_r302_full_ai_path_on_both_sides_of_threshold(
    settings: Settings,
    confidence: int,
    expected_status: str,
    expected_action: str,
    need_human: bool,
) -> None:
    state = workflow(settings, FixedFalsePositiveAnalyzer(confidence)).run("ALT-005")
    assert state["rule_result"].matched_rule.rule_id == "R-302"
    assert state["ai_result"].confidence.total == confidence
    assert state["status"] == expected_status
    assert state["final_action"] == expected_action
    assert state["need_human"] is need_human


@pytest.mark.parametrize(
    ("alert_id", "expected_status", "expected_action"),
    [
        ("ALT-008", "completed", "confirm_false_positive_by_ai"),
        ("ALT-009", "waiting_human", "manual_review"),
        ("ALT-006", "waiting_human", "high_priority_manual_investigation"),
        ("ALT-005", "waiting_human", "manual_review"),
    ],
)
def test_mock_ai_decision_paths(
    settings: Settings, alert_id: str, expected_status: str, expected_action: str
) -> None:
    state = workflow(settings).run(alert_id)
    assert state["status"] == expected_status
    assert state["final_action"] == expected_action


def test_invalid_evidence_reference_routes_to_manual(settings: Settings) -> None:
    state = workflow(settings, InvalidReferenceAnalyzer()).run("ALT-009")
    assert state["status"] == "waiting_human"
    assert state["final_action"] == "manual_review"
    assert state["ai_validation_errors"] == ["unknown_evidence_reference: EV-999"]


def test_ai_exception_routes_to_manual_without_uncaught_crash(settings: Settings) -> None:
    state = workflow(settings, FailingAnalyzer()).run("ALT-009")
    assert state["status"] == "waiting_human"
    assert state["final_action"] == "manual_review"
    assert "TimeoutError" in state["ai_validation_errors"][0]
    ai_event = next(event for event in state["timeline"] if event.node == "analyze_with_ai")
    assert ai_event.status == "failed"


def test_timeline_node_order_for_rule_and_ai_paths(settings: Settings) -> None:
    rule_state = workflow(settings).run("ALT-001")
    ai_state = workflow(settings).run("ALT-008")
    assert [event.node for event in rule_state["timeline"]] == [
        "load_alert", "collect_evidence", "check_evidence", "evaluate_rules",
        "make_decision", "persist_result",
    ]
    assert [event.node for event in ai_state["timeline"]] == [
        "load_alert", "collect_evidence", "check_evidence", "evaluate_rules",
        "analyze_with_ai", "validate_ai_output", "make_decision", "persist_result",
    ]


def test_missing_alert_finishes_failed_instead_of_crashing(settings: Settings) -> None:
    state = workflow(settings).run("ALT-404")
    assert state["status"] == "failed"
    assert [event.node for event in state["timeline"]] == ["load_alert", "persist_result"]
