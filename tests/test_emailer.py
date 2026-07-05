"""Unit tests for the emailer retry logic (no real SMTP, no real sleep)."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from src.emailer import RETRY_DELAYS, send_email


@pytest.fixture
def email_env(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setenv("RECIPIENT_EMAIL", "to@example.com")


def _make_smtp_mock(side_effects):
    """Mock SMTP_SSL whose sendmail fails/succeeds per side_effects list."""
    server = MagicMock()
    server.sendmail.side_effect = side_effects
    smtp_cls = MagicMock()
    smtp_cls.return_value.__enter__ = MagicMock(return_value=server)
    smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    return smtp_cls, server


def test_should_succeed_without_raising_when_second_attempt_works(email_env):
    smtp_cls, server = _make_smtp_mock(
        [smtplib.SMTPException("temporary failure"), None]
    )

    with patch("src.emailer.smtplib.SMTP_SSL", smtp_cls), \
         patch("src.emailer.time.sleep") as mock_sleep:
        send_email("# content")

    assert server.sendmail.call_count == 2
    mock_sleep.assert_called_once_with(RETRY_DELAYS[0])


def test_should_raise_last_error_when_all_attempts_fail(email_env):
    failures = [smtplib.SMTPException(f"fail {i}") for i in range(len(RETRY_DELAYS))]
    smtp_cls, server = _make_smtp_mock(failures)

    with patch("src.emailer.smtplib.SMTP_SSL", smtp_cls), \
         patch("src.emailer.time.sleep") as mock_sleep:
        with pytest.raises(smtplib.SMTPException):
            send_email("# content")

    assert server.sendmail.call_count == len(RETRY_DELAYS)
    # 最后一次失败后不再等待
    assert mock_sleep.call_count == len(RETRY_DELAYS) - 1


def test_should_raise_value_error_when_env_vars_missing(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("RECIPIENT_EMAIL", raising=False)

    with pytest.raises(ValueError, match="GMAIL_ADDRESS"):
        send_email("# content")


def test_should_note_window_in_subject_and_body_when_window_given(email_env):
    smtp_cls, server = _make_smtp_mock([None])

    with patch("src.emailer.smtplib.SMTP_SSL", smtp_cls):
        send_email("# content", window_hours=8.0)

    sent_message = server.sendmail.call_args.args[2]
    assert "8" in sent_message
