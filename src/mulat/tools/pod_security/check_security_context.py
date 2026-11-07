"""check_security_context — PSS rule engine. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from mulat.tools import errors
from mulat.tools.envelope import failure, success
from mulat.tools.pod_security.get_pod_spec import get_pod_spec_impl
from mulat.tools.pod_security.list_pods import list_pods_impl
from mulat.tools.pod_security.pss_rules import check_pod_spec, summarize_findings


def check_security_context_impl(
    *,
    namespace: str,
    name: str = "",
    label_selector: str = "",
    level: str = "baseline",
    max_pods: int = 100,
) -> dict[str, Any]:
    if not namespace:
        return failure(
            "check_security_context",
            errors.INVALID_INPUT,
            "namespace is required",
            retryable=False,
        )
    if name and not namespace:
        return failure(
            "check_security_context",
            errors.INVALID_INPUT,
            "namespace is required when name is set",
            retryable=False,
        )
    level = level if level in ("baseline", "restricted") else "baseline"
    max_pods = min(max(max_pods, 1), 500)

    findings: list[dict[str, Any]] = []
    psa_enforced: str | None = None
    truncated = False
    pods_scanned = 0

    if name:
        spec_result = get_pod_spec_impl(namespace=namespace, name=name)
        if not spec_result.get("ok"):
            return spec_result
        data = spec_result["data"]
        psa = data.get("psa_labels") or {}
        if psa.get("enforce"):
            psa_enforced = str(psa["enforce"]).split(":")[0]
        findings.extend(check_pod_spec(data, namespace=namespace, pod_name=name, level=level))
        pods_scanned = 1
    else:
        listed = list_pods_impl(
            namespace=namespace,
            label_selector=label_selector,
            limit=max_pods,
        )
        if not listed.get("ok"):
            return listed
        truncated = listed.get("truncated", False)
        for row in (listed.get("data") or {}).get("pods") or []:
            ns = row["namespace"]
            pod_name = row["name"]
            spec_result = get_pod_spec_impl(namespace=ns, name=pod_name)
            if not spec_result.get("ok"):
                continue
            data = spec_result["data"]
            if psa_enforced is None:
                psa = data.get("psa_labels") or {}
                if psa.get("enforce"):
                    psa_enforced = str(psa["enforce"]).split(":")[0]
            findings.extend(
                check_pod_spec(data, namespace=ns, pod_name=pod_name, level=level)
            )
            pods_scanned += 1
            if pods_scanned >= max_pods:
                truncated = True
                break

    return success(
        "check_security_context",
        {
            "summary": {
                "pods_scanned": pods_scanned,
                "findings_by_severity": summarize_findings(findings),
            },
            "psa_enforced_level": psa_enforced,
            "findings": findings,
        },
        truncated=truncated,
    )
