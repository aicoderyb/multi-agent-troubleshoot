"""Tool lists per specialist agent (LangChain @tool for ReAct when enabled)."""

from langchain_core.tools import BaseTool, tool

from mulat.tools.node_health.describe_node import describe_node_impl
from mulat.tools.node_health.list_nodes import list_nodes_impl
from mulat.tools.node_health.node_events import node_events_impl
from mulat.tools.node_health.pods_per_node import pods_per_node_impl
from mulat.tools.right_sizing.get_requests_limits import get_requests_limits_impl
from mulat.tools.right_sizing.query_cpu_usage import query_cpu_usage_impl
from mulat.tools.pod_security.check_security_context import check_security_context_impl
from mulat.tools.pod_security.find_latest_tags import find_latest_tags_impl
from mulat.tools.pod_security.get_pod_spec import get_pod_spec_impl
from mulat.tools.pod_security.list_pods import list_pods_impl
from mulat.tools.right_sizing.query_memory_usage import query_memory_usage_impl


@tool
def list_nodes(label_selector: str = "", only_unhealthy: bool = False) -> dict:
    """List Kubernetes nodes with health summary (Tool_API list_nodes)."""
    return list_nodes_impl(label_selector=label_selector, only_unhealthy=only_unhealthy)


@tool
def describe_node(name: str, include_usage: bool = True) -> dict:
    """Describe one node: conditions, capacity, recent events (Tool_API describe_node)."""
    return describe_node_impl(name=name, include_usage=include_usage)


@tool
def node_events(node: str, warnings_only: bool = False, since_minutes: int = 120, limit: int = 30) -> dict:
    """List recent events for a node (Tool_API node_events)."""
    return node_events_impl(
        node=node,
        warnings_only=warnings_only,
        since_minutes=since_minutes,
        limit=limit,
    )


@tool
def pods_per_node(node: str, include_pods: bool = False) -> dict:
    """Pod count and utilization on a node (Tool_API pods_per_node)."""
    return pods_per_node_impl(node=node, include_pods=include_pods)


@tool
def get_requests_limits(
    namespace: str = "",
    label_selector: str = "",
    only_missing: bool = False,
    limit: int = 200,
) -> dict:
    """List container CPU/memory requests and limits from pod specs."""
    return get_requests_limits_impl(
        namespace=namespace,
        label_selector=label_selector,
        only_missing=only_missing,
        limit=limit,
    )


@tool
def query_cpu_usage(
    namespace: str = "all",
    pod_regex: str = ".+",
    container: str = "any",
    stat: str = "p95",
    lookback: str = "7d",
    rate_window: str = "5m",
    limit: int = 200,
) -> dict:
    """Observed CPU usage from Prometheus (Tool_API query_cpu_usage)."""
    return query_cpu_usage_impl(
        namespace=namespace,
        pod_regex=pod_regex,
        container=container,
        stat=stat,
        lookback=lookback,
        rate_window=rate_window,
        limit=limit,
    )


@tool
def query_memory_usage(
    namespace: str = "all",
    pod_regex: str = ".+",
    container: str = "any",
    stat: str = "max",
    lookback: str = "7d",
    limit: int = 200,
) -> dict:
    """Observed memory usage from Prometheus (Tool_API query_memory_usage)."""
    return query_memory_usage_impl(
        namespace=namespace,
        pod_regex=pod_regex,
        container=container,
        stat=stat,
        lookback=lookback,
        limit=limit,
    )


@tool
def list_pods(
    namespace: str = "",
    label_selector: str = "",
    node: str = "",
    phase: str = "any",
    limit: int = 200,
    continue_token: str = "",
) -> dict:
    """List pods for security scanning (Tool_API list_pods)."""
    return list_pods_impl(
        namespace=namespace,
        label_selector=label_selector,
        node=node,
        phase=phase,
        limit=limit,
        continue_token=continue_token,
    )


@tool
def get_pod_spec(namespace: str, name: str, include_status: bool = False) -> dict:
    """Fetch security-relevant pod spec fields (Tool_API get_pod_spec)."""
    return get_pod_spec_impl(namespace=namespace, name=name, include_status=include_status)


@tool
def check_security_context(
    namespace: str,
    name: str = "",
    label_selector: str = "",
    level: str = "baseline",
    max_pods: int = 100,
) -> dict:
    """Evaluate pods against Pod Security Standards (Tool_API check_security_context)."""
    return check_security_context_impl(
        namespace=namespace,
        name=name,
        label_selector=label_selector,
        level=level,
        max_pods=max_pods,
    )


@tool
def find_latest_tags(
    namespace: str = "",
    label_selector: str = "",
    require_digest: bool = False,
) -> dict:
    """Detect unpinned :latest or untagged images (Tool_API find_latest_tags)."""
    return find_latest_tags_impl(
        namespace=namespace,
        label_selector=label_selector,
        require_digest=require_digest,
    )


node_health_tools: list[BaseTool] = [list_nodes, describe_node, node_events, pods_per_node]
sizing_tools: list[BaseTool] = [get_requests_limits, query_cpu_usage, query_memory_usage]
security_tools: list[BaseTool] = [list_pods, get_pod_spec, check_security_context, find_latest_tags]
