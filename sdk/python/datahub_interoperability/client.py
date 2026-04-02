"""
DataHub Client

Main SDK client with authentication, error handling, and retry logic.
"""

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx

from .config import DataHubClientConfig
from .errors import (
    DataHubError,
    NetworkError,
    UnauthorizedError,
    parse_error,
)

logger = logging.getLogger(__name__)


def calculate_backoff_delay(attempt: int, base_delay: float = 1.0) -> float:
    """
    Calculate exponential backoff delay

    Args:
        attempt: Retry attempt number (0-indexed)
        base_delay: Base delay in seconds

    Returns:
        Delay in seconds
    """
    return base_delay * (2**attempt)


def is_retryable_error(error: Exception) -> bool:
    """
    Check if error is retryable

    Args:
        error: Exception to check

    Returns:
        True if error is retryable
    """
    if isinstance(error, NetworkError):
        return True

    if isinstance(error, DataHubError):
        # Retry on 5xx errors and 429 (rate limit)
        return error.http_status >= 500 or error.http_status == 429

    return False


class DataHubClient:
    """
    Main DataHub Client

    Provides authenticated HTTP client with retry logic and error handling.
    Includes high-level APIs for contracts, lineage, scheduled ingestion, versioning,
    governance, mesh, search, observability, virtualization, and webhooks.
    """

    def __init__(self, config: DataHubClientConfig):
        """
        Initialize DataHub client

        Args:
            config: Client configuration
        """
        if not config.base_url:
            raise ValueError("base_url is required")

        self.config = config
        self.token_refresh_callback: Optional[Callable[[], Awaitable[str]]] = None

        # Create httpx client
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout,
            headers={
                "User-Agent": config.user_agent,
                "Content-Type": "application/json",
            },
        )

        # Initialize API modules
        from .ai import AIAPI
        from .assets import AssetsAPI
        from .audit import AuditAPI
        from .auth import AuthAPI
        from .baas import BaaSAPI
        from .billing import BillingAPI
        from .compliance import ComplianceAPI
        from .contracts import ContractsAPI
        from .datasets import DatasetsAPI
        from .dq import DQAPI
        from .files import FilesAPI
        from .gdpr import GDPRAPI
        from .governance import GovernanceAPI
        from .jobs import JobsAPI
        from .lineage import LineageAPI
        from .marketplace import MarketplaceIntegrationAPI
        from .marketplace_listings import MarketplaceListingsAPI
        from .mesh import MeshAPI
        from .ml import InferenceAPI, ODHIntegrationAPI, TrainingAPI
        from .model_serving import ModelServingAPI
        from .observability import ObservabilityAPI
        from .scheduled_export import ScheduledExportAPI
        from .scheduled_ingestion import ScheduledIngestionAPI
        from .search import SearchAPI
        from .semantic import SemanticAPI
        from .social import SocialAPI
        from .tenants import TenantsAPI
        from .transformation import TransformationAPI
        from .users import UsersAPI
        from .versioning import VersioningAPI
        from .virtualization import VirtualizationAPI
        from .webhooks import WebhooksAPI
        from .workflows import WorkflowsAPI

        self.contracts = ContractsAPI(self)
        self.lineage = LineageAPI(self)
        self.scheduled_ingestion = ScheduledIngestionAPI(self)
        self.scheduled_export = ScheduledExportAPI(self)
        self.versioning = VersioningAPI(self)
        self.governance = GovernanceAPI(self)
        self.mesh = MeshAPI(self)
        self.search = SearchAPI(self)
        self.observability = ObservabilityAPI(self)
        self.virtualization = VirtualizationAPI(self)
        self.webhooks = WebhooksAPI(self)
        self.marketplace = MarketplaceIntegrationAPI(self)
        self.baas = BaaSAPI(self)
        self.ml = ODHIntegrationAPI(self)
        self.billing = BillingAPI(self)
        self.tenants = TenantsAPI(self)
        self.gdpr = GDPRAPI(self)
        self.training = TrainingAPI(self)
        self.inference = InferenceAPI(self)
        self.model_serving = ModelServingAPI(self)
        self.ai = AIAPI(self)
        self.assets = AssetsAPI(self)
        self.audit = AuditAPI(self)
        self.auth = AuthAPI(self)
        self.compliance = ComplianceAPI(self)
        self.datasets = DatasetsAPI(self)
        self.dq = DQAPI(self)
        self.files = FilesAPI(self)
        self.jobs = JobsAPI(self)
        self.marketplace_listings = MarketplaceListingsAPI(self)
        self.semantic = SemanticAPI(self)
        self.social = SocialAPI(self)
        self.transformation = TransformationAPI(self)
        self.users = UsersAPI(self)
        self.workflows = WorkflowsAPI(self)

    def set_api_token(self, token: str) -> None:
        """
        Set API token

        Args:
            token: API token (JWT or API key)
        """
        # Update config (create new config with updated token)
        self.config = DataHubClientConfig(
            base_url=self.config.base_url,
            api_token=token,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
            user_agent=self.config.user_agent,
            enable_logging=self.config.enable_logging,
        )

    def set_token_refresh_callback(self, callback: Callable[[], Awaitable[str]]) -> None:
        """
        Set token refresh callback

        Args:
            callback: Async function that returns new token
        """
        self.token_refresh_callback = callback

    async def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with authentication

        Returns:
            Request headers
        """
        headers = {}
        if self.config.api_token:
            # Detect if token is an API key (no dots, unlike JWT tokens).
            # API keys are base64url strings without dots.
            # JWT tokens have the format: header.payload.signature (three dot-separated parts).
            token = self.config.api_token
            if "." not in token:
                # API key — use Authorization: ApiKey header.
                # This is preferred over X-API-Key because Django's CSRF middleware
                # exempts requests carrying an Authorization header, which is required
                # for mutating (POST/PUT/PATCH/DELETE) operations.
                headers["Authorization"] = f"ApiKey {token}"
            else:
                # JWT token — use standard Bearer authorization.
                headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _handle_token_refresh(self, error: httpx.HTTPStatusError) -> bool:
        """
        Handle token refresh for 401 errors

        Args:
            error: HTTP error response

        Returns:
            True if token was refreshed and request should be retried
        """
        if error.response.status_code == 401 and self.token_refresh_callback:
            try:
                new_token = await self.token_refresh_callback()
                if not new_token:
                    logger.error("Token refresh callback returned None or empty token")
                    return False

                # Update token in config
                self.set_api_token(new_token)

                # Verify token was set correctly
                if self.config.api_token != new_token:
                    logger.error(
                        f"Token was not set correctly. Expected: {new_token[:20]}..., Got: {self.config.api_token[:20] if self.config.api_token else None}..."
                    )
                    return False

                logger.debug(f"Token refreshed successfully. New token: {new_token[:20]}...")
                return True
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                raise UnauthorizedError("Token refresh failed")
        return False

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional httpx request arguments

        Returns:
            HTTP response

        Raises:
            DataHubError: On API errors
            NetworkError: On network errors
        """
        max_retries = self.config.max_retries
        last_error: Optional[Exception] = None
        token_refresh_attempted = (
            False  # Track if token refresh was attempted to prevent infinite loops
        )

        for attempt in range(max_retries + 1):
            try:
                # Get headers fresh each attempt (token may have been refreshed)
                headers = await self._get_headers()
                # Preserve any headers passed in kwargs, but update with auth headers
                if "headers" in kwargs:
                    # Merge: kwargs headers take precedence, but we need auth
                    original_headers = kwargs.get("headers", {})
                    headers.update(original_headers)
                kwargs["headers"] = headers

                # Debug: Log token being used (first 20 chars only for security)
                if self.config.enable_logging and self.config.api_token:
                    logger.debug(f"Using token: {self.config.api_token[:20]}...")

                if self.config.enable_logging:
                    logger.info(f"[DataHub SDK] {method} {url} (attempt {attempt + 1})")

                response = await self.client.request(method, url, **kwargs)

                # Check for error responses
                if response.is_error:
                    # Try token refresh for 401 (before parsing error)
                    if response.status_code == 401 and not token_refresh_attempted:
                        error = httpx.HTTPStatusError(
                            f"401 Unauthorized", request=response.request, response=response
                        )
                        if await self._handle_token_refresh(error):
                            # Token was refreshed - retry with new token
                            token_refresh_attempted = True  # Prevent multiple refresh attempts
                            # Headers will be regenerated on next iteration with new token
                            continue
                        else:
                            # Token refresh failed or not available - parse error normally
                            token_refresh_attempted = True

                    # Parse and raise error (only if token refresh didn't happen or failed)
                    try:
                        error_data = response.json()
                        # Add http_status to error_data if not present (for string error format)
                        if "http_status" not in error_data:
                            error_data["http_status"] = response.status_code

                        # Check if this is an ODPS or ODCS-related endpoint and try to parse as ODPS/ODCS error
                        url_lower = url.lower()
                        request_params = kwargs.get("params", {})

                        # Check for ODCS export endpoints (format=odcs parameter or odcs in URL)
                        is_odcs_endpoint = "odcs" in url_lower
                        # Check for ODPS-related endpoints
                        is_odps_endpoint = (
                            "odps" in url_lower
                            or "products" in url_lower
                            or "/link-odps" in url_lower
                        )

                        # For export/download endpoints, check format parameter
                        if "/export" in url_lower or "/download" in url_lower:
                            # Try to get format from params if available
                            if isinstance(request_params, dict):
                                format_param = request_params.get("format", "").lower()
                                if format_param == "odcs":
                                    is_odcs_endpoint = True
                                elif format_param == "odps":
                                    is_odps_endpoint = True

                        # Try ODCS error parsing first (for ODCS endpoints)
                        if is_odcs_endpoint:
                            from .errors import parse_odcs_error

                            try:
                                raise parse_odcs_error(error_data)
                            except Exception:
                                # If ODCS parsing fails, fall back to standard error parsing
                                pass

                        # Try ODPS error parsing (for ODPS endpoints)
                        if is_odps_endpoint:
                            from .errors import parse_odps_error

                            try:
                                raise parse_odps_error(error_data)
                            except Exception:
                                # If ODPS parsing fails, fall back to standard error parsing
                                pass

                        raise parse_error(error_data)
                    except ValueError:
                        # Not JSON, create generic error
                        raise DataHubError(
                            f"HTTP {response.status_code}: {response.text}",
                            "HTTP_ERROR",
                            response.status_code,
                        )

                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                # Try token refresh for 401 (only if not already attempted)
                if e.response.status_code == 401 and not token_refresh_attempted:
                    if await self._handle_token_refresh(e):
                        # Retry with new token
                        token_refresh_attempted = True  # Prevent multiple refresh attempts
                        continue
                    else:
                        token_refresh_attempted = True

                # Parse error response
                try:
                    error_data = e.response.json()
                    # Check if this is an ODPS-related endpoint and try to parse as ODPS error
                    url_lower = str(e.request.url).lower() if e.request.url else ""
                    if (
                        "odps" in url_lower
                        or "products" in url_lower
                        or "/export" in url_lower
                        or "/download" in url_lower
                        or "/link-odps" in url_lower
                    ):
                        from .errors import parse_odps_error

                        try:
                            raise parse_odps_error(error_data)
                        except Exception:
                            # If ODPS parsing fails, fall back to standard error parsing
                            pass
                    raise parse_error(error_data)
                except ValueError:
                    raise DataHubError(
                        f"HTTP {e.response.status_code}: {e.response.text}",
                        "HTTP_ERROR",
                        e.response.status_code,
                    )

            except httpx.RequestError as e:
                last_error = NetworkError(str(e))

                # Don't retry on last attempt or non-retryable errors
                if attempt >= max_retries or not is_retryable_error(last_error):
                    raise last_error

                # Calculate backoff delay
                delay = calculate_backoff_delay(attempt)

                if self.config.enable_logging:
                    logger.info(f"[DataHub SDK] Retrying after {delay}s...")

                # Wait before retry
                await asyncio.sleep(delay)

            except DataHubError:
                # Re-raise DataHub errors immediately
                raise

            except Exception as e:
                last_error = e
                if attempt >= max_retries:
                    raise DataHubError(
                        f"Unexpected error: {str(e)}",
                        "UNEXPECTED_ERROR",
                        0,
                    )

                delay = calculate_backoff_delay(attempt)
                await asyncio.sleep(delay)

        # If we get here, all retries failed
        if last_error:
            raise last_error
        raise DataHubError("Request failed after retries", "REQUEST_FAILED", 0)

    async def get(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        """
        GET request

        Args:
            url: Request URL
            **kwargs: Additional httpx request arguments

        Returns:
            Response data as dictionary
        """
        response = await self.request("GET", url, **kwargs)
        return response.json()

    async def post(
        self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        POST request

        Args:
            url: Request URL
            data: Request body
            **kwargs: Additional httpx request arguments

        Returns:
            Response data as dictionary
        """
        response = await self.request("POST", url, json=data, **kwargs)
        return response.json()

    async def patch(
        self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        PATCH request

        Args:
            url: Request URL
            data: Request body
            **kwargs: Additional httpx request arguments

        Returns:
            Response data as dictionary
        """
        response = await self.request("PATCH", url, json=data, **kwargs)
        return response.json()

    async def delete(self, url: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
        DELETE request

        Args:
            url: Request URL
            **kwargs: Additional httpx request arguments

        Returns:
            Response data as dictionary, or None if response is empty (204 No Content)
        """
        response = await self.request("DELETE", url, **kwargs)
        # DELETE may return 204 No Content with empty body
        if response.status_code == 204 or not response.text:
            return None
        return response.json()

    async def close(self) -> None:
        """
        Close HTTP client
        """
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
