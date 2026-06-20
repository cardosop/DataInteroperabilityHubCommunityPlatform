"""
Comprehensive unit tests for CLI authentication.

Tests API key authentication, JWT authentication, token refresh, and error handling.
Uses real Config and AuthManager - only mocks external HTTP calls when necessary.
"""

from unittest.mock import Mock, patch

import pytest
from datahub_cli.auth import AuthManager
from datahub_cli.config import Config

# ---------------------------------------------------------------------------
# Shared fixtures — every test needs a fresh Config + AuthManager pair
# ---------------------------------------------------------------------------


@pytest.fixture
def test_config(temp_config_dir):
    """Fresh Config instance with an isolated temp config directory."""
    return Config()


@pytest.fixture
def test_auth(test_config):
    """AuthManager wired to the test Config instance."""
    return AuthManager(config_instance=test_config)


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestAPIKeyAuthentication:
    """Test API key authentication"""

    def test_get_auth_headers_with_api_key(self, test_config, test_auth):
        """Test getting auth headers with API key"""

        test_config.set_api_key("test-api-key")
        test_config.set_access_token(None)

        headers = test_auth.get_auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "ApiKey test-api-key"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_get_auth_headers_with_both_auth_methods_uses_access_token(
        self, test_config, test_auth
    ):
        """Test that access token takes precedence over API key when both are set.

        ``get_auth_headers()`` checks access_token before api_key (line 93-96
        of auth.py), so a logged-in user's Bearer token is always used even
        when an ApiKey is also configured.  This is intentional: access tokens
        are user-specific and carry more granular permissions than API keys.
        """

        # Set both API key and access token
        test_config.set_api_key("test-api-key")
        test_config.set_access_token("test-token")

        headers = test_auth.get_auth_headers()
        # Access token takes precedence — must be Bearer, not ApiKey
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"

    def test_ensure_authenticated_with_api_key(self, test_config, test_auth):
        """Test ensure_authenticated with API key"""
        test_config.set_api_key("test-api-key")
        test_config.set_access_token(None)
        test_config.set_refresh_token(None)

        assert test_auth.ensure_authenticated() is True

    def test_ensure_authenticated_with_empty_api_key(self, test_config, test_auth):
        """Test ensure_authenticated with empty API key"""
        test_config.set_api_key("")
        test_config.set_access_token(None)

        assert test_auth.ensure_authenticated() is False

    def test_ensure_authenticated_with_whitespace_api_key(self, test_config, test_auth):
        """Test ensure_authenticated with whitespace-only API key"""
        test_config.set_api_key("   ")
        test_config.set_access_token(None)

        assert test_auth.ensure_authenticated() is False

    def test_api_key_persistence(self, test_config, test_auth):
        """Test that API key persists across AuthManager instances"""
        test_config.set_api_key("test-api-key")

        test_auth1 = AuthManager(config_instance=test_config)
        test_auth2 = AuthManager(config_instance=test_config)

        headers1 = test_auth1.get_auth_headers()
        headers2 = test_auth2.get_auth_headers()

        assert headers1["Authorization"] == headers2["Authorization"]

    def test_get_auth_headers_api_key_with_dots_sent_as_bearer(self, test_config, test_auth):
        """API keys containing '.' (JWTs stored in api_key field) are sent as Bearer tokens.

        auth.py:103-104 — when the api_key value contains a dot, it is
        treated as a JWT and sent with the ``Bearer`` prefix rather than
        the ``ApiKey`` prefix used for opaque API keys.  This supports
        CI/automation workflows that store a JWT in the API_KEY env var.
        """

        # A JWT-like token (three dot-separated segments)
        test_config.set_api_key("header.payload.signature")
        test_config.set_access_token(None)

        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == "Bearer header.payload.signature"
        assert headers["Content-Type"] == "application/json"

    def test_get_auth_headers_api_key_stripped_of_whitespace(self, test_config, test_auth):
        """Whitespace-only API keys are rejected in get_auth_headers().

        auth.py:100 — ``api_key.strip()`` must be truthy; whitespace-only
        strings are treated as if no API key is configured.
        """

        test_config.set_api_key("   ")
        test_config.set_access_token(None)

        headers = test_auth.get_auth_headers()
        assert "Authorization" not in headers


