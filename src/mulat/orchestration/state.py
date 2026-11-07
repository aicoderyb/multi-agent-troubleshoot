"""Shared graph state (TypedDict)."""

import operator
from typing import Annotated, Any, TypedDict


class GraphState(TypedDict, total=False):
    request: str
    source: str
    hints: dict[str, Any]
    targets: list[str]
    findings: Annotated[list[dict[str, Any]], operator.add]
    report: dict[str, Any] | None
