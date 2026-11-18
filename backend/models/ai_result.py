from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfidenceBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_completeness: int = Field(ge=0, le=25)
    support_strength: int = Field(ge=0, le=25)
    evidence_consistency: int = Field(ge=0, le=25)
    conclusion_clarity: int = Field(ge=0, le=25)
    total: int = Field(ge=0, le=100)
    reason: str

    @model_validator(mode="after")
    def validate_total(self) -> "ConfidenceBreakdown":
        parts = (
            self.evidence_completeness + self.support_strength
            + self.evidence_consistency + self.conclusion_clarity
        )
        if parts != self.total:
            raise ValueError("total must equal the sum of the four confidence dimensions")
        return self


class EvidenceReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    reason: str


class AIAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggested_result: Literal[
        "likely_false_positive", "likely_true_positive", "insufficient_evidence"
    ]
    confidence: ConfidenceBreakdown
    supporting_evidence: list[EvidenceReason] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceReason] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_action: str
    summary: str
