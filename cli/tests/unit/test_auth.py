"""
Unit tests for authentication management.

These tests use real config (with temporary directories) and mock only external HTTP calls.
"""
import pytest
from unittest.mock import Mock, patch
from datahub_cli.auth import AuthManager


class TestAuthManager:
    """Tests for AuthManager class"""
    
    def test_get_auth_headers_with_access_token(self, temp_config_dir):
        """Test getting auth headers with access token"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_access_token('test-token')
        test_config.set_api_key(None)
        
        headers = test_auth.get_auth_headers()
        assert headers['Authorization'] == 'Bearer test-token'
        assert headers['Content-Type'] == 'application/json'
    
    def test_get_auth_headers_with_api_key(self, temp_config_dir):
        """Test getting auth headers with API key"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_access_token(None)
        test_config.set_api_key('test-api-key')
        
        headers = test_auth.get_auth_headers()
        assert headers['Authorization'] == 'ApiKey test-api-key'
    
    def test_get_auth_headers_no_auth(self, temp_config_dir):
        """Test getting auth headers without authentication"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.clear_auth()
        headers = test_auth.get_auth_headers()
        assert 'Authorization' not in headers
    
    @patch('datahub_cli.auth.requests.post')
    def test_login_success(self, mock_post, temp_config_dir):
        """Test successful login"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'access-123',
            'refresh_token': 'refresh-123',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response
        
        result = test_auth.login('test@example.com', 'password')
        assert result is True
        assert test_config.get_access_token() == 'access-123'
        assert test_config.get_refresh_token() == 'refresh-123'
    
    @patch('datahub_cli.auth.requests.post')
    def test_login_failure(self, mock_post, temp_config_dir):
        """Test failed login"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'error': {'message': 'Invalid credentials'}
        }
        mock_post.return_value = mock_response
        
        result = test_auth.login('test@example.com', 'wrong-password')
        assert result is False
    
    @patch('datahub_cli.auth.requests.post')
    def test_refresh_access_token_success(self, mock_post, temp_config_dir):
        """Test successful token refresh"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_refresh_token('refresh-123')
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new-access-123'
        }
        mock_post.return_value = mock_response
        
        result = test_auth.refresh_access_token()
        assert result is True
        assert test_config.get_access_token() == 'new-access-123'
    
    @patch('datahub_cli.auth.requests.post')
    def test_refresh_access_token_failure(self, mock_post, temp_config_dir):
        """Test failed token refresh"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_refresh_token('refresh-123')
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        result = test_auth.refresh_access_token()
        assert result is False
        assert test_config.get_access_token() is None
    
    @patch('datahub_cli.auth.requests.post')
    def test_logout(self, mock_post, temp_config_dir):
        """Test logout"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_access_token('token-123')
        test_config.set_refresh_token('refresh-123')
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = test_auth.logout()
        assert result is True
        assert test_config.get_access_token() is None
        assert test_config.get_refresh_token() is None
    
    def test_ensure_authenticated_with_api_key(self, temp_config_dir):
        """Test ensure authenticated with API key"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_access_token(None)
        test_config.set_api_key('test-api-key')
        
        assert test_auth.ensure_authenticated() is True
    
    def test_ensure_authenticated_with_token(self, temp_config_dir):
        """Test ensure authenticated with access token"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_access_token('test-token')
        
        assert test_auth.ensure_authenticated() is True
    
    def test_ensure_authenticated_no_auth(self, temp_config_dir):
        """Test ensure authenticated without auth"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.clear_auth()
        assert test_auth.ensure_authenticated() is False


class TestIsTokenExpired:
    """Tests for AuthManager._is_token_expired() static method.

    Covers all branches: non-JWT (opaque) tokens, JWT parsing, base64
    padding, invalid payloads, missing exp claim, and buffer-second math.
    """

    @staticmethod
    def _make_jwt(exp_offset_seconds):
        """Create a minimal JWT with an ``exp`` claim offset from now.

        Returns a ``header.payload.sig`` string with valid base64url
        encoding.  The signature segment is a placeholder — we never
        verify it.
        """
        import json
        import base64
        import time

        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode())
            .rstrip(b"=")
            .decode()
        )
        payload = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {"exp": int(time.time() + exp_offset_seconds), "sub": "test"}
                ).encode()
            )
            .rstrip(b"=")
            .decode()
        )
        return f"{header}.{payload}.fake_sig"

    # -- JWT expiry tests -------------------------------------------------

    def test_expired_token_returns_true(self):
        token = self._make_jwt(-3600)  # expired 1 hour ago
        assert AuthManager._is_token_expired(token) is True

    def test_future_token_returns_false(self):
        token = self._make_jwt(3600)  # expires in 1 hour
        assert AuthManager._is_token_expired(token) is False

    def test_within_buffer_seconds_returns_true(self):
        token = self._make_jwt(15)  # expires in 15 s, default buffer is 30 s
        assert AuthManager._is_token_expired(token, buffer_seconds=30) is True

    def test_custom_buffer_seconds(self):
        token = self._make_jwt(60)  # expires in 60 s
        assert AuthManager._is_token_expired(token, buffer_seconds=30) is False
        assert AuthManager._is_token_expired(token, buffer_seconds=120) is True

    # -- Non-JWT / opaque token tests ------------------------------------

    def test_opaque_token_no_dots_returns_false(self):
        assert AuthManager._is_token_expired("opaque-token-without-dots") is False

    # -- Malformed JWT tests ----------------------------------------------

    def test_malformed_jwt_too_many_dots_returns_false(self):
        assert AuthManager._is_token_expired("a.b.c.d") is False

    def test_invalid_base64_returns_false(self):
        assert AuthManager._is_token_expired("header.!!!invalid_base64!!!.sig") is False

    def test_payload_not_json_returns_false(self):
        import base64

        bad_payload = base64.urlsafe_b64encode(b"not-json").rstrip(b"=").decode()
        assert (
            AuthManager._is_token_expired(f"header.{bad_payload}.sig") is False
        )

    def test_missing_exp_claim_returns_false(self):
        import json
        import base64

        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode())
            .rstrip(b"=")
            .decode()
        )
        payload = (
            base64.urlsafe_b64encode(json.dumps({"sub": "test"}).encode())
            .rstrip(b"=")
            .decode()
        )
        token = f"{header}.{payload}.sig"
        assert AuthManager._is_token_expired(token) is False

    # -- Edge cases -------------------------------------------------------

    def test_base64_padding_edge_case(self):
        """JWT whose payload base64 length is not a multiple of 4."""
        import json
        import base64
        import time

        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode())
            .rstrip(b"=")
            .decode()
        )
        payload = (
            base64.urlsafe_b64encode(
                json.dumps({"exp": int(time.time() - 3600), "x": "y"}).encode()
            )
            .rstrip(b"=")
            .decode()
        )
        token = f"{header}.{payload}.sig"
        assert AuthManager._is_token_expired(token) is True

