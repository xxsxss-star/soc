from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: str
    status: Literal["started", "completed", "failed"]
    message: str
    timestamp: datetime
    duration_ms: int | None = Field(default=None, ge=0)


class DecisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "confirm_false_positive_by_rule", "confirm_false_positive_by_ai",
        "high_priority_manual_investigation", "manual_enrichment", "manual_review",
    ]
    need_human: bool
    reason: str


class HumanDecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal[
        "confirm_false_positive", "confirm_true_positive", "continue_investigation"
    ]
    comment: str
    submitted_at: datetime


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    alert_id: str
    status: Literal[
        "queued", "collecting_evidence", "rule_analyzing", "ai_analyzing",
        "waiting_human", "completed", "failed",
    ]
    analysis_mode: Literal["rule", "ai", "manual"] | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
