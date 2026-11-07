from mulat.tools.envelope import failure, success


def test_success_envelope():
    result = success("list_nodes", {"count": 0, "nodes": []})
    assert result["ok"] is True
    assert result["tool"] == "list_nodes"
    assert result["error"] is None


def test_failure_envelope():
    result = failure("describe_node", "NOT_FOUND", "node missing", retryable=False)
    assert result["ok"] is False
    assert result["error"]["code"] == "NOT_FOUND"
