from mulat.tools.pod_security.find_latest_tags import classify_image_issue


def test_latest_tag_detected():
    assert classify_image_issue("registry.local/api:latest", require_digest=False) == "LATEST_TAG"


def test_digest_pinned_ok():
    assert (
        classify_image_issue(
            "registry.local/api@sha256:abc123",
            require_digest=True,
        )
        is None
    )


def test_no_tag():
    assert classify_image_issue("registry.local/api", require_digest=False) == "NO_TAG"
