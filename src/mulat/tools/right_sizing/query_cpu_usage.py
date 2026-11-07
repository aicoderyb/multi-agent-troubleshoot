"""query_cpu_usage — Prometheus CPU usage. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from mulat.tools import errors
from mulat.tools.envelope import failure, success
from mulat.clients.prometheus import query_instant_safe
from mulat.tools.right_sizing.promql import build_cpu_query


def _parse_vector(data: dict[str, Any], *, value_key: str = "value_m") -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for item in data.get("result") or []:
        metric = item.get("metric") or {}
        value = item.get("value")
        if not value or len(value) < 2:
            continue
        try:
            cores = float(value[1])
        except (TypeError, ValueError):
            continue
        series.append(
            {
                "namespace": metric.get("namespace"),
                "pod": metric.get("pod"),
                "container": metric.get("container"),
                value_key: round(cores * 1000, 1),
            }
        )
    return series


def query_cpu_usage_impl(
    *,
    namespace: str = "all",
    pod_regex: str = ".+",
    container: str = "any",
    stat: str = "p95",
    lookback: str = "7d",
    rate_window: str = "5m",
    limit: int = 200,
) -> dict[str, Any]:
    if stat not in ("avg", "p95", "max"):
        return failure(
            "query_cpu_usage",
            errors.INVALID_INPUT,
            f"stat must be avg, p95, or max (got {stat!r})",
            retryable=False,
        )
    limit = min(max(limit, 1), 500)
    promql = build_cpu_query(
        namespace=namespace,
        pod_regex=pod_regex,
        container=container,
        stat=stat,
        lookback=lookback,
        rate_window=rate_window,
    )
    ok, payload = query_instant_safe(promql)
    if not ok:
        return failure("query_cpu_usage", errors.PROMETHEUS_ERROR, str(payload), retryable=True)
    series = _parse_vector(payload)[:limit]
    if not series:
        return failure("query_cpu_usage", errors.NO_DATA, "query returned no series", retryable=False)
    truncated = len(_parse_vector(payload)) > limit
    return success(
        "query_cpu_usage",
        {"stat": stat, "lookback": lookback, "promql": promql, "series": series},
        truncated=truncated,
    )
