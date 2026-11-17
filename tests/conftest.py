"""Fixtures shared by the summarizer tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def claude_environment(monkeypatch):
    """本机环境里可能残留真实或失效的 key 和配置，测试一律显式设置，不依赖环境本身。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_EFFORT", raising=False)


@pytest.fixture
def claude(claude_environment, monkeypatch):
    """Replace anthropic.Anthropic so the test never reaches the real API."""
    client = MagicMock()
    client_class = MagicMock(return_value=client)
    monkeypatch.setattr("src.summarizer.anthropic.Anthropic", client_class)
    return SimpleNamespace(client_class=client_class, stream=client.beta.messages.stream)
