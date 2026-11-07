from mulat.orchestration.synthesizer import build_report, sort_findings_by_severity, synthesizer_node


def test_sort_findings_by_severity():
    findings = [
        {"agent": "right_sizing", "severity": "info", "message": "b"},
        {"agent": "node_health", "severity": "high", "message": "a"},
        {"agent": "pod_security", "severity": "warning", "message": "c"},
    ]
    ordered = sort_findings_by_severity(findings)
    assert [f["agent"] for f in ordered] == ["node_health", "pod_security", "right_sizing"]


def test_synthesizer_node_rule_based_no_llm():
    state = {
        "request": "cluster check",
        "targets": ["node_health", "right_sizing"],
        "findings": [
            {"agent": "right_sizing", "severity": "info", "message": "CPU ok"},
        ],
    }
    out = synthesizer_node(state, llm=None)
    report = out["report"]
    assert report["finding_count"] == 1
    assert "right_sizing" in report["summary"]
    assert report["agents_skipped"] == ["node_health"]


def test_build_report_structure():
    state = {"request": "x", "targets": ["right_sizing"]}
    findings = [{"agent": "right_sizing", "severity": "info", "message": "m"}]
    report = build_report(state, findings, summary="done")
    assert report["summary"] == "done"
    assert report["ranked_findings"][0]["rank"] == 1
