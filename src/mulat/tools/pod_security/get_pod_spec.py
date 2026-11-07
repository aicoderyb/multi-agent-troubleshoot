"""get_pod_spec — security-relevant pod fields. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from kubernetes.client import ApiException, V1Pod

from mulat.clients.kubernetes import get_core_v1_api
from mulat.config import settings
from mulat.tools.envelope import success
from mulat.tools.pod_security.k8s_helpers import container_dict, handle_api_exception, volume_dict


def _psa_from_namespace(api, namespace: str) -> dict[str, str | None]:
    try:
        ns = api.read_namespace(namespace, _request_timeout=settings.k8s_api_timeout_seconds)
    except ApiException:
        return {"enforce": None, "audit": None, "warn": None}
    labels = ns.metadata.labels or {}
    return {
        "enforce": labels.get("pod-security.kubernetes.io/enforce"),
        "audit": labels.get("pod-security.kubernetes.io/audit"),
        "warn": labels.get("pod-security.kubernetes.io/warn"),
    }


def pod_to_spec_data(pod: V1Pod, psa_labels: dict[str, str | None]) -> dict[str, Any]:
    spec = pod.spec
    data: dict[str, Any] = {
        "namespace": pod.metadata.namespace,
        "name": pod.metadata.name,
        "service_account": spec.service_account_name,
        "host_network": bool(spec.host_network),
        "host_pid": bool(spec.host_pid),
        "host_ipc": bool(spec.host_ipc),
        "pod_security_context": {},
        "volumes": [volume_dict(v) for v in spec.volumes or []],
        "containers": [container_dict(c) for c in spec.containers or []],
        "init_containers": [container_dict(c) for c in spec.init_containers or []],
        "ephemeral_containers": [container_dict(c) for c in (spec.ephemeral_containers or [])],
        "psa_labels": psa_labels,
    }
    if spec.security_context:
        from mulat.tools.pod_security.k8s_helpers import security_context_dict

        data["pod_security_context"] = security_context_dict(spec.security_context)
    return data


def get_pod_spec_impl(
    *,
    namespace: str,
    name: str,
    include_status: bool = False,
) -> dict[str, Any]:
    if not namespace or not name:
        from mulat.tools import errors
        from mulat.tools.envelope import failure

        return failure(
            "get_pod_spec",
            errors.INVALID_INPUT,
            "namespace and name are required",
            retryable=False,
        )

    api = get_core_v1_api()
    try:
        pod = api.read_namespaced_pod(
            name,
            namespace,
            _request_timeout=settings.k8s_api_timeout_seconds,
        )
    except ApiException as exc:
        return handle_api_exception("get_pod_spec", exc)

    psa = _psa_from_namespace(api, namespace)
    data = pod_to_spec_data(pod, psa)
    if include_status and pod.status:
        data["phase"] = pod.status.phase
        data["conditions"] = [
            {"type": c.type, "status": c.status, "reason": c.reason}
            for c in (pod.status.conditions or [])
        ]
    return success("get_pod_spec", data, truncated=False)
