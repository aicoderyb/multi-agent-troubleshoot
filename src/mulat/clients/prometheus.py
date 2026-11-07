"""Prometheus HTTP API client."""

from __future__ import annotations

from typing import Any

import httpx

from mulat.config import settings
from mulat.logging_config import get_logger

logger = get_logger(__name__)


def query_api_url() -> str:
    return f"{settings.prometheus_url.rstrip('/')}/api/v1/query"


def query_instant(promql: str) -> dict[str, Any]:
    url = query_api_url()
    logger.debug("Prometheus query: %s", promql[:200])
    with httpx.Client(
        timeout=settings.prometheus_query_timeout_seconds,
        verify=settings.prometheus_verify_ssl,
    ) as client:
        response = client.get(url, params={"query": promql})
        response.raise_for_status()
        return response.json()


def query_instant_safe(promql: str) -> tuple[bool, dict[str, Any] | str]:
    """Return (ok, payload_or_error_message)."""
    url = query_api_url()
    try:
        body = query_instant(promql)
    except (httpx.HTTPError, httpx.RequestError) as exc:
        logger.warning(
            "Prometheus HTTP error url=%s verify_ssl=%s: %s",
            url,
            settings.prometheus_verify_ssl,
            exc,
        )
        return False, str(exc)
    status = body.get("status")
    if status != "success":
        return False, body.get("error", "unknown prometheus error")
    return True, body.get("data") or {}
