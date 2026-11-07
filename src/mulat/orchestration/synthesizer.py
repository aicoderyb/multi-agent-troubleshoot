"""Merge specialist findings into one severity-ranked report."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from mulat.logging_config import get_logger
from mulat.orchestration.prompts_loader import load_prompt
from mulat.orchestration.state import GraphState

logger = get_logger(__name__)

_SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "warning": 2,
    "medium": 2,
    "low": 3,
    "info": 4,
    "unknown": 5,
}

_LLM_FINDING_CHARS = 4_000


def _severity_rank(finding: dict[str, Any]) -> tuple[int, str]:
    raw = str(finding.get("severity") or "info").lower()
    return (_SEVERITY_ORDER.get(raw, 5), str(finding.get("agent") or ""))


def sort_findings_by_severity(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(findings, key=_severity_rank)


def _compact_for_llm(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in findings:
        msg = str(f.get("message") or "")[:_LLM_FINDING_CHARS]
        out.append(
            {
                "agent": f.get("agent"),
                "severity": f.get("severity") or "info",
                "message": msg,
            }
        )
    return out


def _rule_based_summary(request: str, findings: list[dict[str, Any]]) -> str:
    if not findings:
        return f"No specialist findings were produced for: {request[:300]}"
    lines = ["Investigation summary (rule-based):"]
    for i, f in enumerate(findings, 1):
        agent = f.get("agent") or "unknown"
        sev = f.get("severity") or "info"
        msg = str(f.get("message") or "").strip()
        lead = msg.split("\n", 1)[0][:400]
        lines.append(f"{i}. [{sev}] {agent}: {lead}")
    return "\n".join(lines)


def build_report(
    state: GraphState,
    findings: list[dict[str, Any]],
    *,
    summary: str,
) -> dict[str, Any]:
    targets = state.get("targets") or []
    agents_in_findings = [f.get("agent") for f in findings if f.get("agent")]
    skipped = [t for t in targets if t not in agents_in_findings]

    return {
        "summary": summary,
        "finding_count": len(findings),
        "findings": findings,
        "targets": targets,
        "agents_run": agents_in_findings,
        "agents_skipped": skipped,
        "ranked_findings": [
            {
                "rank": i,
                "severity": f.get("severity") or "info",
                "agent": f.get("agent"),
            }
            for i, f in enumerate(findings, 1)
        ],
    }


def _summarize_with_llm(llm, state: GraphState, findings: list[dict[str, Any]]) -> str:
    system = load_prompt("synthesizer")
    payload = {
        "request": state.get("request") or "",
        "targets": state.get("targets") or [],
        "findings": _compact_for_llm(findings),
    }
    text = json.dumps(payload, default=str)
    msg = llm.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=text),
        ]
    )
    return msg.content if hasattr(msg, "content") else str(msg)


def synthesizer_node(state: GraphState, llm=None) -> GraphState:
    """Fan-in: rank findings and produce state['report'] for API / approval."""
    raw = state.get("findings") or []
    findings = sort_findings_by_severity(list(raw))
    request = state.get("request") or ""

    if llm is not None and findings:
        try:
            summary = _summarize_with_llm(llm, state, findings)
            logger.info("Synthesizer LLM report findings=%d", len(findings))
        except Exception as exc:
            logger.warning("Synthesizer LLM failed, using rule-based summary: %s", exc)
            summary = _rule_based_summary(request, findings)
    else:
        if llm is None:
            logger.debug("Synthesizer rule-based (no llm)")
        else:
            logger.info("Synthesizer rule-based (no findings)")
        summary = _rule_based_summary(request, findings)

    report = build_report(state, findings, summary=summary)
    return {"report": report}
