"""Тесты форматирования хвоста лога на странице «События»."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pytest

from events_log_display import (
    admin_events_log_timestamp_now,
    events_log_to_csv_bytes,
    filter_parsed_lines_by_local_date,
    format_events_log_for_ui,
    parse_events_log_for_table,
    reformat_log_line,
)


def test_reformat_iso_strips_ms_and_converts_utc_to_moscow(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    monkeypatch.setenv("ADMIN_EVENTS_LOG_PARSE_AS_UTC", "1")
    tz = ZoneInfo("Europe/Moscow")
    line = "2026-04-02 06:21:14,317 [ADMIN] Docker bot/stop ok"
    out = reformat_log_line(line, display_tz=tz, assume_utc=True)
    assert out == "02.04.2026 09:21:14 [ADMIN] Docker bot/stop ok"
    assert ",317" not in out


def test_reformat_iso_no_assume_utc(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    tz = ZoneInfo("Europe/Moscow")
    line = "2026-04-02 09:21:14 [ADMIN] x"
    out = reformat_log_line(line, display_tz=tz, assume_utc=False)
    assert out == "02.04.2026 09:21:14 [ADMIN] x"


def test_reformat_dmy_unchanged(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    tz = ZoneInfo("Europe/Moscow")
    line = "02.04.2026 12:00:00 [ADMIN] login"
    assert reformat_log_line(line, display_tz=tz, assume_utc=True) == line


def test_format_events_log_reverses_and_formats(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    monkeypatch.setenv("ADMIN_EVENTS_LOG_PARSE_AS_UTC", "1")
    raw = "2026-04-02 06:00:00,1 a\n2026-04-02 07:00:00,2 b"
    text = format_events_log_for_ui(raw)
    lines = text.splitlines()
    assert len(lines) == 2
    # После reverse: сначала более поздняя по файлу строка (07:00 UTC → 10:00 MSK).
    assert "b" in lines[0] and "10:00:00" in lines[0]
    assert "a" in lines[1] and "09:00:00" in lines[1]


def test_format_events_log_passes_through_missing_file_message():
    raw = "Файл лога не найден: /x\nhint"
    assert format_events_log_for_ui(raw) == raw


def test_admin_events_log_timestamp_now_respects_bot_timezone(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    s = admin_events_log_timestamp_now()
    assert len(s) == 19
    assert s[2] == "." and s[5] == "."


@pytest.mark.parametrize(
    "off",
    ("0", "false", "no", "off"),
)
def test_parse_as_utc_env_off(monkeypatch, off):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    monkeypatch.setenv("ADMIN_EVENTS_LOG_PARSE_AS_UTC", off)
    line = "2026-04-02 09:21:14 [ADMIN] x"
    text = format_events_log_for_ui(line)
    assert "09:21:14" in text


def test_parse_events_log_for_table_sorts_newest_first(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    monkeypatch.setenv("ADMIN_EVENTS_LOG_PARSE_AS_UTC", "1")
    raw = "2026-04-02 06:00:01 [INFO] a\n2026-04-02 07:00:00 [WARNING] b\n"
    lines = parse_events_log_for_table(raw)
    assert len(lines) == 2
    assert lines[0].level == "WARNING" and "b" in lines[0].message
    assert lines[1].level == "INFO"


def test_filter_parsed_lines_by_local_date(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    monkeypatch.setenv("ADMIN_EVENTS_LOG_PARSE_AS_UTC", "1")
    raw = "2026-04-02 06:00:00 [INFO] x\n"
    lines = parse_events_log_for_table(raw)
    tz = ZoneInfo("Europe/Moscow")
    assert (
        len(filter_parsed_lines_by_local_date(lines, date(2026, 4, 2), date(2026, 4, 2), tz)) == 1
    )
    assert (
        len(filter_parsed_lines_by_local_date(lines, date(2026, 4, 3), date(2026, 4, 3), tz)) == 0
    )


def test_events_log_to_csv_bytes_has_bom_and_header(monkeypatch):
    monkeypatch.setenv("BOT_TIMEZONE", "Europe/Moscow")
    monkeypatch.setenv("ADMIN_EVENTS_LOG_PARSE_AS_UTC", "1")
    lines = parse_events_log_for_table("2026-04-02 12:00:00 [INFO] hi\n")
    b = events_log_to_csv_bytes(lines)
    assert b.startswith("\ufeff".encode("utf-8"))
    assert b"level" in b and b"INFO" in b and b"hi" in b
