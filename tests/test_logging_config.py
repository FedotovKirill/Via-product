"""Тесты для src/logging_config.py — JSON logging configuration."""

from __future__ import annotations

import logging

import pytest

from logging_config import _want_json, get_log_formatter, setup_json_logging


class TestWantJson:
    """_want_json: проверяет WANT_JSON_LOG=1."""

    def test_default_false(self, monkeypatch):
        monkeypatch.delenv("WANT_JSON_LOG", raising=False)
        assert _want_json() is False

    def test_zero_false(self, monkeypatch):
        monkeypatch.setenv("WANT_JSON_LOG", "0")
        assert _want_json() is False

    def test_one_true(self, monkeypatch):
        monkeypatch.setenv("WANT_JSON_LOG", "1")
        assert _want_json() is True

    def test_whitespace_ignored(self, monkeypatch):
        monkeypatch.setenv("WANT_JSON_LOG", "  1  ")
        assert _want_json() is True


class TestSetupJsonLogging:
    """setup_json_logging: настройка JSON логирования."""

    def test_no_op_when_json_disabled(self, monkeypatch):
        monkeypatch.delenv("WANT_JSON_LOG", raising=False)
        test_logger = logging.getLogger("test_no_op")
        before = len(test_logger.handlers)
        setup_json_logging("test_no_op")
        # JSON logging не включено — handlers не добавлены
        assert len(test_logger.handlers) == before

    def test_adds_handler_when_json_enabled(self, monkeypatch):
        monkeypatch.setenv("WANT_JSON_LOG", "1")
        test_logger = logging.getLogger("test_json_on")
        test_logger.handlers.clear()
        setup_json_logging("test_json_on")
        assert len(test_logger.handlers) >= 1


class TestGetLogFormatter:
    """get_log_formatter: возвращает JSON или обычный formatter."""

    def test_text_formatter_by_default(self, monkeypatch):
        monkeypatch.delenv("WANT_JSON_LOG", raising=False)
        fmt = get_log_formatter()
        assert isinstance(fmt, logging.Formatter)

    def test_json_formatter_when_enabled(self, monkeypatch):
        monkeypatch.setenv("WANT_JSON_LOG", "1")
        try:
            from pythonjsonlogger import jsonlogger

            fmt = get_log_formatter()
            assert isinstance(fmt, jsonlogger.JsonFormatter)
        except ImportError:
            pytest.skip("python-json-logger not installed")
