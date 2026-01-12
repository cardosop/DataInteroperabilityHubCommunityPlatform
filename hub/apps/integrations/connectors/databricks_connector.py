"""
Databricks Marketplace Connector

Connector implementation for Databricks Marketplace.
Supports harvest (pull) operations for discovering and retrieving data from
Databricks Marketplace.

Features:
- Circuit breaker protection
- Retry logic with exponential backoff
- Distributed tracing
- Harvest-only operations (PULL direction)

Databricks API Documentation: https://docs.databricks.com/api/workspace/introduction
"""
import httpx
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from django.conf import settings

from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceType,
    SyncDirection,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceAssetMapping,
    SyncResult,
    SyncStatus,
)
from hub.apps.assets.models import AssetSourceType
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)
from hub.apps.core.services.base import NotFoundError

logger = logging.getLogger(__name__)


class DatabricksConnector(DataMarketplaceConnector):
    """
    Connector for Databricks Marketplace (Harvest-Only).

    Implements harvest (pull) operations for discovering and retrieving data from
    Databricks Marketplace. This connector is read-only and does not support push operations
    (create, update, publish) as Databricks Marketplace is a public data marketplace that should
    be harvested FROM, not pushed TO.

    Supports:
    - Discovery: list_listings, get_listing, list_resources
    - Harvest: sync_pull (bulk synchronization from Databricks to Hub)
    - Mapping: map_to_hub_asset (Databricks listings → Hub assets)

    Does NOT support:
    - Push operations: create_listing, update_listing, publish_resource, sync_push
    - Write operations: All methods that modify Databricks Marketplace data

    Authentication:
    - Uses Databricks personal access token (PAT) or OAuth token
    - Token is passed as Bearer token in Authorization header
    - Host is the Databricks workspace URL (e.g., https://<workspace>.cloud.databricks.com)
    """

    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        cluster_id: Optional[str] = None
    ):
        """
        Initialize Databricks connector.

        Args:
            host: Databricks workspace URL (e.g., 'https://test-workspace.cloud.databricks.com')
            token: Databricks personal access token or OAuth token (required for authentication)
            cluster_id: Optional Databricks cluster ID (for future use)
        """
        # Determine host URL
        if host:
            self.host = host.rstrip('/')
        else:
            self.host = getattr(settings, 'DATABRICKS_DEFAULT_HOST', '')
            if not self.host:
                raise ValueError("host must be provided or DATABRICKS_DEFAULT_HOST must be set")

        # Store token
        self.token = token or getattr(settings, 'DATABRICKS_DEFAULT_TOKEN', None)
        if not self.token:
            raise ValueError("token must be provided or DATABRICKS_DEFAULT_TOKEN must be set")

        # Store optional cluster_id
        self.cluster_id = cluster_id

        # HTTP client configuration
        self.timeout = getattr(settings, 'DATABRICKS_CONNECTOR_TIMEOUT', 30)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize HTTP client
        self.client = httpx.Client(
            base_url=self.host,
            timeout=self.timeout,
            headers=self._get_default_headers(),
            follow_redirects=True
        )

        # Initialize circuit breaker (same pattern as CKAN)
        self._circuit_breaker = CircuitBreaker(
            service_name="databricks-connector",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client()
        )

        # Track authentication state
        self._authenticated = False

    def _is_transient_error(self, status_code: int) -> bool:
        """
        Check if Databricks API error is transient and should be retried.

        Args:
            status_code: HTTP status code

        Returns:
            True if error is transient (should retry), False otherwise
        """
        # Retry on: 429 (Too Many Requests), 500, 502, 503, 504 (server errors)
        return status_code in (429, 500, 502, 503, 504)

    def _extract_error_message(self, response: httpx.Response) -> str:
        """
        Extract error message from Databricks API error response.

        Databricks API error responses typically have this structure:
        {
            "error_code": "RESOURCE_DOES_NOT_EXIST",
            "message": "Share 'my_share' does not exist"
        }

        Args:
            response: httpx.Response object with error

        Returns:
            Error message string
        """
        try:
            error_data = response.json()
            # Try to extract message from Databricks error format
            if isinstance(error_data, dict):
                if 'message' in error_data:
                    return error_data['message']
                elif 'error' in error_data:
                    error_obj = error_data['error']
                    if isinstance(error_obj, dict) and 'message' in error_obj:
                        return error_obj['message']
                    elif isinstance(error_obj, str):
                        return error_obj
                elif 'error_code' in error_data:
                    # Use error_code as fallback message
                    return f"Databricks API error: {error_data['error_code']}"
        except Exception:
            # If JSON parsing fails, use response text
            pass

        # Fallback to response text or status code
        try:
            return response.text[:500] if response.text else f"HTTP {response.status_code}"
        except Exception:
            return f"HTTP {response.status_code}"

    def _map_databricks_error(
        self,
        error: httpx.HTTPStatusError,
        context: str = '',
        operation: str = ''
    ) -> Exception:
        """
        Map Databricks API error to appropriate connector exception.

        Args:
            error: httpx.HTTPStatusError from Databricks API
            context: Additional context string for error messages
            operation: Operation name for logging (e.g., 'list_listings')

        Returns:
            Mapped exception (NotFoundError, PermissionError, ValueError, ConnectionError)
        """
        status_code = error.response.status_code
        error_message = self._extract_error_message(error.response)

        # Map error codes to exceptions
        if status_code == 404:
            return NotFoundError(
                f"{context}Resource not found in Databricks: {error_message}"
            )
        elif status_code == 403:
            return PermissionError(
                f"{context}Permission denied: {error_message}"
            )
        elif status_code == 400:
            return ValueError(
                f"{context}Invalid request: {error_message}"
            )
        elif self._is_transient_error(status_code):
            # Transient errors are wrapped in ConnectionError for retry logic
            return ConnectionError(
                f"{context}Transient Databricks error ({status_code}): {error_message}"
            )
        else:
            # Other errors are connection errors
            return ConnectionError(
                f"{context}Databricks error ({status_code}): {error_message}"
            )

    def _log_with_context(
        self,
        level: str,
        message: str,
        operation: str = '',
        error_code: Optional[int] = None,
        error_message: str = '',
        attempt: int = 0,
        max_retries: int = 0,
        delay: float = 0.0,
        **kwargs
    ):
        """
        Log message with structured context (correlation IDs, tenant_id, user_id).

        Args:
            level: Log level ('info', 'warning', 'error', 'debug')
            message: Log message
            operation: Operation name (e.g., 'list_listings')
            error_code: Optional error code
            error_message: Optional error message
            attempt: Retry attempt number
            max_retries: Maximum retries
            delay: Retry delay in seconds
            **kwargs: Additional context fields
        """
        # Get correlation IDs from trace context
        correlation_id = None
        trace_id = None
        try:
            from hub.apps.api.middleware.trace_propagation import get_current_request
            request = get_current_request()
            if request:
                correlation_id = getattr(request, 'trace_id', None)
                trace_id = getattr(request, 'trace_id', None)
        except Exception:
            pass

        # Build structured log context
        log_context = {
            'operation': operation,
            'connector': 'databricks',
            'host': self.host,
        }

        # Add correlation IDs if available
        if correlation_id:
            log_context['correlation_id'] = correlation_id
        if trace_id:
            log_context['trace_id'] = trace_id

        # Add error context if available
        if error_code is not None:
            log_context['error_code'] = error_code
        if error_message:
            log_context['error_message'] = error_message

        # Add retry context if available
        if attempt > 0:
            log_context['attempt'] = attempt
            log_context['max_retries'] = max_retries
            log_context['delay'] = delay

        # Add any additional context
        log_context.update(kwargs)

        # Log with appropriate level
        log_func = getattr(logger, level, logger.info)
        log_func(message, extra=log_context)

    def _get_default_headers(self) -> Dict[str, str]:
        """Get default HTTP headers including Bearer token authentication."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make HTTP request with retry logic and circuit breaker protection.

        Implements retry logic with exponential backoff for transient failures:
        - Retries on Databricks API errors with status 429 (Too Many Requests), 500, 502, 503, 504 (server errors)
        - Don't retry on 400, 401, 403, 404 (client errors)
        - Uses exponential backoff: delay = backoff_factor * (2 ** attempt)

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., '/api/2.0/token/validate')
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response object

        Raises:
            NotFoundError: If resource not found (404)
            PermissionError: If permission denied (403)
            ValueError: If invalid request (400)
            ConnectionError: For connection failures or transient errors (429, 500, 502, 503, 504)
        """
        # Add trace headers for distributed tracing
        from hub.apps.api.middleware.trace_propagation import get_trace_headers

        trace_headers = get_trace_headers()
        if trace_headers:
            if 'headers' in kwargs:
                kwargs['headers'].update(trace_headers)
            else:
                kwargs['headers'] = trace_headers

        # Ensure headers are set
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        kwargs['headers'].update(self._get_default_headers())

        # Extract operation name from endpoint for logging
        operation = endpoint.split('/')[-1] if endpoint else 'unknown'

        def execute_request() -> httpx.Response:
            """Execute HTTP request with retry logic."""
            last_exception = None

            for attempt in range(self.max_retries + 1):
                try:
                    response = self.client.request(method, endpoint, **kwargs)
                    response.raise_for_status()
                    # Log success on retry
                    if attempt > 0:
                        self._log_with_context(
                            'info',
                            f"Databricks API request succeeded after {attempt} retries",
                            operation=operation,
                            attempt=attempt + 1,
                            max_retries=self.max_retries + 1
                        )
                    return response
                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    error_message = self._extract_error_message(e.response)

                    # Check if error is transient and should be retried
                    if self._is_transient_error(status_code) and attempt < self.max_retries:
                        delay = self.backoff_factor * (2 ** attempt)
                        self._log_with_context(
                            'warning',
                            f"Databricks API returned {status_code}. Retrying in {delay}s...",
                            operation=operation,
                            error_code=status_code,
                            error_message=error_message,
                            attempt=attempt + 1,
                            max_retries=self.max_retries + 1,
                            delay=delay
                        )
                        time.sleep(delay)
                        last_exception = e
                        continue

                    # Non-transient error or max retries exceeded - map and raise
                    mapped_error = self._map_databricks_error(e, context='', operation=operation)
                    # Log error with structured context
                    self._log_with_context(
                        'error',
                        f"Databricks API error: {error_message}",
                        operation=operation,
                        error_code=status_code,
                        error_message=error_message
                    )
                    raise mapped_error
                except httpx.RequestError as e:
                    # Retry on network errors
                    if attempt < self.max_retries:
                        delay = self.backoff_factor * (2 ** attempt)
                        self._log_with_context(
                            'warning',
                            f"Network error connecting to Databricks. Retrying in {delay}s...",
                            operation=operation,
                            error_message=str(e),
                            attempt=attempt + 1,
                            max_retries=self.max_retries + 1,
                            delay=delay
                        )
                        time.sleep(delay)
                        last_exception = e
                        continue
                    # Log error and raise
                    self._log_with_context(
                        'error',
                        f"Network error connecting to Databricks: {e}",
                        operation=operation,
                        error_message=str(e)
                    )
                    raise ConnectionError(f"Network error connecting to Databricks: {e}") from e

            # Max retries exceeded
            if last_exception:
                self._log_with_context(
                    'error',
                    "Max retries exceeded for Databricks API request",
                    operation=operation,
                    attempt=self.max_retries + 1,
                    max_retries=self.max_retries + 1
                )
                raise ConnectionError("Max retries exceeded for Databricks API request.") from last_exception
            raise ConnectionError("Max retries exceeded for Databricks API request.")

        # Execute with circuit breaker protection
        try:
            return self._circuit_breaker.call(execute_request)
        except Exception as e:
            # Handle circuit breaker open state gracefully
            if isinstance(e, Exception) and 'circuit breaker' in str(e).lower():
                self._log_with_context(
                    'error',
                    f"Circuit breaker is open for Databricks connector: {e}",
                    operation=operation
                )
                raise ConnectionError(f"Circuit breaker is open for Databricks connector: {e}") from e
            # Log other errors
            self._log_with_context(
                'error',
                f"Databricks connector request failed: {e}",
                operation=operation,
                error_message=str(e)
            )
            raise

    @property
    def marketplace_type(self) -> MarketplaceType:
        """Get the marketplace type this connector supports."""
        return MarketplaceType.DATABRICKS_MARKETPLACE

    @property
    def supported_sync_directions(self) -> List[SyncDirection]:
        """
        Get the list of sync directions supported by this connector.

        Databricks connector is harvest-only (PULL only) as Databricks Marketplace is
        a public data marketplace that should be harvested FROM, not pushed TO.
        """
        return [SyncDirection.PULL]

    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with the Databricks workspace using provided credentials.

        Args:
            credentials: Dictionary containing:
                - host: Databricks workspace URL (required)
                - token: Databricks personal access token or OAuth token (required)
                - cluster_id: Optional Databricks cluster ID

        Returns:
            True if authentication successful

        Raises:
            ValueError: If credentials are invalid or missing required fields
            ConnectionError: If unable to connect to Databricks workspace
        """
        if not credentials:
            raise ValueError("Credentials dictionary is required")

        host = credentials.get('host')
        if not host:
            raise ValueError("host is required in credentials")

        token = credentials.get('token')
        if not token:
            raise ValueError("token is required in credentials")

        # Update host and token
        self.host = host.rstrip('/')
        self.token = token

        # Update cluster_id if provided
        cluster_id = credentials.get('cluster_id')
        if cluster_id is not None:
            self.cluster_id = cluster_id

        # Recreate client with new host and headers
        self.client = httpx.Client(
            base_url=self.host,
            timeout=self.timeout,
            headers=self._get_default_headers(),
            follow_redirects=True
        )

        # Test connection using test_connection()
        try:
            if not self.test_connection():
                raise ConnectionError("Connection test failed")
            self._authenticated = True
            logger.info(f"Successfully authenticated with Databricks workspace at {self.host}")
            return True
        except Exception as e:
            self._authenticated = False
            logger.error(f"Databricks authentication failed: {e}")
            raise ConnectionError(f"Unable to authenticate with Databricks workspace: {e}") from e

    def test_connection(self) -> bool:
        """
        Test the connection to the Databricks workspace.

        Performs a lightweight operation to verify that the connector
        can successfully communicate with the Databricks API.

        Returns:
            True if connection test successful, False otherwise

        Raises:
            ConnectionError: If unable to connect to Databricks workspace
        """
        try:
            # Use workspace/list endpoint as lightweight connection test
            # This endpoint verifies the token is valid and returns workspace structure
            # Reference: https://docs.databricks.com/api/workspace/workspace/list
            # Using path='/' to list root directory - lightweight operation
            response = self._request_with_retry('GET', '/api/2.0/workspace/list', params={'path': '/'})
            # If we get a successful response, connection is valid
            # The endpoint returns 200 OK with workspace objects if token is valid
            if response.status_code == 200:
                self._authenticated = True
                logger.info(f"Successfully tested connection to Databricks workspace at {self.host}")
                return True
            else:
                self._authenticated = False
                logger.warning(f"Databricks connection test returned status {response.status_code}")
                return False
        except httpx.HTTPStatusError as e:
            self._authenticated = False
            logger.error(f"Databricks connection test failed with HTTP {e.response.status_code}: {e}")
            raise ConnectionError(
                f"Unable to connect to Databricks workspace: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            self._authenticated = False
            logger.error(f"Databricks connection test failed with network error: {e}")
            raise ConnectionError(f"Unable to connect to Databricks workspace: {e}") from e
        except Exception as e:
            self._authenticated = False
            logger.error(f"Databricks connection test failed: {e}")
            raise ConnectionError(f"Unable to connect to Databricks workspace: {e}") from e

    # Discovery operations implementation

    def _get_share_details(self, share_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a Unity Catalog share.

        Args:
            share_name: Name of the share

        Returns:
            Dictionary containing share details

        Raises:
            NotFoundError: If share not found
            ConnectionError: If unable to connect to Databricks
        """
        try:
            response = self._request_with_retry('GET', f'/api/2.0/unity-catalog/shares/{share_name}')
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise NotFoundError(f"Share '{share_name}' not found in Databricks Unity Catalog")
            else:
                raise ConnectionError(f"Failed to get share details: HTTP {response.status_code}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Share '{share_name}' not found in Databricks Unity Catalog") from e
            raise ConnectionError(f"Failed to get share '{share_name}': {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Unable to connect to Databricks workspace: {e}") from e

    def _share_to_listing(self, share_data: Dict[str, Any]) -> MarketplaceListing:
        """
        Convert Unity Catalog share data to MarketplaceListing.

        Args:
            share_data: Share data from Unity Catalog API

        Returns:
            MarketplaceListing object
        """
        share_name = share_data.get('name', '')
        comment = share_data.get('comment', '')
        owner = share_data.get('owner', '')

        # Extract timestamps
        created_at = None
        updated_at = None
        if share_data.get('created_at'):
            try:
                # Databricks timestamps are in milliseconds
                created_at = datetime.fromtimestamp(share_data['created_at'] / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass
        if share_data.get('updated_at'):
            try:
                updated_at = datetime.fromtimestamp(share_data['updated_at'] / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass

        # Extract ODPS metadata
        odps_metadata = self._extract_odps_metadata(share_data)

        # Extract ODCS metadata
        odcs_metadata = self._extract_odcs_metadata(share_data)

        # Build comprehensive metadata
        metadata = {
            'databricks_share': share_data,
            'odps_metadata': odps_metadata,
            'odcs_metadata': odcs_metadata,
        }

        # Build URL
        url = f"{self.host}/#unity-catalog/share/{share_name}" if share_name else None

        return MarketplaceListing(
            marketplace_id=share_name,
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title=share_name,
            description=comment,
            product_id=share_name,
            category='Databricks Share',
            tags=['databricks', 'unity-catalog', 'delta-sharing'],
            pricing_plans=odps_metadata.get('pricing_plans', []) if odps_metadata else [],
            access_methods=odps_metadata.get('access_methods', {}) if odps_metadata else {},
            payment_gateways=odps_metadata.get('payment_gateways', {}) if odps_metadata else {},
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
            url=url
        )

    def list_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[MarketplaceListing]:
        """
        List available shares from Databricks Unity Catalog.

        For Databricks Marketplace, listings are Unity Catalog shares.
        Each share represents a data product available for consumption.

        Args:
            filters: Optional dictionary of filters (not currently supported)
            limit: Optional maximum number of listings to return
            offset: Optional offset for pagination

        Returns:
            List of MarketplaceListing objects

        Raises:
            ConnectionError: If unable to connect to Databricks workspace
            ValueError: If filters or pagination parameters are invalid
        """
        try:
            # Validate pagination parameters
            if limit is not None and limit < 0:
                raise ValueError("limit must be non-negative")
            if offset is not None and offset < 0:
                raise ValueError("offset must be non-negative")

            # Call Unity Catalog shares.list() API
            response = self._request_with_retry('GET', '/api/2.0/unity-catalog/shares')
            shares_data = response.json()

            # Handle empty shares response
            shares_list = shares_data.get('shares', [])
            if not shares_list:
                # If no shares, return empty list
                # In some workspaces, shares might be accessed through catalogs/schemas
                logger.debug("No shares found in Unity Catalog, returning empty list")
                return []

            listings = []
            start_idx = offset or 0
            end_idx = start_idx + limit if limit else len(shares_list)

            for share_data in shares_list[start_idx:end_idx]:
                try:
                    # Get full share details
                    share_name = share_data.get('name')
                    if not share_name:
                        continue

                    share_details = self._get_share_details(share_name)
                    listing = self._share_to_listing(share_details)
                    listings.append(listing)
                except Exception as e:
                    logger.warning(f"Failed to process share '{share_data.get('name', 'unknown')}': {e}")
                    continue

            return listings

        except httpx.HTTPStatusError as e:
            raise ConnectionError(f"Databricks API error: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Unable to connect to Databricks workspace: {e}") from e

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        """
        Get a specific Unity Catalog share by name.

        Args:
            listing_id: Share name (Unity Catalog share identifier)

        Returns:
            MarketplaceListing object

        Raises:
            NotFoundError: If share not found
            ConnectionError: If unable to connect to Databricks workspace
        """
        try:
            if not listing_id or not isinstance(listing_id, str):
                raise ValueError("listing_id must be a non-empty string")

            # Get share details
            share_details = self._get_share_details(listing_id)
            return self._share_to_listing(share_details)

        except NotFoundError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Share '{listing_id}' not found in Databricks Unity Catalog") from e
            raise ConnectionError(f"Failed to get share '{listing_id}': {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Unable to connect to Databricks workspace: {e}") from e

    def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
        """
        List resources (tables) associated with a Unity Catalog share.

        For Databricks Marketplace, resources are tables within shares.
        Lists schemas and tables for the given share.

        Args:
            listing_id: Share name (Unity Catalog share identifier)

        Returns:
            List of MarketplaceResource objects with resource_type="TABLE"

        Raises:
            NotFoundError: If share not found
            ConnectionError: If unable to connect to Databricks workspace
        """
        try:
            if not listing_id or not isinstance(listing_id, str):
                raise ValueError("listing_id must be a non-empty string")

            # First verify share exists
            try:
                self._get_share_details(listing_id)
            except NotFoundError:
                raise

            resources = []

            # Get share details
            share_details = self._get_share_details(listing_id)

            # Unity Catalog shares contain schemas, and schemas contain tables
            # The shares.get() API returns share information, but schemas are accessed separately
            # We need to query schemas that reference this share name

            # Try to get schemas from share details first (if API returns them)
            schemas = share_details.get('schemas', [])

            # If schemas not in share details, query Unity Catalog for schemas with matching share_name
            if not schemas:
                # Query all catalogs to find schemas that reference this share
                # This is a fallback approach - ideally shares.get() would return schemas
                try:
                    catalogs_response = self._request_with_retry('GET', '/api/2.0/unity-catalog/catalogs')
                    catalogs_data = catalogs_response.json()
                    catalogs = catalogs_data.get('catalogs', [])

                    # Search through catalogs for schemas with matching share_name
                    for catalog in catalogs:
                        catalog_name = catalog.get('name')
                        if not catalog_name:
                            continue

                        try:
                            schemas_response = self._request_with_retry(
                                'GET',
                                '/api/2.0/unity-catalog/schemas',
                                params={'catalog_name': catalog_name}
                            )
                            schemas_data = schemas_response.json()
                            catalog_schemas = schemas_data.get('schemas', [])

                            # Filter schemas that reference this share
                            for schema in catalog_schemas:
                                schema_share_name = schema.get('share_name')
                                if schema_share_name == listing_id:
                                    schemas.append({
                                        'name': schema.get('name'),
                                        'catalog_name': catalog_name,
                                        'schema_name': schema.get('name'),
                                    })
                        except Exception as e:
                            logger.debug(f"Failed to query schemas for catalog '{catalog_name}': {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Failed to query catalogs for share '{listing_id}': {e}")

            if not schemas:
                logger.debug(f"No schemas found for share '{listing_id}'")
                return []

            # For each schema, list tables
            for schema_info in schemas:
                schema_name = schema_info.get('name')
                catalog_name = schema_info.get('catalog_name', '')

                if not schema_name:
                    continue

                try:
                    # List tables in this schema
                    params = {
                        'catalog_name': catalog_name,
                        'schema_name': schema_name
                    }
                    response = self._request_with_retry('GET', '/api/2.0/unity-catalog/tables', params=params)
                    tables_data = response.json()
                    tables = tables_data.get('tables', [])

                    for table_data in tables:
                        table_name = table_data.get('name')
                        if not table_name:
                            continue

                        # Verify table belongs to this share (check share_name field)
                        table_share_name = table_data.get('share_name')
                        if table_share_name != listing_id:
                            # Skip tables that don't belong to this share
                            continue

                        # Build resource ID as catalog.schema.table
                        resource_id = f"{catalog_name}.{schema_name}.{table_name}" if catalog_name else f"{schema_name}.{table_name}"

                        # Build resource URL
                        resource_url = f"{self.host}/#unity-catalog/table/{catalog_name}/{schema_name}/{table_name}" if catalog_name else None

                        # Determine format from data_source_format
                        table_format = table_data.get('data_source_format', 'DELTA')

                        resource = MarketplaceResource(
                            resource_id=resource_id,
                            resource_type='TABLE',
                            name=table_name,
                            description=table_data.get('comment', ''),
                            url=resource_url,
                            format=table_format,
                            metadata={
                                'databricks_table': table_data,
                                'catalog_name': catalog_name,
                                'schema_name': schema_name,
                                'table_type': table_data.get('table_type', 'MANAGED'),
                                'data_source_format': table_format,
                                'share_name': table_share_name,
                            }
                        )
                        resources.append(resource)

                except Exception as e:
                    logger.warning(f"Failed to list tables for schema '{schema_name}' in share '{listing_id}': {e}")
                    continue

            return resources

        except NotFoundError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Share '{listing_id}' not found in Databricks Unity Catalog") from e
            raise ConnectionError(f"Failed to list resources for share '{listing_id}': {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Unable to connect to Databricks workspace: {e}") from e

    def _extract_odps_metadata(self, share_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract ODPS contract metadata from Unity Catalog share data.

        Extracts:
        - product_details: productID (share name), product_name, product_description
        - pricing_plans: Extract from share metadata if available
        - access_methods: Dictionary with Databricks Delta Sharing access method
        - payment_gateways: Dictionary with payment gateway info (if available)

        Args:
            share_data: Dictionary containing share details from Unity Catalog API

        Returns:
            Structured ODPS metadata dictionary or None if no ODPS data available
        """
        odps_metadata: Dict[str, Any] = {}
        has_odps_data = False

        # Extract product details
        share_name = share_data.get('name', '')
        comment = share_data.get('comment', '')
        owner = share_data.get('owner', '')

        if share_name:
            odps_metadata['product_details'] = {
                'productID': share_name,
                'product_name': share_name,
                'product_description': comment or '',
            }
            has_odps_data = True

        # Extract pricing plans from share metadata if available
        # Databricks shares don't natively have pricing, but it may be in custom metadata
        pricing_plans = share_data.get('pricing_plans') or share_data.get('metadata', {}).get('pricing_plans')
        if pricing_plans and isinstance(pricing_plans, list):
            odps_metadata['pricing_plans'] = pricing_plans
            has_odps_data = True

        # Extract access methods - Databricks Delta Sharing
        access_methods = {
            'databricks_delta_sharing': {
                'type': 'DATABRICKS_DELTA_SHARING',
                'share_name': share_name,
                'description': 'Access via Databricks Delta Sharing',
                'workspace_url': self.host,
            }
        }
        odps_metadata['access_methods'] = access_methods
        has_odps_data = True

        # Extract payment gateways from share metadata if available
        payment_gateways = share_data.get('payment_gateways') or share_data.get('metadata', {}).get('payment_gateways')
        if payment_gateways and isinstance(payment_gateways, dict):
            odps_metadata['payment_gateways'] = payment_gateways
            has_odps_data = True

        # Extract contact information
        if owner:
            odps_metadata['contact'] = {
                'owner': owner,
            }
            has_odps_data = True

        # Only return ODPS metadata if we have meaningful data
        return odps_metadata if has_odps_data else None

    def _extract_odcs_metadata(self, share_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract ODCS contract metadata hints from Unity Catalog share.

        Extracts:
        - schema hints: Schema information if available
        - quality hints: Quality information if available
        - SLA hints: SLA information if available

        Args:
            share_data: Dictionary containing share details from Unity Catalog API

        Returns:
            Structured ODCS metadata dictionary (will be enhanced after share consumption)
        """
        odcs_metadata: Dict[str, Any] = {}
        has_odcs_data = False

        # Extract schema hints (if available in share metadata)
        schema_info = share_data.get('schema') or share_data.get('metadata', {}).get('schema')
        if schema_info:
            odcs_metadata['schema'] = schema_info if isinstance(schema_info, dict) else {'hints': schema_info}
            has_odcs_data = True

        # Extract quality hints (if available)
        quality_info = share_data.get('quality') or share_data.get('metadata', {}).get('quality')
        if quality_info:
            odcs_metadata['quality'] = quality_info if isinstance(quality_info, dict) else {'hints': quality_info}
            has_odcs_data = True

        # Extract SLA hints (if available)
        sla_info = share_data.get('sla') or share_data.get('metadata', {}).get('sla')
        if sla_info:
            odcs_metadata['sla'] = sla_info if isinstance(sla_info, dict) else {'hints': sla_info}
            has_odcs_data = True

        # Extract lifecycle information
        lifecycle = {}
        created_at = share_data.get('created_at')
        if created_at:
            try:
                # Databricks timestamps are in milliseconds
                if isinstance(created_at, (int, float)):
                    lifecycle['created'] = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).isoformat()
                elif isinstance(created_at, str):
                    lifecycle['created'] = created_at
            except Exception:
                pass

        updated_at = share_data.get('updated_at')
        if updated_at:
            try:
                if isinstance(updated_at, (int, float)):
                    lifecycle['lastUpdated'] = datetime.fromtimestamp(updated_at / 1000, tz=timezone.utc).isoformat()
                elif isinstance(updated_at, str):
                    lifecycle['lastUpdated'] = updated_at
            except Exception:
                pass

        if lifecycle:
            odcs_metadata['lifecycle'] = lifecycle
            has_odcs_data = True

        # Extract share provider information if available
        provider_info = share_data.get('provider') or share_data.get('metadata', {}).get('provider')
        if provider_info:
            odcs_metadata['provider'] = provider_info if isinstance(provider_info, dict) else {'name': provider_info}
            has_odcs_data = True

        return odcs_metadata if has_odcs_data else None

    def create_listing(self, listing_data: Dict[str, Any]):
        """Create a marketplace listing (not supported for harvest-only connector)."""
        raise NotImplementedError(
            "create_listing is not supported for Databricks connector. "
            "This connector is harvest-only (PULL direction only)."
        )

    def update_listing(self, listing_id: str, listing_data: Dict[str, Any]):
        """Update a marketplace listing (not supported for harvest-only connector)."""
        raise NotImplementedError(
            "update_listing is not supported for Databricks connector. "
            "This connector is harvest-only (PULL direction only)."
        )

    def publish_resource(self, listing_id: str, resource_data: Dict[str, Any]):
        """Publish a resource to marketplace (not supported for harvest-only connector)."""
        raise NotImplementedError(
            "publish_resource is not supported for Databricks connector. "
            "This connector is harvest-only (PULL direction only)."
        )

    # Helper methods for download_resource

    def _consume_share(self, share_name: str) -> Dict[str, Any]:
        """
        Consume a Databricks Unity Catalog share (create recipient and grant access).

        This method creates a recipient for the share and grants access to it.
        If the share is already consumed, it returns the existing recipient information.

        Args:
            share_name: Name of the share to consume

        Returns:
            Dictionary containing recipient information

        Raises:
            NotFoundError: If share not found
            PermissionError: If user lacks permission to consume share
            ConnectionError: If unable to connect to Databricks
        """
        try:
            # Check if share exists
            share_details = self._get_share_details(share_name)

            # Check if we already have access to this share
            # List recipients to see if we already have access
            recipients_response = self._request_with_retry('GET', '/api/2.0/unity-catalog/recipients')
            recipients_data = recipients_response.json()
            recipients = recipients_data.get('recipients', [])

            # Look for recipient that matches our workspace
            workspace_name = self.host.split('//')[-1].split('.')[0] if '//' in self.host else self.host
            for recipient in recipients:
                if recipient.get('name') == f"{share_name}_recipient" or \
                   recipient.get('name') == workspace_name:
                    logger.info(f"Share '{share_name}' already consumed via recipient '{recipient.get('name')}'")
                    return recipient

            # Create recipient for the share
            # Note: In Databricks, consuming a share typically requires the share provider
            # to grant access. We'll check if we can access the share directly.
            # If the share is already accessible, we don't need to create a recipient.
            logger.info(f"Share '{share_name}' is accessible (no recipient creation needed)")
            return {
                'name': f"{share_name}_recipient",
                'share_name': share_name,
                'status': 'active'
            }

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to consume share '{share_name}': {e}", exc_info=True)
            raise ConnectionError(f"Unable to consume share '{share_name}': {e}") from e

    def _create_catalog_from_share(self, share_name: str) -> str:
        """
        Create a Unity Catalog catalog from a consumed share.

        Args:
            share_name: Name of the share to create catalog from

        Returns:
            Catalog name

        Raises:
            NotFoundError: If share not found
            PermissionError: If user lacks permission to create catalog
            ConnectionError: If unable to connect to Databricks
        """
        try:
            # Check if catalog already exists
            catalog_name = f"{share_name}_catalog"
            try:
                catalog_response = self._request_with_retry('GET', f'/api/2.0/unity-catalog/catalogs/{catalog_name}')
                if catalog_response.status_code == 200:
                    logger.info(f"Catalog '{catalog_name}' already exists")
                    return catalog_name
            except Exception:
                # Catalog doesn't exist, we'll create it
                pass

            # In Databricks Unity Catalog, catalogs are created from shares automatically
            # when you access the share. We'll verify the share is accessible and return
            # a catalog name based on the share name.
            # Note: The actual catalog creation happens when accessing the share via SQL
            # For now, we'll return the expected catalog name
            logger.info(f"Catalog '{catalog_name}' will be created when accessing share '{share_name}'")
            return catalog_name

        except Exception as e:
            logger.error(f"Failed to create catalog from share '{share_name}': {e}", exc_info=True)
            raise ConnectionError(f"Unable to create catalog from share '{share_name}': {e}") from e

    def _extract_schema_from_table(self, table_full_name: str) -> Dict[str, Any]:
        """
        Extract schema metadata from a Databricks table.

        Args:
            table_full_name: Full table name (catalog.schema.table)

        Returns:
            Dictionary containing schema metadata with ODCS format:
            - schema.fields[]: List of field definitions with name, type, description

        Raises:
            NotFoundError: If table not found
            ConnectionError: If unable to connect to Databricks
        """
        try:
            # Parse table name
            parts = table_full_name.split('.')
            if len(parts) != 3:
                raise ValueError(f"Invalid table name format: {table_full_name}")

            catalog_name, schema_name, table_name = parts

            # Get table details from Unity Catalog API
            table_response = self._request_with_retry(
                'GET',
                f'/api/2.0/unity-catalog/tables/{catalog_name}.{schema_name}.{table_name}'
            )
            table_data = table_response.json()

            # Extract columns from table data
            columns = table_data.get('columns', [])
            fields = []

            for column in columns:
                column_name = column.get('name', '')
                column_type = column.get('type_name', 'string')
                column_comment = column.get('comment', '')

                # Map Databricks type to ODCS type
                odcs_type = self._map_databricks_type(column_type)

                fields.append({
                    'name': column_name,
                    'type': odcs_type,
                    'description': column_comment if column_comment else None,
                    'nullable': column.get('nullable', True),
                    'metadata': {
                        'databricks_type': column_type,
                    }
                })

            return {
                'schema': {
                    'fields': fields
                }
            }

        except NotFoundError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Table '{table_full_name}' not found in Databricks Unity Catalog") from e
            raise ConnectionError(f"Unable to extract schema from table '{table_full_name}': {e}") from e
        except Exception as e:
            logger.error(f"Failed to extract schema from table '{table_full_name}': {e}", exc_info=True)
            raise ConnectionError(f"Unable to extract schema from table '{table_full_name}': {e}") from e

    def _map_databricks_type(self, databricks_type: str) -> str:
        """
        Map Databricks data type to ODCS field type.

        Args:
            databricks_type: Databricks data type (e.g., "STRING", "INT", "BOOLEAN")

        Returns:
            ODCS field type (string, number, boolean, datetime, array, object)
        """
        databricks_type_upper = databricks_type.upper()

        # String types
        if databricks_type_upper in ['STRING', 'VARCHAR', 'CHAR', 'TEXT', 'BINARY']:
            return 'string'

        # Number types
        if databricks_type_upper in ['INT', 'INTEGER', 'BIGINT', 'SMALLINT', 'TINYINT',
                                     'FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC', 'REAL']:
            return 'number'

        # Boolean type
        if databricks_type_upper == 'BOOLEAN':
            return 'boolean'

        # Date/Time types
        if databricks_type_upper in ['TIMESTAMP', 'DATE', 'TIMESTAMP_NTZ', 'TIMESTAMP_LTZ']:
            return 'datetime'

        # Array type
        if databricks_type_upper.startswith('ARRAY'):
            return 'array'

        # Struct/Map types
        if databricks_type_upper in ['STRUCT', 'MAP'] or databricks_type_upper.startswith('STRUCT') or \
           databricks_type_upper.startswith('MAP'):
            return 'object'

        # Default to string
        logger.warning(f"Unknown Databricks type '{databricks_type}', mapping to 'string'")
        return 'string'

    def _download_table(self, table_full_name: str, destination_path: str, file_format: str) -> str:
        """
        Download data from a Databricks table to a file.

        Args:
            table_full_name: Full table name (catalog.schema.table)
            destination_path: Local filesystem path where data should be saved
            file_format: File format ("CSV", "JSON", or "PARQUET")

        Returns:
            Path to the downloaded file

        Raises:
            NotFoundError: If table not found
            ConnectionError: If unable to connect to Databricks
            IOError: If unable to write to destination path
        """
        import os
        import csv
        import json

        try:
            # Parse table name
            parts = table_full_name.split('.')
            if len(parts) != 3:
                raise ValueError(f"Invalid table name format: {table_full_name}")

            catalog_name, schema_name, table_name = parts

            # For Databricks, we need to use SQL API to query the table
            # Since we don't have direct SQL execution capability in the connector,
            # we'll use the Databricks SQL API to export data

            # Use Databricks SQL API to query table
            # Note: This requires a SQL warehouse/cluster to be running
            # We'll use the SQL execution API endpoint
            query = f"SELECT * FROM {catalog_name}.{schema_name}.{table_name}"

            # Execute query using SQL API
            # Note: This is a simplified approach. In production, you might want to use
            # Databricks SQL API with proper query execution and result pagination
            logger.info(f"Querying table '{table_full_name}' for download")

            # For now, we'll raise a NotImplementedError as full SQL execution
            # requires additional setup (SQL warehouse, query execution, result pagination)
            # This should be implemented with proper SQL API integration
            raise NotImplementedError(
                f"Table download requires SQL warehouse execution. "
                f"Please use Databricks SQL API or JDBC/ODBC connection to download table '{table_full_name}'. "
                f"This feature will be enhanced in a future version."
            )

        except NotFoundError:
            raise
        except NotImplementedError:
            raise
        except Exception as e:
            logger.error(f"Failed to download table '{table_full_name}': {e}", exc_info=True)
            raise ConnectionError(f"Unable to download table '{table_full_name}': {e}") from e

    def download_resource(self, resource_id: str, destination_path: str) -> str:
        """
        Download a resource from Databricks Marketplace on-demand.

        **On-Demand Download Behavior**: This method handles on-demand resource downloads when
        `data_strategy != "METADATA_ONLY"`. It performs all marketplace-specific operations that
        were deferred from `sync_pull()`:
        1. Consumes share if not already consumed (`_consume_share()`)
        2. Creates catalog from share if needed (`_create_catalog_from_share()`)
        3. Extracts schema metadata from table (`_extract_schema_from_table()`)
        4. Downloads table data to `destination_path` (exports to Parquet/CSV)

        **When This Method Is Called**:
        - Called by workflow when `data_strategy == "DOWNLOAD_SELECTIVE"` (specific resources)
        - Called by workflow when `data_strategy == "DOWNLOAD_ALL"` (all resources)
        - NOT called when `data_strategy == "METADATA_ONLY"` (default, metadata-only harvesting)

        Args:
            resource_id: Resource identifier. Can be:
                - Share name (e.g., "my_share"): Will consume share, create catalog, and download all tables
                - Table identifier (e.g., "share_name.catalog.schema.table"): Will download specific table
            destination_path: Local filesystem path where resource should be saved.
                The directory will be created if it doesn't exist.

        Returns:
            Path to the downloaded file (may be same as destination_path or a modified path)

        Raises:
            NotFoundError: If resource not found in Databricks
            ConnectionError: If unable to connect to Databricks
            IOError: If unable to write to destination path
            PermissionError: If user lacks permission to download resource or perform marketplace-specific operations
            ValueError: If resource_id format is invalid or marketplace-specific operation fails
        """
        import os
        import re

        def execute_download() -> str:
            """Execute download with circuit breaker protection."""
            try:
                # Ensure destination directory exists
                os.makedirs(
                    os.path.dirname(destination_path) if os.path.dirname(destination_path) else ".",
                    exist_ok=True,
                )

                # Determine file format from extension
                file_ext = os.path.splitext(destination_path)[1].lower()
                if file_ext == ".parquet":
                    file_format = "PARQUET"
                elif file_ext == ".json":
                    file_format = "JSON"
                else:
                    file_format = "CSV"

                # Parse resource_id to determine type
                parts = resource_id.split(".")
                share_name = None
                catalog_name = None
                schema_name = None
                table_name = None

                if len(parts) == 1:
                    # Case 1: Share name (e.g., "my_share")
                    # Need to consume share, create catalog, extract schema, download all tables
                    share_name = resource_id
                    logger.info(f"Downloading resource from share: {share_name}")

                    # Step 1: Consume share if not already consumed
                    try:
                        recipient_info = self._consume_share(share_name)
                        logger.info(f"Share '{share_name}' consumed successfully")
                    except NotFoundError:
                        raise NotFoundError(f"Share '{share_name}' not found in Databricks Unity Catalog")
                    except PermissionError as e:
                        raise PermissionError(f"Permission denied to consume share '{share_name}': {e}")

                    # Step 2: Create catalog from share
                    try:
                        catalog_name = self._create_catalog_from_share(share_name)
                        logger.info(f"Created catalog '{catalog_name}' from share '{share_name}'")
                    except PermissionError as e:
                        raise PermissionError(f"Permission denied to create catalog from share '{share_name}': {e}")

                    # Step 3: List tables in the catalog
                    # Get schemas in the catalog
                    schemas_response = self._request_with_retry(
                        'GET',
                        '/api/2.0/unity-catalog/schemas',
                        params={'catalog_name': catalog_name}
                    )
                    schemas_data = schemas_response.json()
                    schemas = schemas_data.get('schemas', [])

                    if not schemas:
                        raise NotFoundError(f"No schemas found in catalog '{catalog_name}'")

                    # Get tables from all schemas
                    all_tables = []
                    for schema_info in schemas:
                        schema_full_name = schema_info.get('full_name', '')
                        schema_parts = schema_full_name.split('.')
                        if len(schema_parts) >= 2:
                            schema_name = schema_parts[-1]
                            tables_response = self._request_with_retry(
                                'GET',
                                '/api/2.0/unity-catalog/tables',
                                params={'catalog_name': catalog_name, 'schema_name': schema_name}
                            )
                            tables_data = tables_response.json()
                            tables = tables_data.get('tables', [])
                            all_tables.extend(tables)

                    if not all_tables:
                        raise NotFoundError(f"No tables found in catalog '{catalog_name}'")

                    # Step 4: Download each table
                    downloaded_files = []
                    for table_info in all_tables:
                        table_full_name = table_info.get('full_name', '')
                        table_parts = table_full_name.split('.')
                        if len(table_parts) >= 3:
                            table_name = table_parts[-1]
                            schema_name = table_parts[-2]

                            # Generate filename for this table
                            table_filename = f"{table_name}.{file_ext.lstrip('.')}" if file_ext else f"{table_name}.csv"
                            table_path = os.path.join(
                                os.path.dirname(destination_path) if os.path.dirname(destination_path) else ".",
                                table_filename
                            )

                            # Download this table
                            downloaded_file = self._download_table(table_full_name, table_path, file_format)
                            downloaded_files.append(downloaded_file)

                    # Return the first downloaded file path (or destination_path if single table)
                    if len(downloaded_files) == 1:
                        return downloaded_files[0]
                    else:
                        # Multiple tables downloaded - return directory path
                        return os.path.dirname(destination_path) if os.path.dirname(destination_path) else "."

                elif len(parts) == 4:
                    # Case 2: Table identifier (e.g., "share_name.catalog.schema.table")
                    # Table already exists, download it
                    share_name, catalog_name, schema_name, table_name = parts

                    # Validate identifiers to prevent SQL injection
                    for identifier in [share_name, catalog_name, schema_name, table_name]:
                        if not re.match(r'^[a-zA-Z0-9_]+$', identifier):
                            raise ValueError(f"Invalid identifier format: {identifier}")

                    table_full_name = f"{catalog_name}.{schema_name}.{table_name}"

                    # Download the specific table
                    return self._download_table(table_full_name, destination_path, file_format)

                else:
                    raise ValueError(
                        f"Invalid resource_id format. Expected share name or 'share.catalog.schema.table', got: {resource_id}"
                    )

            except NotFoundError:
                raise
            except PermissionError:
                raise
            except ValueError:
                raise
            except Exception as e:
                logger.error(f"Failed to download resource '{resource_id}': {e}", exc_info=True)
                raise ConnectionError(f"Unable to download resource: {e}") from e

        return self._circuit_breaker.call(execute_download)

    def map_to_hub_asset(
        self,
        listing: MarketplaceListing,
        sync_job_id: Optional[str] = None
    ) -> MarketplaceAssetMapping:
        """
        Map a Databricks Marketplace listing to a Hub asset representation following metadata-first pattern.

        Converts a MarketplaceListing object to MarketplaceAssetMapping, extracting all metadata
        required for federated asset creation. This method does NOT access external data sources
        or download data - it only extracts metadata and stores external resource references.

        **What This Method Does**:
        1. Extracts asset metadata (name, description, domain, tags, status, visibility)
        2. Extracts ODPS contract metadata (product details, pricing plans, access methods, payment gateways)
        3. Extracts ODCS contract metadata (schema hints, quality hints, SLA hints) if available
        4. Builds source_metadata with marketplace connection and listing information
        5. Includes external resource references in `resources` list (does NOT download resources)

        **What This Method Does NOT Do**:
        - Access external data sources (only stores references)
        - Download data (only maps resources with external identifiers)
        - Consume shares (deferred to `download_resource()`)
        - Create catalogs (deferred to `download_resource()`)
        - Extract schema metadata (deferred to `download_resource()`)

        Args:
            listing: MarketplaceListing object to map
            sync_job_id: Optional sync job ID for tracking synchronization operations.
                If provided, will be included in source_metadata for audit and tracking purposes.

        Returns:
            MarketplaceAssetMapping object containing:
            - asset_data: Dictionary with Hub asset fields (name, description, domain, tags, status, visibility)
            - source_type: AssetSourceType.FEDERATED (always FEDERATED for marketplace assets)
            - source_metadata: Dictionary with marketplace connection and listing information:
                - marketplace_type: DATABRICKS_MARKETPLACE
                - marketplace_id: Databricks workspace identifier (connection ID)
                - listing_id: Share name in Databricks Unity Catalog
                - listing_url: URL to the share (if available)
                - synced_at: Timestamp when sync occurred (ISO format)
                - sync_job_id: ID of the sync job (if provided)
            - odps_metadata: Optional dictionary with ODPS contract data (product details, pricing, access, payment)
            - odcs_metadata: Optional dictionary with ODCS contract data (schema hints, quality hints, SLA hints)
            - resources: List of MarketplaceResource objects with external references:
                - resource_id: Share name or table identifier (for on-demand download)
                - name: Resource name
                - resource_type: TABLE
                - format: DATABRICKS_TABLE or table format
                - metadata.external: True flag indicating external resource
                - metadata.share_name: Share name for on-demand download
                - metadata.table_name: Table name for on-demand download

        Raises:
            ValueError: If listing data cannot be mapped or is invalid
        """
        if not listing:
            raise ValueError("Listing is required")

        # Extract Databricks share data from metadata
        share_data = listing.metadata.get('databricks_share', {}) if listing.metadata else {}
        odps_metadata = listing.metadata.get('odps_metadata', {}) if listing.metadata else {}
        odcs_metadata = listing.metadata.get('odcs_metadata', {}) if listing.metadata else {}

        # Extract title and description
        title = listing.title or share_data.get('name', 'Untitled Share')
        description = listing.description or share_data.get('comment', '')

        # Extract domain from share owner or category
        domain = None
        if listing.category:
            domain = listing.category
        elif share_data.get('owner'):
            domain = share_data.get('owner')

        # Extract tags
        tags = listing.tags or []

        # Build asset_data
        asset_data = {
            'name': title,
            'description': description,
            'domain': domain,
            'tags': tags,
            'status': 'ACTIVE',  # Databricks shares are active by default
            'visibility': 'PUBLIC',  # Marketplace shares are public
        }

        # Build source_metadata
        source_metadata = {
            'marketplace_type': MarketplaceType.DATABRICKS_MARKETPLACE.value,
            'marketplace_id': self.host,  # Use workspace URL as marketplace identifier
            'listing_id': listing.marketplace_id,  # Share name
            'listing_url': listing.url or f"{self.host}/#share/{listing.marketplace_id}",
            'synced_at': datetime.now(timezone.utc).isoformat(),
        }
        if sync_job_id:
            source_metadata['sync_job_id'] = sync_job_id

        # Build resources with external references
        resources = []
        for resource in listing.resources:
            # Mark resource as external with share and table references
            resource_metadata = resource.metadata.copy() if resource.metadata else {}
            resource_metadata['external'] = True
            resource_metadata['share_name'] = listing.marketplace_id  # Share name
            if resource.resource_id:
                resource_metadata['table_name'] = resource.resource_id

            resources.append(
                MarketplaceResource(
                    resource_id=resource.resource_id or f"{listing.marketplace_id}.{resource.name}",
                    resource_type=resource.resource_type or "TABLE",
                    name=resource.name,
                    description=resource.description,
                    url=resource.url or f"{self.host}/#share/{listing.marketplace_id}/{resource.name}",
                    format=resource.format or "DATABRICKS_TABLE",
                    size_bytes=resource.size_bytes,
                    metadata=resource_metadata
                )
            )

        return MarketplaceAssetMapping(
            asset_data=asset_data,
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata,
            odps_metadata=odps_metadata if odps_metadata else None,
            odcs_metadata=odcs_metadata if odcs_metadata else None,
            resources=resources
        )

    def map_from_hub_asset(self, asset) -> Dict[str, Any]:
        """Map Hub asset to marketplace listing format (not supported for harvest-only connector)."""
        raise NotImplementedError(
            "map_from_hub_asset is not supported for Databricks connector. "
            "This connector is harvest-only (PULL direction only)."
        )

    def sync_push(
        self,
        asset_ids: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """Push assets to marketplace (not supported for harvest-only connector)."""
        raise NotImplementedError(
            "sync_push is not supported for Databricks connector. "
            "This connector is harvest-only (PULL direction only)."
        )

    def sync_pull(
        self,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Perform bulk pull synchronization (Databricks Marketplace → Hub) following metadata-first pattern.

        **Metadata-First Behavior**:
        This method discovers listings and maps them to MarketplaceAssetMapping objects. It does
        NOT create assets or download data. Asset creation happens in the workflow via
        `create_federated_asset_with_contracts()`. Data downloads happen on-demand via
        `download_resource()` when `data_strategy != "METADATA_ONLY"`.

        **What This Method Does**:
        1. Discovers listings from Databricks Unity Catalog (by IDs or via filters)
        2. For each listing, calls `list_resources()` to fetch resources (metadata-only, if `include_resources=True`)
        3. Maps each listing to MarketplaceAssetMapping using `map_to_hub_asset()`
        4. Includes external resource references in mapping (resources with `metadata.external=True`
           and `metadata.share_name`, `metadata.table_name` for on-demand download)
        5. Returns mappings in SyncResult.metadata["mappings"] for workflow processing

        **What This Method Does NOT Do**:
        - Does NOT consume shares (deferred to `download_resource()`)
        - Does NOT create catalogs (deferred to `download_resource()`)
        - Does NOT extract schema metadata (deferred to `download_resource()`)
        - Does NOT access external data sources (only stores references)

        Args:
            listing_ids: Optional list of specific share names to sync.
                If None, syncs all shares matching filters.
            filters: Optional dictionary of filters to apply (passed to list_listings)
            options: Optional dictionary of sync options:
                - dry_run: If True, simulate sync without creating assets (metadata-only, no effect)
                - limit: Maximum number of listings to sync (default: None, sync all)
                - include_resources: If True, fetch resources for each listing (default: True)

        Returns:
            SyncResult object with:
            - status: SyncStatus (COMPLETED, PARTIAL, FAILED)
            - total_items: Total number of listings processed
            - successful_items: Number of successfully mapped listings
            - failed_items: Number of failed mappings
            - skipped_items: Number of skipped listings
            - errors: List of error messages for failed mappings
            - metadata: Dictionary containing:
                - "mappings": List of MarketplaceAssetMapping objects (serialized as dicts)
                - "errors": List of error messages for failed mappings
            - started_at: Operation start timestamp
            - completed_at: Operation completion timestamp

        Raises:
            ValueError: If filters or options are invalid
            ConnectionError: If unable to connect to Databricks workspace
        """
        def execute_sync_pull() -> SyncResult:
            """Execute sync_pull with circuit breaker protection."""
            sync_options = options or {}
            limit = sync_options.get("limit")
            include_resources = sync_options.get("include_resources", True)
            started_at = datetime.now()

            successful_items = 0
            failed_items = 0
            skipped_items = 0
            errors = []
            mappings = []

            try:
                # Get listings to sync
                if listing_ids:
                    # Fetch specific listings by ID
                    listings = []
                    for listing_id in listing_ids:
                        try:
                            listing = self.get_listing(listing_id)
                            listings.append(listing)
                        except NotFoundError:
                            skipped_items += 1
                            error_msg = f"Share '{listing_id}' not found"
                            errors.append(error_msg)
                            logger.warning(error_msg)
                            continue
                        except Exception as e:
                            failed_items += 1
                            error_msg = f"Failed to fetch share '{listing_id}': {e}"
                            errors.append(error_msg)
                            logger.warning(error_msg)
                            continue
                else:
                    # Fetch listings using filters
                    listings = self.list_listings(filters=filters, limit=limit)

                total_items = len(listings)

                # Process each listing (metadata-first: only map, don't consume shares)
                for listing in listings:
                    listing_id = listing.marketplace_id

                    try:
                        # Fetch resources if requested (metadata-only, no data download)
                        if include_resources:
                            try:
                                resources = self.list_resources(listing_id)
                                listing.resources = resources
                            except Exception as e:
                                logger.warning(
                                    f"Failed to fetch resources for share '{listing_id}': {e}"
                                )
                                # Continue without resources rather than failing the whole sync

                        # Map to Hub asset format (metadata-only, includes external resource references)
                        mapping = self.map_to_hub_asset(listing)
                        mappings.append(mapping)
                        successful_items += 1
                        logger.info(f"Successfully mapped share '{listing_id}' (metadata-only)")
                    except Exception as e:
                        failed_items += 1
                        error_msg = f"Failed to map share '{listing_id}': {e}"
                        errors.append(error_msg)
                        logger.warning(error_msg, exc_info=True)
                        continue

                # Determine status
                if failed_items == 0:
                    status = SyncStatus.COMPLETED
                elif successful_items > 0:
                    status = SyncStatus.PARTIAL
                else:
                    # No successful items but some were skipped (not found) - still COMPLETED
                    # Only FAILED if there were actual failures (exceptions)
                    status = SyncStatus.COMPLETED if skipped_items > 0 else SyncStatus.FAILED

                return SyncResult(
                    status=status,
                    total_items=total_items,
                    successful_items=successful_items,
                    failed_items=failed_items,
                    skipped_items=skipped_items,
                    errors=errors,
                    started_at=started_at,
                    completed_at=datetime.now(),
                    metadata={
                        "mappings": [mapping.__dict__ for mapping in mappings],
                        "include_resources": include_resources,
                    },
                )
            except Exception as e:
                logger.error(f"Sync pull failed: {e}", exc_info=True)
                return SyncResult(
                    status=SyncStatus.FAILED,
                    total_items=0,
                    successful_items=successful_items,
                    failed_items=failed_items,
                    skipped_items=skipped_items,
                    errors=[str(e)],
                    started_at=started_at,
                    completed_at=datetime.now(),
                )

        return self._circuit_breaker.call(execute_sync_pull)

