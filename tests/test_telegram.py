"""Integration tests for Telegram and Instagram with mocked HTTP."""

import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.common.telegram import get_telegram_config, send_message


class TestTelegramConfig:

    def test_disabled(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "false")
        assert get_telegram_config() is None

    def test_not_set(self):
        assert get_telegram_config() is None

    def test_enabled_with_values(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        result = get_telegram_config()
        assert result == ("test-token", "12345")

    def test_enabled_missing_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        assert get_telegram_config() is None

    def test_enabled_missing_chat_id(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        assert get_telegram_config() is None


class TestSendMessage:

    @pytest.mark.asyncio
    async def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.common.telegram.httpx.AsyncClient", return_value=mock_client):
            result = await send_message("token", "123", "hello")

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_resp.json.return_value = {"ok": False}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.common.telegram.httpx.AsyncClient", return_value=mock_client):
            result = await send_message("token", "123", "hello")

        assert result is False


class TestInstagramConfig:

    def test_disabled(self, monkeypatch):
        from src.common.instagram import get_ig_config
        monkeypatch.setenv("IG_ENABLED", "false")
        assert get_ig_config() is None

    def test_not_set(self):
        from src.common.instagram import get_ig_config
        assert get_ig_config() is None

    def test_enabled(self, monkeypatch, tmp_path):
        from src.common.instagram import get_ig_config
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")
        monkeypatch.setenv("IG_ENABLED", "true")
        monkeypatch.setenv("IG_USERNAME", "testuser")
        monkeypatch.setenv("IG_PASSWORD", "testpass")
        monkeypatch.setenv("IG_SESSION_PATH", str(session_file))
        config = get_ig_config()
        assert config is not None
        assert config["username"] == "testuser"


class TestInstagramClient:

    def test_session_only_login_success(self, monkeypatch, tmp_path):
        from src.common.instagram import _get_client

        session_file = tmp_path / "session.json"
        session_file.write_text("{}")

        # Mock optional dependency import inside _get_client
        monkeypatch.setitem(sys.modules, "instagrapi", MagicMock())

        mock_client = MagicMock()
        mock_client.get_timeline_feed.return_value = {}

        with patch("src.common.instagram._new_client", return_value=mock_client):
            config = {
                "username": "",
                "password": "",
                "session_path": str(session_file),
            }
            result = _get_client(config)

        assert result is mock_client
        mock_client.load_settings.assert_called_once_with(str(session_file))
        mock_client.get_timeline_feed.assert_called_once()
        mock_client.dump_settings.assert_called_once_with(str(session_file))

    def test_session_invalid_without_credentials_returns_none(self, monkeypatch, tmp_path):
        from src.common.instagram import _get_client

        session_file = tmp_path / "session.json"
        session_file.write_text("{}")

        monkeypatch.setitem(sys.modules, "instagrapi", MagicMock())

        mock_client = MagicMock()
        mock_client.get_timeline_feed.side_effect = Exception("expired")
        mock_client.account_info.side_effect = Exception("expired")

        with patch("src.common.instagram._new_client", return_value=mock_client):
            config = {
                "username": "",
                "password": "",
                "session_path": str(session_file),
            }
            result = _get_client(config)

        assert result is None