class TestJWTAuthentication:
    """Test JWT token authentication"""

    def test_get_auth_headers_with_access_token(self, test_config, test_auth):
        """Test getting auth headers with access token"""

        test_config.set_access_token("test-access-token")
        test_config.set_api_key(None)

        headers = test_auth.get_auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-access-token"
        assert headers["Content-Type"] == "application/json"

    def test_ensure_authenticated_with_access_token(self, test_config, test_auth):
        """Test ensure_authenticated with access token"""

        test_config.set_access_token("test-access-token")
        test_config.set_api_key(None)

        assert test_auth.ensure_authenticated() is True

    def test_ensure_authenticated_without_token(self, test_config, test_auth):
        """Test ensure_authenticated without any token"""

        test_config.clear_auth()
        test_config.set_api_key(None)

        assert test_auth.ensure_authenticated() is False

    @patch("datahub_cli.auth.requests.post")
    def test_login_success(self, mock_post, test_config, test_auth):
        """Test successful login"""

        # Mock successful login response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_response.content = b"{}"
        mock_post.return_value = mock_response

        result = test_auth.login("test@example.com", "password123")

        assert result is True
        assert test_config.get_access_token() == "access-token-123"
        assert test_config.get_refresh_token() == "refresh-token-123"

    @patch("datahub_cli.auth.requests.post")
    def test_login_failure_invalid_credentials(self, mock_post, test_config, test_auth):
        """Test login failure with invalid credentials"""

        # Mock failed login response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid email or password"}}
        mock_response.content = b'{"error": {"message": "Invalid email or password"}}'
        mock_post.return_value = mock_response

        result = test_auth.login("test@example.com", "wrong-password")

        assert result is False
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None

    @patch("datahub_cli.auth.requests.post")
    def test_login_failure_network_error(self, mock_post, test_config, test_auth):
        """Test login failure with network error"""

        # Mock network error
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = test_auth.login("test@example.com", "password123")

        assert result is False
        assert test_config.get_access_token() is None

    @patch("datahub_cli.auth.requests.post")
    def test_login_failure_timeout(self, mock_post, test_config, test_auth):
        """Test login failure with timeout"""

        # Mock timeout
        import requests

        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        result = test_auth.login("test@example.com", "password123")

        assert result is False

    @patch("datahub_cli.auth.requests.post")
    def test_login_empty_response(self, mock_post, test_config, test_auth):
        """Test login with empty response"""

        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.content = b""
        mock_response.json.side_effect = ValueError("No JSON object")
        mock_post.return_value = mock_response

        result = test_auth.login("test@example.com", "password123")

        assert result is False


