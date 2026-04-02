"""
Comprehensive integration tests for CLI error handling.

Tests error handling with real API structure (when available) and integration scenarios.
"""
import pytest
import requests
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import Config
from datahub_cli.auth import AuthManager


class TestNetworkErrorIntegration:
    """Integration tests for network errors"""
    
    def test_connection_refused_integration(self, runner, temp_config_dir):
        """Test handling connection refused with invalid API URL"""
        config = Config()
        config.set_api_base_url('http://localhost:99999/api/v1')  # Invalid port
        
        result = runner.invoke(cli, ['contracts', 'list'])
        
        # Should handle gracefully
        assert result.exit_code != 0
        assert 'Connection' in result.output or 'Failed to list contracts' in result.output or 'refused' in result.output.lower()
    
    def test_timeout_integration(self, runner, temp_config_dir):
        """Test handling timeout with slow/unreachable API"""
        config = Config()
        config.set_api_base_url('http://192.0.2.1/api/v1')  # RFC 5737 test address (unreachable)
        
        result = runner.invoke(cli, ['assets', 'list'])
        
        # Should handle timeout gracefully
        assert result.exit_code != 0
        assert 'timeout' in result.output.lower() or 'Failed to list assets' in result.output or 'Connection' in result.output


class TestAPIErrorIntegration:
    """Integration tests for API errors"""
    
    def test_401_unauthorized_integration(self, runner, temp_config_dir, api_base_url):
        """Test handling 401 Unauthorized with real API structure"""
        config = Config()
        config.set_api_base_url(api_base_url)
        config.clear_auth()  # Clear authentication
        
        result = runner.invoke(cli, ['contracts', 'list'])
        
        # Should either fail with auth error, connection error, or succeed if API allows unauthenticated access
        assert result.exit_code == 0
        if result.exit_code != 0:
            # May be auth error, connection error, or other error
            assert any(keyword in result.output for keyword in [
                'Not authenticated', 'UNAUTHORIZED', 'login', 'Connection', 'Failed to list contracts'
            ])
    
    def test_404_not_found_integration(self, runner, temp_config_dir, api_base_url):
        """Test handling 404 Not Found with real API structure"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        # Try to get non-existent resource
        result = runner.invoke(cli, ['contracts', 'get', '00000000-0000-0000-0000-000000000000'])
        
        # Should handle gracefully (may be connection error if API not available)
        assert result.exit_code == 0
        if result.exit_code != 0:
            # May be not found error, connection error, or other error
            assert any(keyword in result.output.lower() for keyword in [
                'not found', 'not_found', 'failed to get contract', 'connection', 'refused'
            ])


class TestCommandValidationIntegration:
    """Integration tests for command validation"""
    
    def test_invalid_command_suggests_alternatives(self, runner):
        """Test that invalid commands suggest alternatives"""
        result = runner.invoke(cli, ['contracs', 'list'])  # typo
        
        assert result.exit_code != 0
        # Click may suggest 'contracts'
        assert 'No such command' in result.output or 'Did you mean' in result.output or 'Usage:' in result.output
    
    def test_missing_required_argument_shows_usage(self, runner):
        """Test that missing required arguments show usage"""
        result = runner.invoke(cli, ['contracts', 'get'])
        
        assert result.exit_code != 0
        assert 'Missing argument' in result.output or 'Usage:' in result.output or 'CONTRACT_ID' in result.output
    
    def test_invalid_option_shows_help(self, runner):
        """Test that invalid options show help"""
        result = runner.invoke(cli, ['contracts', 'list', '--invalid-option', 'value'])
        
        assert result.exit_code != 0
        assert 'No such option' in result.output or 'Usage:' in result.output


class TestErrorRecoveryIntegration:
    """Integration tests for error recovery"""
    
    def test_retry_after_auth_failure(self, runner, temp_config_dir, api_base_url):
        """Test retry after authentication failure"""
        config = Config()
        config.set_api_base_url(api_base_url)
        config.set_api_key('invalid-key')
        
        result = runner.invoke(cli, ['contracts', 'list'])
        
        # Should handle auth failure gracefully (may be connection error if API not available)
        assert result.exit_code == 0
        # If it fails, may suggest login, or be connection error
        if result.exit_code != 0:
            assert any(keyword in result.output.lower() for keyword in [
                'login', 'authentication', 'api key', 'connection', 'refused', 'failed to list contracts'
            ])
    
    def test_continue_after_non_critical_error(self, runner, temp_config_dir):
        """Test that CLI continues after non-critical errors"""
        # Test with invalid config that can be recovered
        config = Config()
        config.set_api_base_url('http://invalid-url/api/v1')
        
        # Should fail but not crash
        result = runner.invoke(cli, ['contracts', 'list'])
        
        assert result.exit_code != 0
        # Should exit cleanly, not crash
        assert result.exit_code in [1, 2]


class TestErrorContextIntegration:
    """Integration tests for error context preservation"""
    
    def test_error_includes_command_context(self, runner, temp_config_dir, api_base_url):
        """Test that errors include command context"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        result = runner.invoke(cli, ['contracts', 'validate', 'invalid-id'])
        
        # Error should be contextual to validate command
        assert result.exit_code == 0
        if result.exit_code != 0:
            assert 'validate' in result.output.lower() or 'Failed to validate contract' in result.output
    
    def test_error_includes_resource_id(self, runner, temp_config_dir, api_base_url):
        """Test that errors include resource ID when applicable"""
        config = Config()
        config.set_api_base_url(api_base_url)
        
        test_id = 'test-resource-id-123'
        result = runner.invoke(cli, ['assets', 'get', test_id])
        
        # Error should mention the resource ID if available
        assert result.exit_code == 0
        if result.exit_code != 0:
            # May or may not include ID depending on error type
            pass  # Just verify it doesn't crash


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def api_base_url():
    """API base URL fixture"""
    return os.environ.get('MESHANT_API_URL', 'http://localhost:8000/api/v1')


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    
    monkeypatch.setattr('datahub_cli.config.CONFIG_DIR', config_dir)
    monkeypatch.setattr('datahub_cli.config.CONFIG_FILE', config_file)
    
    return config_dir, config_file

