"""
Unit tests for API client logic that doesn't require HTTP requests.

These tests verify authentication checks, header generation, and error handling logic.
HTTP request tests are in integration tests with real services.
"""
import pytest
from click import ClickException


class TestAPIClientLogic:
    """Tests for APIClient logic (no HTTP calls)"""
    
    def test_ensure_authenticated_check(self, temp_config_dir):
        """Test that ensure_authenticated works correctly"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        # Create fresh instances with isolated config
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        # Clear auth
        test_config.clear_auth()
        
        # Verify ensure_authenticated returns False
        assert test_auth.ensure_authenticated() is False
        
        # Setting API key should make it return True
        test_config.set_api_key('test-api-key')
        assert test_auth.ensure_authenticated() is True
    
    def test_auth_headers_with_api_key(self, temp_config_dir):
        """Test that API key is used in auth headers"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_api_key('test-api-key')
        headers = test_auth.get_auth_headers()
        
        assert 'Authorization' in headers
        assert headers['Authorization'] == 'ApiKey test-api-key'
        assert headers['Content-Type'] == 'application/json'
    
    def test_auth_headers_with_token(self, temp_config_dir):
        """Test that access token is used in auth headers"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_access_token('test-token')
        headers = test_auth.get_auth_headers()
        
        assert 'Authorization' in headers
        assert headers['Authorization'] == 'Bearer test-token'
    
    def test_auth_headers_prefer_token_over_key(self, temp_config_dir):
        """Test that access token is preferred over API key"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.set_api_key('test-api-key')
        test_config.set_access_token('test-token')
        headers = test_auth.get_auth_headers()
        
        # Token should be used, not API key
        assert headers['Authorization'] == 'Bearer test-token'
    
    def test_auth_headers_no_auth(self, temp_config_dir):
        """Test headers when no authentication is set"""
        from datahub_cli.config import Config
        from datahub_cli.auth import AuthManager
        
        test_config = Config()
        test_auth = AuthManager(config_instance=test_config)
        
        test_config.clear_auth()
        headers = test_auth.get_auth_headers()
        
        assert 'Authorization' not in headers
        assert 'Content-Type' in headers
        assert 'Accept' in headers

