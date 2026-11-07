"""LangGraph routing: parallel fan-out from supervisor via Send."""

from __future__ import annotations

from langgraph.types import Send

from mulat.logging_config import get_logger
from mulat.orchestration.state import GraphState
from mulat.orchestration.supervisor import ALL_AGENTS

logger = get_logger(__name__)

_SPECIALIST_NODES = frozenset(ALL_AGENTS)


def supervisor_fan_out(state: GraphState) -> list[Send] | str:
    """Run selected specialists in parallel; skip straight to synthesize if none."""
    targets = state.get("targets") or []
    nodes = [t for t in targets if t in _SPECIALIST_NODES]
    if not nodes:
        logger.info("Supervisor fan-out: no specialists → synthesize")
        return "synthesize"
    logger.info("Supervisor fan-out parallel: %s", nodes)
    return [Send(node, state) for node in nodes]
