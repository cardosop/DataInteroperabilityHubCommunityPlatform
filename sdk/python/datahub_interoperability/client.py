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
from ._mvp_detection import detect_mvp_gated_feature, extract_environment_url
from .errors import (
    DataHubError,
    MVPGatedFeatureError,
    NetworkError,
    RateLimitError,
    UnauthorizedError,
    parse_error,
)

logger = logging.getLogger(__name__)


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    error: Optional[Exception] = None,
) -> float:
    """
    Calculate exponential backoff delay.

    When *error* is a :class:`RateLimitError` with a ``retry_after`` hint,
    the delay is at least ``retry_after`` seconds — the server told us how
    long to wait, and exponential backoff alone is often not enough.

    Args:
        attempt: Retry attempt number (0-indexed)
        base_delay: Base delay in seconds
        error: The error that triggered the retry (optional)

    Returns:
        Delay in seconds
    """
    base = base_delay * (2 ** attempt)
    if error is not None and isinstance(error, RateLimitError):
        retry_after = getattr(error, "retry_after", None)
        if isinstance(retry_after, (int, float)) and retry_after > 0:
            # Honour the server's Retry-After hint.
            return max(base, retry_after)
    return base


def _maybe_raise_mvp_gated(response: httpx.Response) -> None:
    """If ``response`` is a 404 against an MVP-gated /api/v1/ prefix, raise
    :class:`MVPGatedFeatureError`. Otherwise return None and let the caller
    fall through to its normal error-parsing path.

    Factored as a single helper (D132) so both ``parse_error`` sites in
    :meth:`DataHubClient.request` share one detection path with zero inline
    duplication.
    """
    if response.status_code != 404:
        return
    request_url = str(response.request.url) if response.request is not None else ""
    detected = detect_mvp_gated_feature(request_url)
    if detected is None:
        return
    prefix, feature = detected
    if "/api/v1/" in request_url:
        endpoint = request_url.split("/api/v1/", 1)[1]
    else:
        endpoint = request_url
    raise MVPGatedFeatureError(
        feature=feature,
        prefix=prefix,
        endpoint=endpoint,
        environment_url=extract_environment_url(request_url),
    )


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

        # Phase 5 / 279 API modules — initialised so they are reachable as
        # client.<attr> (e.g. client.capabilities.list_capabilities()).
        from .admin import AdminAPI
        from .capabilities import CapabilitiesAPI
        from .developer import DeveloperAPI
        from .dpia import DpiaAPI
        from .drafts import DraftsAPI
        from .events import EventsAPI
        from .integrations import IntegrationsAPI
        from .lineage_subscriptions import LineageSubscriptionsAPI
        from .notifications import NotificationAPI
        from .openlineage import OpenLineageAPI
        from .platform import PlatformAPI
        from .public_dsar import PublicDsarAPI
        from .ropa import RopaAPI
        from .security import SecurityAPI

        self.admin = AdminAPI(self)
        self.capabilities = CapabilitiesAPI(self)
        self.developer = DeveloperAPI(self)
        self.dpia = DpiaAPI(self)
        self.drafts = DraftsAPI(self)
        self.events = EventsAPI(self)
        self.integrations = IntegrationsAPI(self)
        self.lineage_subscriptions = LineageSubscriptionsAPI(self)
        self.notifications = NotificationAPI(self)
        self.openlineage = OpenLineageAPI(self)
        self.platform = PlatformAPI(self)
        self.public_dsar = PublicDsarAPI(self)
        self.ropa = RopaAPI(self)
        self.security = SecurityAPI(self)

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

    @staticmethod
    def _is_jwt_expired(token: str) -> bool:
        """Return True if *token* is a JWT whose ``exp`` claim is in the past.

        Does NOT verify the signature — this is a lightweight client-side
        check to avoid sending requests with an obviously-expired token.
        Non-JWT tokens (API keys) always return False.
        """
        if "." not in token:
            return False
        try:
            import base64, json
            payload_b64 = token.split(".")[1]
            # Add padding if needed
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get("exp", 0)
            return time.time() > exp
        except Exception:
            return False

    async def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with authentication.

        If the configured token is an expired JWT and a refresh callback
        is registered, the callback is invoked to obtain a fresh token
        before returning headers.  This avoids a guaranteed 401 round-trip
        on every request that follows token expiry.
        """
        headers = {}
        if self.config.api_token:
            token = self.config.api_token
            # Proactive JWT refresh: if the token is expired and we have
            # a callback, refresh it now rather than waiting for a 401.
            if (
                self._is_jwt_expired(token)
                and self.token_refresh_callback is not None
            ):
                try:
                    new_token = await self.token_refresh_callback()
                    if new_token:
                        self.config.api_token = new_token
                        token = new_token
                except Exception:
                    pass  # Fall through — the 401 handler will retry

            if "." not in token:
                # API key — use Authorization: ApiKey header.
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
                                logger.debug(
                                    "[DataHub SDK] ODCS error parsing failed, "
                                    "falling back to generic parse_error",
                                    exc_info=True,
                                )

                        # Try ODPS error parsing (for ODPS endpoints)
                        if is_odps_endpoint:
                            from .errors import parse_odps_error

                            try:
                                raise parse_odps_error(error_data)
                            except Exception:
                                # If ODPS parsing fails, fall back to standard error parsing
                                logger.debug(
                                    "[DataHub SDK] ODPS error parsing failed, "
                                    "falling back to generic parse_error",
                                    exc_info=True,
                                )

                        # MVP-gated 404 detection runs BEFORE the generic
                        # parse_error fall-through (Phase 215.2 D132).
                        _maybe_raise_mvp_gated(response)
                        parsed = parse_error(error_data, http_status=response.status_code)
                        if attempt < max_retries and is_retryable_error(parsed):
                            last_error = parsed
                            delay = calculate_backoff_delay(attempt, error=parsed)
                            if self.config.enable_logging:
                                logger.info(
                                    f"[DataHub SDK] Retrying retryable error "
                                    f"(status={parsed.http_status}) after {delay}s..."
                                )
                            await asyncio.sleep(delay)
                            continue
                        raise parsed
                    except ValueError:
                        # Not JSON — still check for MVP-gated 404 before
                        # falling back to a bare HTTP_ERROR.
                        _maybe_raise_mvp_gated(response)
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
                            logger.debug(
                                "[DataHub SDK] ODPS error parsing failed in "
                                "HTTPStatusError handler, falling back to generic parse_error",
                                exc_info=True,
                            )
                    # MVP-gated 404 detection runs BEFORE parse_error here too.
                    _maybe_raise_mvp_gated(e.response)
                    parsed = parse_error(error_data, http_status=e.response.status_code)
                    if attempt < max_retries and is_retryable_error(parsed):
                        last_error = parsed
                        delay = calculate_backoff_delay(attempt, error=last_error)
                        if self.config.enable_logging:
                            logger.info(
                                f"[DataHub SDK] Retrying retryable error "
                                f"(status={parsed.http_status}) after {delay}s..."
                            )
                        await asyncio.sleep(delay)
                        continue
                    raise parsed
                except ValueError:
                    _maybe_raise_mvp_gated(e.response)
                    raise DataHubError(
                        f"HTTP {e.response.status_code}: {e.response.text}",
                        "HTTP_ERROR",
                        e.response.status_code,
                    )

            except httpx.RequestError as e:
                # Preserve the underlying error info — str(e) can be empty
                # for some httpcore exceptions (ConnectError, ReadError).
                msg = str(e) or repr(e) or type(e).__name__
                last_error = NetworkError(msg)

                # Don't retry on last attempt or non-retryable errors
                if attempt >= max_retries or not is_retryable_error(last_error):
                    raise last_error

                # Calculate backoff delay
                delay = calculate_backoff_delay(attempt, error=last_error)

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

                delay = calculate_backoff_delay(attempt, error=last_error)
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

    async def check_health(self) -> Dict[str, Any]:
        """GET /health/ — check API health status.

        The health endpoint lives at the server root (``/health/``), not
        under ``/api/v1/``.  We construct an absolute URL from the
        configured base_url so the path is correct regardless of whether
        the base_url includes a prefix path.
        """
        from urllib.parse import urlparse

        parsed = urlparse(self.config.base_url)
        health_url = f"{parsed.scheme}://{parsed.netloc}/health/"
        # Use self.client directly (not self.get) because self.get
        # appends the URL to the configured base_url.
        response = await self.client.get(health_url)
        if response.is_error:
            return response.json() if response.headers.get("content-type", "").startswith("application/json") else {"status": "error", "http_status": response.status_code}
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
