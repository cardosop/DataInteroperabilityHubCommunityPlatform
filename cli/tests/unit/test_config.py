"""
Unit tests for configuration management.
"""
import pytest
import yaml
from pathlib import Path
from datahub_cli.config import Config, CONFIG_DIR, CONFIG_FILE


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
    
    def test_config_get_set(self, mock_config):
        """Test getting and setting config values"""
        mock_config.set('test_key', 'test_value')
        assert mock_config.get('test_key') == 'test_value'
        assert mock_config.get('nonexistent', 'default') == 'default'
    
    def test_config_api_base_url(self, mock_config):
        """Test API base URL getter/setter"""
        mock_config.set_api_base_url('http://test.example.com/api/v1')
        assert mock_config.get_api_base_url() == 'http://test.example.com/api/v1'
        # Test default
        mock_config._config = {}
        assert mock_config.get_api_base_url() == 'http://localhost:8000/api/v1'
    
    def test_config_api_key(self, mock_config):
        """Test API key getter/setter"""
        mock_config.set_api_key('test-api-key')
        assert mock_config.get_api_key() == 'test-api-key'
        assert mock_config.get('api_key') == 'test-api-key'
    
    def test_config_default_tenant(self, mock_config):
        """Test default tenant getter/setter"""
        mock_config.set_default_tenant('tenant-123')
        assert mock_config.get_default_tenant() == 'tenant-123'
    
    def test_config_access_token(self, mock_config):
        """Test access token getter/setter"""
        mock_config.set_access_token('token-123')
        assert mock_config.get_access_token() == 'token-123'
    
    def test_config_refresh_token(self, mock_config):
        """Test refresh token getter/setter"""
        mock_config.set_refresh_token('refresh-123')
        assert mock_config.get_refresh_token() == 'refresh-123'
    
    def test_config_clear_auth(self, mock_config):
        """Test clearing authentication tokens"""
        mock_config.set_access_token('token-123')
        mock_config.set_refresh_token('refresh-123')
        mock_config.clear_auth()
        assert mock_config.get_access_token() is None
        assert mock_config.get_refresh_token() is None
        assert mock_config.get('access_token') is None
        assert mock_config.get('refresh_token') is None
    
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

