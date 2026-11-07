"""POST /approve — resume run paused at interrupt()."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from mulat.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ApproveRequest(BaseModel):
    thread_id: str
    run_id: str
    decision: str  # approve | reject
    comment: str = ""


class ApproveResponse(BaseModel):
    thread_id: str
    status: str
    detail: str | None = None


@router.post("/approve", response_model=ApproveResponse)
async def approve(body: ApproveRequest, request: Request) -> ApproveResponse:
    logger.info(
        "POST /approve thread_id=%s decision=%s",
        body.thread_id,
        body.decision,
    )
    _ = request.app.state.graph
    # TODO: Command(resume={...}) against checkpointer for body.thread_id
    return ApproveResponse(
        thread_id=body.thread_id,
        status="accepted",
        detail=f"Resume pending implementation (decision={body.decision})",
    )
