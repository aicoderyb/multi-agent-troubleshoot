"""Standard tool result envelope."""

from typing import Any


def success(tool: str, data: dict[str, Any], *, truncated: bool = False) -> dict[str, Any]:
    return {
        "ok": True,
        "tool": tool,
        "data": data,
        "truncated": truncated,
        "error": None,
    }


def failure(
    tool: str,
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "data": None,
        "truncated": False,
        "error": {"code": code, "message": message, "retryable": retryable},
    }
