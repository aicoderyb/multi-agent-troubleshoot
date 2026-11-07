"""Shared Kubernetes helpers for node health tools."""

from __future__ import annotations

import re
from typing import Any

from kubernetes.client import ApiException, V1Node

from mulat.clients.kubernetes import get_core_v1_api
from mulat.config import settings
from mulat.tools import errors
from mulat.tools.envelope import failure

_PRESSURE_TYPES = frozenset(
    {"DiskPressure", "MemoryPressure", "PIDPressure", "NetworkUnavailable"}
)


def handle_api_exception(tool: str, exc: ApiException) -> dict[str, Any]:
    if exc.status == 404:
        return failure(tool, errors.NOT_FOUND, str(exc.reason or "not found"), retryable=False)
    if exc.status == 403:
        return failure(tool, errors.FORBIDDEN, str(exc.body or "forbidden"), retryable=False)
    if exc.status in (429, 500, 502, 503, 504):
        return failure(tool, errors.UNAVAILABLE, str(exc.reason or "unavailable"), retryable=True)
    return failure(tool, errors.UNAVAILABLE, str(exc), retryable=True)


def parse_cpu_millicores(value: str | None) -> int | None:
    if not value:
        return None
    if value.endswith("m"):
        return int(value[:-1])
    return int(float(value) * 1000)


def parse_memory_mib(value: str | None) -> int | None:
    if not value:
        return None
    if value.endswith("Ki"):
        return int(int(value[:-2]) / 1024)
    if value.endswith("Mi"):
        return int(value[:-2])
    if value.endswith("Gi"):
        return int(float(value[:-2]) * 1024)
    if value.endswith("k") or value.endswith("K"):
        return int(int(value[:-1]) / 1024)
    # bytes
    if value.isdigit():
        return int(int(value) / (1024 * 1024))
    return None


def node_roles(node: V1Node) -> list[str]:
    labels = node.metadata.labels or {}
    roles: list[str] = []
    for key in labels:
        if key == "node-role.kubernetes.io/control-plane" or key == "node-role.kubernetes.io/master":
            roles.append("control-plane")
        elif key.startswith("node-role.kubernetes.io/"):
            roles.append(key.split("/", 1)[1])
    return roles or ["worker"]


def node_ready(node: V1Node) -> bool:
    for cond in node.status.conditions or []:
        if cond.type == "Ready":
            return cond.status == "True"
    return False


def failing_conditions(node: V1Node) -> list[str]:
    bad: list[str] = []
    for cond in node.status.conditions or []:
        if cond.type == "Ready" and cond.status != "True":
            bad.append(cond.type)
        elif cond.type in _PRESSURE_TYPES and cond.status == "True":
            bad.append(cond.type)
    return bad


def is_unhealthy(node: V1Node) -> bool:
    if node.spec.unschedulable:
        return True
    if not node_ready(node):
        return True
    return bool(failing_conditions(node))


def summarize_node(node: V1Node) -> dict[str, Any]:
    alloc = node.status.allocatable or {}
    taints = [
        f"{t.key}:{t.effect}" for t in (node.spec.taints or [])
    ]
    return {
        "name": node.metadata.name,
        "ready": node_ready(node),
        "roles": node_roles(node),
        "unschedulable": bool(node.spec.unschedulable),
        "failing_conditions": failing_conditions(node),
        "taints": taints,
        "kubelet_version": (node.status.node_info.kubelet_version if node.status.node_info else None),
        "os_image": (node.status.node_info.os_image if node.status.node_info else None),
        "cpu_allocatable_m": parse_cpu_millicores(alloc.get("cpu")),
        "mem_allocatable_mib": parse_memory_mib(alloc.get("memory")),
        "pods_allocatable": int(alloc["pods"]) if alloc.get("pods") else None,
    }


def infer_node_names_from_text(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b[\w.-]+\b", text)))  # fallback weak
