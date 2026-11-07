"""get_requests_limits — pod resource requests/limits. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from kubernetes.client import ApiException

from mulat.clients.kubernetes import get_core_v1_api
from mulat.config import settings
from mulat.tools.envelope import success
from mulat.tools.node_health.k8s_util import handle_api_exception, parse_cpu_millicores, parse_memory_mib


def _container_row(pod, container, qos: str) -> dict[str, Any]:
    owner = {"kind": None, "name": None}
    if pod.metadata.owner_references:
        ref = pod.metadata.owner_references[0]
        owner = {"kind": ref.kind, "name": ref.name}
    res = container.resources
    req = res.requests or {}
    lim = res.limits or {}
    cpu_request_m = parse_cpu_millicores(req.get("cpu"))
    cpu_limit_m = parse_cpu_millicores(lim.get("cpu"))
    mem_request_mib = parse_memory_mib(req.get("memory"))
    mem_limit_mib = parse_memory_mib(lim.get("memory"))
    missing = []
    if cpu_request_m is None:
        missing.append("cpu_request")
    if cpu_limit_m is None:
        missing.append("cpu_limit")
    if mem_request_mib is None:
        missing.append("mem_request")
    if mem_limit_mib is None:
        missing.append("mem_limit")
    return {
        "namespace": pod.metadata.namespace,
        "pod": pod.metadata.name,
        "container": container.name,
        "owner": owner,
        "qos_class": qos,
        "cpu_request_m": cpu_request_m,
        "cpu_limit_m": cpu_limit_m,
        "mem_request_mib": mem_request_mib,
        "mem_limit_mib": mem_limit_mib,
        "missing": missing,
    }


def get_requests_limits_impl(
    *,
    namespace: str = "",
    label_selector: str = "",
    only_missing: bool = False,
    limit: int = 200,
) -> dict[str, Any]:
    limit = min(max(limit, 1), 500)
    api = get_core_v1_api()
    try:
        if namespace:
            resp = api.list_namespaced_pod(
                namespace,
                label_selector=label_selector or None,
                limit=limit,
                _request_timeout=settings.k8s_api_timeout_seconds,
            )
        else:
            resp = api.list_pod_for_all_namespaces(
                label_selector=label_selector or None,
                limit=limit,
                _request_timeout=settings.k8s_api_timeout_seconds,
            )
    except ApiException as exc:
        return handle_api_exception("get_requests_limits", exc)

    containers: list[dict[str, Any]] = []
    truncated = False
    for pod in resp.items:
        qos = pod.status.qos_class if pod.status else None
        for c in pod.spec.containers or []:
            row = _container_row(pod, c, qos or "Unknown")
            if only_missing and not row["missing"]:
                continue
            containers.append(row)
            if len(containers) >= limit:
                truncated = True
                break
        if len(containers) >= limit:
            break

    data: dict[str, Any] = {"containers": containers}
    if truncated:
        data["omitted_count"] = "at least one container omitted due to limit"
    return success("get_requests_limits", data, truncated=truncated)
