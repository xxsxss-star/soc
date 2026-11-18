from typing import Any

from pydantic import ValidationError

from backend.models.ai_result import AIAnalysisResult
from backend.models.evidence import EvidencePackage


class AIValidator:
    def validate(
        self,
        candidate: Any,
        evidence: EvidencePackage,
    ) -> tuple[AIAnalysisResult | None, list[str]]:
        try:
            result = (
                candidate
                if isinstance(candidate, AIAnalysisResult)
                else AIAnalysisResult.model_validate(candidate)
            )
        except ValidationError as exc:
            return None, [f"schema_validation_error: {exc}"]
        except (TypeError, ValueError) as exc:
            return None, [f"schema_validation_error: {exc}"]

        errors: list[str] = []
        confidence = result.confidence
        dimensions = (
            confidence.evidence_completeness,
            confidence.support_strength,
            confidence.evidence_consistency,
            confidence.conclusion_clarity,
        )
        if any(value < 0 or value > 25 for value in dimensions):
            errors.append("confidence_dimension_out_of_range")
        if sum(dimensions) != confidence.total:
            errors.append("confidence_total_mismatch")

        valid_refs = {item.evidence_id for item in evidence.items}
        used_refs = {
            reason.evidence_id
            for reason in result.supporting_evidence + result.contradicting_evidence
        }
        for invalid_ref in sorted(used_refs - valid_refs):
            errors.append(f"unknown_evidence_reference: {invalid_ref}")

        return (result if not errors else None), errors
