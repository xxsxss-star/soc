from __future__ import annotations

from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from backend.config import Settings, get_settings
from backend.services.ai_analyzer import AIAnalyzer, create_ai_analyzer
from backend.services.ai_validator import AIValidator
from backend.services.data_store import JsonDataStore
from backend.services.decision_router import DecisionRouter
from backend.services.evidence_builder import EvidenceBuilder
from backend.services.rule_engine import RuleEngine
from backend.workflow.nodes import WorkflowNodes
from backend.workflow.routes import route_after_rules, route_after_step
from backend.workflow.state import WorkflowState


def build_workflow(
    *,
    data_store: JsonDataStore,
    ai_analyzer: AIAnalyzer,
    settings: Settings,
):
    nodes = WorkflowNodes(
        data_store=data_store,
        evidence_builder=EvidenceBuilder(data_store),
        rule_engine=RuleEngine(),
        ai_analyzer=ai_analyzer,
        ai_validator=AIValidator(),
        decision_router=DecisionRouter(settings),
        settings=settings,
    )
    builder = StateGraph(WorkflowState)
    builder.add_node("load_alert", nodes.load_alert)
    builder.add_node("collect_evidence", nodes.collect_evidence)
    builder.add_node("check_evidence", nodes.check_evidence)
    builder.add_node("evaluate_rules", nodes.evaluate_rules)
    builder.add_node("analyze_with_ai", nodes.analyze_with_ai)
    builder.add_node("validate_ai_output", nodes.validate_ai_output)
    builder.add_node("make_decision", nodes.make_decision)
    builder.add_node("persist_result", nodes.persist_result)

    builder.add_edge(START, "load_alert")
    builder.add_conditional_edges(
        "load_alert",
        lambda state: route_after_step(state, "collect_evidence"),
        {"collect_evidence": "collect_evidence", "persist_result": "persist_result"},
    )
    builder.add_conditional_edges(
        "collect_evidence",
        lambda state: route_after_step(state, "check_evidence"),
        {"check_evidence": "check_evidence", "persist_result": "persist_result"},
    )
    builder.add_conditional_edges(
        "check_evidence",
        lambda state: route_after_step(state, "evaluate_rules"),
        {"evaluate_rules": "evaluate_rules", "persist_result": "persist_result"},
    )
    builder.add_conditional_edges(
        "evaluate_rules",
        route_after_rules,
        {
            "analyze_with_ai": "analyze_with_ai",
            "make_decision": "make_decision",
            "persist_result": "persist_result",
        },
    )
    builder.add_edge("analyze_with_ai", "validate_ai_output")
    builder.add_edge("validate_ai_output", "make_decision")
    builder.add_edge("make_decision", "persist_result")
    builder.add_edge("persist_result", END)
    return builder.compile(name="alertlens_workflow")


class AlertWorkflow:
    def __init__(
        self,
        data_store: JsonDataStore | None = None,
        ai_analyzer: AIAnalyzer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.data_store = data_store or JsonDataStore(self.settings.data_dir)
        self.ai_analyzer = ai_analyzer or create_ai_analyzer(self.settings)
        self.graph = build_workflow(
            data_store=self.data_store,
            ai_analyzer=self.ai_analyzer,
            settings=self.settings,
        )

    @staticmethod
    def initial_state(alert_id: str, run_id: str | None = None) -> WorkflowState:
        return {
            "run_id": run_id or f"RUN-{uuid4().hex[:12]}",
            "alert_id": alert_id,
            "status": "queued",
            "analysis_mode": None,
            "timeline": [],
            "errors": [],
            "ai_validation_errors": [],
        }

    def stream(self, alert_id: str, run_id: str | None = None):
        initial = self.initial_state(alert_id, run_id)
        yield from self.graph.stream(initial, stream_mode="values")

    def run(self, alert_id: str, run_id: str | None = None) -> WorkflowState:
        return self.graph.invoke(self.initial_state(alert_id, run_id))
