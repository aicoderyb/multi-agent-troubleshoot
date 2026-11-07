"""Kubernetes client — env token, in-cluster ServiceAccount, or kubeconfig."""

from __future__ import annotations

from kubernetes import client, config

from mulat.config import settings
from mulat.logging_config import get_logger

logger = get_logger(__name__)


def _normalize_api_server(server: str) -> str:
    server = server.strip().rstrip("/")
    if not server.startswith("http://") and not server.startswith("https://"):
        server = f"https://{server}"
    return server


def _api_from_env_token() -> client.CoreV1Api:
    host = _normalize_api_server(settings.k8s_api_server)
    token = settings.k8s_token.strip()
    cfg = client.Configuration()
    cfg.host = host
    cfg.api_key = {"authorization": f"Bearer {token}"}
    cfg.verify_ssl = settings.k8s_verify_ssl
    api_client = client.ApiClient(cfg)
    logger.info(
        "Kubernetes client: bearer token to %s (verify_ssl=%s)",
        host,
        settings.k8s_verify_ssl,
    )
    return client.CoreV1Api(api_client)


def get_core_v1_api() -> client.CoreV1Api:
    if settings.k8s_api_server and settings.k8s_token:
        return _api_from_env_token()
    try:
        config.load_incluster_config()
        logger.debug("Kubernetes client: in-cluster ServiceAccount")
    except config.ConfigException:
        config.load_kube_config()
        logger.debug("Kubernetes client: kubeconfig")
    return client.CoreV1Api()
