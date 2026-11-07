from mulat.tools.pod_security.pss_rules import check_pod_spec, summarize_findings


def test_privileged_container_finding():
    spec = {
        "host_network": False,
        "host_pid": False,
        "host_ipc": False,
        "volumes": [],
        "pod_security_context": {},
        "containers": [
            {
                "name": "app",
                "security_context": {"privileged": True},
                "ports": [],
            }
        ],
        "init_containers": [],
        "ephemeral_containers": [],
    }
    findings = check_pod_spec(spec, namespace="prod", pod_name="p1", level="baseline")
    rules = {f["rule"] for f in findings}
    assert "PRIVILEGED" in rules
    assert any(f["severity"] == "high" for f in findings)


def test_summarize_findings():
    items = [{"severity": "high"}, {"severity": "high"}, {"severity": "low"}]
    assert summarize_findings(items) == {"high": 2, "low": 1}
