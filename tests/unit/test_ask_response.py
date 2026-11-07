from mulat.api.routes.ask import _detail_from_state, _report_from_state


def test_detail_not_truncated():
    long_summary = "x" * 2000
    result = {"report": {"summary": long_summary, "finding_count": 0}}
    assert len(_detail_from_state(result)) == 2000


def test_report_includes_findings_messages():
    result = {
        "targets": ["right_sizing"],
        "report": {
            "summary": "full text",
            "finding_count": 1,
            "targets": ["right_sizing"],
            "agents_run": ["right_sizing"],
            "agents_skipped": [],
            "ranked_findings": [],
        },
        "findings": [{"agent": "right_sizing", "severity": "info", "message": "cpu ok", "data": {"huge": 1}}],
    }
    report = _report_from_state(result, include_raw_data=False)
    assert report is not None
    assert report.summary == "full text"
    assert report.findings[0].message == "cpu ok"
    assert report.findings[0].data is None
