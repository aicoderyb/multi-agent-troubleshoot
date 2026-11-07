"""Pod security specialist — PSS rules and unpinned images."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from mulat.logging_config import get_logger
from mulat.orchestration.prompts_loader import load_prompt
from mulat.orchestration.state import GraphState
from mulat.tools.pod_security.check_security_context import check_security_context_impl
from mulat.tools.pod_security.find_latest_tags import find_latest_tags_impl

logger = get_logger(__name__)

_NAMESPACE_RE = re.compile(
    r"(?:\bin\s+)?(?:namespace|ns)\s+[`\"']?([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)",
    re.I,
)
_LLM_MAX_CHARS = 24_000
_FINDING_PREVIEW = 80


def resolve_namespace(state: GraphState) -> str:
    hints = state.get("hints") or {}
    if hints.get("namespace"):
        return str(hints["namespace"])
    request = state.get("request") or ""
    if match := _NAMESPACE_RE.search(request):
        return match.group(1)
    return "all"


def _max_finding_severity(payload: dict[str, Any]) -> str:
    check = payload.get("check_security_context") or {}
    if not check.get("ok"):
        return "info"
    by_sev = (check.get("data") or {}).get("summary", {}).get("findings_by_severity") or {}
    if by_sev.get("high"):
        return "high"
    if by_sev.get("medium"):
        return "medium"
    if by_sev.get("low"):
        return "low"
    tags = payload.get("find_latest_tags") or {}
    if tags.get("ok"):
        counts = (tags.get("data") or {}).get("summary", {}).get("counts_by_issue") or {}
        if counts:
            return "medium"
    return "info"


def collect_pod_security_data(state: GraphState) -> dict[str, Any]:
    namespace = resolve_namespace(state)
    logger.info("pod_security scope namespace=%r", namespace)
    payload: dict[str, Any] = {"scope_namespace": namespace}

    if namespace != "all":
        payload["check_security_context"] = check_security_context_impl(
            namespace=namespace,
            level="baseline",
            max_pods=100,
        )
    else:
        from mulat.tools import errors
        from mulat.tools.envelope import failure

        payload["check_security_context"] = failure(
            "check_security_context",
            errors.INVALID_INPUT,
            "PSS namespace scan requires a namespace (hints.namespace or 'in namespace ...')",
            retryable=False,
        )

    payload["find_latest_tags"] = find_latest_tags_impl(
        namespace="" if namespace == "all" else namespace,
        limit=200,
    )
    return payload


def _build_llm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    check = payload.get("check_security_context") or {}
    tags = payload.get("find_latest_tags") or {}

    def _check_compact() -> dict[str, Any]:
        if not check.get("ok"):
            return {"ok": False, "error": check.get("error")}
        data = check.get("data") or {}
        findings = list(data.get("findings") or [])[:_FINDING_PREVIEW]
        return {
            "ok": True,
            "summary": data.get("summary"),
            "psa_enforced_level": data.get("psa_enforced_level"),
            "findings_sample": findings,
            "findings_total": len(data.get("findings") or []),
        }

    def _tags_compact() -> dict[str, Any]:
        if not tags.get("ok"):
            return {"ok": False, "error": tags.get("error")}
        data = tags.get("data") or {}
        images = list(data.get("images") or [])[:_FINDING_PREVIEW]
        return {
            "ok": True,
            "summary": data.get("summary"),
            "images_sample": images,
            "images_total": len(data.get("images") or []),
        }

    return {
        "scope_namespace": payload.get("scope_namespace"),
        "check_security_context": _check_compact(),
        "find_latest_tags": _tags_compact(),
    }


def _summarize_with_llm(llm, payload: dict[str, Any], request: str) -> str:
    try:
        system = load_prompt("pod_security")
        compact = _build_llm_payload(payload)
        text = json.dumps(compact, default=str)
        if len(text) > _LLM_MAX_CHARS:
            text = text[:_LLM_MAX_CHARS]
        msg = llm.invoke(
            [
                SystemMessage(content=system),
                HumanMessage(
                    content=(
                        f"Request: {request}\n\nTool results JSON:\n{text}\n\n"
                        "Summarize PSS violations and unpinned images. "
                        "Rank by severity with evidence. Read-only — no cluster changes."
                    )
                ),
            ]
        )
        return msg.content if hasattr(msg, "content") else str(msg)
    except Exception as exc:
        logger.warning("Pod security LLM summary skipped: %s", exc)
        return _fallback_message(payload)


def _fallback_message(payload: dict[str, Any]) -> str:
    check = payload.get("check_security_context") or {}
    if check.get("ok"):
        summary = (check.get("data") or {}).get("summary") or {}
        n = summary.get("pods_scanned", 0)
        by_sev = summary.get("findings_by_severity") or {}
        return f"PSS scan: {n} pod(s), findings by severity: {by_sev}"
    err = (check.get("error") or {}).get("message", "check failed")
    tags = payload.get("find_latest_tags") or {}
    if tags.get("ok"):
        counts = (tags.get("data") or {}).get("summary", {}).get("counts_by_issue") or {}
        return f"{err}; latest-tag issues: {counts}"
    return err


def pod_security_node(state: GraphState, llm) -> GraphState:
    targets = state.get("targets") or []
    if "pod_security" not in targets:
        logger.debug("pod_security skipped (not in targets)")
        return {}

    request = state.get("request") or ""
    logger.info("pod_security collecting tool data request=%r", request[:120])
    payload = collect_pod_security_data(state)
    message = _summarize_with_llm(llm, payload, request)
    severity = _max_finding_severity(payload)

    return {
        "findings": [
            {
                "agent": "pod_security",
                "severity": severity,
                "message": message,
                "data": payload,
            }
        ]
    }
