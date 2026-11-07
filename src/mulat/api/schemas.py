"""Shared API response models."""

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    message: str
    source: str = "api"
    thread_id: str | None = None
    hints: dict[str, Any] = Field(default_factory=dict)
    """When true, each finding includes full tool JSON in `data` (can be very large)."""
    include_raw_data: bool = False


class FindingOut(BaseModel):
    agent: str | None = None
    severity: str | None = None
    message: str | None = None
    data: dict[str, Any] | None = None


class ReportOut(BaseModel):
    summary: str
    finding_count: int = 0
    targets: list[str] = Field(default_factory=list)
    agents_run: list[str] = Field(default_factory=list)
    agents_skipped: list[str] = Field(default_factory=list)
    ranked_findings: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)


class RunResponse(BaseModel):
    thread_id: str
    run_id: str
    status: str
    """Full synthesizer summary (same as report.summary when present)."""
    detail: str | None = None
    report: ReportOut | None = None
