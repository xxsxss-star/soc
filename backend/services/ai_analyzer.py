from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, cast

from openai import OpenAI

from backend.config import Settings, get_settings
from backend.models.ai_result import AIAnalysisResult, ConfidenceBreakdown, EvidenceReason
from backend.models.alert import Alert
from backend.models.evidence import EvidencePackage


class AIAnalysisError(RuntimeError):
    """Recognizable failure returned to the workflow instead of a fallback conclusion."""


class AIAnalyzer(Protocol):
    def analyze(self, alert: Alert, evidence: EvidencePackage) -> AIAnalysisResult: ...


def _confidence(total: int, reason: str) -> ConfidenceBreakdown:
    parts = [min(max(total - offset, 0), 25) for offset in (0, 25, 50, 75)]
    return ConfidenceBreakdown(
        evidence_completeness=parts[0],
        support_strength=parts[1],
        evidence_consistency=parts[2],
        conclusion_clarity=parts[3],
        total=total,
        reason=reason,
    )


class MockAIAnalyzer:
    """Deterministic structured results; validation is still performed downstream."""

    def analyze(self, alert: Alert, evidence: EvidencePackage) -> AIAnalysisResult:
        refs = [item.evidence_id for item in evidence.items]
        first_ref = refs[0] if refs else "EV-NOT-FOUND"

        if alert.alert_id == "ALT-008":
            return AIAnalysisResult(
                suggested_result="likely_false_positive",
                confidence=_confidence(90, "授权测试行为与非恶意情报相互一致"),
                supporting_evidence=[EvidenceReason(evidence_id=ref, reason="支持授权测试解释") for ref in refs],
                recommended_action="确认测试任务后标记为误报",
                summary="现有证据高度支持授权测试活动。",
            )
        if alert.alert_id == "ALT-009":
            return AIAnalysisResult(
                suggested_result="likely_false_positive",
                confidence=_confidence(70, "行为信息有限，结论清晰度不足"),
                supporting_evidence=[EvidenceReason(evidence_id=first_ref, reason="未发现明确高风险行为")],
                missing_evidence=["完整进程链", "有效授权记录"],
                recommended_action="由分析师补充进程和授权信息",
                summary="倾向误报，但证据强度不足，需要人工确认。",
            )
        if alert.alert_id == "ALT-006":
            return AIAnalysisResult(
                suggested_result="likely_true_positive",
                confidence=_confidence(92, "恶意情报与可疑载荷行为一致"),
                supporting_evidence=[EvidenceReason(evidence_id=ref, reason="支持真实攻击判断") for ref in refs],
                recommended_action="立即开展高优先级人工调查",
                summary="多项证据支持疑似真实攻击。",
            )
        if alert.alert_id in {"ALT-005", "ALT-MOCK-INSUFFICIENT"}:
            return AIAnalysisResult(
                suggested_result="insufficient_evidence",
                confidence=_confidence(55, "授权信息与恶意情报冲突"),
                supporting_evidence=[EvidenceReason(evidence_id=first_ref, reason="存在有效输入证据")],
                missing_evidence=["目标情报历史变化", "完整行为链"],
                recommended_action="人工核对授权目的和目标情报",
                summary="当前证据存在冲突，无法可靠判断。",
            )
        if alert.alert_id == "ALT-MOCK-INVALID-REF":
            return AIAnalysisResult(
                suggested_result="likely_false_positive",
                confidence=_confidence(90, "用于校验非法证据引用"),
                supporting_evidence=[EvidenceReason(evidence_id="EV-999", reason="不存在的证据")],
                recommended_action="test",
                summary="该结果应被验证器拒绝。",
            )
        if alert.alert_id == "ALT-MOCK-INVALID-SCHEMA":
            return cast(AIAnalysisResult, {"suggested_result": "not_a_valid_result"})

        return AIAnalysisResult(
            suggested_result="insufficient_evidence",
            confidence=_confidence(50, "没有该案例的专用 Mock 结论"),
            missing_evidence=["案例专用分析证据"],
            recommended_action="人工研判",
            summary="Mock 模式没有足够证据形成结论。",
        )


class LiveAIAnalyzer:
    def __init__(self, settings: Settings | None = None, client: OpenAI | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.openai_api_key or not self.settings.openai_model:
            raise ValueError("live AI mode requires OPENAI_API_KEY and OPENAI_MODEL")
        kwargs: dict[str, Any] = {
            "api_key": self.settings.openai_api_key,
            "timeout": self.settings.ai_timeout_seconds,
            "max_retries": 0,
        }
        if self.settings.openai_base_url:
            kwargs["base_url"] = self.settings.openai_base_url
        self.client = client or OpenAI(**kwargs)
        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "alert_analysis.txt"
        self.system_prompt = prompt_path.read_text(encoding="utf-8")

    def analyze(self, alert: Alert, evidence: EvidencePackage) -> AIAnalysisResult:
        safe_alert = {
            "alert_id": alert.alert_id,
            "alert_time": alert.alert_time.isoformat(),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "source": alert.source,
            "src_ip": str(alert.src_ip),
            "dst_ip": str(alert.dst_ip),
            "dst_port": alert.dst_port,
            "protocol": alert.protocol,
            "host_id": alert.host_id,
            "hostname": alert.hostname,
            "user": alert.user,
            "process": alert.process.model_dump(mode="json") if alert.process else None,
            "detection": alert.detection.model_dump(mode="json"),
        }
        payload = json.dumps(
            {"alert": safe_alert, "evidence_package": evidence.model_dump(mode="json")},
            ensure_ascii=False,
        )
        last_error: Exception | None = None
        for _attempt in range(self.settings.ai_max_retries + 1):
            try:
                response = self.client.responses.parse(
                    model=self.settings.openai_model,
                    instructions=self.system_prompt,
                    input=payload,
                    text_format=AIAnalysisResult,
                    timeout=self.settings.ai_timeout_seconds,
                )
                parsed = response.output_parsed
                if parsed is None:
                    raise ValueError("model response did not contain parsed structured output")
                return parsed
            except Exception as exc:
                last_error = exc
        raise AIAnalysisError(
            f"AI_UNAVAILABLE after {self.settings.ai_max_retries + 1} attempt(s): "
            f"{type(last_error).__name__}: {last_error}"
        ) from last_error


def create_ai_analyzer(settings: Settings | None = None) -> AIAnalyzer:
    selected = settings or get_settings()
    if selected.ai_mode == "live":
        return LiveAIAnalyzer(selected)
    return MockAIAnalyzer()
