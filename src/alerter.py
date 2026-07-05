"""Failure alerter - best-effort webhook notification (Server酱 compatible).

告警是辅助路径：任何失败只 log，绝不抛异常，避免反过来搞挂主流程。
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

ALERT_TIMEOUT = 10  # seconds per request
ALERT_ATTEMPTS = 2


def send_alert(title: str, body: str) -> None:
    """POST an alert to ALERT_WEBHOOK_URL if configured; never raises.

    Payload carries both "body" and "desp" keys for compatibility with
    Server酱 and common webhook receivers.
    """
    url = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
    if not url:
        logger.debug("ALERT_WEBHOOK_URL not set, skipping alert: %s", title)
        return

    payload = {"title": title, "body": body, "desp": body}

    for attempt in range(1, ALERT_ATTEMPTS + 1):
        try:
            response = requests.post(url, json=payload, timeout=ALERT_TIMEOUT)
            response.raise_for_status()
            logger.info("Alert sent: %s", title)
            return
        except Exception as exc:
            logger.warning(
                "Alert attempt %d/%d failed: %s: %s",
                attempt, ALERT_ATTEMPTS, type(exc).__name__, exc,
            )

    logger.error("All %d alert attempts failed, giving up: %s", ALERT_ATTEMPTS, title)
