"""Pod Security Standards rule checks (baseline + restricted)."""

from __future__ import annotations

from typing import Any

_BASELINE_ONLY = frozenset(
    {"PRIVILEGED", "HOST_NAMESPACES", "HOST_PATH", "HOST_PORT", "CAPABILITIES_ADDED"}
)
_RESTRICTED = frozenset(
    {"RUN_AS_ROOT", "PRIV_ESCALATION", "CAPABILITIES_NOT_DROPPED", "SECCOMP_MISSING"}
)


def _add(
    findings: list[dict[str, Any]],
    *,
    namespace: str,
    pod: str,
    container: str,
    rule: str,
    severity: str,
    level: str,
    field_path: str,
    observed: Any,
    message: str,
    hint: str,
) -> None:
    findings.append(
        {
            "namespace": namespace,
            "pod": pod,
            "container": container,
            "rule": rule,
            "severity": severity,
            "level": level,
            "field_path": field_path,
            "observed": observed,
            "message": message,
            "hint": hint,
        }
    )


def check_pod_spec(
    spec: dict[str, Any],
    *,
    namespace: str,
    pod_name: str,
    level: str = "baseline",
) -> list[dict[str, Any]]:
    """Evaluate one normalized pod spec dict (from get_pod_spec)."""
    findings: list[dict[str, Any]] = []
    check_restricted = level == "restricted"

    if spec.get("host_network") or spec.get("host_pid") or spec.get("host_ipc"):
        _add(
            findings,
            namespace=namespace,
            pod=pod_name,
            container="",
            rule="HOST_NAMESPACES",
            severity="high",
            level="baseline",
            field_path="spec.hostNetwork/hostPID/hostIPC",
            observed=True,
            message="Pod uses host namespace(s)",
            hint="Disable hostNetwork, hostPID, and hostIPC unless strictly required",
        )

    for vol in spec.get("volumes") or []:
        if vol.get("type") == "hostPath" or vol.get("host_path"):
            _add(
                findings,
                namespace=namespace,
                pod=pod_name,
                container="",
                rule="HOST_PATH",
                severity="high",
                level="baseline",
                field_path=f"spec.volumes[{vol.get('name')}]",
                observed=vol.get("host_path"),
                message="Pod mounts hostPath volume",
                hint="Use PVC or other volume types instead of hostPath",
            )

    pod_sc = spec.get("pod_security_context") or {}

    def _scan_container(container: dict[str, Any], kind: str, index: int) -> None:
        name = container.get("name") or f"{kind}-{index}"
        merged = dict(pod_sc)
        ctr_sc = container.get("security_context") or {}
        for key, val in ctr_sc.items():
            if key == "capabilities" and "capabilities" in merged:
                mc = dict(merged["capabilities"])
                cc = dict(val)
                if cc.get("add"):
                    mc["add"] = cc["add"]
                if cc.get("drop"):
                    mc["drop"] = cc["drop"]
                merged["capabilities"] = mc
            else:
                merged[key] = val

        path = f"spec.{kind}[{index}]"

        if merged.get("privileged") is True:
            _add(
                findings,
                namespace=namespace,
                pod=pod_name,
                container=name,
                rule="PRIVILEGED",
                severity="high",
                level="baseline",
                field_path=f"{path}.securityContext.privileged",
                observed=True,
                message="Container runs privileged",
                hint="Remove privileged or grant only the needed capability",
            )

        for port in container.get("ports") or []:
            hp = port.get("host_port")
            if hp:
                _add(
                    findings,
                    namespace=namespace,
                    pod=pod_name,
                    container=name,
                    rule="HOST_PORT",
                    severity="medium",
                    level="baseline",
                    field_path=f"{path}.ports",
                    observed=hp,
                    message="Container binds a host port",
                    hint="Avoid hostPort; expose via Service instead",
                )

        caps = (merged.get("capabilities") or {}).get("add") or []
        extra = [c for c in caps if c != "NET_BIND_SERVICE"]
        if extra:
            _add(
                findings,
                namespace=namespace,
                pod=pod_name,
                container=name,
                rule="CAPABILITIES_ADDED",
                severity="high",
                level="baseline",
                field_path=f"{path}.securityContext.capabilities.add",
                observed=extra,
                message="Container adds capabilities beyond NET_BIND_SERVICE",
                hint="Drop unnecessary capabilities; avoid custom adds on baseline",
            )

        if not check_restricted:
            return

        run_non_root = merged.get("runAsNonRoot")
        run_as_user = merged.get("runAsUser")
        if run_non_root is not True and run_as_user == 0:
            _add(
                findings,
                namespace=namespace,
                pod=pod_name,
                container=name,
                rule="RUN_AS_ROOT",
                severity="medium",
                level="restricted",
                field_path=f"{path}.securityContext.runAsNonRoot/runAsUser",
                observed={"runAsNonRoot": run_non_root, "runAsUser": run_as_user},
                message="Container may run as root",
                hint="Set runAsNonRoot: true and non-zero runAsUser",
            )
        elif run_non_root is not True and run_as_user is None:
            _add(
                findings,
                namespace=namespace,
                pod=pod_name,
                container=name,
                rule="RUN_AS_ROOT",
                severity="medium",
                level="restricted",
                field_path=f"{path}.securityContext.runAsNonRoot",
                observed=run_non_root,
                message="runAsNonRoot is not explicitly true",
                hint="Set securityContext.runAsNonRoot: true",
            )

        if merged.get("allowPrivilegeEscalation") is not False:
            _add(
                findings,
                namespace=namespace,
                pod=pod_name,
                container=name,
                rule="PRIV_ESCALATION",
                severity="medium",
                level="restricted",
                field_path=f"{path}.securityContext.allowPrivilegeEscalation",
                observed=merged.get("allowPrivilegeEscalation"),
                message="allowPrivilegeEscalation is not false",
                hint="Set allowPrivilegeEscalation: false",
            )

        drop = (merged.get("capabilities") or {}).get("drop") or []
        if "ALL" not in drop:
            _add(
                findings,
                namespace=namespace,
                pod=pod_name,
                container=name,
                rule="CAPABILITIES_NOT_DROPPED",
                severity="low",
                level="restricted",
                field_path=f"{path}.securityContext.capabilities.drop",
                observed=drop,
                message="Capabilities do not drop ALL",
                hint="Set capabilities.drop: [ALL] and add only what you need",
            )

        seccomp = (merged.get("seccompProfile") or {}).get("type")
        if seccomp not in ("RuntimeDefault", "Localhost"):
            _add(
                findings,
                namespace=namespace,
                pod=pod_name,
                container=name,
                rule="SECCOMP_MISSING",
                severity="low",
                level="restricted",
                field_path=f"{path}.securityContext.seccompProfile.type",
                observed=seccomp,
                message="seccompProfile is not RuntimeDefault or Localhost",
                hint="Set seccompProfile.type: RuntimeDefault",
            )

    for i, c in enumerate(spec.get("containers") or []):
        _scan_container(c, "containers", i)
    for i, c in enumerate(spec.get("init_containers") or []):
        _scan_container(c, "initContainers", i)
    for i, c in enumerate(spec.get("ephemeral_containers") or []):
        _scan_container(c, "ephemeralContainers", i)

    if level == "baseline":
        findings = [f for f in findings if f["rule"] in _BASELINE_ONLY]
    return findings


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    by_sev: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity") or "info"
        by_sev[sev] = by_sev.get(sev, 0) + 1
    return by_sev
