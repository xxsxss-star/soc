from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    evidence_type: Literal[
        "asset_context", "approved_activity", "threat_intelligence", "behavior_context"
    ]
    source: str
    observed_at: datetime
    content: dict[str, Any]


class EvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: str
    items: list[EvidenceItem] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    retrieval_errors: list[str] = Field(default_factory=list)
