"""query_memory_usage — Prometheus memory usage. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from mulat.tools import errors
from mulat.tools.envelope import failure, success
from mulat.clients.prometheus import query_instant_safe
from mulat.tools.right_sizing.promql import build_memory_query


def _parse_memory_vector(data: dict[str, Any]) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for item in data.get("result") or []:
        metric = item.get("metric") or {}
        value = item.get("value")
        if not value or len(value) < 2:
            continue
        try:
            bytes_val = float(value[1])
        except (TypeError, ValueError):
            continue
        series.append(
            {
                "namespace": metric.get("namespace"),
                "pod": metric.get("pod"),
                "container": metric.get("container"),
                "value_mib": round(bytes_val / (1024 * 1024), 1),
                "oom_killed_recently": False,
            }
        )
    return series


def query_memory_usage_impl(
    *,
    namespace: str = "all",
    pod_regex: str = ".+",
    container: str = "any",
    stat: str = "max",
    lookback: str = "7d",
    limit: int = 200,
) -> dict[str, Any]:
    if stat not in ("avg", "p95", "max"):
        return failure(
            "query_memory_usage",
            errors.INVALID_INPUT,
            f"stat must be avg, p95, or max (got {stat!r})",
            retryable=False,
        )
    limit = min(max(limit, 1), 500)
    promql = build_memory_query(
        namespace=namespace,
        pod_regex=pod_regex,
        container=container,
        stat=stat,
        lookback=lookback,
    )
    ok, payload = query_instant_safe(promql)
    if not ok:
        return failure("query_memory_usage", errors.PROMETHEUS_ERROR, str(payload), retryable=True)
    all_series = _parse_memory_vector(payload)
    series = all_series[:limit]
    if not series:
        return failure("query_memory_usage", errors.NO_DATA, "query returned no series", retryable=False)
    return success(
        "query_memory_usage",
        {"stat": stat, "lookback": lookback, "promql": promql, "series": series},
        truncated=len(all_series) > limit,
    )
