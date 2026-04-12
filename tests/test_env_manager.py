"""Тесты для src/admin/env_manager.py — file-locking при записи .env."""

from __future__ import annotations

import pytest

from admin.env_manager import update_env_file_with_lock


class TestUpdateEnvFileWithLock:
    """update_env_file_with_lock: безопасная запись в .env."""

    def test_updates_existing(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("POSTGRES_PASSWORD=old\nAPP_MASTER_KEY=key123\n")
        update_env_file_with_lock({"POSTGRES_PASSWORD": "new"}, env_path=env)
        content = env.read_text()
        assert "POSTGRES_PASSWORD=new" in content
        assert "APP_MASTER_KEY=key123" in content

    def test_adds_new_key(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("POSTGRES_PASSWORD=secret\n")
        update_env_file_with_lock({"NEW_KEY": "value"}, env_path=env)
        content = env.read_text()
        assert "POSTGRES_PASSWORD=secret" in content
        assert "NEW_KEY=value" in content

    def test_preserves_comments(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# Comment line\nPOSTGRES_PASSWORD=old\n")
        update_env_file_with_lock({"POSTGRES_PASSWORD": "new"}, env_path=env)
        content = env.read_text()
        assert "# Comment line" in content
        assert "POSTGRES_PASSWORD=new" in content

    def test_missing_file_raises_error(self, tmp_path):
        env = tmp_path / ".env"
        with pytest.raises(RuntimeError, match="not found"):
            update_env_file_with_lock({"KEY": "value"}, env_path=env)

    def test_multiple_updates(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("A=1\nB=2\nC=3\n")
        update_env_file_with_lock({"A": "10", "C": "30", "D": "40"}, env_path=env)
        content = env.read_text()
        assert "A=10" in content
        assert "B=2" in content
        assert "C=30" in content
        assert "D=40" in content
