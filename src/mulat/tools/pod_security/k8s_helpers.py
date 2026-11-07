"""Pod list/spec helpers for security tools."""

from __future__ import annotations

from typing import Any

from kubernetes.client import V1Container, V1Pod, V1PodSpec, V1SecurityContext, V1Volume

# Pod-level V1PodSecurityContext lacks privileged/capabilities; use getattr for shared serializer.

from mulat.tools.node_health.k8s_util import handle_api_exception

__all__ = ["handle_api_exception", "owner_dict", "security_context_dict", "volume_dict"]


def owner_dict(pod: V1Pod) -> dict[str, str | None]:
    refs = pod.metadata.owner_references or []
    if not refs:
        return {"kind": None, "name": None}
    ref = refs[0]
    return {"kind": ref.kind, "name": ref.name}


def security_context_dict(sc: V1SecurityContext | None) -> dict[str, Any]:
    if sc is None:
        return {}
    out: dict[str, Any] = {}

    privileged = getattr(sc, "privileged", None)
    if privileged is not None:
        out["privileged"] = privileged
    run_as_non_root = getattr(sc, "run_as_non_root", None)
    if run_as_non_root is not None:
        out["runAsNonRoot"] = run_as_non_root
    run_as_user = getattr(sc, "run_as_user", None)
    if run_as_user is not None:
        out["runAsUser"] = run_as_user
    allow_pe = getattr(sc, "allow_privilege_escalation", None)
    if allow_pe is not None:
        out["allowPrivilegeEscalation"] = allow_pe

    capabilities = getattr(sc, "capabilities", None)
    if capabilities:
        caps: dict[str, Any] = {}
        if capabilities.add:
            caps["add"] = list(capabilities.add)
        if capabilities.drop:
            caps["drop"] = list(capabilities.drop)
        if caps:
            out["capabilities"] = caps

    seccomp_profile = getattr(sc, "seccomp_profile", None)
    if seccomp_profile and seccomp_profile.type:
        out["seccompProfile"] = {"type": seccomp_profile.type}
    return out


def _merge_security(pod_sc: dict[str, Any], container_sc: dict[str, Any]) -> dict[str, Any]:
    merged = dict(pod_sc)
    for key, val in container_sc.items():
        if key == "capabilities" and "capabilities" in merged:
            mc = dict(merged["capabilities"])
            cc = dict(val)
            add = list(cc.get("add") or mc.get("add") or [])
            drop = list(cc.get("drop") or mc.get("drop") or [])
            if add:
                mc["add"] = add
            if drop:
                mc["drop"] = drop
            merged["capabilities"] = mc
        else:
            merged[key] = val
    return merged


def merged_container_context(pod_spec: V1PodSpec, container: V1Container) -> dict[str, Any]:
    pod_sc = security_context_dict(pod_spec.security_context)
    ctr_sc = security_context_dict(container.security_context)
    return _merge_security(pod_sc, ctr_sc)


def volume_dict(vol: V1Volume) -> dict[str, Any]:
    row: dict[str, Any] = {"name": vol.name, "type": "unknown"}
    if vol.host_path:
        row["type"] = "hostPath"
        row["host_path"] = vol.host_path.path
    elif vol.empty_dir:
        row["type"] = "emptyDir"
    elif vol.config_map:
        row["type"] = "configMap"
    elif vol.secret:
        row["type"] = "secret"
    elif vol.persistent_volume_claim:
        row["type"] = "persistentVolumeClaim"
    return row


def container_dict(c: V1Container) -> dict[str, Any]:
    ports = []
    for p in c.ports or []:
        ports.append(
            {
                "container_port": p.container_port,
                "host_port": p.host_port,
            }
        )
    return {
        "name": c.name,
        "image": c.image,
        "image_pull_policy": c.image_pull_policy,
        "security_context": security_context_dict(c.security_context),
        "resources": {},
        "ports": ports,
    }
