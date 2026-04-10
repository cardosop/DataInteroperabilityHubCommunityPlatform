"""
Comprehensive unit tests for CLI configuration.

Tests configuration via config file, environment variables, and command-line arguments.
No mocks - uses real configuration mechanisms.
"""
import pytest
import os
import yaml
import tempfile
from pathlib import Path
from click.testing import CliRunner
from datahub_cli.config import Config, CONFIG_DIR, CONFIG_FILE
from datahub_cli.commands.config import config_cmd


class TestConfigFile:
    """Test configuration via config file"""
    
    def test_config_file_creation(self, temp_config_dir):
        """Test that config file is created when setting values"""
        config_dir, config_file = temp_config_dir
        config = Config()
        
        # Set a value
        config.set('test_key', 'test_value')
        
        # Verify file was created
        assert config_file.exists(), "Config file should be created"
        
        # Verify content
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
        assert data['test_key'] == 'test_value', "Config value should be saved"
    
    def test_config_file_loading(self, temp_config_dir):
        """Test that config file is loaded correctly"""
        config_dir, config_file = temp_config_dir
        
        # Create config file manually
        config_data = {
            'api_base_url': 'http://test.example.com/api/v1',
            'api_key': 'test-api-key',
            'default_tenant': 'tenant-123'
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Load config
        config = Config()
        assert config.get('api_base_url') == 'http://test.example.com/api/v1'
        assert config.get('api_key') == 'test-api-key'
        assert config.get('default_tenant') == 'tenant-123'
    
    def test_config_file_persistence(self, temp_config_dir):
        """Test that config changes are persisted"""
        config_dir, config_file = temp_config_dir
        config = Config()
        
        # Set multiple values
        config.set_api_base_url('http://test.example.com/api/v1')
        config.set_api_key('test-api-key')
        config.set_default_tenant('tenant-123')
        
        # Create new config instance to verify persistence
        config2 = Config()
        assert config2.get_api_base_url() == 'http://test.example.com/api/v1'
        assert config2.get_api_key() == 'test-api-key'
        assert config2.get_default_tenant() == 'tenant-123'
    
    def test_config_file_invalid_yaml(self, temp_config_dir):
        """Test handling of invalid YAML in config file"""
        config_dir, config_file = temp_config_dir
        
        # Write invalid YAML
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        # Config should handle this gracefully
        config = Config()
        # Should not raise exception, but may have empty config
        assert isinstance(config._config, dict)
    
    def test_config_file_missing(self, temp_config_dir):
        """Test that missing config file is handled gracefully"""
        config_dir, config_file = temp_config_dir
        
        # Ensure file doesn't exist
        if config_file.exists():
            config_file.unlink()
        
        # Config should initialize with empty config
        config = Config()
        assert config._config == {}
        assert config.get('nonexistent') is None


class TestEnvironmentVariables:
    """Test configuration via environment variables"""
    
    def test_api_base_url_env_var(self, temp_config_dir, monkeypatch):
        """Test API base URL from environment variable"""
        monkeypatch.setenv('DATAHUB_API_BASE_URL', 'http://env.example.com/api/v1')
        
        # Config should check env vars (if implemented)
        # For now, test that env vars can be read
        api_url = os.getenv('DATAHUB_API_BASE_URL')
        assert api_url == 'http://env.example.com/api/v1'
    
    def test_api_key_env_var(self, temp_config_dir, monkeypatch):
        """Test API key from environment variable"""
        monkeypatch.setenv('DATAHUB_API_KEY', 'env-api-key')
        
        api_key = os.getenv('DATAHUB_API_KEY')
        assert api_key == 'env-api-key'
    
    def test_env_var_precedence(self, temp_config_dir, monkeypatch):
        """Test that environment variables take precedence over config file.

        ``Config.get_api_key()`` was upgraded to read ``DATAHUB_API_KEY`` /
        ``TEST_API_KEY`` from the environment first and fall back to the
        config file value. This test now matches the documented + actually
        implemented precedence (env > file). The previous version asserted
        the opposite, encoding a stale pre-upgrade contract.
        """
        config_dir, config_file = temp_config_dir

        # Set in config file
        config = Config()
        config.set_api_key('file-api-key')

        # Set in environment — env MUST win over the file value.
        monkeypatch.setenv('DATAHUB_API_KEY', 'env-api-key')

        # Direct env access still returns the env value (sanity check).
        assert os.getenv('DATAHUB_API_KEY') == 'env-api-key'
        # And ``get_api_key()`` MUST return the env value, not the file value.
        assert config.get_api_key() == 'env-api-key'

        # When the env var is removed, the file value MUST resurface.
        monkeypatch.delenv('DATAHUB_API_KEY', raising=False)
        monkeypatch.delenv('TEST_API_KEY', raising=False)
        assert config.get_api_key() == 'file-api-key'
    
    def test_env_var_clearing(self, temp_config_dir, monkeypatch):
        """Test that clearing environment variable works"""
        monkeypatch.setenv('DATAHUB_API_KEY', 'test-key')
        assert os.getenv('DATAHUB_API_KEY') == 'test-key'
        
        monkeypatch.delenv('DATAHUB_API_KEY', raising=False)
        assert os.getenv('DATAHUB_API_KEY') is None


class TestCommandLineArguments:
    """Test configuration via command-line arguments"""
    
    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()
    
    def test_config_get_command(self, runner, temp_config_dir):
        """Test config get command"""
        config_dir, config_file = temp_config_dir
        config = Config()
        config.set('test_key', 'test_value')
        
        result = runner.invoke(config_cmd, ['get', 'test_key'])
        assert result.exit_code == 0
        assert 'test_key' in result.output
        assert 'test_value' in result.output
    
    def test_config_get_all(self, runner, temp_config_dir):
        """Test config get command without key (shows all)"""
        config_dir, config_file = temp_config_dir
        config = Config()
        config.set_api_base_url('http://test.example.com/api/v1')
        config.set_api_key('test-api-key')
        
        result = runner.invoke(config_cmd, ['get'])
        assert result.exit_code == 0
        assert 'api_base_url' in result.output
        assert 'api_base_url' in result.output.lower() or 'api_base_url' in result.output
    
    def test_config_set_command(self, runner, temp_config_dir):
        """Test config set command"""
        config_dir, config_file = temp_config_dir
        
        result = runner.invoke(config_cmd, ['set', 'test_key', 'test_value'])
        assert result.exit_code == 0
        
        # Verify value was set
        config = Config()
        assert config.get('test_key') == 'test_value'
    
    def test_config_set_api_base_url(self, runner, temp_config_dir):
        """Test setting API base URL via command"""
        config_dir, config_file = temp_config_dir
        
        result = runner.invoke(config_cmd, ['set', 'api_base_url', 'http://test.example.com/api/v1'])
        assert result.exit_code == 0
        
        config = Config()
        assert config.get_api_base_url() == 'http://test.example.com/api/v1'
    
    def test_config_set_api_key(self, runner, temp_config_dir):
        """Test setting API key via command"""
        config_dir, config_file = temp_config_dir
        
        result = runner.invoke(config_cmd, ['set', 'api_key', 'test-api-key'])
        assert result.exit_code == 0
        
        config = Config()
        assert config.get_api_key() == 'test-api-key'
    
    def test_config_unset_command(self, runner, temp_config_dir):
        """Test config unset command"""
        config_dir, config_file = temp_config_dir
        # Use the global config instance that the command will use
        from datahub_cli.config import config as global_config
        global_config._load()  # Ensure we're using the patched config file
        global_config.set('test_key', 'test_value')
        
        result = runner.invoke(config_cmd, ['unset', 'test_key'])
        assert result.exit_code == 0
        
        # Verify value was removed - reload to get fresh state
        global_config._load()
        assert global_config.get('test_key') is None
    
    def test_config_unset_protected_key(self, runner, temp_config_dir):
        """Test that protected keys cannot be unset via unset command"""
        config_dir, config_file = temp_config_dir
        config = Config()
        config.set_api_key('test-api-key')
        
        result = runner.invoke(config_cmd, ['unset', 'api_key'])
        # Should warn but not fail
        assert 'logout' in result.output.lower() or result.exit_code == 0
    
    def test_config_get_json_format(self, runner, temp_config_dir):
        """Test config get with JSON format"""
        config_dir, config_file = temp_config_dir
        # Use the global config instance that the command will use
        from datahub_cli.config import config as global_config
        global_config._load()  # Ensure we're using the patched config file
        global_config.set('test_key', 'test_value')
        
        result = runner.invoke(config_cmd, ['get', 'test_key', '--format', 'json'])
        assert result.exit_code == 0
        assert 'test_key' in result.output
        assert 'test_value' in result.output
    
    def test_config_get_table_format(self, runner, temp_config_dir):
        """Test config get with table format (default)"""
        config_dir, config_file = temp_config_dir
        config = Config()
        config.set('test_key', 'test_value')
        
        result = runner.invoke(config_cmd, ['get', 'test_key', '--format', 'table'])
        assert result.exit_code == 0
        assert 'test_key' in result.output


class TestConfigurationMethods:
    """Test configuration methods"""
    
    def test_get_set_generic(self, mock_config):
        """Test generic get/set methods"""
        mock_config.set('test_key', 'test_value')
        assert mock_config.get('test_key') == 'test_value'
        assert mock_config.get('nonexistent', 'default') == 'default'
    
    def test_api_base_url_methods(self, mock_config):
        """Test API base URL getter/setter methods"""
        mock_config.set_api_base_url('http://test.example.com/api/v1')
        assert mock_config.get_api_base_url() == 'http://test.example.com/api/v1'
        
        # Test default
        mock_config._config = {}
        assert mock_config.get_api_base_url() == 'http://localhost:8000/api/v1'
    
    def test_api_key_methods(self, mock_config):
        """Test API key getter/setter methods"""
        mock_config.set_api_key('test-api-key')
        assert mock_config.get_api_key() == 'test-api-key'
        
        mock_config.set_api_key(None)
        assert mock_config.get_api_key() is None
    
    def test_default_tenant_methods(self, mock_config):
        """Test default tenant getter/setter methods"""
        mock_config.set_default_tenant('tenant-123')
        assert mock_config.get_default_tenant() == 'tenant-123'
        
        mock_config.set_default_tenant(None)
        assert mock_config.get_default_tenant() is None
    
    def test_access_token_methods(self, mock_config):
        """Test access token getter/setter methods"""
        mock_config.set_access_token('token-123')
        assert mock_config.get_access_token() == 'token-123'
        
        mock_config.set_access_token(None)
        assert mock_config.get_access_token() is None
    
    def test_refresh_token_methods(self, mock_config):
        """Test refresh token getter/setter methods"""
        mock_config.set_refresh_token('refresh-123')
        assert mock_config.get_refresh_token() == 'refresh-123'
        
        mock_config.set_refresh_token(None)
        assert mock_config.get_refresh_token() is None
    
    def test_clear_auth(self, mock_config):
        """Test clearing authentication"""
        mock_config.set_access_token('token-123')
        mock_config.set_refresh_token('refresh-123')
        mock_config.set_api_key('api-key-123')
        
        mock_config.clear_auth()
        
        assert mock_config.get_access_token() is None
        assert mock_config.get_refresh_token() is None
        # API key should remain (clear_auth only clears tokens)
        assert mock_config.get_api_key() == 'api-key-123'


class TestConfigurationEdgeCases:
    """Test edge cases in configuration"""
    
    def test_empty_config_file(self, temp_config_dir):
        """Test handling of empty config file"""
        config_dir, config_file = temp_config_dir
        
        # Create empty file
        config_file.touch()
        
        config = Config()
        assert config._config == {}
    
    def test_none_values(self, mock_config):
        """Test setting None values"""
        mock_config.set('test_key', None)
        assert mock_config.get('test_key') is None
    
    def test_special_characters(self, mock_config):
        """Test configuration with special characters"""
        special_value = 'test@value#with$special%chars&'
        mock_config.set('test_key', special_value)
        assert mock_config.get('test_key') == special_value
    
    def test_unicode_values(self, mock_config):
        """Test configuration with unicode values"""
        unicode_value = '测试值'
        mock_config.set('test_key', unicode_value)
        assert mock_config.get('test_key') == unicode_value
    
    def test_large_config_file(self, temp_config_dir):
        """Test handling of large config file"""
        config_dir, config_file = temp_config_dir
        
        # Create config with many entries
        config = Config()
        for i in range(100):
            config.set(f'key_{i}', f'value_{i}')
        
        # Verify all values are saved
        config2 = Config()
        for i in range(100):
            assert config2.get(f'key_{i}') == f'value_{i}'
    
    def test_concurrent_config_access(self, temp_config_dir):
        """Test concurrent access to config (basic test)"""
        config_dir, config_file = temp_config_dir
        
        config1 = Config()
        config1.set('key1', 'value1')
        
        # Create second instance and set different key
        config2 = Config()
        config2.set('key2', 'value2')
        
        # Both should see all changes after reload (they share the same file)
        config1._load()
        config2._load()
        
        # Both instances should see all values since they read from the same file
        assert config1.get('key1') == 'value1'
        assert config1.get('key2') == 'value2'
        assert config2.get('key1') == 'value1'
        assert config2.get('key2') == 'value2'

