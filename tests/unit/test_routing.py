from langgraph.types import Send

from mulat.orchestration.routing import supervisor_fan_out


def test_fan_out_parallel_sends():
    state = {"targets": ["node_health", "right_sizing"], "request": "check"}
    out = supervisor_fan_out(state)
    assert isinstance(out, list)
    assert len(out) == 2
    assert all(isinstance(s, Send) for s in out)
    assert {s.node for s in out} == {"node_health", "right_sizing"}


def test_fan_out_empty_targets_to_synthesize():
    assert supervisor_fan_out({"targets": []}) == "synthesize"
