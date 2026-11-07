"""list_nodes — GET /api/v1/nodes. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from kubernetes.client import ApiException

from mulat.clients.kubernetes import get_core_v1_api
from mulat.config import settings
from mulat.tools.envelope import success
from mulat.tools.node_health.k8s_util import handle_api_exception, is_unhealthy, summarize_node


def list_nodes_impl(
    *,
    label_selector: str = "",
    only_unhealthy: bool = False,
) -> dict[str, Any]:
    api = get_core_v1_api()
    try:
        resp = api.list_node(
            label_selector=label_selector or None,
            _request_timeout=settings.k8s_api_timeout_seconds,
        )
    except ApiException as exc:
        return handle_api_exception("list_nodes", exc)

    nodes = []
    for item in resp.items:
        summary = summarize_node(item)
        if only_unhealthy and not is_unhealthy(item):
            continue
        nodes.append(summary)
    return success("list_nodes", {"count": len(nodes), "nodes": nodes})
