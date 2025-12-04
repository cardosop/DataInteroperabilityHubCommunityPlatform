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

