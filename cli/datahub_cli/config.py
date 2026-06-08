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
                    loaded = yaml.safe_load(f)
                    # Ensure loaded data is a dict (handle corrupted/invalid YAML)
                    if isinstance(loaded, dict):
                        self._config = loaded
                    else:
                        # Invalid YAML or non-dict data - reset to empty dict
                        self._config = {}
                        click.echo(f"Warning: Config file contains invalid data, resetting to defaults", err=True)
            except Exception as e:
                click.echo(f"Warning: Failed to load config file: {e}", err=True)
                self._config = {}
        else:
            self._config = {}

    def _save(self):
        """Save configuration to file.

        Writes the in-memory config dict to disk as YAML.  A ``flush()``
        pushes the data from Python's stdio buffers to the OS; we
        intentionally do **not** call ``os.fsync()`` here — it is a full
        OS-buffer-to-storage barrier and would make every ``set()`` call
        stall for 200+ ms on rotational media.  The CLI config file does
        not need power-loss durability.
        """
        config_dir = self._get_config_dir()
        config_file = self._get_config_file()
        config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_file, 'w') as f:
                yaml.dump(self._config, f, default_flow_style=False)
                f.flush()
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
        """Get API base URL.

        Checks the ``DATAHUB_BASE_URL`` and ``MESHANT_API_URL`` environment
        variables before falling back to the config-file value, matching the
        convention used by :meth:`get_api_key`.
        """
        import os
        env_url = (
            os.environ.get("DATAHUB_BASE_URL")
            or os.environ.get("MESHANT_API_URL")
            or os.environ.get("API_BASE_URL")
        )
        if env_url:
            return env_url.rstrip("/")
        return self.get("api_base_url", "http://localhost:8000/api/v1")

    def set_api_base_url(self, url: str):
        """Set API base URL"""
        self.set('api_base_url', url)

    def get_api_key(self) -> Optional[str]:
        """Get API key from config file or environment variable"""
        # Check environment variable first (for testing/integration)
        import os
        env_key = (
            os.environ.get("DATAHUB_API_KEY")
            or os.environ.get("TEST_API_KEY")
            or os.environ.get("DATAHUB_API_TOKEN")
            or os.environ.get("E2E_TEST_USER_TOKEN")
        )
        if env_key:
            return env_key
        # Fall back to config file
        return self.get("api_key")

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
        """Clear authentication tokens (but keep API key)"""
        if 'access_token' in self._config:
            del self._config['access_token']
        if 'refresh_token' in self._config:
            del self._config['refresh_token']
        # Note: We don't clear api_key here - it should be explicitly cleared if needed
        self._save()


# Global config instance
config = Config()

