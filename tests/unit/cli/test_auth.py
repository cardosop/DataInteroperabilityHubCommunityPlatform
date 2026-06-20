"""
Unit tests for CLI authentication.

Tests API key and JWT token authentication logic.
Uses real AuthManager and Config (no mocks for internal logic).
"""

import sys
from pathlib import Path

import pytest

# Add CLI to path
cli_path = Path(__file__).parent.parent.parent.parent / "cli"
sys.path.insert(0, str(cli_path))

from datahub_cli.auth import AuthManager
from datahub_cli.config import Config


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"

    # Patch the config paths at module level
    monkeypatch.setattr("datahub_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("datahub_cli.config.CONFIG_FILE", config_file)

    return config_dir, config_file


class TestAuthManager:
    """Tests for AuthManager class"""

    def test_get_auth_headers_with_access_token(self, temp_config_dir):
        """Test getting auth headers with access token"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token("test-token")
        test_config.set_api_key(None)

        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_get_auth_headers_with_api_key(self, temp_config_dir):
        """Test getting auth headers with API key"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token(None)
        test_config.set_api_key("test-api-key")

        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == "ApiKey test-api-key"
        assert headers["Content-Type"] == "application/json"

    def test_get_auth_headers_access_token_priority(self, temp_config_dir):
        """Test that access token takes priority over API key"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token("test-token")
        test_config.set_api_key("test-api-key")

        headers = test_auth.get_auth_headers()
        # Access token should be used, not API key
        assert headers["Authorization"] == "Bearer test-token"
        assert "ApiKey" not in headers["Authorization"]

    def test_get_auth_headers_no_auth(self, temp_config_dir):
        """Test getting auth headers without authentication"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.clear_auth()
        headers = test_auth.get_auth_headers()
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"

    def test_get_auth_headers_api_key_only(self, temp_config_dir):
        """Test getting auth headers with API key only"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token(None)
        test_config.set_api_key("api-key-only")

        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == "ApiKey api-key-only"

    def test_ensure_authenticated_with_api_key(self, temp_config_dir):
        """Test ensure authenticated with API key"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token(None)
        test_config.set_api_key("test-api-key")

        assert test_auth.ensure_authenticated() is True

    def test_ensure_authenticated_with_token(self, temp_config_dir):
        """Test ensure authenticated with access token"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token("test-token")

        assert test_auth.ensure_authenticated() is True

    def test_ensure_authenticated_no_auth(self, temp_config_dir):
        """Test ensure authenticated without auth"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.clear_auth()
        assert test_auth.ensure_authenticated() is False

    def test_ensure_authenticated_api_key_preferred(self, temp_config_dir):
        """Test that API key is preferred for ensure_authenticated"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_api_key("test-api-key")
        test_config.set_access_token("test-token")

        # API key should make it authenticated immediately
        assert test_auth.ensure_authenticated() is True

    def test_auth_manager_with_custom_config(self, temp_config_dir):
        """Test AuthManager with custom config instance"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_api_key("custom-api-key")

        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == "ApiKey custom-api-key"

    def test_auth_manager_with_global_config(self, temp_config_dir):
        """Test AuthManager with global config"""
        from datahub_cli.config import config as global_config

        test_auth = AuthManager()  # Uses global config

        global_config.set_api_key("global-api-key")

        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == "ApiKey global-api-key"

    def test_get_auth_headers_empty_token(self, temp_config_dir):
        """Test getting auth headers with empty token"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token("")
        test_config.set_api_key(None)

        headers = test_auth.get_auth_headers()
        # Empty token should not be used
        assert "Authorization" not in headers or headers.get("Authorization") == ""

    def test_get_auth_headers_empty_api_key(self, temp_config_dir):
        """Test getting auth headers with empty API key"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token(None)
        test_config.set_api_key("")

        headers = test_auth.get_auth_headers()
        # Empty API key should not be used
        assert "Authorization" not in headers or headers.get("Authorization") == ""

    def test_get_auth_headers_special_characters_in_token(self, temp_config_dir):
        """Test getting auth headers with special characters in token"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token("token-with-special-chars-!@#$%")

        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == "Bearer token-with-special-chars-!@#$%"

    def test_get_auth_headers_unicode_in_token(self, temp_config_dir):
        """Test getting auth headers with unicode in token"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        # Tokens typically don't have unicode, but test handling
        test_config.set_access_token("token-测试")

        headers = test_auth.get_auth_headers()
        assert "Bearer" in headers["Authorization"]

    def test_get_auth_headers_very_long_token(self, temp_config_dir):
        """Test getting auth headers with very long token"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        long_token = "a" * 1000
        test_config.set_access_token(long_token)

        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == f"Bearer {long_token}"

    def test_clear_auth_after_setting(self, temp_config_dir):
        """Test clearing auth after setting tokens"""
        test_config = Config()
        AuthManager(config_instance=test_config)

        test_config.set_access_token("token-123")
        test_config.set_refresh_token("refresh-123")
        test_config.set_api_key("api-key-123")

        test_config.clear_auth()

        # Access and refresh tokens should be cleared
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None
        # API key should remain (clear_auth only clears tokens)
        assert test_config.get_api_key() == "api-key-123"

    def test_get_auth_headers_after_clear(self, temp_config_dir):
        """Test getting auth headers after clearing auth"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token("token-123")
        test_config.clear_auth()

        headers = test_auth.get_auth_headers()
        assert "Authorization" not in headers

    def test_ensure_authenticated_after_clear(self, temp_config_dir):
        """Test ensure authenticated after clearing auth"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        test_config.set_access_token("token-123")
        test_config.clear_auth()

        assert test_auth.ensure_authenticated() is False

    def test_auth_manager_config_isolation(self, temp_config_dir):
        """Test that different AuthManager instances use their configs independently"""
        config1 = Config()
        config2 = Config()

        auth1 = AuthManager(config_instance=config1)
        auth2 = AuthManager(config_instance=config2)

        config1.set_api_key("key1")
        config2.set_api_key("key2")

        headers1 = auth1.get_auth_headers()
        headers2 = auth2.get_auth_headers()

        assert headers1["Authorization"] == "ApiKey key1"
        assert headers2["Authorization"] == "ApiKey key2"

    def test_get_auth_headers_content_type(self, temp_config_dir):
        """Test that Content-Type header is always present"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        headers = test_auth.get_auth_headers()
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    def test_get_auth_headers_accept(self, temp_config_dir):
        """Test that Accept header is always present"""
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)

        headers = test_auth.get_auth_headers()
        assert "Accept" in headers
        assert headers["Accept"] == "application/json"
