from backend.workflow.state import WorkflowState


def route_after_step(state: WorkflowState, next_node: str) -> str:
    if state.get("status") == "failed" or state.get("errors"):
        return "persist_result"
    return next_node


def route_after_rules(state: WorkflowState) -> str:
    if state.get("status") == "failed" or state.get("errors"):
        return "persist_result"
    rule_result = state.get("rule_result")
    if rule_result and rule_result.decision == "NEED_AI":
        return "analyze_with_ai"
    return "make_decision"
