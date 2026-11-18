import operator
from typing import Annotated, Any, TypedDict

from backend.models.ai_result import AIAnalysisResult
from backend.models.alert import Alert
from backend.models.evidence import EvidencePackage
from backend.models.rule import RuleResult
from backend.models.run import DecisionResult, TimelineEvent


class WorkflowState(TypedDict, total=False):
    run_id: str
    alert_id: str
    alert: Alert
    status: str
    analysis_mode: str | None

    evidence_package: EvidencePackage
    evidence_complete: bool
    rule_result: RuleResult
    high_risk_veto: bool

    ai_raw_result: Any
    ai_result: AIAnalysisResult
    ai_analysis_error: str
    ai_validation_errors: list[str]

    decision: DecisionResult
    final_action: str
    need_human: bool
    final_reason: str

    timeline: Annotated[list[TimelineEvent], operator.add]
    errors: Annotated[list[str], operator.add]