class TestTokenRefresh:
    """Test token refresh functionality"""

    @patch("datahub_cli.auth.requests.post")
    def test_refresh_access_token_success(self, mock_post, test_config, test_auth):
        """Test successful token refresh"""

        test_config.set_refresh_token("refresh-token-123")

        # Mock successful refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new-access-token-456"}
        mock_post.return_value = mock_response

        result = test_auth.refresh_access_token()

        assert result is True
        assert test_config.get_access_token() == "new-access-token-456"
        # Refresh token should remain
        assert test_config.get_refresh_token() == "refresh-token-123"

    @patch("datahub_cli.auth.requests.post")
    def test_refresh_access_token_no_refresh_token(self, mock_post, test_config, test_auth):
        """Test refresh when no refresh token exists"""

        test_config.set_refresh_token(None)

        result = test_auth.refresh_access_token()

        assert result is False
        mock_post.assert_not_called()

    @patch("datahub_cli.auth.requests.post")
    def test_refresh_access_token_expired(self, mock_post, test_config, test_auth):
        """Test refresh with expired refresh token"""

        test_config.set_refresh_token("expired-refresh-token")
        test_config.set_access_token("old-access-token")

        # Mock expired token response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = test_auth.refresh_access_token()

        assert result is False
        # Auth should be cleared
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None

    @patch("datahub_cli.auth.requests.post")
    def test_refresh_access_token_network_error(self, mock_post, test_config, test_auth):
        """Test refresh with network error"""

        test_config.set_refresh_token("refresh-token-123")

        # Mock network error
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = test_auth.refresh_access_token()

        assert result is False
        # Token should remain (network error is transient)
        assert test_config.get_refresh_token() == "refresh-token-123"

    @patch("datahub_cli.auth.requests.post")
    def test_ensure_authenticated_refreshes_token(self, mock_post, test_config, test_auth):
        """Test that ensure_authenticated refreshes token when needed"""

        test_config.set_access_token(None)
        test_config.set_refresh_token("refresh-token-123")

        # Mock successful refresh
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new-access-token"}
        mock_post.return_value = mock_response

        result = test_auth.ensure_authenticated()

        assert result is True
        assert test_config.get_access_token() == "new-access-token"
        mock_post.assert_called_once()

    @patch("datahub_cli.auth.requests.post")
    def test_refresh_access_token_server_error(self, mock_post, test_config, test_auth):
        """Test refresh with 5xx server error — auth is cleared (current behaviour).

        auth.py:172-179 — any non-200 status (including 5xx) falls through
        to ``clear_auth()``.  Whether 5xx should clear auth is debatable
        (a transient backend error does not mean the token is invalid),
        but this test documents the implemented behaviour so any change
        is deliberate and reviewed.
        """

        test_config.set_refresh_token("refresh-token-123")
        test_config.set_access_token("old-access-token")

        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = test_auth.refresh_access_token()

        assert result is False
        # Current behaviour: 5xx clears auth (same as 401)
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None

    @patch("datahub_cli.auth.requests.post")
    def test_ensure_authenticated_with_expired_jwt(self, mock_post, test_config, test_auth):
        """Test that ensure_authenticated refreshes an expired JWT access token.

        auth.py:229-234 — when the access token is a JWT whose ``exp``
        claim is in the past, ``_is_token_expired()`` returns True and
        ``refresh_access_token()`` is called.  On success the new token
        is used; on failure the caller gets False.
        """
        import base64
        import json as _json
        import time as _time

        # Build an expired JWT (exp = 1 hour ago)
        expired_payload = _json.dumps(
            {
                "sub": "u-1",  # noqa: PHASE216-STATIC-ID — JWT payload example
                "exp": int(_time.time()) - 3600,
            }
        ).encode()
        expired_token = (
            "header."
            + base64.urlsafe_b64encode(expired_payload).rstrip(b"=").decode()
            + ".signature"
        )
        test_config.set_access_token(expired_token)
        test_config.set_refresh_token("refresh-token-123")

        # Mock successful refresh
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new-access-token"}
        mock_post.return_value = mock_response

        result = test_auth.ensure_authenticated()

        assert result is True
        assert test_config.get_access_token() == "new-access-token"
        mock_post.assert_called_once()

    @patch("datahub_cli.auth.requests.post")
    def test_refresh_access_token_clears_jwt_preserves_api_key(
        self, mock_post, test_config, test_auth
    ):
        """clear_auth() clears JWT tokens but preserves the API key.

        auth.py:150-157 — ``clear_auth()`` only removes ``access_token``
        and ``refresh_token``; ``api_key`` is explicitly NOT cleared.
        This means a 401 on token refresh will wipe the JWT session but
        leave a configured API key intact so subsequent CLI commands can
        still authenticate (via the API key).
        """

        # User has both API key and JWT tokens
        test_config.set_api_key("api-key-survivor")
        test_config.set_access_token("expired-jwt")
        test_config.set_refresh_token("refresh-token-123")

        # Refresh fails with 401
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = test_auth.refresh_access_token()

        assert result is False
        # JWT tokens cleared
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None
        # API key preserved
        assert test_config.get_api_key() == "api-key-survivor"

    def test_clear_auth_preserves_api_key_direct(self, test_config):
        """Direct clear_auth() call preserves API key — unit-level contract.

        This is the behavioural contract that ``refresh_access_token()``,
        ``logout()``, and any future caller of ``clear_auth()`` rely on:
        the API key is never cleared implicitly — only JWT tokens are.
        Callers that need to clear the API key must call
        ``set_api_key(None)`` explicitly.
        """
        test_config.set_api_key("persistent-key")
        test_config.set_access_token("some-token")
        test_config.set_refresh_token("some-refresh")

        test_config.clear_auth()

        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None
        assert test_config.get_api_key() == "persistent-key"


