"""Unit tests for the summarizer module, with the Claude stream faked out."""

import logging

import anthropic
import httpx2
import pytest

from src.summarizer import summarize_news
from tests.summarizer_fakes import (
    NEWS,
    USAGE_LIMIT_MESSAGE,
    FakeStreamManager,
    api_request,
    final_message,
    status_error,
    text_block,
    thinking_block,
)


def test_should_join_text_blocks_and_skip_thinking_when_claude_responds(claude):
    claude.stream.return_value = FakeStreamManager(
        final_message([thinking_block(), text_block("# 摘要\n"), text_block("正文")])
    )

    assert summarize_news(NEWS) == "# 摘要\n正文"


def test_should_request_opus_at_high_effort_with_refusal_fallback_by_default(claude):
    claude.stream.return_value = FakeStreamManager(final_message([text_block("ok")]))

    summarize_news(NEWS)

    request = claude.stream.call_args.kwargs
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"] == {"effort": "high"}
    assert request["max_tokens"] == 128000
    assert request["betas"] == ["server-side-fallback-2026-07-01"]
    assert request["fallbacks"] == "default"
    assert [message["role"] for message in request["messages"]] == ["user"]
    assert "Chip makers race ahead" in request["messages"][0]["content"]
    # Opus 5.5 对这些参数直接报 400，思考强度只走 output_config.effort
    assert not {"thinking", "temperature", "top_p", "top_k"} & request.keys()


