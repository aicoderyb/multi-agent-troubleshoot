"""list_pods — GET /api/v1/pods. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from kubernetes.client import ApiException, V1Pod

from mulat.clients.kubernetes import get_core_v1_api
from mulat.config import settings
from mulat.tools.envelope import success
from mulat.tools.pod_security.k8s_helpers import handle_api_exception, owner_dict

_ALLOWED_PHASES = frozenset({"Running", "Pending", "Failed", "Succeeded"})


def _pod_row(pod: V1Pod) -> dict[str, Any]:
    containers = [c.name for c in (pod.spec.containers or [])]
    images = []
    for c in pod.spec.containers or []:
        if c.image:
            images.append(c.image)
    for c in pod.spec.init_containers or []:
        if c.image:
            images.append(c.image)
    started = None
    if pod.status and pod.status.start_time:
        started = pod.status.start_time.isoformat()
    return {
        "namespace": pod.metadata.namespace,
        "name": pod.metadata.name,
        "node": pod.spec.node_name,
        "phase": pod.status.phase if pod.status else None,
        "owner": owner_dict(pod),
        "containers": containers,
        "images": images,
        "started_at": started,
    }


def list_pods_impl(
    *,
    namespace: str = "",
    label_selector: str = "",
    node: str = "",
    phase: str = "any",
    limit: int = 200,
    continue_token: str = "",
) -> dict[str, Any]:
    limit = min(max(limit, 1), 500)
    phase_filter = phase if phase and phase != "any" else None
    if phase_filter and phase_filter not in _ALLOWED_PHASES:
        from mulat.tools import errors
        from mulat.tools.envelope import failure

        return failure(
            "list_pods",
            errors.INVALID_INPUT,
            f"phase must be one of {sorted(_ALLOWED_PHASES)} or any",
            retryable=False,
        )

    field_selector = f"spec.nodeName={node}" if node else None
    api = get_core_v1_api()
    kwargs: dict[str, Any] = {
        "limit": limit,
        "_continue": continue_token or None,
        "label_selector": label_selector or None,
        "field_selector": field_selector,
        "_request_timeout": settings.k8s_api_timeout_seconds,
    }
    try:
        if namespace:
            resp = api.list_namespaced_pod(namespace, **kwargs)
        else:
            resp = api.list_pod_for_all_namespaces(**kwargs)
    except ApiException as exc:
        return handle_api_exception("list_pods", exc)

    pods: list[dict[str, Any]] = []
    for pod in resp.items:
        row = _pod_row(pod)
        if phase_filter and row.get("phase") != phase_filter:
            continue
        pods.append(row)
        if len(pods) >= limit:
            break

    data: dict[str, Any] = {"pods": pods}
    if resp.metadata._continue:
        data["continue_token"] = resp.metadata._continue
    return success("list_pods", data, truncated=bool(resp.metadata._continue))
