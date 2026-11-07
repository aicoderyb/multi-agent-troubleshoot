"""describe_node — GET /api/v1/nodes/{name}. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from kubernetes.client import ApiException

from mulat.clients.kubernetes import get_core_v1_api
from mulat.config import settings
from mulat.tools import errors
from mulat.tools.envelope import failure, success
from mulat.tools.node_health.k8s_util import (
    handle_api_exception,
    parse_cpu_millicores,
    parse_memory_mib,
)
from mulat.tools.node_health.node_events import node_events_impl


def describe_node_impl(*, name: str, include_usage: bool = True) -> dict[str, Any]:
    if not name or not name.strip():
        return failure("describe_node", errors.INVALID_INPUT, "name is required", retryable=False)
    api = get_core_v1_api()
    try:
        node = api.read_node(name, _request_timeout=settings.k8s_api_timeout_seconds)
    except ApiException as exc:
        return handle_api_exception("describe_node", exc)

    conditions = []
    for cond in node.status.conditions or []:
        conditions.append(
            {
                "type": cond.type,
                "status": cond.status,
                "reason": cond.reason,
                "message": cond.message,
                "last_transition": cond.last_transition_time.isoformat().replace("+00:00", "Z")
                if cond.last_transition_time
                else None,
            }
        )
    taints = [f"{t.key}:{t.effect}" for t in (node.spec.taints or [])]
    cap = node.status.capacity or {}
    alloc = node.status.allocatable or {}
    ni = node.status.node_info
    recent = node_events_impl(node=name, limit=10)
    recent_events = recent["data"]["events"] if recent.get("ok") else []

    usage = None
    if include_usage:
        usage = {"cpu_m": None, "mem_mib": None}  # metrics.k8s.io optional later

    data = {
        "name": name,
        "conditions": conditions,
        "taints": taints,
        "capacity": {
            "cpu_m": parse_cpu_millicores(cap.get("cpu")),
            "mem_mib": parse_memory_mib(cap.get("memory")),
            "pods": int(cap["pods"]) if cap.get("pods") else None,
        },
        "allocatable": {
            "cpu_m": parse_cpu_millicores(alloc.get("cpu")),
            "mem_mib": parse_memory_mib(alloc.get("memory")),
            "pods": int(alloc["pods"]) if alloc.get("pods") else None,
        },
        "node_info": {
            "kubelet_version": ni.kubelet_version if ni else None,
            "kernel_version": ni.kernel_version if ni else None,
            "container_runtime": ni.container_runtime_version if ni else None,
            "os_image": ni.os_image if ni else None,
        },
        "unschedulable": bool(node.spec.unschedulable),
        "usage": usage,
        "recent_events": recent_events,
    }
    return success("describe_node", data)
