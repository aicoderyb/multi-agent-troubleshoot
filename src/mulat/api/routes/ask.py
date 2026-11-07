"""POST /ask — user or CLI investigation request."""

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from langgraph.errors import GraphInterrupt

from mulat.api.schemas import AskRequest, FindingOut, ReportOut, RunResponse
from mulat.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _findings_for_api(
    result: dict[str, Any],
    *,
    include_raw_data: bool,
) -> list[FindingOut]:
    out: list[FindingOut] = []
    for f in result.get("findings") or []:
        if not isinstance(f, dict):
            continue
        out.append(
            FindingOut(
                agent=f.get("agent"),
                severity=f.get("severity"),
                message=f.get("message"),
                data=f.get("data") if include_raw_data else None,
            )
        )
    return out


def _report_from_state(
    result: dict[str, Any],
    *,
    include_raw_data: bool,
) -> ReportOut | None:
    raw_report = result.get("report")
    if not raw_report and not (result.get("findings")):
        return None

    if isinstance(raw_report, dict) and raw_report.get("summary"):
        summary = str(raw_report["summary"])
        return ReportOut(
            summary=summary,
            finding_count=int(raw_report.get("finding_count") or 0),
            targets=list(raw_report.get("targets") or result.get("targets") or []),
            agents_run=list(raw_report.get("agents_run") or []),
            agents_skipped=list(raw_report.get("agents_skipped") or []),
            ranked_findings=list(raw_report.get("ranked_findings") or []),
            findings=_findings_for_api(result, include_raw_data=include_raw_data),
        )

    findings = _findings_for_api(result, include_raw_data=include_raw_data)
    if not findings:
        targets = result.get("targets") or []
        return ReportOut(
            summary=f"Run finished (agents: {', '.join(targets) or 'none'}).",
            finding_count=0,
            targets=list(targets),
            findings=[],
        )

    first_msg = findings[0].message or str(findings[0])
    return ReportOut(
        summary=str(first_msg),
        finding_count=len(findings),
        targets=list(result.get("targets") or []),
        findings=findings,
    )


def _detail_from_state(result: dict[str, Any]) -> str:
    report = _report_from_state(result, include_raw_data=False)
    if report:
        return report.summary
    targets = result.get("targets") or []
    return f"Run finished (agents: {', '.join(targets) or 'none'})."


def _completed_response(
    *,
    thread_id: str,
    run_id: str,
    result: dict[str, Any],
    include_raw_data: bool,
) -> RunResponse:
    report = _report_from_state(result, include_raw_data=include_raw_data)
    detail = report.summary if report else _detail_from_state(result)
    return RunResponse(
        thread_id=thread_id,
        run_id=run_id,
        status="completed",
        detail=detail,
        report=report,
    )


@router.post("/ask", response_model=RunResponse)
async def ask(body: AskRequest, request: Request) -> RunResponse:
    thread_id = body.thread_id or str(uuid4())
    run_id = str(uuid4())
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id, "run_id": run_id}}
    initial: dict[str, Any] = {
        "request": body.message,
        "source": body.source,
        "hints": body.hints,
    }

    logger.info(
        "POST /ask thread_id=%s run_id=%s source=%s message_len=%d",
        thread_id,
        run_id,
        body.source,
        len(body.message),
    )
    try:
        result = await asyncio.to_thread(graph.invoke, initial, config)
    except GraphInterrupt:
        logger.info("Graph interrupted (approval) thread_id=%s", thread_id)
        return RunResponse(
            thread_id=thread_id,
            run_id=run_id,
            status="awaiting_approval",
            detail="Paused at human approval gate. Call POST /approve with this thread_id.",
        )
    except Exception as exc:
        logger.exception("Graph invoke failed thread_id=%s", thread_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result.get("__interrupt__"):
        logger.info("Graph __interrupt__ thread_id=%s", thread_id)
        return RunResponse(
            thread_id=thread_id,
            run_id=run_id,
            status="awaiting_approval",
            detail="Paused at human approval gate. Call POST /approve with this thread_id.",
        )

    logger.info("Graph completed thread_id=%s targets=%s", thread_id, result.get("targets"))
    return _completed_response(
        thread_id=thread_id,
        run_id=run_id,
        result=result,
        include_raw_data=body.include_raw_data,
    )
