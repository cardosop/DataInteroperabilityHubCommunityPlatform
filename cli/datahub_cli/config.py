"""
Configuration management for DataHub CLI.

Handles reading and writing configuration from ~/.datahub/config.yaml
"""
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import click


CONFIG_DIR = Path.home() / ".datahub"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class Config:
    """Configuration manager for DataHub CLI"""
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _get_config_file(self):
        """Get config file path (allows patching in tests)"""
        # Import here to get patched value at runtime
        from datahub_cli.config import CONFIG_FILE
        return CONFIG_FILE
    
    def _get_config_dir(self):
        """Get config directory path (allows patching in tests)"""
        # Import here to get patched value at runtime
        from datahub_cli.config import CONFIG_DIR
        return CONFIG_DIR
    
    def _load(self):
        """Load configuration from file"""
        config_file = self._get_config_file()
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception as e:
                click.echo(f"Warning: Failed to load config file: {e}", err=True)
                self._config = {}
        else:
            self._config = {}
    
    def _save(self):
        """Save configuration to file"""
        config_dir = self._get_config_dir()
        config_file = self._get_config_file()
        config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_file, 'w') as f:
                yaml.dump(self._config, f, default_flow_style=False)
        except Exception as e:
            click.echo(f"Error: Failed to save config file: {e}", err=True)
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self._config[key] = value
        self._save()
    
    def get_api_base_url(self) -> str:
        """Get API base URL"""
        return self.get('api_base_url', 'http://localhost:8000/api/v1')
    
    def set_api_base_url(self, url: str):
        """Set API base URL"""
        self.set('api_base_url', url)
    
    def get_api_key(self) -> Optional[str]:
        """Get API key"""
        return self.get('api_key')
    
    def set_api_key(self, api_key: str):
        """Set API key"""
        self.set('api_key', api_key)
    
    def get_default_tenant(self) -> Optional[str]:
        """Get default tenant ID"""
        return self.get('default_tenant')
    
    def set_default_tenant(self, tenant_id: str):
        """Set default tenant ID"""
        self.set('default_tenant', tenant_id)
    
    def get_access_token(self) -> Optional[str]:
        """Get access token"""
        return self.get('access_token')
    
    def set_access_token(self, token: str):
        """Set access token"""
        self.set('access_token', token)
    
    def get_refresh_token(self) -> Optional[str]:
        """Get refresh token"""
        return self.get('refresh_token')
    
    def set_refresh_token(self, token: str):
        """Set refresh token"""
        self.set('refresh_token', token)
    
    def clear_auth(self):
        """Clear authentication tokens"""
        if 'access_token' in self._config:
            del self._config['access_token']
        if 'refresh_token' in self._config:
            del self._config['refresh_token']
        self._save()


# Global config instance
config = Config()

