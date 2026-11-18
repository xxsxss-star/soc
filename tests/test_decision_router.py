from backend.config import Settings
from backend.models.ai_result import AIAnalysisResult, ConfidenceBreakdown
from backend.models.rule import MatchedRule, RuleResult
from backend.services.decision_router import DecisionRouter


def rule(decision: str = "NEED_AI") -> RuleResult:
    return RuleResult(
        decision=decision,
        matched_rule=MatchedRule(
            rule_id="R-TEST", rule_name="test", reason="test", evidence_refs=[]
        ),
        evidence_refs=[],
        need_ai=decision == "NEED_AI",
        need_human=decision in {"HIGH_RISK", "MANUAL_ENRICHMENT"},
    )


def ai_result(suggested_result: str, total: int) -> AIAnalysisResult:
    first = min(total, 25)
    second = min(max(total - 25, 0), 25)
    third = min(max(total - 50, 0), 25)
    fourth = min(max(total - 75, 0), 25)
    return AIAnalysisResult(
        suggested_result=suggested_result,
        confidence=ConfidenceBreakdown(
            evidence_completeness=first,
            support_strength=second,
            evidence_consistency=third,
            conclusion_clarity=fourth,
            total=total,
            reason="constructed test result",
        ),
        recommended_action="test",
        summary="test",
    )


def test_rule_decisions_route_without_ai() -> None:
    router = DecisionRouter(Settings(AI_FALSE_POSITIVE_THRESHOLD=85))
    assert router.decide(rule("RULE_CONFIRMED_FP")).action == "confirm_false_positive_by_rule"
    assert router.decide(rule("RULE_CONFIRMED_FP")).need_human is False
    assert router.decide(rule("HIGH_RISK")).action == "high_priority_manual_investigation"
    assert router.decide(rule("MANUAL_ENRICHMENT")).action == "manual_enrichment"


def test_invalid_or_insufficient_ai_output_routes_to_manual_review() -> None:
    router = DecisionRouter(Settings(AI_FALSE_POSITIVE_THRESHOLD=85))
    assert router.decide(rule(), ai_validation_errors=["invalid_ref"]).action == "manual_review"
    assert router.decide(rule(), ai_result("insufficient_evidence", 60)).action == "manual_review"


def test_false_positive_confidence_boundary_84_and_85() -> None:
    router = DecisionRouter(Settings(AI_FALSE_POSITIVE_THRESHOLD=85))
    below = router.decide(rule(), ai_result("likely_false_positive", 84))
    at = router.decide(rule(), ai_result("likely_false_positive", 85))
    assert below.action == "manual_review"
    assert below.need_human is True
    assert at.action == "confirm_false_positive_by_ai"
    assert at.need_human is False


def test_likely_true_positive_cannot_be_automatically_disposed() -> None:
    router = DecisionRouter(Settings(AI_FALSE_POSITIVE_THRESHOLD=85))
    result = router.decide(rule(), ai_result("likely_true_positive", 100))
    assert result.action == "high_priority_manual_investigation"
    assert result.need_human is True


def test_router_uses_configured_threshold() -> None:
    router = DecisionRouter(Settings(AI_FALSE_POSITIVE_THRESHOLD=90))
    result = router.decide(rule(), ai_result("likely_false_positive", 89))
    assert result.action == "manual_review"
    assert "90" in result.reason
