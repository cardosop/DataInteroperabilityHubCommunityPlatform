"""
Unit tests for CLI configuration management.

Tests config file parsing, command-line overrides, and configuration persistence.
Uses real Config class (no mocks).
"""
import pytest
import yaml
from pathlib import Path
import sys

# Add CLI to path
cli_path = Path(__file__).parent.parent.parent.parent / "cli"
sys.path.insert(0, str(cli_path))

from datahub_cli.config import Config, CONFIG_DIR, CONFIG_FILE


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    
    # Patch the config paths at module level
    monkeypatch.setattr('datahub_cli.config.CONFIG_DIR', config_dir)
    monkeypatch.setattr('datahub_cli.config.CONFIG_FILE', config_file)
    
    return config_dir, config_file


class TestConfig:
    """Tests for Config class"""
    
    def test_config_initialization(self, temp_config_dir):
        """Test config initialization"""
        config_dir, config_file = temp_config_dir
        config = Config()
        assert config._config == {}
    
    def test_config_load_existing(self, temp_config_dir):
        """Test loading existing config file"""
        config_dir, config_file = temp_config_dir
        config_data = {'api_base_url': 'http://test.example.com/api/v1'}
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        config = Config()
        assert config.get('api_base_url') == 'http://test.example.com/api/v1'
    
    def test_config_load_nonexistent(self, temp_config_dir):
        """Test loading nonexistent config file"""
        config_dir, config_file = temp_config_dir
        # File doesn't exist
        config = Config()
        assert config._config == {}
    
    def test_config_get_set(self, temp_config_dir):
        """Test getting and setting config values"""
        config = Config()
        config.set('test_key', 'test_value')
        assert config.get('test_key') == 'test_value'
        assert config.get('nonexistent', 'default') == 'default'
    
    def test_config_get_default(self, temp_config_dir):
        """Test getting config with default value"""
        config = Config()
        assert config.get('nonexistent_key', 'default_value') == 'default_value'
        assert config.get('nonexistent_key') is None
    
    def test_config_api_base_url(self, temp_config_dir):
        """Test API base URL getter/setter"""
        config = Config()
        config.set_api_base_url('http://test.example.com/api/v1')
        assert config.get_api_base_url() == 'http://test.example.com/api/v1'
        # Test default
        config._config = {}
        assert config.get_api_base_url() == 'http://localhost:8000/api/v1'
    
    def test_config_api_key(self, temp_config_dir):
        """Test API key getter/setter"""
        config = Config()
        config.set_api_key('test-api-key')
        assert config.get_api_key() == 'test-api-key'
        assert config.get('api_key') == 'test-api-key'
    
    def test_config_api_key_none(self, temp_config_dir):
        """Test API key when not set"""
        config = Config()
        assert config.get_api_key() is None
    
    def test_config_default_tenant(self, temp_config_dir):
        """Test default tenant getter/setter"""
        config = Config()
        config.set_default_tenant('tenant-123')
        assert config.get_default_tenant() == 'tenant-123'
    
    def test_config_default_tenant_none(self, temp_config_dir):
        """Test default tenant when not set"""
        config = Config()
        assert config.get_default_tenant() is None
    
    def test_config_access_token(self, temp_config_dir):
        """Test access token getter/setter"""
        config = Config()
        config.set_access_token('token-123')
        assert config.get_access_token() == 'token-123'
    
    def test_config_access_token_none(self, temp_config_dir):
        """Test access token when not set"""
        config = Config()
        assert config.get_access_token() is None
    
    def test_config_refresh_token(self, temp_config_dir):
        """Test refresh token getter/setter"""
        config = Config()
        config.set_refresh_token('refresh-123')
        assert config.get_refresh_token() == 'refresh-123'
    
    def test_config_refresh_token_none(self, temp_config_dir):
        """Test refresh token when not set"""
        config = Config()
        assert config.get_refresh_token() is None
    
    def test_config_clear_auth(self, temp_config_dir):
        """Test clearing authentication tokens"""
        config = Config()
        config.set_access_token('token-123')
        config.set_refresh_token('refresh-123')
        config.clear_auth()
        assert config.get_access_token() is None
        assert config.get_refresh_token() is None
        assert config.get('access_token') is None
        assert config.get('refresh_token') is None
    
    def test_config_clear_auth_partial(self, temp_config_dir):
        """Test clearing auth when only one token exists"""
        config = Config()
        config.set_access_token('token-123')
        config.clear_auth()
        assert config.get_access_token() is None
        assert config.get_refresh_token() is None
    
    def test_config_save(self, temp_config_dir):
        """Test saving config to file"""
        config_dir, config_file = temp_config_dir
        config = Config()
        config.set('test_key', 'test_value')
        
        # Verify file was created and contains data
        assert config_file.exists()
        with open(config_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        assert saved_data['test_key'] == 'test_value'
    
    def test_config_save_multiple_values(self, temp_config_dir):
        """Test saving multiple config values"""
        config_dir, config_file = temp_config_dir
        config = Config()
        config.set('key1', 'value1')
        config.set('key2', 'value2')
        config.set('key3', 'value3')
        
        # Verify all values saved
        assert config_file.exists()
        with open(config_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        assert saved_data['key1'] == 'value1'
        assert saved_data['key2'] == 'value2'
        assert saved_data['key3'] == 'value3'
    
    def test_config_update_existing(self, temp_config_dir):
        """Test updating existing config value"""
        config_dir, config_file = temp_config_dir
        config = Config()
        config.set('test_key', 'value1')
        config.set('test_key', 'value2')
        
        assert config.get('test_key') == 'value2'
        with open(config_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        assert saved_data['test_key'] == 'value2'
    
    def test_config_load_invalid_yaml(self, temp_config_dir):
        """Test loading invalid YAML config file"""
        config_dir, config_file = temp_config_dir
        # Write invalid YAML
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        # Should handle gracefully
        config = Config()
        # Should have empty config or handle error
        assert isinstance(config._config, dict)
    
    def test_config_load_empty_file(self, temp_config_dir):
        """Test loading empty config file"""
        config_dir, config_file = temp_config_dir
        # Create empty file
        config_file.touch()
        
        config = Config()
        assert config._config == {}
    
    def test_config_save_creates_directory(self, temp_config_dir):
        """Test that saving config creates directory if it doesn't exist"""
        config_dir, config_file = temp_config_dir
        # Remove directory
        import shutil
        shutil.rmtree(config_dir)
        
        config = Config()
        config.set('test_key', 'test_value')
        
        # Directory should be created
        assert config_dir.exists()
        assert config_file.exists()
    
    def test_config_all_getters_setters(self, temp_config_dir):
        """Test all getter/setter methods"""
        config = Config()
        
        # Test all setters
        config.set_api_base_url('http://api.example.com/v1')
        config.set_api_key('api-key-123')
        config.set_default_tenant('tenant-456')
        config.set_access_token('access-token-789')
        config.set_refresh_token('refresh-token-012')
        
        # Test all getters
        assert config.get_api_base_url() == 'http://api.example.com/v1'
        assert config.get_api_key() == 'api-key-123'
        assert config.get_default_tenant() == 'tenant-456'
        assert config.get_access_token() == 'access-token-789'
        assert config.get_refresh_token() == 'refresh-token-012'
    
    def test_config_persistence(self, temp_config_dir):
        """Test that config persists across instances"""
        config_dir, config_file = temp_config_dir
        
        # Create first config instance and set value
        config1 = Config()
        config1.set('persistent_key', 'persistent_value')
        
        # Create second config instance
        config2 = Config()
        
        # Should have the value from first instance
        assert config2.get('persistent_key') == 'persistent_value'
    
    def test_config_nested_values(self, temp_config_dir):
        """Test config with nested values"""
        config = Config()
        nested_value = {
            'level1': {
                'level2': {
                    'level3': 'value'
                }
            }
        }
        config.set('nested', nested_value)
        
        assert config.get('nested') == nested_value
        assert config.get('nested')['level1']['level2']['level3'] == 'value'
    
    def test_config_special_characters(self, temp_config_dir):
        """Test config with special characters"""
        config = Config()
        config.set('special_key', 'value with spaces and !@#$%^&*()')
        assert config.get('special_key') == 'value with spaces and !@#$%^&*()'
    
    def test_config_unicode(self, temp_config_dir):
        """Test config with unicode characters"""
        config = Config()
        config.set('unicode_key', 'value with 测试 Unicode and émojis 🎉')
        assert config.get('unicode_key') == 'value with 测试 Unicode and émojis 🎉'
    
    def test_config_empty_string(self, temp_config_dir):
        """Test config with empty string value"""
        config = Config()
        config.set('empty_key', '')
        assert config.get('empty_key') == ''
    
    def test_config_none_value(self, temp_config_dir):
        """Test config with None value"""
        config = Config()
        config.set('none_key', None)
        assert config.get('none_key') is None
    
    def test_config_numeric_values(self, temp_config_dir):
        """Test config with numeric values"""
        config = Config()
        config.set('int_key', 123)
        config.set('float_key', 45.67)
        assert config.get('int_key') == 123
        assert config.get('float_key') == 45.67
    
    def test_config_boolean_values(self, temp_config_dir):
        """Test config with boolean values"""
        config = Config()
        config.set('bool_true', True)
        config.set('bool_false', False)
        assert config.get('bool_true') is True
        assert config.get('bool_false') is False
    
    def test_config_list_values(self, temp_config_dir):
        """Test config with list values"""
        config = Config()
        list_value = ['item1', 'item2', 'item3']
        config.set('list_key', list_value)
        assert config.get('list_key') == list_value
    
    def test_config_dict_values(self, temp_config_dir):
        """Test config with dict values"""
        config = Config()
        dict_value = {'key1': 'value1', 'key2': 'value2'}
        config.set('dict_key', dict_value)
        assert config.get('dict_key') == dict_value

