"""Summarizer tests that keep the real anthropic SDK and fake only the HTTP transport.

Nothing here touches the network, but the request body, the headers and the
stream parsing all run through the SDK's own code.
"""

import json
import logging

import anthropic
import httpx2
import pytest

from src.summarizer import summarize_news
from tests.summarizer_fakes import NEWS, USAGE_LIMIT_MESSAGE

pytestmark = pytest.mark.usefixtures("claude_environment")

STREAMED_REPLY_EVENTS = [
    {
        "type": "message_start",
        "message": {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 25, "output_tokens": 1},
        },
    },
    {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "thinking", "thinking": "", "signature": ""},
    },
    {"type": "ping"},
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "signature_delta", "signature": "sig"},
    },
    {"type": "content_block_stop", "index": 0},
    {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "# 摘要\n"}},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "正文"}},
    {"type": "content_block_stop", "index": 1},
    {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 15},
    },
    {"type": "message_stop"},
]


def _as_event_stream(events):
    """Encode events the way the Messages API streams them (server-sent events)."""
    lines = [f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events]
    return "".join(lines).encode()


def _use_real_sdk_with_fake_transport(monkeypatch, respond):
    """Keep the real anthropic client but answer its HTTP requests with `respond`."""
    real_client_class = anthropic.Anthropic

    def create_client(**options):
        http_client = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(respond))
        return real_client_class(**options, http_client=http_client)

    monkeypatch.setattr("src.summarizer.anthropic.Anthropic", create_client)


def test_should_send_streaming_request_and_parse_reply_when_using_real_sdk(monkeypatch):
    captured = {}

    def respond(request):
        captured["body"] = json.loads(request.content)
        captured["beta_header"] = request.headers.get("anthropic-beta")
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=_as_event_stream(STREAMED_REPLY_EVENTS),
        )

    _use_real_sdk_with_fake_transport(monkeypatch, respond)

    result = summarize_news(NEWS)

    assert result == "# 摘要\n正文"
    assert captured["body"]["stream"] is True
    assert captured["body"]["model"] == "claude-opus-5-5"
    assert captured["body"]["max_tokens"] == 128000
    assert captured["body"]["output_config"] == {"effort": "high"}
    assert captured["body"]["fallbacks"] == "default"
    assert captured["beta_header"] == "server-side-fallback-2026-07-01"


def test_should_surface_api_message_when_real_sdk_gets_http_400(monkeypatch, caplog):
    def respond(request):
        error_body = {
            "type": "error",
            "error": {"type": "invalid_request_error", "message": USAGE_LIMIT_MESSAGE},
            "request_id": "req_usage_limit",
        }
        return httpx2.Response(400, json=error_body, headers={"request-id": "req_usage_limit"})

    _use_real_sdk_with_fake_transport(monkeypatch, respond)

    with caplog.at_level(logging.ERROR, logger="src.summarizer"):
        result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "HTTP 400" in result
    assert "regain access on 2026-12-01" in result
    assert "req_usage_limit" in caplog.text
