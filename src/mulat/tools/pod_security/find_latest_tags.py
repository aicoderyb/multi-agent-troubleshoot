"""find_latest_tags — unpinned image detection. See Tool_API.md."""

from __future__ import annotations

from typing import Any

from mulat.tools.envelope import success
from mulat.tools.pod_security.list_pods import list_pods_impl


def classify_image_issue(image: str, *, require_digest: bool) -> str | None:
    if not image:
        return "NO_TAG"
    if "@sha256:" in image:
        return None
    last_slash = image.rfind("/")
    ref = image[last_slash + 1 :] if last_slash >= 0 else image
    if ":" not in ref:
        return "NO_TAG"
    _name, tag = ref.rsplit(":", 1)
    if tag.lower() == "latest":
        return "LATEST_TAG"
    if require_digest:
        return "NO_DIGEST"
    return None


def find_latest_tags_impl(
    *,
    namespace: str = "",
    label_selector: str = "",
    require_digest: bool = False,
    limit: int = 200,
) -> dict[str, Any]:
    limit = min(max(limit, 1), 500)
    listed = list_pods_impl(namespace=namespace, label_selector=label_selector, limit=limit)
    if not listed.get("ok"):
        return listed

    images_out: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    images_scanned = 0

    for pod in (listed.get("data") or {}).get("pods") or []:
        ns = pod.get("namespace")
        pod_name = pod.get("name")
        container_names = pod.get("containers") or []
        for i, image in enumerate(pod.get("images") or []):
            images_scanned += 1
            issue = classify_image_issue(image, require_digest=require_digest)
            if not issue:
                continue
            counts[issue] = counts.get(issue, 0) + 1
            cname = container_names[i] if i < len(container_names) else f"container-{i}"
            images_out.append(
                {
                    "namespace": ns,
                    "pod": pod_name,
                    "container": cname,
                    "image": image,
                    "issue": issue,
                    "image_pull_policy": None,
                }
            )

    return success(
        "find_latest_tags",
        {
            "summary": {
                "images_scanned": images_scanned,
                "counts_by_issue": counts,
            },
            "images": images_out,
        },
        truncated=listed.get("truncated", False),
    )
