"""node_events — GET /api/v1/events. See Tool_API.md."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from kubernetes.client import ApiException

from mulat.clients.kubernetes import get_core_v1_api
from mulat.config import settings
from mulat.tools import errors
from mulat.tools.envelope import failure, success
from mulat.tools.node_health.k8s_util import handle_api_exception


def node_events_impl(
    *,
    node: str,
    warnings_only: bool = False,
    since_minutes: int = 120,
    limit: int = 30,
) -> dict[str, Any]:
    if not node or not node.strip():
        return failure("node_events", errors.INVALID_INPUT, "node is required", retryable=False)
    limit = min(max(limit, 1), 100)
    api = get_core_v1_api()
    field_selector = f"involvedObject.kind=Node,involvedObject.name={node}"
    try:
        resp = api.list_event_for_all_namespaces(
            field_selector=field_selector,
            _request_timeout=settings.k8s_api_timeout_seconds,
        )
    except ApiException as exc:
        return handle_api_exception("node_events", exc)

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    events = []
    for ev in sorted(resp.items, key=lambda e: e.last_timestamp or e.event_time or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        if warnings_only and ev.type != "Warning":
            continue
        ts = ev.last_timestamp or ev.event_time
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts and ts < cutoff:
            continue
        events.append(
            {
                "type": ev.type,
                "reason": ev.reason,
                "message": ev.message,
                "count": ev.count,
                "first_seen": ev.first_timestamp.isoformat().replace("+00:00", "Z")
                if ev.first_timestamp
                else None,
                "last_seen": ev.last_timestamp.isoformat().replace("+00:00", "Z")
                if ev.last_timestamp
                else None,
                "source": ev.reporting_component or ev.source.component if ev.source else None,
            }
        )
        if len(events) >= limit:
            break
    return success("node_events", {"events": events, "node": node})
