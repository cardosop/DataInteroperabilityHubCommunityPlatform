"""
Authentication management for DataHub CLI.

Handles API key and JWT token authentication.
"""
import requests
import click
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .config import config


class AuthManager:
    """Manages authentication for CLI"""

    def __init__(self, config_instance=None):
        """
        Initialize AuthManager.

        Args:
            config_instance: Optional Config instance. If None, uses global config.
        """
        if config_instance is None:
            from .config import config as global_config
            self.config = global_config
        else:
            self.config = config_instance
        # Don't cache api_base_url - read it dynamically so config changes are picked up

    def _get_api_base_url(self):
        """Get API base URL dynamically from config"""
        return self.config.get_api_base_url()

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # Prioritize access token over API key (access tokens are user-specific and more secure)
        # This ensures that when a user is logged in, their token is used even if API key exists
        access_token = self.config.get_access_token()
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
            return headers

        # Fall back to API key if no access token (for automation/CI scenarios)
        api_key = self.config.get_api_key()
        if api_key and api_key.strip():
            # Backend expects "ApiKey <key>" format, not "Bearer <key>"
            headers['Authorization'] = f'ApiKey {api_key}'
            return headers

        return headers

    def login(self, email: str, password: str) -> bool:
        """
        Login with email and password to get JWT tokens.

        Returns True if successful, False otherwise.
        """
        try:
            response = requests.post(
                f'{self._get_api_base_url()}/auth/login/',
                json={
                    'email': email,
                    'password': password
                },
                timeout=10
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    click.echo(f"Login failed: Invalid response from server: {e}", err=True)
                    return False

                # Validate response contains required tokens
                if 'access_token' not in data or 'refresh_token' not in data:
                    click.echo("Login failed: Server response missing required tokens", err=True)
                    return False

                self.config.set_access_token(data['access_token'])
                self.config.set_refresh_token(data['refresh_token'])
                click.echo("Login successful!")
                return True
            else:
                try:
                    error_data = response.json() if response.content else {}
                except ValueError:
                    error_data = {}
                error_msg = error_data.get('error', {}).get('message', 'Login failed')
                click.echo(f"Login failed: {error_msg}", err=True)
                return False
        except requests.exceptions.RequestException as e:
            click.echo(f"Error connecting to API: {e}", err=True)
            return False

    def refresh_access_token(self) -> bool:
        """
        Refresh access token using refresh token.

        Returns True if successful, False otherwise.
        """
        refresh_token = self.config.get_refresh_token()
        if not refresh_token:
            return False

        try:
            response = requests.post(
                f'{self._get_api_base_url()}/auth/refresh/',
                json={'refresh_token': refresh_token},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.config.set_access_token(data['access_token'])
                return True
            else:
                # Refresh token expired, clear auth
                self.config.clear_auth()
                return False
        except requests.exceptions.RequestException:
            return False

    def logout(self) -> bool:
        """
        Logout and clear authentication tokens.

        Returns True if successful, False otherwise.
        """
        refresh_token = self.config.get_refresh_token()
        if refresh_token:
            try:
                headers = self.get_auth_headers()
                requests.post(
                    f'{self._get_api_base_url()}/auth/logout/',
                    json={'refresh_token': refresh_token},
                    headers=headers,
                    timeout=10
                )
            except requests.exceptions.RequestException:
                pass  # Continue to clear local tokens even if API call fails

        self.config.clear_auth()
        click.echo("Logged out successfully!")
        return True

    def ensure_authenticated(self) -> bool:
        """
        Ensure we have valid authentication.

        Tries to refresh token if access token is missing or expired.
        Returns True if authenticated, False otherwise.
        """
        access_token = self.config.get_access_token()
        api_key = self.config.get_api_key()

        # Check if API key is set (not None and not empty string)
        if api_key and api_key.strip():
            return True  # API key doesn't expire

        if not access_token:
            # Try to refresh
            if self.refresh_access_token():
                return True
            return False

        # TODO: Check if access token is expired (would need to decode JWT)
        # For now, assume it's valid if present
        return True


# Global auth manager instance
auth_manager = AuthManager()

