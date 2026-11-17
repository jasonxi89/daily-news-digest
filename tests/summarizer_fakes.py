"""Shared fakes and builders for the summarizer tests."""

from types import SimpleNamespace

import httpx2

NEWS = {
    "tech": [
        {
            "title": "Chip makers race ahead",
            "summary": "S",
            "link": "https://example.com/chips",
            "source": "X",
            "published": "2026-11-16",
        }
    ]
}
USAGE_LIMIT_MESSAGE = (
    "You have reached your specified API usage limits. "
    "You will regain access on 2026-12-01 at 00:00 UTC."
)


class FakeStream:
    """Stands in for the SDK stream object inside the `with` block."""

    def __init__(self, final_message, read_error):
        self._final_message = final_message
        self._read_error = read_error

    def get_final_message(self):
        if self._read_error:
            raise self._read_error
        return self._final_message


class FakeStreamManager:
    """Stands in for `client.beta.messages.stream(...)`.

    The real SDK sends the request on `__enter__`, so request-time failures
    are raised there (enter_error); failures while reading the stream are
    raised from `get_final_message()` (read_error).
    """

    def __init__(self, final_message=None, *, enter_error=None, read_error=None):
        self._final_message = final_message
        self._enter_error = enter_error
        self._read_error = read_error

    def __enter__(self):
        if self._enter_error:
            raise self._enter_error
        return FakeStream(self._final_message, self._read_error)

    def __exit__(self, *exception_info):
        return False


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def thinking_block():
    return SimpleNamespace(type="thinking", thinking="", signature="sig")


def final_message(blocks, stop_reason="end_turn"):
    return SimpleNamespace(
        model="claude-opus-5-5",
        stop_reason=stop_reason,
        stop_details=None,
        content=blocks,
        usage=SimpleNamespace(input_tokens=1200, output_tokens=3400),
    )


def api_request():
    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(error_class, status_code, message):
    """Build a real SDK status error: parsed JSON body plus a request-id header."""
    response = httpx2.Response(
        status_code, request=api_request(), headers={"request-id": "req_test_123"}
    )
    body = {"type": "error", "error": {"type": "error", "message": message}}
    return error_class(message, response=response, body=body)
