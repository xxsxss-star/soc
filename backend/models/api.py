from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress

from backend.models.ai_result import AIAnalysisResult
from backend.models.evidence import EvidencePackage
from backend.models.rule import RuleResult
from backend.models.run import DecisionResult, HumanDecisionRecord, TimelineEvent


class AlertListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: str
    alert_name: str
    severity: Literal["low", "medium", "high", "critical"]
    source: str
    hostname: str
    dst_ip: IPvAnyAddress
    demo_scenario: str
    status: Literal["ready", "processing", "waiting_human", "completed", "failed"] = "ready"


class AlertListResponse(BaseModel):
    items: list[AlertListItem]


class CreateRunRequest(BaseModel):
    alert_id: str


class CreateRunResponse(BaseModel):
    run_id: str
    alert_id: str
    status: Literal["queued"] = "queued"
    poll_url: str


class RunResponse(BaseModel):
    run_id: str
    alert_id: str
    status: str
    analysis_mode: Literal["rule", "ai", "manual"] | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
    evidence_package: EvidencePackage | None = None
    rule_result: RuleResult | None = None
    ai_result: AIAnalysisResult | None = None
    decision: DecisionResult | None = None
    human_decision: HumanDecisionRecord | None = None


class HumanDecisionRequest(BaseModel):
    decision: Literal["confirm_false_positive", "confirm_true_positive", "continue_investigation"]
    comment: str = ""


class HumanDecisionResponse(BaseModel):
    run_id: str
    status: Literal["completed"] = "completed"
    human_decision: HumanDecisionRecord


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    ai_mode: Literal["mock", "live"]
    data_loaded: bool
    alert_count: int = Field(ge=0)


class DemoResetResponse(BaseModel):
    success: bool
    message: str
    alerts_reset: int = Field(ge=0)
    runs_removed: int = Field(ge=0)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
