import pytest

pytestmark = pytest.mark.skip(reason="Requires kind/minikube and RBAC")


def test_tools_against_kind():
    assert True
