from __future__ import annotations

import time
from datetime import datetime

from backend.config import Settings
from backend.models.run import TimelineEvent
from backend.services.ai_analyzer import AIAnalyzer
from backend.services.ai_validator import AIValidator
from backend.services.data_store import JsonDataStore
from backend.services.decision_router import DecisionRouter
from backend.services.evidence_builder import EvidenceBuilder
from backend.services.rule_engine import RuleEngine
from backend.workflow.state import WorkflowState


class WorkflowNodes:
    def __init__(
        self,
        *,
        data_store: JsonDataStore,
        evidence_builder: EvidenceBuilder,
        rule_engine: RuleEngine,
        ai_analyzer: AIAnalyzer,
        ai_validator: AIValidator,
        decision_router: DecisionRouter,
        settings: Settings,
    ) -> None:
        self.data_store = data_store
        self.evidence_builder = evidence_builder
        self.rule_engine = rule_engine
        self.ai_analyzer = ai_analyzer
        self.ai_validator = ai_validator
        self.decision_router = decision_router
        self.settings = settings

    def _delay(self) -> None:
        if self.settings.app_env == "demo" and self.settings.demo_node_delay_ms:
            time.sleep(self.settings.demo_node_delay_ms / 1000)

    @staticmethod
    def _event(node: str, status: str, message: str, started: float) -> TimelineEvent:
        return TimelineEvent(
            node=node,
            status=status,
            message=message,
            timestamp=datetime.now().astimezone(),
            duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
        )

    def load_alert(self, state: WorkflowState) -> dict:
        started = time.perf_counter()
        try:
            alert = self.data_store.get_alert(state["alert_id"])
            if alert is None:
                raise LookupError(f"alert not found: {state['alert_id']}")
            self._delay()
            return {
                "alert": alert,
                "status": "collecting_evidence",
                "timeline": [self._event("load_alert", "completed", "告警加载完成", started)],
            }
        except Exception as exc:
            return {
                "status": "failed",
                "errors": [f"load_alert_error: {type(exc).__name__}: {exc}"],
                "timeline": [self._event("load_alert", "failed", str(exc), started)],
            }

    def collect_evidence(self, state: WorkflowState) -> dict:
        started = time.perf_counter()
        try:
            package = self.evidence_builder.build(state["alert"])
            self._delay()
            return {
                "evidence_package": package,
                "timeline": [self._event(
                    "collect_evidence", "completed",
                    f"已获取 {len(package.items)} 条标准化证据", started,
                )],
            }
        except Exception as exc:
            return {
                "status": "failed",
                "errors": [f"collect_evidence_error: {type(exc).__name__}: {exc}"],
                "timeline": [self._event("collect_evidence", "failed", str(exc), started)],
            }

    def check_evidence(self, state: WorkflowState) -> dict:
        started = time.perf_counter()
        try:
            package = state["evidence_package"]
            complete = not package.missing_evidence and not package.retrieval_errors
            self._delay()
            return {
                "evidence_complete": complete,
                "timeline": [self._event(
                    "check_evidence", "completed",
                    "证据完整" if complete else "证据存在缺失或查询错误", started,
                )],
            }
        except Exception as exc:
            return {
                "status": "failed",
                "errors": [f"check_evidence_error: {type(exc).__name__}: {exc}"],
                "timeline": [self._event("check_evidence", "failed", str(exc), started)],
            }

    def evaluate_rules(self, state: WorkflowState) -> dict:
        started = time.perf_counter()
        try:
            result = self.rule_engine.evaluate(state["alert"], state["evidence_package"])
            self._delay()
            return {
                "rule_result": result,
                "high_risk_veto": result.decision == "HIGH_RISK",
                "status": "rule_analyzing",
                "analysis_mode": "ai" if result.decision == "NEED_AI" else "rule",
                "timeline": [self._event(
                    "evaluate_rules", "completed",
                    f"命中 {result.matched_rule.rule_id}：{result.matched_rule.rule_name}", started,
                )],
            }
        except Exception as exc:
            return {
                "status": "failed",
                "errors": [f"evaluate_rules_error: {type(exc).__name__}: {exc}"],
                "timeline": [self._event("evaluate_rules", "failed", str(exc), started)],
            }

    def analyze_with_ai(self, state: WorkflowState) -> dict:
        started = time.perf_counter()
        try:
            candidate = self.ai_analyzer.analyze(state["alert"], state["evidence_package"])
            self._delay()
            return {
                "ai_raw_result": candidate,
                "status": "ai_analyzing",
                "analysis_mode": "ai",
                "timeline": [self._event(
                    "analyze_with_ai", "completed", "AI 结构化分析完成", started,
                )],
            }
        except Exception as exc:
            message = f"ai_analysis_error: {type(exc).__name__}: {exc}"
            return {
                "ai_analysis_error": message,
                "ai_validation_errors": [message],
                "status": "ai_analyzing",
                "analysis_mode": "ai",
                "timeline": [self._event("analyze_with_ai", "failed", message, started)],
            }

    def validate_ai_output(self, state: WorkflowState) -> dict:
        started = time.perf_counter()
        existing_errors = list(state.get("ai_validation_errors", []))
        if existing_errors:
            self._delay()
            return {
                "ai_validation_errors": existing_errors,
                "timeline": [self._event(
                    "validate_ai_output", "completed", "AI 调用失败，转人工确认", started,
                )],
            }
        result, errors = self.ai_validator.validate(
            state.get("ai_raw_result"), state["evidence_package"]
        )
        self._delay()
        output: dict = {
            "ai_validation_errors": errors,
            "timeline": [self._event(
                "validate_ai_output", "completed",
                "AI 输出校验通过" if not errors else "AI 输出校验失败，转人工确认",
                started,
            )],
        }
        if result is not None:
            output["ai_result"] = result
        return output

    def make_decision(self, state: WorkflowState) -> dict:
        started = time.perf_counter()
        try:
            decision = self.decision_router.decide(
                state["rule_result"],
                state.get("ai_result"),
                state.get("ai_validation_errors"),
            )
            status = "waiting_human" if decision.need_human else "completed"
            self._delay()
            return {
                "decision": decision,
                "final_action": decision.action,
                "need_human": decision.need_human,
                "final_reason": decision.reason,
                "status": status,
                "timeline": [self._event(
                    "make_decision", "completed", decision.reason, started,
                )],
            }
        except Exception as exc:
            return {
                "status": "failed",
                "errors": [f"make_decision_error: {type(exc).__name__}: {exc}"],
                "timeline": [self._event("make_decision", "failed", str(exc), started)],
            }

    def persist_result(self, state: WorkflowState) -> dict:
        started = time.perf_counter()
        status = "failed" if state.get("errors") else state.get("status", "failed")
        self._delay()
        return {
            "status": status,
            "timeline": [self._event(
                "persist_result", "completed",
                f"运行结果已汇总，最终状态为 {status}", started,
            )],
        }
