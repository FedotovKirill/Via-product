"""Формат даты/времени для UI панели (фильтр Jinja dt_ui)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ui_datetime import format_datetime_ui


def test_format_datetime_ui_none_and_non_datetime():
    assert format_datetime_ui(None) == "—"
    assert format_datetime_ui("x") == "—"
    assert format_datetime_ui(1) == "—"


def test_format_datetime_ui_utc_to_moscow(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    dt = datetime(2026, 4, 1, 8, 5, 40, 66237, tzinfo=timezone.utc)
    assert format_datetime_ui(dt) == "01.04.2026 11:05:40"


def test_format_datetime_ui_naive_treated_as_utc(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    dt = datetime(2026, 4, 1, 8, 5, 40)
    assert format_datetime_ui(dt) == "01.04.2026 11:05:40"


def test_format_datetime_ui_no_microseconds_in_output(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    dt = datetime(2026, 1, 2, 3, 4, 5, 999999, tzinfo=timezone.utc)
    out = format_datetime_ui(dt)
    assert out == "02.01.2026 06:04:05"
    assert "999999" not in out
    assert "+00:00" not in out
    assert "T" not in out
