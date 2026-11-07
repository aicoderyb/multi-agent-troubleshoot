from mulat.orchestration.supervisor import supervisor_node


def test_supervisor_routes_node_request():
    out = supervisor_node({"request": "node-3 is NotReady"})
    assert out["targets"] == ["node_health"]


def test_supervisor_full_check_default():
    out = supervisor_node({"request": "pre-release cluster check"})
    assert len(out["targets"]) == 3
