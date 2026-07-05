"""Unit tests for run_state: state file persistence and window calculation."""

from datetime import datetime, timedelta, timezone

import pytest

from src.run_state import (
    FALLBACK_WINDOW_HOURS,
    MAX_WINDOW_HOURS,
    MIN_WINDOW_HOURS,
    compute_window_hours,
    load_last_success,
    save_last_success,
)

NOW = datetime(2026, 7, 4, 23, 0, tzinfo=timezone.utc)


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "last_success.json"
    monkeypatch.setenv("STATE_FILE", str(path))
    monkeypatch.delenv("DEFAULT_WINDOW_HOURS", raising=False)
    return path


def test_should_return_none_when_state_file_missing(state_file):
    assert load_last_success() is None


def test_should_return_none_when_state_file_corrupted(state_file):
    state_file.write_text("{ not valid json", encoding="utf-8")
    assert load_last_success() is None


def test_should_roundtrip_saved_timestamp(state_file):
    save_last_success(NOW)
    assert load_last_success() == NOW


def test_should_use_elapsed_hours_since_last_success(state_file):
    save_last_success(NOW - timedelta(hours=8))
    assert compute_window_hours(NOW) == pytest.approx(8)


def test_should_cap_window_at_48_hours(state_file):
    save_last_success(NOW - timedelta(hours=100))
    assert compute_window_hours(NOW) == MAX_WINDOW_HOURS


def test_should_floor_window_at_1_hour(state_file):
    save_last_success(NOW - timedelta(minutes=10))
    assert compute_window_hours(NOW) == MIN_WINDOW_HOURS


def test_should_use_default_env_window_when_no_state(state_file, monkeypatch):
    monkeypatch.setenv("DEFAULT_WINDOW_HOURS", "12")
    assert compute_window_hours(NOW) == pytest.approx(12)


def test_should_fall_back_to_24_when_no_state_and_no_env(state_file):
    assert compute_window_hours(NOW) == FALLBACK_WINDOW_HOURS


def test_should_fall_back_to_24_when_default_env_invalid(state_file, monkeypatch):
    monkeypatch.setenv("DEFAULT_WINDOW_HOURS", "not-a-number")
    assert compute_window_hours(NOW) == FALLBACK_WINDOW_HOURS
