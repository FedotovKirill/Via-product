"""Тесты для src/redmine_cache.py — кэширование запросов к Redmine."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import redmine_cache as rc


class TestFetchRedmineUserById:
    """fetch_redmine_user_by_id: GET /users/:id.json с кэшированием."""

    def setup_method(self):
        rc._redmine_user_cache.clear()

    def test_returns_cached_on_second_call(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"user": {"id": 42, "login": "ivan", "firstname": "Ivan"}}
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("redmine_cache.urlopen", return_value=mock_response):
            user, err = rc.fetch_redmine_user_by_id(42, "https://rm.test", "key123")
        assert user["id"] == 42
        assert err is None

        # Второй вызов — из кэша, urlopen не вызывается
        with patch("redmine_cache.urlopen") as mock_urlopen:
            user2, err2 = rc.fetch_redmine_user_by_id(42, "https://rm.test", "key123")
        mock_urlopen.assert_not_called()
        assert user2["id"] == 42
        assert err2 is None

    def test_404_returns_not_found(self):
        err_mock = HTTPError("https://rm.test", 404, "Not Found", {}, None)
        with patch("redmine_cache.urlopen", side_effect=err_mock):
            user, err = rc.fetch_redmine_user_by_id(999, "https://rm.test", "key")
        assert user is None
        assert err == "not_found"

    def test_missing_config(self):
        user, err = rc.fetch_redmine_user_by_id(1, "", "")
        assert user is None
        assert err == "not_configured"

    def test_different_ids_not_cached(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"user": {"id": 1, "login": "a"}}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("redmine_cache.urlopen", return_value=mock_response):
            rc.fetch_redmine_user_by_id(1, "https://rm.test", "key")
            rc.fetch_redmine_user_by_id(2, "https://rm.test", "key")

        assert len(rc._redmine_user_cache) == 2


class TestSearchRedmineUsers:
    """search_redmine_users: GET /users.json?name=... с кэшированием."""

    def setup_method(self):
        rc._redmine_search_cache.clear()

    def test_returns_cached_on_same_query(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "users": [
                    {"id": 1, "login": "alice", "firstname": "Alice"},
                    {"id": 2, "login": "bob", "firstname": "Bob"},
                ]
            }
        ).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("redmine_cache.urlopen", return_value=mock_response):
            result = rc.search_redmine_users("ali", "https://rm.test", "key")
        assert len(result) == 2

        # Кэш — urlopen не вызывается
        with patch("redmine_cache.urlopen") as mock_urlopen:
            result2 = rc.search_redmine_users("ali", "https://rm.test", "key")
        mock_urlopen.assert_not_called()
        assert len(result2) == 2

    def test_different_queries_not_cached(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"users": []}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("redmine_cache.urlopen", return_value=mock_response):
            rc.search_redmine_users("ali", "https://rm.test", "key")
            rc.search_redmine_users("bob", "https://rm.test", "key")

        assert len(rc._redmine_search_cache) == 2

    def test_empty_config_returns_empty(self):
        assert rc.search_redmine_users("q", "", "") == []

    def test_http_error_returns_empty(self):
        err_mock = HTTPError("https://rm.test", 500, "Error", {}, None)
        with patch("redmine_cache.urlopen", side_effect=err_mock):
            assert rc.search_redmine_users("q", "https://rm.test", "key") == []


class TestCheckRedmineAccess:
    """check_redmine_access: GET /users/current.json с кэшированием."""

    def setup_method(self):
        rc._redmine_user_cache.clear()

    def test_success_cached(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("redmine_cache.urlopen", return_value=mock_response):
            ok, err = rc.check_redmine_access("https://rm.test", "key")
        assert ok is True
        assert err is None

        # Кэш — urlopen не вызывается
        with patch("redmine_cache.urlopen") as mock_urlopen:
            ok2, err2 = rc.check_redmine_access("https://rm.test", "key")
        mock_urlopen.assert_not_called()
        assert ok2 is True

    def test_missing_config(self):
        ok, err = rc.check_redmine_access("", "")
        assert ok is False
        assert "укажите URL" in err

    def test_non_ascii_key_rejected(self):
        ok, err = rc.check_redmine_access("https://rm.test", "ключ_123")
        assert ok is False
        assert "недопустимые символы" in err

    def test_http_error_returns_false(self):
        err_mock = HTTPError("https://rm.test", 401, "Unauthorized", {}, None)
        with patch("redmine_cache.urlopen", side_effect=err_mock):
            ok, err = rc.check_redmine_access("https://rm.test", "key")
        assert ok is False
        assert "HTTP 401" in err


class TestCacheUtils:
    """clear_redmine_caches, get_redmine_cache_stats."""

    def setup_method(self):
        rc._redmine_user_cache.clear()
        rc._redmine_search_cache.clear()

    def test_clear_clears_all(self):
        rc._redmine_user_cache["test"] = "val"
        rc._redmine_search_cache["test"] = "val"
        rc.clear_redmine_caches()
        assert len(rc._redmine_user_cache) == 0
        assert len(rc._redmine_search_cache) == 0

    def test_stats_returns_dict(self):
        rc._redmine_user_cache["a"] = 1
        rc._redmine_user_cache["b"] = 2
        rc._redmine_search_cache["c"] = 3
        rc._redmine_search_cache["d"] = 4
        stats = rc.get_redmine_cache_stats()
        assert stats["user_cache_size"] == 2
        assert stats["search_cache_size"] == 2
        assert stats["user_cache_maxsize"] == 500
        assert stats["search_cache_maxsize"] == 100
