from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MatchedRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_name: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)


class RuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["HIGH_RISK", "RULE_CONFIRMED_FP", "MANUAL_ENRICHMENT", "NEED_AI"]
    matched_rule: MatchedRule
    need_ai: bool
    need_human: bool
