"""PromQL builders for right-sizing tools (Tool_API.md)."""

from __future__ import annotations


def _label_filters(namespace: str, pod_regex: str, container: str) -> str:
    parts = ['container!="", container!="POD"']
    if namespace and namespace.lower() != "all":
        parts.append(f'namespace="{namespace}"')
    if pod_regex and pod_regex != ".+":
        parts.append(f'pod=~"{pod_regex}"')
    if container and container.lower() not in ("any", ""):
        parts.append(f'container="{container}"')
    return "{" + ", ".join(parts) + "}"


def build_cpu_query(
    *,
    namespace: str = "all",
    pod_regex: str = ".+",
    container: str = "any",
    stat: str = "p95",
    lookback: str = "7d",
    rate_window: str = "5m",
) -> str:
    labels = _label_filters(namespace, pod_regex, container)
    inner = (
        f"sum by (namespace, pod, container) "
        f"(rate(container_cpu_usage_seconds_total{labels}[{rate_window}]))"
    )
    if stat == "avg":
        return f"avg_over_time(({inner})[{lookback}:{rate_window}])"
    if stat == "max":
        return f"max_over_time(({inner})[{lookback}:{rate_window}])"
    quantile = {"p95": "0.95", "p99": "0.99"}.get(stat, "0.95")
    return f"quantile_over_time({quantile}, ({inner})[{lookback}:{rate_window}])"


def build_memory_query(
    *,
    namespace: str = "all",
    pod_regex: str = ".+",
    container: str = "any",
    stat: str = "max",
    lookback: str = "7d",
    step: str = "5m",
) -> str:
    labels = _label_filters(namespace, pod_regex, container)
    inner = f"max by (namespace, pod, container) (container_memory_working_set_bytes{labels})"
    if stat == "avg":
        return f"avg_over_time(({inner})[{lookback}:{step}])"
    if stat == "p95":
        return f"quantile_over_time(0.95, ({inner})[{lookback}:{step}])"
    return f"max_over_time(({inner})[{lookback}:{step}])"
