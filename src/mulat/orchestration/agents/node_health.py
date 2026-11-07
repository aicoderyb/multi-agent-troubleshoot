"""Node health specialist — collects list/describe/events/pods_per_node tool data."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from mulat.logging_config import get_logger
from mulat.orchestration.prompts_loader import load_prompt
from mulat.orchestration.state import GraphState
from mulat.tools.node_health.describe_node import describe_node_impl
from mulat.tools.node_health.list_nodes import list_nodes_impl
from mulat.tools.node_health.node_events import node_events_impl
from mulat.tools.node_health.pods_per_node import pods_per_node_impl

logger = get_logger(__name__)
_MAX_DETAIL_NODES = 3


def _node_name_from_request(request: str) -> str | None:
    match = re.search(r"\bnode[-_]?[\w.]+\b", request, re.I)
    return match.group(0) if match else None


def _pick_detail_nodes(state: GraphState, list_result: dict[str, Any]) -> list[str]:
    hints = state.get("hints") or {}
    if hint_node := hints.get("node"):
        return [str(hint_node)]

    if name := _node_name_from_request(state.get("request") or ""):
        return [name]

    if not list_result.get("ok"):
        return []

    nodes = list_result.get("data", {}).get("nodes") or []
    unhealthy = [n["name"] for n in nodes if not n.get("ready") or n.get("failing_conditions")]
    if unhealthy:
        return unhealthy[:_MAX_DETAIL_NODES]

    if len(nodes) == 1:
        return [nodes[0]["name"]]
    return [n["name"] for n in nodes[:_MAX_DETAIL_NODES]]


def collect_node_health_data(state: GraphState) -> dict[str, Any]:
    """Run all four node health tools; primary job of this agent."""
    only_unhealthy = "notready" in (state.get("request") or "").lower()
    list_result = list_nodes_impl(only_unhealthy=only_unhealthy)

    per_node: list[dict[str, Any]] = []
    for node_name in _pick_detail_nodes(state, list_result):
        per_node.append(
            {
                "node": node_name,
                "describe_node": describe_node_impl(name=node_name),
                "node_events": node_events_impl(node=node_name),
                "pods_per_node": pods_per_node_impl(node=node_name),
            }
        )

    return {
        "list_nodes": list_result,
        "per_node": per_node,
    }


def _summarize_with_llm(llm, payload: dict[str, Any], request: str) -> str:
    """Optional narrative; cluster data is already in payload."""
    try:
        system = load_prompt("node_health")
        text = json.dumps(payload, default=str)[:12_000]
        msg = llm.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(
                    content=(
                        f"Request: {request}\n\nTool results JSON:\n{text}\n\n"
                        "Write a short finding: likely cause, evidence, severity."
                    )
                ),
            ]
        )
        return msg.content if hasattr(msg, "content") else str(msg)
    except Exception as exc:
        logger.warning("LLM summary skipped: %s", exc)
        return _fallback_message(payload)


def _fallback_message(payload: dict[str, Any]) -> str:
    ln = payload.get("list_nodes") or {}
    if not ln.get("ok"):
        err = (ln.get("error") or {}).get("message", "list_nodes failed")
        return f"Node health check failed at list_nodes: {err}"
    count = (ln.get("data") or {}).get("count", 0)
    return f"Collected node health data for {count} node(s); see finding.data for tool JSON."


def node_health_node(state: GraphState, llm) -> GraphState:
    targets = state.get("targets") or []
    if "node_health" not in targets:
        logger.debug("node_health skipped (not in targets)")
        return {}

    request = state.get("request") or ""
    logger.info("node_health collecting tool data request=%r", request[:120])
    payload = collect_node_health_data(state)
    message = _summarize_with_llm(llm, payload, request)

    return {
        "findings": [
            {
                "agent": "node_health",
                "severity": "info",
                "message": message,
                "data": payload,
            }
        ]
    }
