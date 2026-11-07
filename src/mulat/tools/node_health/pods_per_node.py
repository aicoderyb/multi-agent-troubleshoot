"""pods_per_node — GET /api/v1/pods fieldSelector. See Tool_API.md."""

from __future__ import annotations

from collections import Counter
from typing import Any

from kubernetes.client import ApiException

from mulat.clients.kubernetes import get_core_v1_api
from mulat.config import settings
from mulat.tools import errors
from mulat.tools.envelope import failure, success
from mulat.tools.node_health.k8s_util import handle_api_exception


def pods_per_node_impl(
    *,
    node: str,
    include_pods: bool = False,
) -> dict[str, Any]:
    if not node or not node.strip():
        return failure("pods_per_node", errors.INVALID_INPUT, "node is required", retryable=False)
    api = get_core_v1_api()
    try:
        node_obj = api.read_node(node, _request_timeout=settings.k8s_api_timeout_seconds)
        pods_resp = api.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={node}",
            _request_timeout=settings.k8s_api_timeout_seconds,
        )
    except ApiException as exc:
        return handle_api_exception("pods_per_node", exc)

    alloc = node_obj.status.allocatable or {}
    max_pods = int(alloc["pods"]) if alloc.get("pods") else None
    by_phase: Counter[str] = Counter()
    ns_counts: Counter[str] = Counter()
    pod_list = []
    for pod in pods_resp.items:
        phase = pod.status.phase or "Unknown"
        by_phase[phase] += 1
        ns = pod.metadata.namespace or ""
        ns_counts[ns] += 1
        if include_pods:
            pod_list.append(
                {
                    "namespace": ns,
                    "name": pod.metadata.name,
                    "phase": phase,
                }
            )
    pod_count = len(pods_resp.items)
    utilization_pct = round((pod_count / max_pods) * 100, 1) if max_pods else None
    top_namespaces = [
        {"namespace": ns, "count": count}
        for ns, count in ns_counts.most_common(10)
    ]
    data: dict[str, Any] = {
        "node": node,
        "pod_count": pod_count,
        "max_pods": max_pods,
        "utilization_pct": utilization_pct,
        "by_phase": dict(by_phase),
        "top_namespaces": top_namespaces,
    }
    if include_pods:
        data["pods"] = pod_list
    return success("pods_per_node", data)
