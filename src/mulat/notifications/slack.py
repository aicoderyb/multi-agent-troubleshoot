"""Post report to Slack incoming webhook."""

import httpx

from mulat.config import settings


def send_slack_report(text: str) -> None:
    if not settings.slack_webhook_url:
        return
    with httpx.Client(timeout=15) as client:
        client.post(settings.slack_webhook_url, json={"text": text})
