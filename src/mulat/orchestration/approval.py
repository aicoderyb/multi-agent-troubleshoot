"""Human approval gate via LangGraph interrupt()."""

from langgraph.types import interrupt

from mulat.orchestration.state import GraphState


def approval_node(state: GraphState) -> GraphState:
    report = state.get("report") or {}
    decision = interrupt(
        {
            "report": report,
            "ask": "Approve sending this report and any suggested follow-ups?",
        }
    )
    return {"report": {**report, "approval": decision}}
