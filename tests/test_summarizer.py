"""Unit tests for the summarizer module (OpenRouter/openai streaming path)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.summarizer import summarize_news


def _make_chunk(content):
    """Build a fake streaming chunk matching openai SDK shape."""
    delta = SimpleNamespace(content=content)
    choice = SimpleNamespace(delta=delta)
    return SimpleNamespace(choices=[choice])


def _make_stream(parts):
    """Return an iterable of fake chunks for the given content parts."""
    return [_make_chunk(p) for p in parts]


def test_summarize_news_accumulates_stream_chunks():
    """summarize_news should join all delta.content chunks into one string."""
    fake_stream = _make_stream(["Hello", " ", "World"])

    mock_completions = MagicMock()
    mock_completions.create.return_value = iter(fake_stream)

    mock_chat = MagicMock()
    mock_chat.completions = mock_completions

    mock_client = MagicMock()
    mock_client.chat = mock_chat

    news = {"international": [{"title": "T", "summary": "S", "link": "L", "source": "X", "published": "2026-06-16"}]}

    with patch("src.summarizer.openai.OpenAI", return_value=mock_client):
        result = summarize_news(news)

    assert result == "Hello World"


def test_summarize_news_uses_streaming_and_default_model(monkeypatch):
    """summarize_news must pass stream=True and default to deepseek/deepseek-v4-pro."""
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    fake_stream = _make_stream(["ok"])

    mock_completions = MagicMock()
    mock_completions.create.return_value = iter(fake_stream)

    mock_chat = MagicMock()
    mock_chat.completions = mock_completions

    mock_client = MagicMock()
    mock_client.chat = mock_chat

    news = {"tech": [{"title": "T2", "summary": "S2", "link": "L2", "source": "Y", "published": "2026-06-16"}]}

    with patch("src.summarizer.openai.OpenAI", return_value=mock_client):
        summarize_news(news)

    call_kwargs = mock_completions.create.call_args
    assert call_kwargs.kwargs.get("stream") is True, "stream=True must be set"
    assert call_kwargs.kwargs.get("model") == "deepseek/deepseek-v4-pro", (
        f"default model should be deepseek/deepseek-v4-pro, got {call_kwargs.kwargs.get('model')}"
    )


def test_summarize_news_returns_empty_summary_when_no_news():
    """summarize_news should return a fallback string when all sections are empty."""
    result = summarize_news({})
    assert "每日新闻摘要" in result
    assert "暂无新闻" in result


def test_should_return_fallback_content_when_any_exception_raised():
    """summarize_news must catch arbitrary exceptions and return sendable fallback."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("boom")

    news = {"tech": [{"title": "T", "summary": "S", "link": "L", "source": "X", "published": "2026-07-04"}]}

    with patch("src.summarizer.openai.OpenAI", return_value=mock_client):
        result = summarize_news(news)

    assert "摘要生成失败" in result
    assert "未知错误" in result
    assert "RuntimeError" in result


def test_should_create_client_with_explicit_max_retries():
    """OpenAI client must be constructed with max_retries=2 explicitly."""
    fake_stream = _make_stream(["ok"])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter(fake_stream)

    news = {"tech": [{"title": "T", "summary": "S", "link": "L", "source": "X", "published": "2026-07-04"}]}

    with patch("src.summarizer.openai.OpenAI", return_value=mock_client) as mock_openai:
        summarize_news(news)

    assert mock_openai.call_args.kwargs.get("max_retries") == 2