def test_should_use_model_and_effort_from_environment_when_set(claude, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("CLAUDE_EFFORT", "medium")
    claude.stream.return_value = FakeStreamManager(final_message([text_block("ok")]))

    summarize_news(NEWS)

    request = claude.stream.call_args.kwargs
    assert request["model"] == "claude-sonnet-5-5"
    assert request["output_config"] == {"effort": "medium"}


def test_should_fall_back_to_defaults_when_model_and_effort_are_blank(claude, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "")
    monkeypatch.setenv("CLAUDE_EFFORT", "  ")
    claude.stream.return_value = FakeStreamManager(final_message([text_block("ok")]))

    summarize_news(NEWS)

    request = claude.stream.call_args.kwargs
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"] == {"effort": "high"}


def test_should_create_client_with_env_key_long_read_timeout_and_retries(claude):
    claude.stream.return_value = FakeStreamManager(final_message([text_block("ok")]))

    summarize_news(NEWS)

    client_options = claude.client_class.call_args.kwargs
    assert client_options["api_key"] == "test-key"
    assert client_options["max_retries"] == 2
    assert client_options["timeout"].read == 600
    assert client_options["timeout"].connect == 10


def test_should_return_empty_notice_without_calling_claude_when_no_news(claude):
    result = summarize_news({"tech": [], "health_hot": {}})

    assert "每日新闻摘要" in result
    assert "暂无新闻" in result
    claude.client_class.assert_not_called()


def test_should_log_usage_line_when_summary_completes(claude, caplog):
    claude.stream.return_value = FakeStreamManager(final_message([text_block("正文")]))

    with caplog.at_level(logging.INFO, logger="src.summarizer"):
        summarize_news(NEWS)

    usage_lines = [line for line in caplog.messages if "summarize done" in line]
    assert len(usage_lines) == 1
    for expected in (
        "model=claude-opus-5-5",
        "stop_reason=end_turn",
        "input_tokens=1200",
        "output_tokens=3400",
        "elapsed_seconds=",
    ):
        assert expected in usage_lines[0]


def test_should_return_fallback_notice_when_claude_refuses(claude):
    claude.stream.return_value = FakeStreamManager(
        final_message([text_block("写到一半的内容")], stop_reason="refusal")
    )

    result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "拒绝" in result
    assert "写到一半的内容" not in result


@pytest.mark.parametrize("stop_reason", ["max_tokens", "model_context_window_exceeded"])
def test_should_send_partial_summary_with_notice_when_truncated(claude, caplog, stop_reason):
    claude.stream.return_value = FakeStreamManager(
        final_message([text_block("# 摘要\n前半段")], stop_reason=stop_reason)
    )

    with caplog.at_level(logging.WARNING, logger="src.summarizer"):
        result = summarize_news(NEWS)

    assert result.startswith("# 摘要\n前半段")
    assert "截断" in result
    assert "摘要生成失败" not in result
    assert any(record.levelno == logging.WARNING for record in caplog.records)


@pytest.mark.parametrize(
    ("blocks", "stop_reason"),
    [
        ([], "end_turn"),
        ([thinking_block()], "end_turn"),
        ([text_block("  \n")], "end_turn"),
        ([thinking_block()], "max_tokens"),
    ],
)
def test_should_return_fallback_notice_when_summary_body_is_empty(claude, blocks, stop_reason):
    claude.stream.return_value = FakeStreamManager(final_message(blocks, stop_reason=stop_reason))

    result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "没有返回正文" in result
    assert stop_reason in result


def test_should_skip_claude_and_return_notice_when_effort_is_invalid(claude, monkeypatch):
    monkeypatch.setenv("CLAUDE_EFFORT", "ultra")

    result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "CLAUDE_EFFORT" in result
    assert "ultra" in result
    assert "xhigh" in result
    claude.stream.assert_not_called()


def test_should_skip_claude_and_return_notice_when_api_key_missing(claude, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")

    result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "ANTHROPIC_API_KEY" in result
    claude.client_class.assert_not_called()


def test_should_return_fallback_notice_when_connection_fails(claude):
    claude.stream.return_value = FakeStreamManager(
        enter_error=anthropic.APIConnectionError(request=api_request())
    )

    result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "无法连接" in result


def test_should_return_fallback_notice_when_stream_times_out_midway(claude):
    claude.stream.return_value = FakeStreamManager(
        read_error=anthropic.APITimeoutError(request=api_request())
    )

    result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "无法连接" in result


def test_should_return_fallback_notice_when_authentication_fails(claude, caplog):
    claude.stream.return_value = FakeStreamManager(
        enter_error=status_error(anthropic.AuthenticationError, 401, "invalid x-api-key")
    )

    with caplog.at_level(logging.ERROR, logger="src.summarizer"):
        result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "认证失败" in result
    assert "req_test_123" in caplog.text


def test_should_return_fallback_notice_when_rate_limited(claude, caplog):
    claude.stream.return_value = FakeStreamManager(
        enter_error=status_error(anthropic.RateLimitError, 429, "Too many requests")
    )

    with caplog.at_level(logging.ERROR, logger="src.summarizer"):
        result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "HTTP 429" in result
    assert "Too many requests" in result
    assert "req_test_123" in caplog.text


def test_should_include_api_message_in_fallback_notice_when_api_returns_error(claude, caplog):
    claude.stream.return_value = FakeStreamManager(
        enter_error=status_error(anthropic.BadRequestError, 400, USAGE_LIMIT_MESSAGE)
    )

    with caplog.at_level(logging.ERROR, logger="src.summarizer"):
        result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "HTTP 400" in result
    assert "regain access on 2026-12-01" in result
    assert "req_test_123" in caplog.text


def test_should_return_fallback_notice_when_api_error_has_no_json_body(claude):
    response = httpx2.Response(500, request=api_request())
    claude.stream.return_value = FakeStreamManager(
        enter_error=anthropic.InternalServerError("upstream exploded", response=response, body=None)
    )

    result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "HTTP 500" in result
    assert "upstream exploded" in result


def test_should_return_fallback_notice_when_unexpected_exception_raised(claude):
    claude.stream.return_value = FakeStreamManager(enter_error=RuntimeError("boom"))

    result = summarize_news(NEWS)

    assert "摘要生成失败" in result
    assert "未知错误" in result
    assert "RuntimeError" in result
