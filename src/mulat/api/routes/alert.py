"""POST /alert — Alertmanager webhook → same graph entry as /ask."""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mulat.api.schemas import RunResponse
from mulat.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


class AlertmanagerWebhook(BaseModel):
    receiver: str = ""
    status: str = "firing"
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    commonLabels: dict[str, Any] = Field(default_factory=dict)


@router.post("/alert", response_model=RunResponse)
async def alert(body: AlertmanagerWebhook, request: Request) -> RunResponse:
    thread_id = str(uuid4())
    run_id = str(uuid4())
    _ = request.app.state.graph
    summary = body.alerts[0].get("annotations", {}).get("summary") if body.alerts else "alert"
    logger.info("POST /alert thread_id=%s alerts=%d summary=%r", thread_id, len(body.alerts), summary)
    return RunResponse(
        thread_id=thread_id,
        run_id=run_id,
        status="accepted",
        detail=f"Alert normalized; graph invoke pending: {summary}",
    )