class TestLogout:
    """Test logout functionality"""

    @patch("datahub_cli.auth.requests.post")
    def test_logout_success(self, mock_post, test_config, test_auth):
        """Test successful logout"""

        test_config.set_access_token("access-token-123")
        test_config.set_refresh_token("refresh-token-123")

        # Mock successful logout response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = test_auth.logout()

        assert result is True
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None

    @patch("datahub_cli.auth.requests.post")
    def test_logout_no_refresh_token(self, mock_post, test_config, test_auth):
        """Test logout without refresh token"""

        test_config.set_access_token("access-token-123")
        test_config.set_refresh_token(None)

        result = test_auth.logout()

        assert result is True
        assert test_config.get_access_token() is None
        # Should still clear local tokens even if API call fails
        mock_post.assert_not_called()

    @patch("datahub_cli.auth.requests.post")
    def test_logout_api_failure(self, mock_post, test_config, test_auth):
        """Test logout when API call fails"""

        test_config.set_access_token("access-token-123")
        test_config.set_refresh_token("refresh-token-123")

        # Mock API failure
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = test_auth.logout()

        # Should still clear local tokens even if API call fails
        assert result is True
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None


class TestAuthenticationErrorHandling:
    """Test authentication error handling"""

    def test_get_auth_headers_no_auth(self, test_config, test_auth):
        """Test getting auth headers without authentication"""

        test_config.clear_auth()
        test_config.set_api_key(None)

        headers = test_auth.get_auth_headers()
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"

    @patch("datahub_cli.auth.requests.post")
    def test_login_malformed_response(self, mock_post, test_config, test_auth):
        """Test login with malformed response"""

        # Mock malformed response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.content = b"invalid json"
        mock_post.return_value = mock_response

        result = test_auth.login("test@example.com", "password123")

        # Should handle gracefully
        assert result is False

    @patch("datahub_cli.auth.requests.post")
    def test_login_missing_tokens_in_response(self, mock_post, test_config, test_auth):
        """Test login with missing tokens in response.

        When the server returns 200 but omits ``access_token`` or
        ``refresh_token``, login() must return False and NOT set either
        token — no KeyError, no partial state.  (auth.py:135-137 checks
        for missing keys before any dict access.)
        """

        # Mock response without tokens
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Success"}
        mock_response.content = b'{"message": "Success"}'
        mock_post.return_value = mock_response

        result = test_auth.login("test@example.com", "password123")

        # Must return False and NOT set any tokens
        assert result is False
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None

    def test_auth_manager_dynamic_config(self, test_config, test_auth):
        """Test that AuthManager reads config dynamically"""

        # Set API key
        test_config.set_api_key("initial-key")
        headers1 = test_auth.get_auth_headers()

        # Change API key
        test_config.set_api_key("updated-key")
        headers2 = test_auth.get_auth_headers()

        # Headers should reflect the change
        assert headers1["Authorization"] == "ApiKey initial-key"
        assert headers2["Authorization"] == "ApiKey updated-key"


class TestAuthenticationIntegration:
    """Integration tests for authentication flow"""

    @patch("datahub_cli.auth.requests.post")
    def test_full_auth_flow(self, mock_post, test_config, test_auth):
        """Test complete authentication flow: login -> use token -> refresh -> logout"""

        # Step 1: Login
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access-token-1",
            "refresh_token": "refresh-token-1",
        }
        mock_response.content = b"{}"
        mock_post.return_value = mock_response

        login_result = test_auth.login("test@example.com", "password")
        assert login_result is True
        assert test_config.get_access_token() == "access-token-1"

        # Step 2: Use token (get headers)
        headers = test_auth.get_auth_headers()
        assert headers["Authorization"] == "Bearer access-token-1"

        # Step 3: Refresh token
        mock_response.json.return_value = {"access_token": "access-token-2"}
        refresh_result = test_auth.refresh_access_token()
        assert refresh_result is True
        assert test_config.get_access_token() == "access-token-2"

        # Step 4: Logout
        mock_response.status_code = 200
        logout_result = test_auth.logout()
        assert logout_result is True
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None

    def test_auth_with_config_changes(self, test_config, test_auth):
        """Test that auth works with config changes"""

        # Start with API key
        test_config.set_api_key("api-key-1")
        assert test_auth.ensure_authenticated() is True

        # Switch to JWT
        test_config.set_api_key(None)
        test_config.set_access_token("jwt-token-1")
        assert test_auth.ensure_authenticated() is True

        # Clear all
        test_config.clear_auth()
        assert test_auth.ensure_authenticated() is False
