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
        stream: bool = False,
        timeout: Optional[int] = None
    ) -> requests.Response:
        """
        Make an API request.

        Args:
            timeout: Request timeout in seconds. Defaults to 30 for regular requests,
                    120 for workflow operations (contracts/products/, contracts/{id}/link-odps/)

        Returns Response object. Raises click.ClickException on error.
        """
        # Reload config to ensure we have the latest API key (important for tests)
        config._load()

        # Ensure authenticated
        if not self.auth_manager.ensure_authenticated():
            raise click.ClickException(
                "Not authenticated. Please run 'datahub login' or set API key with 'datahub config set api_key <key>'"
            )

        base_url = self._get_base_url()
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = self.auth_manager.get_auth_headers()

        # Determine timeout: use provided timeout, or detect workflow endpoints for longer timeout
        if timeout is None:
            # Workflow endpoints that may take longer
            workflow_endpoints = ['contracts/products/', 'contracts/', '/link-odps']
            is_workflow = any(we in endpoint for we in workflow_endpoints)
            timeout = 120 if is_workflow else 30

        # Retry logic for connection errors
        max_retries = 3
        retry_delay = 1
        response = None

        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    files=files,
                    headers=headers,
                    timeout=timeout,
                    stream=stream
                )
                # Success - break out of retry loop
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionResetError, OSError) as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Last attempt failed - raise exception
                    raise click.ClickException(f"API request failed after {max_retries} attempts: {e}")

        if response is None:
            raise click.ClickException("API request failed: No response received")

        # Handle 401 Unauthorized - try to refresh token (only for JWT, not API keys)
        if response.status_code == 401:
            # Check if we're using API key authentication
            api_key = self.auth_manager.config.get_api_key()
            if api_key and api_key.strip():
                # Using API key - don't try to refresh, just return the error response
                # The _handle_response will process the error properly
                return response

            # Using JWT - try to refresh token
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
                    timeout=timeout,
                    stream=stream
                )
            else:
                raise click.ClickException(
                    "Authentication failed. Please run 'datahub login' again."
                )

        return response

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request"""
        response = self._request('GET', endpoint, params=params)
        return self._handle_response(response)

    def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
        """POST request

        Args:
            timeout: Request timeout in seconds. Defaults to 30 for regular requests,
                    120 for workflow operations
        """
        response = self._request('POST', endpoint, json_data=json_data, files=files, timeout=timeout)
        return self._handle_response(response)

    def patch(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PATCH request"""
        response = self._request('PATCH', endpoint, json_data=json_data)
        return self._handle_response(response)

    def delete(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """DELETE request"""
        response = self._request('DELETE', endpoint, json_data=json_data)
        return self._handle_response(response)

    def get_stream(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """GET request with streaming"""
        return self._request('GET', endpoint, params=params, stream=True)

    def request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> requests.Response:
        """Make a raw request and return Response object"""
        return self._request(method, endpoint, params=params, json_data=json_data, timeout=timeout)

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

