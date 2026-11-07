"""Compile StateGraph: supervisor → specialists (parallel) → synthesizer → approval."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from mulat.clients.llm import get_chat_model
from mulat.logging_config import get_logger
from mulat.orchestration.agents.node_health import node_health_node
from mulat.orchestration.agents.pod_security import pod_security_node
from mulat.orchestration.agents.right_sizing import right_sizing_node
from mulat.orchestration.approval import approval_node
from mulat.orchestration.routing import supervisor_fan_out
from mulat.orchestration.state import GraphState
from mulat.orchestration.supervisor import supervisor_node_llm
from mulat.orchestration.synthesizer import synthesizer_node

logger = get_logger(__name__)

_SPECIALISTS = ("node_health", "right_sizing", "pod_security")
_FAN_OUT_PATHS = [*_SPECIALISTS, "synthesize"]


def build_graph(*, checkpointer: BaseCheckpointSaver | None = None, llm=None):
    """Build and compile the troubleshooter graph."""
    llm = llm or get_chat_model()
    logger.info("Building LangGraph (checkpointer=%s)", type(checkpointer).__name__)
    graph = StateGraph(GraphState)

    def node_health_step(state: GraphState) -> GraphState:
        return node_health_node(state, llm)

    def supervisor_node_step(state: GraphState) -> GraphState:
        return supervisor_node_llm(state, llm)

    def right_sizing_step(state: GraphState) -> GraphState:
        return right_sizing_node(state, llm)

    def synthesizer_step(state: GraphState) -> GraphState:
        return synthesizer_node(state, llm)

    def pod_security_step(state: GraphState) -> GraphState:
        return pod_security_node(state, llm)

    graph.add_node("supervisor", supervisor_node_step)
    graph.add_node("node_health", node_health_step)
    graph.add_node("right_sizing", right_sizing_step)
    graph.add_node("pod_security", pod_security_step)
    graph.add_node("synthesize", synthesizer_step)
    # graph.add_node("approval", approval_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", supervisor_fan_out, _FAN_OUT_PATHS)

    for name in _SPECIALISTS:
        graph.add_edge(name, "synthesize")

    # graph.add_edge("synthesize", "approval")
    # graph.add_edge("approval", END)
    graph.add_edge("synthesize", END)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("LangGraph compiled (parallel specialist fan-out)")
    return compiled
