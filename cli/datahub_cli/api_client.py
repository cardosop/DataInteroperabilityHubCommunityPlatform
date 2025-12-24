"""
API client for DataHub CLI.

Handles HTTP requests to the DataHub API.
"""
import json
import requests
import click
from typing import Optional, Dict, Any, List
from .auth import auth_manager
from .config import config


class APIClient:
    """Client for making API requests"""

    def __init__(self):
        # Don't cache base_url - read it dynamically so config changes are picked up
        self.auth_manager = auth_manager

    def _get_base_url(self):
        """Get API base URL dynamically from config"""
        return config.get_api_base_url()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> requests.Response:
        """
        Make an API request.

        Returns Response object. Raises click.ClickException on error.
        """
        # Ensure authenticated
        if not self.auth_manager.ensure_authenticated():
            raise click.ClickException(
                "Not authenticated. Please run 'datahub login' or set API key with 'datahub config set api_key <key>'"
            )

        base_url = self._get_base_url()
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = self.auth_manager.get_auth_headers()

        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                files=files,
                headers=headers,
                timeout=30,
                stream=stream
            )

            # Handle 401 Unauthorized - try to refresh token
            if response.status_code == 401:
                if self.auth_manager.refresh_access_token():
                    # Retry request with new token
                    headers = self.auth_manager.get_auth_headers()
                    response = requests.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                        files=files,
                        headers=headers,
                        timeout=30,
                        stream=stream
                    )
                else:
                    raise click.ClickException(
                        "Authentication failed. Please run 'datahub login' again."
                    )

            return response
        except requests.exceptions.RequestException as e:
            raise click.ClickException(f"API request failed: {e}")

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request"""
        response = self._request('GET', endpoint, params=params)
        return self._handle_response(response)

    def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST request"""
        response = self._request('POST', endpoint, json_data=json_data, files=files)
        return self._handle_response(response)

    def patch(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PATCH request"""
        response = self._request('PATCH', endpoint, json_data=json_data)
        return self._handle_response(response)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE request"""
        response = self._request('DELETE', endpoint)
        return self._handle_response(response)

    def get_stream(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """GET request with streaming"""
        return self._request('GET', endpoint, params=params, stream=True)

    def request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Make a raw request and return Response object"""
        return self._request(method, endpoint, params=params)

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response"""
        if response.status_code >= 400:
            error_data = {}
            try:
                error_data = response.json()
            except (json.JSONDecodeError, ValueError):
                error_data = {'error': {'message': response.text or 'Unknown error'}}

            # Try to use ODPS error handling if available
            try:
                from .odps_errors import handle_api_error
                endpoint = response.url.split('/api/v1/')[-1] if '/api/v1/' in response.url else None
                raise handle_api_error(response.text, response.status_code, endpoint)
            except ImportError:
                # Fallback to basic error handling
                error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                error_code = error_data.get('error', {}).get('code', 'UNKNOWN_ERROR')
                raise click.ClickException(f"API error ({error_code}): {error_msg}")

        if response.status_code == 204:  # No content
            return {}

        try:
            json_data = response.json()
            # Ensure we always return a dict or list, never None
            return json_data if json_data is not None else {}
        except ValueError:
            # Response is not JSON - return empty dict
            return {}


# Global API client instance
api_client = APIClient()

