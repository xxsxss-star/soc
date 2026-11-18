from backend.config import Settings, get_settings
from backend.models.ai_result import AIAnalysisResult
from backend.models.rule import RuleResult
from backend.models.run import DecisionResult


class DecisionRouter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def decide(
        self,
        rule_result: RuleResult,
        ai_result: AIAnalysisResult | None = None,
        ai_validation_errors: list[str] | None = None,
    ) -> DecisionResult:
        if rule_result.decision == "RULE_CONFIRMED_FP":
            return DecisionResult(
                action="confirm_false_positive_by_rule",
                need_human=False,
                reason="确定性规则已满足明确误报的全部条件",
            )
        if rule_result.decision == "HIGH_RISK":
            return DecisionResult(
                action="high_priority_manual_investigation",
                need_human=True,
                reason="命中高风险否决规则，禁止自动确认误报",
            )
        if rule_result.decision == "MANUAL_ENRICHMENT":
            return DecisionResult(
                action="manual_enrichment",
                need_human=True,
                reason="关键字段或证据缺失，需要人工补充信息",
            )
        if ai_validation_errors:
            return DecisionResult(
                action="manual_review",
                need_human=True,
                reason="AI 输出校验失败，需要人工确认",
            )
        if ai_result is None:
            return DecisionResult(
                action="manual_review",
                need_human=True,
                reason="缺少有效 AI 分析结果，需要人工确认",
            )
        if ai_result.suggested_result == "insufficient_evidence":
            return DecisionResult(
                action="manual_review",
                need_human=True,
                reason="AI 判断证据不足，需要人工确认",
            )
        if ai_result.suggested_result == "likely_true_positive":
            return DecisionResult(
                action="high_priority_manual_investigation",
                need_human=True,
                reason="AI 建议为疑似真实攻击，必须进行高优先级人工调查",
            )
        if ai_result.confidence.total >= self.settings.ai_false_positive_threshold:
            return DecisionResult(
                action="confirm_false_positive_by_ai",
                need_human=False,
                reason=(
                    "AI 建议为疑似误报且置信度达到配置阈值 "
                    f"{self.settings.ai_false_positive_threshold}"
                ),
            )
        return DecisionResult(
            action="manual_review",
            need_human=True,
            reason=(
                "AI 疑似误报置信度未达到配置阈值 "
                f"{self.settings.ai_false_positive_threshold}"
            ),
        )
