"""Unit tests for the alerter module (webhook is mocked, never raises)."""

from unittest.mock import MagicMock, patch

import requests

from src.alerter import ALERT_ATTEMPTS, send_alert


def test_should_skip_post_when_webhook_url_not_configured(monkeypatch):
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)

    with patch("src.alerter.requests.post") as mock_post:
        send_alert("title", "body")

    mock_post.assert_not_called()


def test_should_post_json_payload_when_webhook_configured(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://example.com/hook")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch("src.alerter.requests.post", return_value=mock_response) as mock_post:
        send_alert("标题", "正文")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://example.com/hook"
    assert kwargs["json"] == {"title": "标题", "body": "正文", "desp": "正文"}
    assert kwargs["timeout"] == 10


def test_should_not_raise_when_webhook_is_down(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://example.com/hook")

    with patch(
        "src.alerter.requests.post",
        side_effect=requests.ConnectionError("webhook down"),
    ) as mock_post:
        send_alert("title", "body")  # 不应抛出任何异常

    assert mock_post.call_count == ALERT_ATTEMPTS
