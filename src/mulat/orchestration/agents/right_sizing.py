"""Right-sizing specialist — requests/limits + Prometheus usage (Tool_API)."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from mulat.logging_config import get_logger
from mulat.orchestration.prompts_loader import load_prompt
from mulat.orchestration.state import GraphState
from mulat.tools.right_sizing.get_requests_limits import get_requests_limits_impl
from mulat.tools.right_sizing.query_cpu_usage import query_cpu_usage_impl
from mulat.tools.right_sizing.query_memory_usage import query_memory_usage_impl

logger = get_logger(__name__)

_NAMESPACE_RE = re.compile(
    r"(?:\bin\s+)?(?:namespace|ns)\s+[`\"']?([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)",
    re.I,
)
_LLM_MAX_CHARS = 28_000
_LLM_MAX_ROWS = 120


def resolve_namespace(state: GraphState) -> str:
    """hints.namespace, else parse from natural-language request, else all."""
    hints = state.get("hints") or {}
    if hints.get("namespace"):
        return str(hints["namespace"])
    request = state.get("request") or ""
    if match := _NAMESPACE_RE.search(request):
        return match.group(1)
    return "all"


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("namespace") or ""),
        str(row.get("pod") or ""),
        str(row.get("container") or ""),
    )


def _merge_comparison_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    k8s = payload.get("get_requests_limits") or {}
    cpu = payload.get("query_cpu_usage") or {}
    mem = payload.get("query_memory_usage") or {}
    if not (k8s.get("ok") and cpu.get("ok") and mem.get("ok")):
        return []

    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for c in (k8s.get("data") or {}).get("containers") or []:
        by_key[_row_key(c)] = {
            "namespace": c.get("namespace"),
            "pod": c.get("pod"),
            "container": c.get("container"),
            "cpu_request_m": c.get("cpu_request_m"),
            "cpu_limit_m": c.get("cpu_limit_m"),
            "mem_request_mib": c.get("mem_request_mib"),
            "mem_limit_mib": c.get("mem_limit_mib"),
            "missing": c.get("missing"),
        }
    for s in (cpu.get("data") or {}).get("series") or []:
        key = _row_key(s)
        by_key.setdefault(
            key,
            {
                "namespace": s.get("namespace"),
                "pod": s.get("pod"),
                "container": s.get("container"),
            },
        )
        by_key[key]["cpu_usage_p95_m"] = s.get("value_m")
    for s in (mem.get("data") or {}).get("series") or []:
        key = _row_key(s)
        by_key.setdefault(
            key,
            {
                "namespace": s.get("namespace"),
                "pod": s.get("pod"),
                "container": s.get("container"),
            },
        )
        by_key[key]["mem_usage_max_mib"] = s.get("value_mib")

    rows = list(by_key.values())
    rows.sort(key=lambda r: (r.get("namespace") or "", r.get("pod") or "", r.get("container") or ""))
    return rows[:_LLM_MAX_ROWS]


def _build_llm_payload(payload: dict[str, Any], namespace: str) -> dict[str, Any]:
    cpu = payload.get("query_cpu_usage") or {}
    mem = payload.get("query_memory_usage") or {}
    k8s = payload.get("get_requests_limits") or {}

    def _status(tool: dict[str, Any], list_key: str) -> dict[str, Any]:
        items = (tool.get("data") or {}).get(list_key) or []
        return {
            "ok": tool.get("ok"),
            "error": tool.get("error"),
            "truncated": tool.get("truncated"),
            "count": len(items),
        }

    compact: dict[str, Any] = {
        "scope_namespace": namespace,
        "query_cpu_usage": _status(cpu, "series"),
        "query_memory_usage": _status(mem, "series"),
        "get_requests_limits": _status(k8s, "containers"),
        "comparison_rows": _merge_comparison_rows(payload),
    }
    if cpu.get("ok"):
        compact["query_cpu_usage"]["stat"] = (cpu.get("data") or {}).get("stat")
        compact["query_cpu_usage"]["lookback"] = (cpu.get("data") or {}).get("lookback")
    if mem.get("ok"):
        compact["query_memory_usage"]["stat"] = (mem.get("data") or {}).get("stat")
        compact["query_memory_usage"]["lookback"] = (mem.get("data") or {}).get("lookback")
    return compact


def collect_right_sizing_data(state: GraphState) -> dict[str, Any]:
    """Run all three right-sizing tools (Kubernetes + Prometheus)."""
    namespace = resolve_namespace(state)
    logger.info("right_sizing scope namespace=%r", namespace)
    k8s_limit = 200 if namespace != "all" else 80

    return {
        "scope_namespace": namespace,
        "get_requests_limits": get_requests_limits_impl(
            namespace="" if namespace == "all" else namespace,
            limit=k8s_limit,
        ),
        "query_cpu_usage": query_cpu_usage_impl(
            namespace=namespace, stat="p95", lookback="7d", limit=k8s_limit
        ),
        "query_memory_usage": query_memory_usage_impl(
            namespace=namespace, stat="max", lookback="7d", limit=k8s_limit
        ),
    }


def _summarize_with_llm(llm, payload: dict[str, Any], request: str) -> str:
    try:
        system = load_prompt("right_sizing")
        namespace = payload.get("scope_namespace") or "all"
        compact = _build_llm_payload(payload, namespace)
        text = json.dumps(compact, default=str)
        if len(text) > _LLM_MAX_CHARS:
            compact["comparison_rows"] = compact.get("comparison_rows") or []
            compact["comparison_rows"] = compact["comparison_rows"][: max(20, _LLM_MAX_ROWS // 2)]
            compact["note"] = "comparison_rows truncated for token limit"
            text = json.dumps(compact, default=str)[:_LLM_MAX_CHARS]
        msg = llm.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(
                    content=(
                        f"Request: {request}\n\nTool results JSON:\n{text}\n\n"
                        "Use comparison_rows (requests/limits vs cpu_usage_p95_m and "
                        "mem_usage_max_mib). Flag over- and under-provisioned workloads. "
                        "If a tool ok=false, say what failed. Do not change the cluster."
                    )
                ),
            ]
        )
        return msg.content if hasattr(msg, "content") else str(msg)
    except Exception as exc:
        logger.warning("Right-sizing LLM summary skipped: %s", exc)
        return _fallback_message(payload)


def _fallback_message(payload: dict[str, Any]) -> str:
    k8s = payload.get("get_requests_limits") or {}
    if not k8s.get("ok"):
        err = (k8s.get("error") or {}).get("message", "get_requests_limits failed")
        return f"Right-sizing failed at Kubernetes: {err}"
    count = len((k8s.get("data") or {}).get("containers") or [])
    return f"Collected requests/limits for {count} container(s); see finding.data for Prometheus series."


def right_sizing_node(state: GraphState, llm) -> GraphState:
    targets = state.get("targets") or []
    if "right_sizing" not in targets:
        logger.debug("right_sizing skipped (not in targets)")
        return {}

    request = state.get("request") or ""
    logger.info("right_sizing collecting tool data request=%r", request[:120])
    payload = collect_right_sizing_data(state)
    message = _summarize_with_llm(llm, payload, request)

    return {
        "findings": [
            {
                "agent": "right_sizing",
                "severity": "info",
                "message": message,
                "data": payload,
            }
        ]
    }
