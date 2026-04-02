"""
GCP Marketplace Connector

Connector implementation for Google Cloud Platform Marketplace (Analytics Hub).
Supports harvest (pull) operations for discovering and retrieving data listings
from Google Cloud Analytics Hub.

Features:
- Circuit breaker protection
- Google Cloud authentication (ADC and service account JSON)
- BigQuery and Analytics Hub client integration
- Error handling with proper exception mapping
- Discovery operations (list_listings, get_listing, list_resources)
- ODPS and ODCS metadata extraction

Google Cloud Analytics Hub Documentation:
https://cloud.google.com/analytics-hub/docs
"""

import csv
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from google.cloud.bigquery_analyticshub_v1 import AnalyticsHubServiceClient

# Optional Google Cloud imports - handle gracefully if not available
try:
    from google.api_core import exceptions as google_exceptions
    from google.auth import default as google_auth_default
    from google.auth.exceptions import GoogleAuthError
    from google.cloud import bigquery
    from google.oauth2 import service_account

    # Use GoogleAPIError from google.api_core.exceptions
    GoogleAPIError = google_exceptions.GoogleAPIError
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    # Google Cloud libraries not available - mark as unavailable
    bigquery = None
    google_exceptions = None
    google_auth_default = None
    GoogleAuthError = None
    service_account = None
    GoogleAPIError = Exception  # Fallback
    GOOGLE_CLOUD_AVAILABLE = False

# Analytics Hub client - optional import
try:
    from google.cloud.bigquery_analyticshub_v1 import AnalyticsHubServiceClient
    from google.cloud.bigquery_analyticshub_v1.types import (
        DataExchange,
        Listing,
    )

    ANALYTICSHUB_AVAILABLE = True
except ImportError:
    # Analytics Hub client not available
    AnalyticsHubServiceClient = None
    DataExchange = None
    Listing = None
    ANALYTICSHUB_AVAILABLE = False

from hub.apps.assets.models import AssetSourceType
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)
from hub.apps.core.services.base import (
    ConnectionError as HubConnectionError,
    NotFoundError,
    PermissionError,
)
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)

logger = logging.getLogger(__name__)


class GCPMarketplaceConnector(DataMarketplaceConnector):
    """
    Connector for Google Cloud Platform Marketplace (Analytics Hub).

    Implements harvest (pull) operations for discovering and retrieving data listings
    from Google Cloud Analytics Hub. This connector is read-only and supports pull
    operations only.

    Supports:
    - Discovery: list_listings, get_listing, list_resources
    - Harvest: sync_pull (bulk synchronization from Analytics Hub to Hub)
    - Mapping: map_to_hub_asset (Analytics Hub listings → Hub assets)

    Authentication:
    - Application Default Credentials (ADC): Set use_adc=True
    - Service Account JSON: Provide credentials_json dictionary

    Does NOT support:
    - Push operations: create_listing, update_listing, publish_resource, sync_push
    - Write operations: All methods that modify Analytics Hub data
    """

    _SENTINEL = object()  # Used to detect omitted project_id vs explicit None

    def __init__(
        self,
        project_id: Optional[str] = _SENTINEL,  # type: ignore[assignment]
        credentials_json: Optional[Dict[str, Any]] = None,
        location: str = "US",
        use_adc: bool = False,
    ):
        """
        Initialize GCP Marketplace connector.

        Args:
            project_id: Google Cloud project ID (required when using credentials_json)
            credentials_json: Optional service account credentials as dictionary
            location: GCP location/region (default: 'US')
            use_adc: If True, use Application Default Credentials (default: False)
        """
        # Check if Google Cloud libraries are available
        if not GOOGLE_CLOUD_AVAILABLE:
            raise ImportError(
                "Google Cloud libraries are not installed. "
                "Install them with: pip install google-cloud-bigquery google-cloud-bigquery-analyticshub google-auth"
            )

        # Validate that at least one authentication method is specified
        if not use_adc and not credentials_json:
            raise ValueError(
                "Either 'use_adc=True' or 'credentials_json' must be provided for authentication"
            )

        # Track whether project_id was omitted (so tests can create connector then set project_id=None)
        project_id_omitted = project_id is self._SENTINEL
        if project_id_omitted:
            project_id = None

        # When using credentials_json, reject explicitly invalid project_id (not when omitted)
        if not use_adc and credentials_json is not None:
            if project_id is None and not project_id_omitted:
                raise TypeError("project_id is required when using credentials_json")
            if project_id is not None and (
                not isinstance(project_id, str) or not project_id.strip()
            ):
                raise ValueError("project_id must be a non-empty string")

        # Store configuration
        self.project_id = project_id
        self.credentials_json = credentials_json
        self.location = location
        self.use_adc = use_adc

        # Initialize circuit breaker (same pattern as CKAN)
        self._circuit_breaker = CircuitBreaker(
            service_name="gcp-marketplace-connector",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client(),
        )

        # Retry configuration (same pattern as CKAN)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize client placeholders (lazy initialization)
        self._bigquery_client = None  # type: Optional[Any]  # bigquery.Client when available
        self._analyticshub_client: Optional[Any] = None  # AnalyticsHubServiceClient when available
        self._credentials = None

        # Track authentication state
        self._authenticated = False

    def _is_transient_error(self, error_code: Optional[int]) -> bool:
        """
        Check if Google Cloud API error is transient and should be retried.

        Args:
            error_code: Google Cloud API error code

        Returns:
            True if error is transient (should retry), False otherwise
        """
        if error_code is None:
            return False
        # Retry on: 429 (Too Many Requests), 500, 502, 503, 504 (server errors)
        return error_code in (429, 500, 502, 503, 504)

    def _map_google_error(
        self, error: GoogleAPIError, context: str = "", operation: str = ""
    ) -> Exception:
        """
        Map Google Cloud API error to appropriate connector exception.

        Args:
            error: GoogleAPIError from Google Cloud API
            context: Additional context string for error messages
            operation: Operation name for logging (e.g., 'list_listings')

        Returns:
            Mapped exception (NotFoundError, PermissionError, ValueError, HubConnectionError)
        """
        error_code = getattr(error, "code", None)
        error_message = str(error)

        # Extract error message from Google Cloud error response if available
        if hasattr(error, "message"):
            error_message = error.message
        elif hasattr(error, "errors") and error.errors:
            # Try to extract more detailed error message
            error_details = error.errors[0] if isinstance(error.errors, list) else error.errors
            if isinstance(error_details, dict):
                error_message = error_details.get("message", error_message)
            elif hasattr(error_details, "message"):
                error_message = error_details.message

        # Map error codes to exceptions
        if error_code == 404:
            return NotFoundError(
                f"Resource not found{': ' + context if context else ''}. {error_message}"
            )
        elif error_code == 403:
            return PermissionError(
                f"Permission denied{': ' + context if context else ''}. {error_message}"
            )
        elif error_code == 400:
            # GCP Analytics Hub returns INVALID_ARGUMENT (400) for nonexistent
            # listing/exchange paths instead of NOT_FOUND (404). Treat as NotFoundError
            # when the operation involves fetching a specific resource.
            if operation in ("get_listing", "list_resources", "get_data_exchange"):
                return NotFoundError(
                    f"Resource not found (invalid path){': ' + context if context else ''}. {error_message}"
                )
            return ValueError(
                f"Invalid request{': ' + context if context else ''}. {error_message}"
            )
        elif error_code == 401:
            return PermissionError(
                f"Authentication failed{': ' + context if context else ''}. {error_message}"
            )
        elif self._is_transient_error(error_code):
            # Transient error - will be retried, but return ConnectionError for final failure
            return HubConnectionError(
                f"Transient error{': ' + context if context else ''}. {error_message}"
            )
        else:
            # Unknown error code
            return HubConnectionError(
                f"Google Cloud API error{': ' + context if context else ''}. "
                f"Code: {error_code}, Message: {error_message}"
            )

    def _log_with_context(
        self,
        level: str,
        message: str,
        operation: str = "",
        error_code: Optional[int] = None,
        error_message: str = "",
        attempt: int = 0,
        max_retries: int = 0,
        delay: float = 0.0,
        **kwargs,
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
                correlation_id = getattr(request, "trace_id", None)
                trace_id = getattr(request, "trace_id", None)
        except Exception:
            pass

        # Build structured log context
        log_context = {
            "operation": operation,
            "connector": "gcp-marketplace",
            "project_id": self.project_id,
        }

        # Add correlation IDs if available
        if correlation_id:
            log_context["correlation_id"] = correlation_id
        if trace_id:
            log_context["trace_id"] = trace_id

        # Add error context if available
        if error_code is not None:
            log_context["error_code"] = error_code
        if error_message:
            log_context["error_message"] = error_message

        # Add retry context if available
        if attempt > 0:
            log_context["attempt"] = attempt
            log_context["max_retries"] = max_retries
        if delay > 0:
            log_context["retry_delay"] = delay

        # Add any additional context
        log_context.update(kwargs)

        # Log with appropriate level
        if level == "error":
            logger.error(message, extra=log_context)
        elif level == "warning":
            logger.warning(message, extra=log_context)
        elif level == "debug":
            logger.debug(message, extra=log_context)
        else:
            logger.info(message, extra=log_context)

    def _execute_with_retry(self, operation: callable, operation_name: str, context: str = ""):
        """
        Execute Google Cloud API operation with retry logic and circuit breaker protection.

        Implements exponential backoff retry for transient failures:
        - Retries on 429 (Too Many Requests), 500, 502, 503, 504 (server errors)
        - Does not retry on 400, 401, 403, 404 (client errors)
        - Uses exponential backoff: delay = backoff_factor * (2 ** attempt)

        Args:
            operation: Callable that executes Google Cloud API operation
            operation_name: Name of the operation for logging (e.g., 'list_listings')
            context: Additional context string for error messages

        Returns:
            Result of the operation

        Raises:
            NotFoundError: If resource not found (404)
            PermissionError: If access denied (403, 401)
            ValueError: If validation error (400)
            HubConnectionError: If connection failed after retries or other errors
        """

        def execute_with_retry_inner():
            """Inner function for retry logic."""
            last_exception = None

            for attempt in range(self.max_retries + 1):
                try:
                    result = operation()
                    # Log success on retry
                    if attempt > 0:
                        self._log_with_context(
                            "info",
                            f"GCP Marketplace {operation_name} succeeded after {attempt} retries",
                            operation=operation_name,
                            attempt=attempt + 1,
                            max_retries=self.max_retries + 1,
                        )
                    return result

                except GoogleAPIError as e:
                    error_code = getattr(e, "code", None)

                    # Check if error is transient and should be retried
                    if self._is_transient_error(error_code) and attempt < self.max_retries:
                        delay = self.backoff_factor * (2**attempt)
                        self._log_with_context(
                            "warning",
                            f"GCP Marketplace {operation_name} returned {error_code}. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries + 1})",
                            operation=operation_name,
                            error_code=error_code,
                            error_message=str(e),
                            attempt=attempt + 1,
                            max_retries=self.max_retries + 1,
                            delay=delay,
                        )
                        time.sleep(delay)
                        last_exception = e
                        continue

                    # Non-transient error or max retries exceeded - map and raise
                    mapped_error = self._map_google_error(e, context, operation_name)
                    raise mapped_error

                except (NotFoundError, PermissionError, ValueError):
                    # Re-raise mapped errors as-is (no retry)
                    raise

                except Exception as e:
                    # Unexpected error - log and raise
                    self._log_with_context(
                        "error",
                        f"Unexpected error in {operation_name}: {e}",
                        operation=operation_name,
                        error_message=str(e),
                    )
                    raise HubConnectionError(f"Unexpected error in {operation_name}: {e}") from e

            # Max retries exceeded
            if last_exception:
                mapped_error = self._map_google_error(last_exception, context, operation_name)
                raise mapped_error
            raise HubConnectionError(f"Max retries exceeded for {operation_name}")

        # Execute with circuit breaker protection
        try:
            return self._circuit_breaker.call(execute_with_retry_inner)
        except Exception as e:
            self._log_with_context(
                "error",
                f"GCP Marketplace connector {operation_name} failed: {e}",
                operation=operation_name,
                error_message=str(e),
            )
            raise

    def _get_credentials(self):
        """
        Get Google Cloud credentials.

        Returns:
            google.auth.credentials.Credentials object

        Raises:
            GoogleAuthError: If authentication fails
            ValueError: If credentials configuration is invalid
        """
        if self._credentials is not None:
            return self._credentials

        try:
            if self.use_adc:
                # Use Application Default Credentials
                credentials, project = google_auth_default()
                # Update project_id if not provided and ADC has project
                if not self.project_id and project:
                    self.project_id = project
                self._credentials = credentials
            elif self.credentials_json:
                # Use service account credentials from JSON
                if not isinstance(self.credentials_json, dict):
                    raise ValueError("credentials_json must be a dictionary")
                self._credentials = service_account.Credentials.from_service_account_info(
                    self.credentials_json
                )
            else:
                raise ValueError("Either 'use_adc=True' or 'credentials_json' must be provided")

            return self._credentials
        except GoogleAuthError as e:
            logger.error(f"Failed to get Google Cloud credentials: {e}")
            raise ValueError(f"Invalid Google Cloud credentials: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting credentials: {e}")
            raise ValueError(f"Failed to initialize credentials: {e}") from e

    def _get_bigquery_client(self):
        """
        Get or create BigQuery client instance.

        Returns:
            bigquery.Client instance

        Raises:
            ValueError: If project_id is not set
        """
        if self._bigquery_client is not None:
            return self._bigquery_client

        if not self.project_id:
            raise ValueError("project_id is required to create BigQuery client")

        credentials = self._get_credentials()
        self._bigquery_client = bigquery.Client(
            credentials=credentials, project=self.project_id, location=self.location
        )
        return self._bigquery_client

    def _get_analyticshub_client(self):
        """
        Get or create Analytics Hub client instance.

        Returns:
            AnalyticsHubServiceClient instance

        Raises:
            ImportError: If Analytics Hub client library is not installed
            ValueError: If credentials cannot be obtained
        """
        if self._analyticshub_client is not None:
            return self._analyticshub_client

        if not ANALYTICSHUB_AVAILABLE or AnalyticsHubServiceClient is None:
            raise ImportError(
                "Analytics Hub client library is not installed. "
                "Install it with: pip install google-cloud-bigquery-analyticshub"
            )

        credentials = self._get_credentials()
        self._analyticshub_client = AnalyticsHubServiceClient(credentials=credentials)
        return self._analyticshub_client

    def _get_location_path(self) -> str:
        """
        Get Analytics Hub location path.

        Returns:
            Location path string (e.g., 'projects/PROJECT_ID/locations/US')
        """
        if not self.project_id:
            raise ValueError("project_id is required")
        return f"projects/{self.project_id}/locations/{self.location}"

    def _get_data_exchange_path(self, data_exchange_id: str) -> str:
        """
        Get Analytics Hub data exchange path.

        Args:
            data_exchange_id: Data exchange ID

        Returns:
            Data exchange path string
        """
        location_path = self._get_location_path()
        return f"{location_path}/dataExchanges/{data_exchange_id}"

    def _get_listing_path(self, data_exchange_id: str, listing_id: str) -> str:
        """
        Get Analytics Hub listing path.

        Args:
            data_exchange_id: Data exchange ID
            listing_id: Listing ID

        Returns:
            Listing path string
        """
        data_exchange_path = self._get_data_exchange_path(data_exchange_id)
        return f"{data_exchange_path}/listings/{listing_id}"

    def _parse_listing_name(self, listing_name: str) -> tuple:
        """
        Parse Analytics Hub listing name to extract components.

        Listing name format: projects/{project}/locations/{location}/dataExchanges/{exchange}/listings/{listing}

        Args:
            listing_name: Full listing name/path

        Returns:
            Tuple of (project_id, location, data_exchange_id, listing_id)
        """
        if listing_name is None:
            raise ValueError("listing_name cannot be None")
        if not isinstance(listing_name, str):
            raise TypeError("listing_name must be a string")
        parts = listing_name.split("/")
        if (
            len(parts) != 8
            or parts[0] != "projects"
            or parts[2] != "locations"
            or parts[4] != "dataExchanges"
            or parts[6] != "listings"
        ):
            # If not a full path, assume it's just the listing ID and use current project/location
            return (self.project_id, self.location, None, listing_name)
        return (parts[1], parts[3], parts[5], parts[7])

    @property
    def marketplace_type(self) -> MarketplaceType:
        """Get the marketplace type this connector supports."""
        return MarketplaceType.GOOGLE_CLOUD_MARKETPLACE

    @property
    def supported_sync_directions(self) -> List[SyncDirection]:
        """
        Get the list of sync directions supported by this connector.

        GCP Marketplace connector is harvest-only (PULL only) as Analytics Hub
        is a data marketplace that should be harvested FROM, not pushed TO.
        """
        return [SyncDirection.PULL]

    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Google Cloud using provided credentials.

        Args:
            credentials: Dictionary containing:
                - project_id: Google Cloud project ID (required)
                - credentials_json: Optional service account credentials as dictionary
                - location: Optional GCP location (default: 'US')
                - use_adc: Optional flag to use Application Default Credentials (default: False)

        Returns:
            True if authentication successful, False otherwise

        Raises:
            ValueError: If credentials are invalid or missing required fields
            ConnectionError: If unable to connect to Google Cloud
        """
        if not credentials:
            raise ValueError("Credentials dictionary is required")

        # Extract credentials
        project_id = credentials.get("project_id")
        if not project_id:
            raise ValueError("project_id is required in credentials")

        credentials_json = credentials.get("credentials_json")
        location = credentials.get("location", "US")
        use_adc = credentials.get("use_adc", False)

        # Validate that at least one authentication method is specified
        if not use_adc and not credentials_json:
            raise ValueError(
                "Either 'use_adc=True' or 'credentials_json' must be provided in credentials"
            )

        # Update instance configuration
        self.project_id = project_id
        self.credentials_json = credentials_json
        self.location = location
        self.use_adc = use_adc

        # Reset clients to force re-authentication
        self._bigquery_client = None
        self._analyticshub_client = None
        self._credentials = None

        # Test connection
        try:
            result = self.test_connection()
            if result:
                self._authenticated = True
                logger.info(f"Successfully authenticated with GCP project {project_id}")
                return True
            else:
                self._authenticated = False
                logger.warning("GCP authentication failed: Connection test returned False")
                return False
        except ValueError:
            self._authenticated = False
            raise
        except Exception as e:
            if GoogleAuthError is not None and isinstance(e, GoogleAuthError):
                self._authenticated = False
                raise
            self._authenticated = False
            logger.error(f"GCP authentication failed: {e}")
            raise HubConnectionError(f"Unable to authenticate with Google Cloud: {e}") from e

    def test_connection(self) -> bool:
        """
        Test the connection to Google Cloud.

        Performs a lightweight BigQuery operation (list_datasets with max_results=1)
        to verify connectivity and authentication.

        Returns:
            True if connection test successful, False otherwise

        Raises:
            NotFoundError: If project not found (404)
            PermissionError: If access denied (403)
            ConnectionError: If unable to connect or other errors occur
        """

        def execute_test() -> bool:
            """Execute connection test."""
            try:
                client = self._get_bigquery_client()
                # Perform lightweight operation: list datasets with max_results=1
                datasets = list(client.list_datasets(max_results=1))
                self._log_with_context(
                    "info",
                    f"Connection test successful for GCP project {self.project_id}",
                    operation="test_connection",
                )
                return True
            except GoogleAuthError as e:
                self._log_with_context(
                    "error",
                    f"Google Cloud authentication error: {e}",
                    operation="test_connection",
                    error_message=str(e),
                )
                raise HubConnectionError(f"Authentication failed: {e}") from e
            except ValueError as e:
                # Re-raise ValueError as-is (e.g., missing project_id)
                raise

        # Execute with retry logic and circuit breaker protection
        return self._execute_with_retry(
            execute_test, "test_connection", f"GCP project '{self.project_id}'"
        )

    def list_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[MarketplaceListing]:
        """
        List available listings from Analytics Hub.

        Calls Analytics Hub API to:
        1. List data exchanges in the project/location
        2. For each exchange, list listings
        3. Get full listing details and extract ODPS/ODCS metadata
        4. Map to MarketplaceListing objects

        Args:
            filters: Optional dictionary of filters:
                - category: Filter by category
                - data_exchange_id: Filter by specific data exchange
            limit: Optional maximum number of listings to return
            offset: Optional offset for pagination (skip first N items)

        Returns:
            List of MarketplaceListing objects

        Raises:
            ConnectionError: If unable to connect to Analytics Hub
            ValueError: If filters or pagination parameters are invalid
        """

        def execute_list_listings() -> List[MarketplaceListing]:
            """Execute list_listings."""
            if not ANALYTICSHUB_AVAILABLE:
                raise ImportError(
                    "Analytics Hub client library is not installed. "
                    "Install it with: pip install google-cloud-bigquery-analyticshub"
                )

            # Validate pagination parameters
            if offset is not None:
                if not isinstance(offset, int) or offset < 0:
                    raise ValueError("offset must be a non-negative integer")
            if limit is not None:
                if not isinstance(limit, int) or limit < 0:
                    raise ValueError("limit must be a non-negative integer")

            client = self._get_analyticshub_client()
            if client is None:
                raise ImportError("Analytics Hub client is not available")
            location_path = self._get_location_path()
            all_listings = []

            # List data exchanges
            data_exchanges = []
            if filters and filters.get("data_exchange_id"):
                # Get specific data exchange
                exchange_path = self._get_data_exchange_path(filters["data_exchange_id"])
                exchange = client.get_data_exchange(name=exchange_path)
                data_exchanges = [exchange]
            else:
                # List all data exchanges
                response = client.list_data_exchanges(parent=location_path)
                data_exchanges = list(response)

            # For each data exchange, list listings
            for exchange in data_exchanges:
                try:
                    exchange_id = (
                        exchange.name.split("/")[-1] if "/" in exchange.name else exchange.name
                    )
                    exchange_path = self._get_data_exchange_path(exchange_id)

                    # List listings in this exchange
                    try:
                        listings_response = client.list_listings(parent=exchange_path)
                        exchange_listings = list(listings_response)
                    except GoogleAPIError as e:
                        error_code = getattr(e, "code", None)
                        if error_code == 404:
                            self._log_with_context(
                                "debug",
                                f"Data exchange '{exchange_id}' has no listings or not found",
                                operation="list_listings",
                                error_code=error_code,
                            )
                            continue
                        elif error_code == 403:
                            self._log_with_context(
                                "warning",
                                f"Permission denied accessing listings in '{exchange_id}'",
                                operation="list_listings",
                                error_code=error_code,
                            )
                            continue
                        # Transient errors will be retried by _execute_with_retry
                        raise

                    # Get full details for each listing
                    for listing in exchange_listings:
                        try:
                            # Get full listing details
                            listing_details = self._get_listing_details(
                                exchange_id,
                                (
                                    listing.name.split("/")[-1]
                                    if "/" in listing.name
                                    else listing.name
                                ),
                            )

                            # Build MarketplaceListing
                            marketplace_listing = self._build_marketplace_listing(
                                listing_details, exchange_id, exchange
                            )

                            # Apply filters
                            if filters:
                                if filters.get("category"):
                                    if marketplace_listing.category != filters["category"]:
                                        continue

                            all_listings.append(marketplace_listing)
                        except NotFoundError:
                            self._log_with_context(
                                "warning",
                                f"Listing not found, skipping: {listing.name}",
                                operation="list_listings",
                            )
                            continue
                        except Exception as e:
                            self._log_with_context(
                                "warning",
                                f"Failed to process listing {listing.name}: {e}",
                                operation="list_listings",
                                error_message=str(e),
                            )
                            continue

                except Exception as e:
                    self._log_with_context(
                        "warning",
                        f"Failed to process data exchange {exchange.name}: {e}",
                        operation="list_listings",
                        error_message=str(e),
                    )
                    continue

            # Apply pagination
            if offset is not None and offset > 0:
                all_listings = all_listings[offset:]
            if limit is not None and limit > 0:
                all_listings = all_listings[:limit]

            return all_listings

        # Execute with retry logic and circuit breaker protection
        return self._execute_with_retry(execute_list_listings, "list_listings", "Analytics Hub")

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        """
        Get a specific listing by its marketplace ID.

        Calls Analytics Hub API get_listing() to retrieve full listing details,
        extracts ODPS and ODCS metadata, and maps to MarketplaceListing object.

        Args:
            listing_id: Analytics Hub listing ID or full listing path
                Format: projects/{project}/locations/{location}/dataExchanges/{exchange}/listings/{listing}
                Or just: {listing_id} (will search all exchanges)

        Returns:
            MarketplaceListing object with complete metadata

        Raises:
            ValueError: If listing_id is None or empty
            NotFoundError: If listing not found (404)
            ConnectionError: If unable to connect to Analytics Hub
        """
        if listing_id is None:
            raise ValueError("listing_id cannot be None")
        if not isinstance(listing_id, str) or not listing_id.strip():
            raise ValueError("listing_id must be a non-empty string")

        def execute_get_listing() -> MarketplaceListing:
            """Execute get_listing."""
            if not ANALYTICSHUB_AVAILABLE or AnalyticsHubServiceClient is None:
                raise ImportError(
                    "Analytics Hub client library is not installed. "
                    "Install it with: pip install google-cloud-bigquery-analyticshub"
                )

            client = self._get_analyticshub_client()
            if client is None:
                raise ImportError("Analytics Hub client is not available")

            # Parse listing name to get components
            project_id, location, data_exchange_id, listing_id_short = self._parse_listing_name(
                listing_id
            )

            # If we have full path, use it directly
            if data_exchange_id:
                listing_path = self._get_listing_path(data_exchange_id, listing_id_short)
                listing = client.get_listing(name=listing_path)
                # Get data exchange for metadata
                exchange_path = self._get_data_exchange_path(data_exchange_id)
                exchange = client.get_data_exchange(name=exchange_path)
                listing_details = self._get_listing_details(data_exchange_id, listing_id_short)
                return self._build_marketplace_listing(listing_details, data_exchange_id, exchange)

            # Otherwise, search across all data exchanges
            location_path = self._get_location_path()
            exchanges_response = client.list_data_exchanges(parent=location_path)
            exchanges = list(exchanges_response)

            for exchange in exchanges:
                exchange_id = (
                    exchange.name.split("/")[-1] if "/" in exchange.name else exchange.name
                )
                try:
                    listing_path = self._get_listing_path(exchange_id, listing_id_short)
                    listing = client.get_listing(name=listing_path)
                    listing_details = self._get_listing_details(exchange_id, listing_id_short)
                    return self._build_marketplace_listing(listing_details, exchange_id, exchange)
                except GoogleAPIError as e:
                    error_code = getattr(e, "code", None)
                    if error_code == 404:
                        # Not in this exchange, try next
                        continue
                    elif error_code == 403:
                        self._log_with_context(
                            "warning",
                            f"Permission denied accessing listing in exchange '{exchange_id}'",
                            operation="get_listing",
                            error_code=error_code,
                        )
                        continue
                    # Transient errors will be retried by _execute_with_retry
                    raise

            # Not found in any exchange
            raise NotFoundError(f"Listing '{listing_id}' not found in any data exchange")

        # Execute with retry logic and circuit breaker protection
        return self._execute_with_retry(
            execute_get_listing, "get_listing", f"listing '{listing_id}'"
        )

    def _get_listing_details(self, data_exchange_id: str, listing_id: str) -> Dict[str, Any]:
        """
        Get full listing details from Analytics Hub API.

        Args:
            data_exchange_id: Data exchange ID
            listing_id: Listing ID

        Returns:
            Dictionary containing listing details

        Raises:
            ValueError: If data_exchange_id or listing_id is None or empty
            NotFoundError: If listing not found (404)
            ConnectionError: If unable to connect to Analytics Hub
        """
        if data_exchange_id is None or (isinstance(data_exchange_id, str) and not data_exchange_id.strip()):
            raise ValueError("data_exchange_id cannot be None or empty")
        if listing_id is None or (isinstance(listing_id, str) and not listing_id.strip()):
            raise ValueError("listing_id cannot be None or empty")
        if not ANALYTICSHUB_AVAILABLE or AnalyticsHubServiceClient is None:
            raise ImportError(
                "Analytics Hub client library is not installed. "
                "Install it with: pip install google-cloud-bigquery-analyticshub"
            )

        def execute_get_listing_details() -> Dict[str, Any]:
            """Execute get_listing_details."""
            client = self._get_analyticshub_client()
            if client is None:
                raise ImportError("Analytics Hub client is not available")

            listing_path = self._get_listing_path(data_exchange_id, listing_id)
            listing = client.get_listing(name=listing_path)
            # Convert protobuf message to dictionary
            listing_dict = listing.to_dict()
            return listing_dict

        # Execute with retry logic and circuit breaker protection
        return self._execute_with_retry(
            execute_get_listing_details,
            "get_listing_details",
            f"listing '{listing_id}' in data exchange '{data_exchange_id}'",
        )

    def _build_marketplace_listing(
        self, listing_details: Dict[str, Any], data_exchange_id: str, exchange: Any = None
    ) -> MarketplaceListing:
        """
        Build MarketplaceListing object from Analytics Hub listing details.

        Args:
            listing_details: Dictionary containing listing details from Analytics Hub API
            data_exchange_id: Data exchange ID
            exchange: Optional DataExchange object for additional metadata

        Returns:
            MarketplaceListing object with ODPS and ODCS metadata
        """
        # Extract basic listing information
        listing_name = listing_details.get("name", "")
        display_name = listing_details.get("display_name", "")
        description = listing_details.get("description", "")
        categories = listing_details.get("categories", [])
        category = categories[0] if categories else None

        # Extract listing ID from name path
        listing_id = listing_name.split("/")[-1] if "/" in listing_name else listing_name

        # Extract timestamps
        created_at = None
        updated_at = None
        # Analytics Hub listings may have create_time/update_time in different formats
        if listing_details.get("create_time"):
            try:
                create_time = listing_details["create_time"]
                if isinstance(create_time, str):
                    created_at = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                elif hasattr(create_time, "timestamp"):
                    created_at = datetime.fromtimestamp(create_time.timestamp())
            except (ValueError, AttributeError):
                pass

        if listing_details.get("update_time"):
            try:
                update_time = listing_details["update_time"]
                if isinstance(update_time, str):
                    updated_at = datetime.fromisoformat(update_time.replace("Z", "+00:00"))
                elif hasattr(update_time, "timestamp"):
                    updated_at = datetime.fromtimestamp(update_time.timestamp())
            except (ValueError, AttributeError):
                pass

        # Build URL (Analytics Hub console URL)
        url = None
        if self.project_id and data_exchange_id and listing_id:
            url = (
                f"https://console.cloud.google.com/bigquery/analytics-hub/"
                f"exchange/{self.project_id}/{self.location}/{data_exchange_id}/"
                f"listing/{listing_id}"
            )

        # Extract ODPS metadata
        odps_metadata = self._extract_odps_metadata(listing_details, data_exchange_id, exchange)

        # Extract ODCS metadata
        odcs_metadata = self._extract_odcs_metadata(listing_details)

        # Build metadata dictionary
        metadata = {
            "analytics_hub_listing": listing_details,
            "data_exchange_id": data_exchange_id,
            "listing_name": listing_name,
        }
        if exchange:
            metadata["data_exchange"] = (
                exchange.to_dict() if hasattr(exchange, "to_dict") else str(exchange)
            )

        # Extract tags from categories or other metadata
        tags = []
        if categories:
            tags.extend(categories)
        if listing_details.get("data_provider"):
            tags.append(f"provider:{listing_details['data_provider']}")

        return MarketplaceListing(
            marketplace_id=listing_id,
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
            title=display_name or listing_id,
            description=description,
            product_id=listing_id,
            category=category,
            tags=tags,
            pricing_plans=odps_metadata.get("pricing_plans", []) if odps_metadata else [],
            access_methods=odps_metadata.get("access_methods", {}) if odps_metadata else {},
            payment_gateways=odps_metadata.get("payment_gateways", {}) if odps_metadata else {},
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
            url=url,
        )

    def _extract_odps_metadata(
        self, listing_details: Dict[str, Any], data_exchange_id: str, exchange: Any = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extract ODPS contract metadata from Analytics Hub listing.

        Extracts:
        - product_details: productID (listing name), product_name (display_name), product_description, version
        - pricing_plans: Extract from commercial_info if available (GCP Marketplace pricing is subscription-based)
        - access_methods: Dictionary with BigQuery access method (linked dataset query access)
        - payment_gateways: Dictionary with Google payment gateway info (if available)

        Args:
            listing_details: Dictionary containing listing details from Analytics Hub API
            data_exchange_id: Data exchange ID
            exchange: Optional DataExchange object

        Returns:
            Structured ODPS metadata dictionary or None if no ODPS data available
        """
        odps_metadata: Dict[str, Any] = {}

        # Extract product details
        listing_name = listing_details.get("name", "")
        listing_id = listing_name.split("/")[-1] if "/" in listing_name else listing_name
        display_name = listing_details.get("display_name", "")
        description = listing_details.get("description", "")

        product_details: Dict[str, Any] = {
            "productID": listing_id,
            "product_name": display_name or listing_id,
            "product_description": description or "",
        }

        # Extract version if available (may be in metadata or exchange)
        version = listing_details.get("version")
        if version:
            product_details["product_version"] = str(version)

        # Extract categories
        categories = listing_details.get("categories", [])
        if categories:
            product_details["categories"] = categories

        # Extract data provider and publisher
        data_provider = listing_details.get("data_provider")
        publisher = listing_details.get("publisher")
        if data_provider:
            product_details["data_provider"] = data_provider
        if publisher:
            product_details["publisher"] = publisher

        # Track if we have ODPS-specific data
        has_odps_data = False

        # Extract pricing plans from commercial_info
        commercial_info = listing_details.get("commercial_info")
        pricing_plans = []
        if commercial_info:
            # Commercial info may contain pricing information
            # GCP Marketplace uses subscription-based pricing
            pricing_info = (
                commercial_info.get("pricing") if isinstance(commercial_info, dict) else None
            )
            if pricing_info:
                pricing_plans.append(
                    {
                        "plan_name": "subscription",
                        "plan_type": "SUBSCRIPTION",
                        "pricing_model": "SUBSCRIPTION",
                        "price_amount": pricing_info.get("amount"),
                        "currency": pricing_info.get("currency", "USD"),
                        "billing_period": pricing_info.get("period", "MONTHLY"),
                    }
                )
                has_odps_data = True

        # Check for pricing in metadata
        if listing_details.get("metadata") and isinstance(listing_details["metadata"], dict):
            metadata_pricing = listing_details["metadata"].get("pricing_plans")
            if metadata_pricing and isinstance(metadata_pricing, list):
                pricing_plans.extend(metadata_pricing)
                has_odps_data = True

        if pricing_plans:
            odps_metadata["pricing_plans"] = pricing_plans

        # Extract access methods
        # Analytics Hub listings provide BigQuery dataset access
        bigquery_dataset = listing_details.get("bigquery_dataset")
        access_methods = {}
        if bigquery_dataset:
            dataset_ref = (
                bigquery_dataset.get("dataset")
                if isinstance(bigquery_dataset, dict)
                else str(bigquery_dataset)
            )
            access_methods["bigquery"] = {
                "method": "LINKED_DATASET",
                "dataset_reference": dataset_ref,
                "query_access": True,
                "description": "Access via BigQuery linked dataset",
            }
            has_odps_data = True

        # Also check for Pub/Sub topic source
        pubsub_topic = listing_details.get("pubsub_topic")
        if pubsub_topic:
            topic_ref = (
                pubsub_topic.get("topic") if isinstance(pubsub_topic, dict) else str(pubsub_topic)
            )
            access_methods["pubsub"] = {
                "method": "PUBSUB_TOPIC",
                "topic_reference": topic_ref,
                "description": "Access via Pub/Sub topic",
            }
            has_odps_data = True

        if access_methods:
            odps_metadata["access_methods"] = access_methods

        # Extract payment gateways
        # GCP Marketplace uses Google payment gateway
        payment_gateways = {}
        if commercial_info or pricing_plans:
            payment_gateways["google"] = {
                "gateway_name": "Google Cloud Billing",
                "gateway_type": "GOOGLE_CLOUD_BILLING",
                "enabled": True,
                "description": "Google Cloud Marketplace billing",
            }
            has_odps_data = True

        if payment_gateways:
            odps_metadata["payment_gateways"] = payment_gateways

        # Only return ODPS metadata if we have meaningful ODPS-specific data
        if has_odps_data:
            odps_metadata["product_details"] = product_details
            return odps_metadata

        return None

    def _extract_odcs_metadata(self, listing_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract ODCS contract metadata hints from Analytics Hub listing.

        Extracts:
        - Schema hints (if available in listing metadata or bigquery_dataset metadata)
        - Quality hints (if available)
        - SLA hints (if available)

        Args:
            listing_details: Dictionary containing listing details from Analytics Hub API

        Returns:
            Structured ODCS metadata dictionary (will be enhanced after dataset subscription)
        """
        odcs_metadata: Dict[str, Any] = {}

        # Extract schema hints from BigQuery dataset reference
        bigquery_dataset = listing_details.get("bigquery_dataset")
        schema_hints = {}
        if bigquery_dataset:
            dataset_ref = (
                bigquery_dataset.get("dataset")
                if isinstance(bigquery_dataset, dict)
                else str(bigquery_dataset)
            )
            schema_hints["dataset_reference"] = dataset_ref
            schema_hints["data_format"] = "BIGQUERY"
            schema_hints["description"] = (
                "Schema available via BigQuery INFORMATION_SCHEMA after subscription"
            )

        # Check for schema information in metadata
        if listing_details.get("metadata") and isinstance(listing_details["metadata"], dict):
            metadata_schema = listing_details["metadata"].get("schema") or listing_details[
                "metadata"
            ].get("schema_hints")
            if metadata_schema:
                if isinstance(metadata_schema, dict):
                    schema_hints.update(metadata_schema)
                else:
                    schema_hints["schema_data"] = metadata_schema

        if schema_hints:
            odcs_metadata["schema"] = schema_hints

        # Extract quality hints (if available in metadata)
        quality_hints = {}
        if listing_details.get("metadata") and isinstance(listing_details["metadata"], dict):
            metadata_quality = listing_details["metadata"].get("quality") or listing_details[
                "metadata"
            ].get("quality_hints")
            if metadata_quality:
                if isinstance(metadata_quality, dict):
                    quality_hints.update(metadata_quality)
                else:
                    quality_hints["quality_data"] = metadata_quality

        if quality_hints:
            odcs_metadata["quality"] = quality_hints

        # Extract SLA hints (if available in metadata)
        sla_hints = {}
        if listing_details.get("metadata") and isinstance(listing_details["metadata"], dict):
            metadata_sla = listing_details["metadata"].get("sla") or listing_details[
                "metadata"
            ].get("sla_hints")
            if metadata_sla:
                if isinstance(metadata_sla, dict):
                    sla_hints.update(metadata_sla)
                else:
                    sla_hints["sla_data"] = metadata_sla

        # Analytics Hub may have availability information
        state = listing_details.get("state")
        if state:
            sla_hints["availability"] = state
            sla_hints["description"] = f"Listing state: {state}"

        if sla_hints:
            odcs_metadata["sla"] = sla_hints

        # Only return ODCS metadata if we have meaningful data
        if odcs_metadata:
            return odcs_metadata

        return None

    def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
        """
        List resources associated with an Analytics Hub listing.

        For GCP Marketplace, resources are BigQuery tables in linked datasets.
        Queries BigQuery INFORMATION_SCHEMA.TABLES for tables in the linked dataset.

        Args:
            listing_id: Analytics Hub listing ID or full listing path

        Returns:
            List of MarketplaceResource objects (resource_type="BIGQUERY_TABLE")

        Raises:
            ValueError: If listing_id is None or empty
            NotFoundError: If listing not found
            ConnectionError: If unable to connect to BigQuery or Analytics Hub
        """
        if listing_id is None:
            raise ValueError("listing_id cannot be None")
        if not isinstance(listing_id, str) or not listing_id.strip():
            raise ValueError("listing_id must be a non-empty string")

        def execute_list_resources() -> List[MarketplaceResource]:
            """Execute list_resources."""
            # First, get the listing to find the BigQuery dataset
            listing = self.get_listing(listing_id)
            listing_details = listing.metadata.get("analytics_hub_listing", {})

            # Extract BigQuery dataset reference
            bigquery_dataset = listing_details.get("bigquery_dataset")
            if not bigquery_dataset:
                # No BigQuery dataset associated with this listing
                self._log_with_context(
                    "info",
                    f"Listing '{listing_id}' has no BigQuery dataset, returning empty resources",
                    operation="list_resources",
                )
                return []

            # Get dataset reference
            dataset_ref = None
            if isinstance(bigquery_dataset, dict):
                dataset_ref = bigquery_dataset.get("dataset")
            else:
                dataset_ref = str(bigquery_dataset)

            if not dataset_ref:
                self._log_with_context(
                    "warning",
                    f"Listing '{listing_id}' has invalid BigQuery dataset reference",
                    operation="list_resources",
                )
                return []

            # Parse dataset reference (format: project.dataset or just dataset)
            dataset_parts = dataset_ref.split(".")
            if len(dataset_parts) == 2:
                dataset_project, dataset_id = dataset_parts
            else:
                # Use current project if not specified
                dataset_project = self.project_id
                dataset_id = dataset_ref

            # Query BigQuery INFORMATION_SCHEMA.TABLES
            bq_client = self._get_bigquery_client()
            resources = []

            # Query INFORMATION_SCHEMA.TABLES for the dataset
            query = f"""
                SELECT
                    table_catalog,
                    table_schema,
                    table_name,
                    table_type,
                    creation_time,
                    ddl,
                    description
                FROM `{dataset_project}.{dataset_id}.INFORMATION_SCHEMA.TABLES`
                ORDER BY table_schema, table_name
            """

            query_job = bq_client.query(query)
            results = query_job.result()

            for row in results:
                try:
                    table_schema = row.get("table_schema", "")
                    table_name = row.get("table_name", "")
                    table_type = row.get("table_type", "BASE TABLE")
                    description = row.get("description", "")
                    creation_time = row.get("creation_time")

                    # Build resource ID
                    resource_id = f"{dataset_project}.{dataset_id}.{table_schema}.{table_name}"

                    # Determine resource type
                    resource_type = "BIGQUERY_TABLE"
                    if table_type == "VIEW":
                        resource_type = "BIGQUERY_VIEW"

                    # Build resource URL
                    resource_url = (
                        f"https://console.cloud.google.com/bigquery?"
                        f"project={dataset_project}&"
                        f"ws=!1m5!1m4!4m3!1s{dataset_project}!2s{dataset_id}!3s{table_name}"
                    )

                    resource = MarketplaceResource(
                        resource_id=resource_id,
                        resource_type=resource_type,
                        name=table_name,
                        description=description
                        or f"{table_type} {table_name} in dataset {dataset_id}",
                        url=resource_url,
                        format="BIGQUERY",
                        size_bytes=None,  # Table size not available in INFORMATION_SCHEMA
                        metadata={
                            "table_catalog": row.get("table_catalog"),
                            "table_schema": table_schema,
                            "table_name": table_name,
                            "table_type": table_type,
                            "creation_time": creation_time.isoformat() if creation_time else None,
                            "dataset_reference": dataset_ref,
                        },
                    )
                    resources.append(resource)
                except Exception as e:
                    self._log_with_context(
                        "warning",
                        f"Failed to process table {row.get('table_name', 'unknown')}: {e}",
                        operation="list_resources",
                        error_message=str(e),
                    )
                    continue

            return resources

        # Execute with retry logic and circuit breaker protection
        return self._execute_with_retry(
            execute_list_resources, "list_resources", f"listing '{listing_id}'"
        )

    def create_listing(self, listing):
        """
        Create a new listing in Analytics Hub.

        **DEPRECATED**: GCP Marketplace connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            listing: MarketplaceListing object

        Returns:
            Created MarketplaceListing object

        Raises:
            NotImplementedError: GCP Marketplace connector does not support push operations
        """
        raise NotImplementedError(
            "GCP Marketplace connector is harvest-only (PULL only). "
            "Analytics Hub is a data marketplace that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from Analytics Hub."
        )

    def update_listing(self, listing_id: str, listing):
        """
        Update an existing listing in Analytics Hub.

        **DEPRECATED**: GCP Marketplace connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            listing_id: ID of the listing to update
            listing: MarketplaceListing object with updated details

        Returns:
            Updated MarketplaceListing object

        Raises:
            NotImplementedError: GCP Marketplace connector does not support push operations
        """
        raise NotImplementedError(
            "GCP Marketplace connector is harvest-only (PULL only). "
            "Analytics Hub is a data marketplace that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from Analytics Hub."
        )

    def publish_resource(self, listing_id: str, resource):
        """
        Publish a resource to an Analytics Hub listing.

        **DEPRECATED**: GCP Marketplace connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            listing_id: Analytics Hub listing ID
            resource: MarketplaceResource object

        Returns:
            Published MarketplaceResource object

        Raises:
            NotImplementedError: GCP Marketplace connector does not support push operations
        """
        raise NotImplementedError(
            "GCP Marketplace connector is harvest-only (PULL only). "
            "Analytics Hub is a data marketplace that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from Analytics Hub."
        )

    def download_resource(self, resource_id: str, destination_path: str) -> str:
        """
        Download a resource from Analytics Hub on-demand.

        **On-Demand Download Behavior**: This method handles on-demand resource downloads when
        `data_strategy != "METADATA_ONLY"`. It performs all marketplace-specific operations
        that were deferred from `sync_pull()`:
        1. Subscribes to listing if not already subscribed (`_subscribe_to_listing()`)
        2. Extracts schema from linked BigQuery dataset (`_extract_schema_from_bigquery_dataset()`)
        3. Exports table data to file using BigQuery export job
        4. Downloads file to `destination_path`

        Args:
            resource_id: Table identifier or listing name. Format can be:
                - Full listing path: `projects/PROJECT/locations/LOCATION/dataExchanges/EXCHANGE/listings/LISTING`
                - Short listing ID: `LISTING_ID` (will be resolved to full path)
                - Table identifier: `project.dataset.table` (for direct table export)
            destination_path: Local filesystem path where resource should be saved.
                The directory will be created if it doesn't exist.

        Returns:
            Path to the downloaded file

        Raises:
            ValueError: If resource_id is None or empty
            NotFoundError: If resource or listing not found
            ConnectionError: If unable to connect to Analytics Hub or BigQuery
            IOError: If unable to write to destination path
            PermissionError: If user lacks permission to subscribe or access dataset
        """
        if resource_id is None:
            raise ValueError("resource_id cannot be None")
        if not isinstance(resource_id, str) or not resource_id.strip():
            raise ValueError("resource_id must be a non-empty string")

        def execute_download_resource() -> str:
            """Execute download_resource with circuit breaker protection."""
            # Parse resource_id to determine if it's a listing or table
            # If it contains '/', it's likely a listing path
            # If it contains '.', it might be a table identifier
            # Otherwise, treat it as a listing ID

            listing_id = None
            table_ref = None
            data_exchange_id = None

            if "/" in resource_id:
                # Full listing path
                project, location, exchange, listing = self._parse_listing_name(resource_id)
                listing_id = listing
                data_exchange_id = exchange
            elif "." in resource_id and resource_id.count(".") >= 2:
                # Table identifier: project.dataset.table
                table_ref = resource_id
            else:
                # Short listing ID - need to resolve
                listing_id = resource_id

            # If we have a listing ID, subscribe to it first
            linked_dataset = None
            if listing_id:
                # Get listing details to find data exchange
                if not data_exchange_id:
                    listing = self.get_listing(listing_id)
                    data_exchange_id = (
                        listing.metadata.get("data_exchange_id", "") if listing.metadata else ""
                    )
                    listing_details = (
                        listing.metadata.get("analytics_hub_listing", {})
                        if listing.metadata
                        else {}
                    )
                    # Check if already subscribed (has bigquery_dataset)
                    bigquery_dataset = listing_details.get("bigquery_dataset")
                    if bigquery_dataset:
                        dataset_ref = (
                            bigquery_dataset.get("dataset")
                            if isinstance(bigquery_dataset, dict)
                            else str(bigquery_dataset)
                        )
                        if dataset_ref:
                            linked_dataset = dataset_ref
                            logger.info(
                                f"Listing {listing_id} already has linked dataset: {linked_dataset}"
                            )

                # Subscribe if not already subscribed
                if not linked_dataset:
                    linked_dataset = self._subscribe_to_listing(listing_id, data_exchange_id)

                # If no table_ref specified, use the first table from the linked dataset
                if not table_ref:
                    # List tables in the linked dataset
                    resources = self.list_resources(listing_id)
                    if not resources:
                        raise NotFoundError(
                            f"No tables found in linked dataset for listing {listing_id}"
                        )
                    # Use the first resource's table reference
                    first_resource = resources[0]
                    table_ref = (
                        first_resource.metadata.get("table_reference")
                        if first_resource.metadata
                        else None
                    )
                    if not table_ref:
                        # Construct from resource_id
                        table_ref = f"{linked_dataset}.{first_resource.resource_id}"

            if not table_ref:
                raise ValueError(
                    f"Could not determine table reference from resource_id: {resource_id}"
                )

            # Parse table reference
            table_parts = table_ref.split(".")
            if len(table_parts) == 3:
                table_project, dataset_id, table_id = table_parts
            elif len(table_parts) == 2:
                table_project = self.project_id
                dataset_id, table_id = table_parts
            else:
                raise ValueError(f"Invalid table reference format: {table_ref}")

            # Extract schema from BigQuery dataset
            schema = self._extract_schema_from_bigquery_dataset(dataset_id, table_id, table_project)

            # Create destination directory if it doesn't exist
            dest_path = Path(destination_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Export table data using BigQuery export job
            client = self._get_bigquery_client()
            table_ref_obj = client.dataset(dataset_id, project=table_project).table(table_id)

            # Determine file format from destination path extension
            file_ext = dest_path.suffix.lower()
            if file_ext in [".csv", ".json", ".avro", ".parquet"]:
                format_type = file_ext[1:].upper()  # Remove dot and uppercase
            else:
                # Default to CSV
                format_type = "CSV"
                dest_path = dest_path.with_suffix(".csv")

            # Export to GCS first (BigQuery requires GCS for exports)
            # For now, export directly to local file using extract_table
            # Note: In production, you might want to export to GCS first, then download
            job_config = bigquery.ExtractJobConfig()
            if format_type == "CSV":
                job_config.destination_format = bigquery.DestinationFormat.CSV
            elif format_type == "JSON":
                job_config.destination_format = bigquery.DestinationFormat.NEWLINE_DELIMITED_JSON
            elif format_type == "AVRO":
                job_config.destination_format = bigquery.DestinationFormat.AVRO
            elif format_type == "PARQUET":
                job_config.destination_format = bigquery.DestinationFormat.PARQUET
            else:
                job_config.destination_format = bigquery.DestinationFormat.CSV

            # For local export, we'll use the extract_table method which writes directly to a file
            # However, BigQuery Python client doesn't support direct local file export
            # We need to export to GCS first, then download
            # For now, we'll use a workaround: export to a temporary GCS bucket
            # In production, you should configure a GCS bucket for exports

            # Alternative: Use query to export data (for smaller datasets)
            # For larger datasets, GCS export is required
            query = f"SELECT * FROM `{table_project}.{dataset_id}.{table_id}`"
            query_job = client.query(query)
            results = query_job.result()

            # Write results to file
            if format_type == "CSV":
                with open(dest_path, "w", newline="", encoding="utf-8") as f:
                    writer = None
                    for row in results:
                        if writer is None:
                            # Initialize CSV writer with headers
                            writer = csv.DictWriter(f, fieldnames=row.keys())
                            writer.writeheader()
                        writer.writerow(dict(row))
            elif format_type == "JSON":
                with open(dest_path, "w", encoding="utf-8") as f:
                    for row in results:
                        json.dump(dict(row), f)
                        f.write("\n")
            else:
                # For other formats, default to CSV
                with open(dest_path, "w", newline="", encoding="utf-8") as f:
                    writer = None
                    for row in results:
                        if writer is None:
                            writer = csv.DictWriter(f, fieldnames=row.keys())
                            writer.writeheader()
                        writer.writerow(dict(row))

            logger.info(f"Exported table {table_ref} to {dest_path}")
            return str(dest_path)

        try:
            return self._execute_with_retry(
                execute_download_resource, "download_resource", f"resource '{resource_id}'"
            )
        except (NotFoundError, PermissionError, ValueError):
            raise
        except Exception as e:
            self._log_with_context(
                "error",
                f"Failed to download resource {resource_id}: {e}",
                operation="download_resource",
                error_message=str(e),
            )
            raise HubConnectionError(f"Failed to download resource: {e}") from e

    def _subscribe_to_listing(self, listing_id: str, data_exchange_id: str) -> str:
        """
        Subscribe to an Analytics Hub listing and create linked dataset.

        Calls Analytics Hub API `subscribe_listing()` with listing name and destination dataset.
        Creates a linked dataset in the project's BigQuery instance.

        Args:
            listing_id: Analytics Hub listing ID
            data_exchange_id: Data exchange ID containing the listing

        Returns:
            Linked dataset name (format: project.dataset)

        Raises:
            NotFoundError: If listing not found
            PermissionError: If user lacks permission to subscribe
            ConnectionError: If unable to connect to Analytics Hub
            ValueError: If listing_id or data_exchange_id is invalid
        """
        if not ANALYTICSHUB_AVAILABLE or AnalyticsHubServiceClient is None:
            raise ImportError(
                "Analytics Hub client library is not installed. "
                "Install it with: pip install google-cloud-bigquery-analyticshub"
            )

        client = self._get_analyticshub_client()
        if client is None:
            raise ImportError("Analytics Hub client is not available")

        def execute_subscribe_to_listing() -> str:
            """Execute subscribe_to_listing."""
            # Build listing path
            listing_path = self._get_listing_path(data_exchange_id, listing_id)

            # Create destination dataset ID (use listing ID as dataset name, sanitized)
            # Dataset IDs must be alphanumeric and underscores, max 1024 chars
            dataset_id = listing_id.replace("-", "_").replace("/", "_")[:1024]
            # Ensure it starts with a letter
            if dataset_id and not dataset_id[0].isalpha():
                dataset_id = "dataset_" + dataset_id

            # Import SubscribeListingRequest and DestinationDataset
            from google.cloud.bigquery_analyticshub_v1.types import (
                DestinationDataset,
                DestinationDatasetReference,
                SubscribeListingRequest,
            )

            # Build destination dataset reference
            # Note: location is not part of DestinationDatasetReference, it's inferred from the dataset
            dataset_ref = DestinationDatasetReference(
                project_id=self.project_id, dataset_id=dataset_id
            )

            # Build destination dataset object
            dest_dataset = DestinationDataset(dataset_reference=dataset_ref)

            # Build subscribe request
            request = SubscribeListingRequest(name=listing_path, destination_dataset=dest_dataset)

            # Subscribe to listing
            try:
                response = client.subscribe_listing(request=request)
                linked_dataset_ref = response.destination_dataset

                # Build dataset reference string
                if linked_dataset_ref:
                    linked_dataset = (
                        f"{linked_dataset_ref.project_id}.{linked_dataset_ref.dataset_id}"
                    )
                    self._log_with_context(
                        "info",
                        f"Successfully subscribed to listing {listing_id}, linked dataset: {linked_dataset}",
                        operation="subscribe_to_listing",
                    )
                    return linked_dataset
                else:
                    # Fallback: construct from destination_dataset
                    linked_dataset = f"{self.project_id}.{dataset_id}"
                    self._log_with_context(
                        "info",
                        f"Subscribed to listing {listing_id}, using dataset: {linked_dataset}",
                        operation="subscribe_to_listing",
                    )
                    return linked_dataset
            except GoogleAPIError as e:
                error_code = getattr(e, "code", None)
                if error_code == 409:
                    # Already subscribed - get the existing dataset
                    self._log_with_context(
                        "info",
                        f"Listing {listing_id} is already subscribed",
                        operation="subscribe_to_listing",
                        error_code=error_code,
                    )
                    # Try to get the listing to find the linked dataset
                    listing = self.get_listing(listing_id)
                    listing_details = (
                        listing.metadata.get("analytics_hub_listing", {})
                        if listing.metadata
                        else {}
                    )
                    bigquery_dataset = listing_details.get("bigquery_dataset")
                    if bigquery_dataset:
                        dataset_ref = (
                            bigquery_dataset.get("dataset")
                            if isinstance(bigquery_dataset, dict)
                            else str(bigquery_dataset)
                        )
                        if dataset_ref:
                            return dataset_ref
                    # Fallback: construct dataset name
                    return f"{self.project_id}.{dataset_id}"
                # Re-raise other errors to be handled by retry logic
                raise

        # Execute with retry logic and circuit breaker protection
        return self._execute_with_retry(
            execute_subscribe_to_listing,
            "subscribe_to_listing",
            f"listing '{listing_id}' in data exchange '{data_exchange_id}'",
        )

    def _extract_schema_from_bigquery_dataset(
        self, dataset_id: str, table_id: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract schema from BigQuery dataset table.

        Queries BigQuery INFORMATION_SCHEMA.COLUMNS for the specified table and
        maps BigQuery data types to ODCS field types.

        Args:
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            project_id: Optional project ID (defaults to self.project_id)

        Returns:
            Structured schema metadata dictionary with fields array

        Raises:
            NotFoundError: If table not found
            ConnectionError: If unable to connect to BigQuery
        """
        project_id = project_id or self.project_id
        if not project_id:
            raise ValueError("project_id is required")

        client = self._get_bigquery_client()

        # Query INFORMATION_SCHEMA.COLUMNS
        query = f"""
        SELECT
            table_schema,
            table_name,
            column_name,
            data_type,
            is_nullable,
            column_default,
            description,
            ordinal_position
        FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = @table_name
        ORDER BY ordinal_position
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("table_name", "STRING", table_id)]
        )

        try:
            query_job = client.query(query, job_config=job_config)
            results = query_job.result()

            # Group columns by table and build schema
            fields = []
            for row in results:
                field = {
                    "name": row.column_name,
                    "type": self._map_bigquery_type(row.data_type),
                    "nullable": row.is_nullable == "YES",
                }
                if row.description:
                    field["description"] = row.description
                if row.column_default:
                    field["default"] = row.column_default
                fields.append(field)

            if not fields:
                raise NotFoundError(
                    f"Table {project_id}.{dataset_id}.{table_id} not found or has no columns"
                )

            schema = {
                "fields": fields,
                "table_name": table_id,
                "dataset_id": dataset_id,
                "project_id": project_id,
            }

            return schema

        except GoogleAPIError as e:
            error_code = getattr(e, "code", None)
            if error_code == 404:
                raise NotFoundError(f"Table {project_id}.{dataset_id}.{table_id} not found") from e
            elif error_code == 403:
                raise PermissionError(
                    f"Permission denied accessing table {project_id}.{dataset_id}.{table_id}"
                ) from e
            raise HubConnectionError(f"Unable to extract schema: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error extracting schema: {e}", exc_info=True)
            raise HubConnectionError(f"Failed to extract schema: {e}") from e

    def _map_bigquery_type(self, bigquery_type: str) -> str:
        """
        Map BigQuery data type to ODCS field type.

        Args:
            bigquery_type: BigQuery data type (e.g., 'STRING', 'INT64', 'FLOAT64')

        Returns:
            ODCS field type (e.g., 'string', 'number', 'boolean', 'datetime')
        """
        bigquery_type_upper = bigquery_type.upper()

        # String types
        if bigquery_type_upper in ["STRING", "BYTES"]:
            return "string"

        # Number types
        if bigquery_type_upper in ["INTEGER", "INT64", "FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"]:
            return "number"

        # Boolean types
        if bigquery_type_upper in ["BOOLEAN", "BOOL"]:
            return "boolean"

        # Date/time types
        if bigquery_type_upper in ["TIMESTAMP", "DATETIME"]:
            return "datetime"
        if bigquery_type_upper == "DATE":
            return "date"
        if bigquery_type_upper == "TIME":
            return "time"

        # Geography types
        if bigquery_type_upper == "GEOGRAPHY":
            return "string"

        # Array types
        if bigquery_type_upper == "ARRAY":
            return "array"

        # Struct/Record types
        if bigquery_type_upper in ["STRUCT", "RECORD"]:
            return "object"

        # Default to string for unknown types
        logger.warning(f"Unknown BigQuery type '{bigquery_type}', mapping to 'string'")
        return "string"

    def map_to_hub_asset(
        self, listing: MarketplaceListing, sync_job_id: Optional[str] = None
    ) -> MarketplaceAssetMapping:
        """
        Map an Analytics Hub listing to a Hub asset representation.

        Extracts comprehensive metadata from Analytics Hub listing including:
        - Asset fields (name, description, domain, status, visibility, tags)
        - ODPS contract data (product details, pricing, access, payment)
        - ODCS contract data (schema hints, quality hints, SLA hints)
        - Marketplace source metadata
        - Resource information (with external references for on-demand download)

        Args:
            listing: MarketplaceListing object to map
            sync_job_id: Optional sync job ID for tracking synchronization operations

        Returns:
            MarketplaceAssetMapping object containing all mapped data

        Raises:
            ValueError: If listing data cannot be mapped
        """
        if not listing:
            raise ValueError("Listing is required")

        # Extract Analytics Hub listing data from metadata
        listing_details = (
            listing.metadata.get("analytics_hub_listing", {}) if listing.metadata else {}
        )
        data_exchange_id = listing.metadata.get("data_exchange_id", "") if listing.metadata else ""
        odps_metadata = listing.metadata.get("odps_metadata", {}) if listing.metadata else {}
        odcs_metadata = listing.metadata.get("odcs_metadata", {}) if listing.metadata else {}

        # Extract title and description
        title = listing.title or listing_details.get("display_name", "Untitled Listing")
        description = listing.description or listing_details.get("description", "")

        # Extract domain from exchange_name (data_exchange_id) as per specification
        # Use data_exchange_id as domain, fallback to category if exchange not available
        domain = None
        if data_exchange_id:
            # Use data_exchange_id as the domain (exchange_name)
            domain = data_exchange_id
        elif listing.category:
            domain = listing.category
        elif listing_details.get("categories"):
            categories = listing_details["categories"]
            if isinstance(categories, list) and categories:
                domain = categories[0]

        # Determine status and visibility
        # Analytics Hub listings are typically ACTIVE and PUBLIC
        status = "ACTIVE"
        visibility = "PUBLIC"

        # Extract tags
        tags = listing.tags or []

        # Build comprehensive asset_data
        asset_data: Dict[str, Any] = {
            "name": title,
            "description": description,
            "key": f"gcp-marketplace-{listing.marketplace_id}",
            "tags": tags,
            "status": status,
            "visibility": visibility,
        }

        # Add optional fields if available
        if domain:
            asset_data["domain"] = domain

        # Extract data provider/publisher from listing details
        provider = listing_details.get("data_provider") or listing_details.get("publisher")

        # Extract source metadata
        source_metadata: Dict[str, Any] = {
            "marketplace_type": MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
            "marketplace_id": listing.marketplace_id,
            "listing_id": listing.marketplace_id,
            "listing_url": listing.url,
            "synced_at": datetime.now().isoformat(),
            "data_exchange_id": data_exchange_id,
        }

        # Add Provider if available
        if provider:
            source_metadata["provider"] = provider

        # Add BigQuery dataset reference if available
        bigquery_dataset = listing_details.get("bigquery_dataset")
        if bigquery_dataset:
            dataset_ref = (
                bigquery_dataset.get("dataset")
                if isinstance(bigquery_dataset, dict)
                else str(bigquery_dataset)
            )
            source_metadata["bigquery_dataset"] = dataset_ref

        # Add sync_job_id if provided
        if sync_job_id:
            source_metadata["sync_job_id"] = sync_job_id

        # Use ODPS and ODCS metadata from listing (already extracted)
        # If not present, extract them
        if not odps_metadata:
            odps_metadata = self._extract_odps_metadata(listing_details, data_exchange_id)
        if not odcs_metadata:
            odcs_metadata = self._extract_odcs_metadata(listing_details)

        # Get resources (with external references for on-demand download)
        resources = []
        try:
            resources = self.list_resources(listing.marketplace_id)
            # Mark resources as external for on-demand download
            for resource in resources:
                if not resource.metadata:
                    resource.metadata = {}
                resource.metadata["external"] = True
                resource.metadata["listing_id"] = listing.marketplace_id
                resource.metadata["data_exchange_id"] = data_exchange_id
                if bigquery_dataset:
                    dataset_ref = (
                        bigquery_dataset.get("dataset")
                        if isinstance(bigquery_dataset, dict)
                        else str(bigquery_dataset)
                    )
                    resource.metadata["bigquery_dataset"] = dataset_ref
        except Exception as e:
            logger.warning(f"Failed to fetch resources for mapping: {e}")

        return MarketplaceAssetMapping(
            asset_data=asset_data,
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata,
            odps_metadata=odps_metadata if odps_metadata else None,
            odcs_metadata=odcs_metadata if odcs_metadata else None,
            resources=resources,
        )

    def map_from_hub_asset(
        self,
        asset_data: Dict[str, Any],
        odps_metadata: Optional[Dict[str, Any]] = None,
        odcs_metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Map a Hub asset to an Analytics Hub listing representation.

        **DEPRECATED**: GCP Marketplace connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            asset_data: Dictionary containing Hub asset fields
            odps_metadata: Optional ODPS contract data
            odcs_metadata: Optional ODCS contract data

        Returns:
            MarketplaceListing object

        Raises:
            NotImplementedError: GCP Marketplace connector does not support push operations
        """
        raise NotImplementedError(
            "GCP Marketplace connector is harvest-only (PULL only). "
            "Analytics Hub is a data marketplace that should be harvested FROM, not pushed TO. "
            "Use map_to_hub_asset() to map Analytics Hub listings TO Hub assets."
        )

    def sync_push(self, asset_ids: List[str], options: Optional[Dict[str, Any]] = None):
        """
        Perform bulk push synchronization (Hub → Analytics Hub).

        **DEPRECATED**: GCP Marketplace connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            asset_ids: List of Hub asset IDs to synchronize
            options: Optional dictionary of sync options

        Returns:
            SyncResult object

        Raises:
            NotImplementedError: GCP Marketplace connector does not support push operations
        """
        raise NotImplementedError(
            "GCP Marketplace connector is harvest-only (PULL only). "
            "Analytics Hub is a data marketplace that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from Analytics Hub."
        )

    def sync_pull(
        self,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """
        Perform bulk pull synchronization (Analytics Hub → Hub) following metadata-first pattern.

        **Metadata-First Behavior**:
        This method discovers listings and maps them to MarketplaceAssetMapping objects. It does
        NOT create assets or download data. Asset creation happens in the workflow via
        `create_federated_asset_with_contracts()`. Data downloads happen on-demand via
        `download_resource()` when `data_strategy != "METADATA_ONLY"`.

        **What This Method Does**:
        1. Discovers listings from Analytics Hub (by IDs or via filters)
        2. For each listing, calls `list_resources()` to fetch resources (metadata-only, if `include_resources=True`)
        3. Maps each listing to MarketplaceAssetMapping using `map_to_hub_asset()`
        4. Includes external resource references in mapping (resources with `metadata.external=True`
           and `metadata.listing_id`, `metadata.bigquery_dataset` for on-demand download)
        5. Returns mappings in SyncResult.metadata["mappings"] for workflow processing

        **What This Method Does NOT Do**:
        - Does NOT subscribe to listings (deferred to `download_resource()`)
        - Does NOT extract schema from BigQuery datasets (deferred to `download_resource()`)
        - Does NOT access external data sources (only stores references)

        Args:
            listing_ids: Optional list of specific listing IDs to sync.
                If None, syncs all listings matching filters.
            filters: Optional dictionary of filters to apply (e.g., category, data_exchange_id)
            options: Optional dictionary of sync options:
                - dry_run: If True, simulate sync without creating assets
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
            ConnectionError: If unable to connect to Analytics Hub
        """
        options = options or {}
        dry_run = options.get("dry_run", False)
        limit = options.get("limit")
        include_resources = options.get("include_resources", True)
        started_at = datetime.now()

        successful_items = 0
        failed_items = 0
        skipped_items = 0
        errors = []
        mappings = []

        def execute_sync_pull() -> SyncResult:
            """Execute sync_pull with circuit breaker protection."""
            nonlocal successful_items, failed_items, skipped_items, errors, mappings

            # Get listings to sync
            try:
                if listing_ids:
                    # Fetch specific listings
                    listings = []
                    for listing_id in listing_ids:
                        try:
                            listing = self.get_listing(listing_id)
                            listings.append(listing)
                        except NotFoundError:
                            skipped_items += 1
                            errors.append(f"Listing {listing_id} not found")
                        except Exception as e:
                            failed_items += 1
                            error_msg = f"Failed to fetch listing {listing_id}: {e}"
                            errors.append(error_msg)
                            logger.error(error_msg, exc_info=True)
                else:
                    # Fetch listings using filters
                    listings = self.list_listings(filters=filters, limit=limit)
            except Exception as e:
                error_msg = f"Failed to fetch listings: {e}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
                return SyncResult(
                    status=SyncStatus.FAILED,
                    total_items=0,
                    successful_items=0,
                    failed_items=0,
                    skipped_items=0,
                    errors=errors,
                    metadata={"dry_run": dry_run},
                    started_at=started_at,
                    completed_at=datetime.now(),
                )

            # If we have skipped items but no listings, return early
            if not listings and skipped_items > 0:
                logger.info(f"No listings found to sync, {skipped_items} skipped")
                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=len(listing_ids) if listing_ids else 0,
                    successful_items=0,
                    failed_items=failed_items,
                    skipped_items=skipped_items,
                    errors=errors,
                    metadata={"dry_run": dry_run, "reason": "no_listings_found", "mappings": []},
                    started_at=started_at,
                    completed_at=datetime.now(),
                )

            if not listings:
                logger.info("No listings found to sync")
                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=0,
                    successful_items=0,
                    failed_items=0,
                    skipped_items=0,
                    errors=[],
                    metadata={"dry_run": dry_run, "reason": "no_listings_found", "mappings": []},
                    started_at=started_at,
                    completed_at=datetime.now(),
                )

            # Process each listing
            for listing in listings:
                try:
                    if dry_run:
                        logger.info(
                            f"DRY RUN: Would pull listing {listing.marketplace_id} from Analytics Hub"
                        )
                        successful_items += 1
                        continue

                    # Fetch resources for the listing (metadata-only)
                    resources = []
                    if include_resources:
                        try:
                            resources = self.list_resources(listing.marketplace_id)
                            # Mark resources as external for on-demand download
                            for resource in resources:
                                if not resource.metadata:
                                    resource.metadata = {}
                                resource.metadata["external"] = True
                                resource.metadata["listing_id"] = listing.marketplace_id
                                # Get data exchange ID and BigQuery dataset from listing metadata
                                data_exchange_id = (
                                    listing.metadata.get("data_exchange_id", "")
                                    if listing.metadata
                                    else ""
                                )
                                resource.metadata["data_exchange_id"] = data_exchange_id
                                listing_details = (
                                    listing.metadata.get("analytics_hub_listing", {})
                                    if listing.metadata
                                    else {}
                                )
                                bigquery_dataset = listing_details.get("bigquery_dataset")
                                if bigquery_dataset:
                                    dataset_ref = (
                                        bigquery_dataset.get("dataset")
                                        if isinstance(bigquery_dataset, dict)
                                        else str(bigquery_dataset)
                                    )
                                    resource.metadata["bigquery_dataset"] = dataset_ref
                        except Exception as e:
                            logger.warning(
                                f"Listing {listing.marketplace_id}: Failed to fetch resources: {e}"
                            )
                            # Continue without resources

                    # Map listing to Hub asset format
                    try:
                        mapping = self.map_to_hub_asset(listing)
                        # Add resources to the mapping if they were fetched
                        if resources:
                            mapping.resources = resources

                        # Serialize mapping to dict for SyncResult metadata
                        mapping_dict = {
                            "asset_data": mapping.asset_data,
                            "source_type": (
                                mapping.source_type.value
                                if hasattr(mapping.source_type, "value")
                                else str(mapping.source_type)
                            ),
                            "source_metadata": mapping.source_metadata,
                            "odps_metadata": mapping.odps_metadata,
                            "odcs_metadata": mapping.odcs_metadata,
                            "resources": [
                                {
                                    "resource_id": r.resource_id,
                                    "resource_type": r.resource_type,
                                    "name": r.name,
                                    "description": r.description,
                                    "url": r.url,
                                    "format": r.format,
                                    "size_bytes": r.size_bytes,
                                    "metadata": r.metadata,
                                }
                                for r in mapping.resources
                            ],
                        }
                        mappings.append(
                            {
                                "listing_id": listing.marketplace_id,
                                "mapping": mapping_dict,
                            }
                        )
                        successful_items += 1
                        logger.info(f"Listing {listing.marketplace_id}: Mapped to Hub asset format")
                    except Exception as e:
                        failed_items += 1
                        error_msg = (
                            f"Listing {listing.marketplace_id}: Failed to map to Hub asset: {e}"
                        )
                        errors.append(error_msg)
                        logger.error(error_msg, exc_info=True)
                        continue

                except Exception as e:
                    failed_items += 1
                    error_msg = f"Listing {listing.marketplace_id}: Unexpected error: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
                    continue

            completed_at = datetime.now()
            status = (
                SyncStatus.COMPLETED
                if failed_items == 0
                else SyncStatus.PARTIAL if successful_items > 0 else SyncStatus.FAILED
            )

            return SyncResult(
                status=status,
                total_items=len(listings),
                successful_items=successful_items,
                failed_items=failed_items,
                skipped_items=skipped_items,
                errors=errors,
                metadata={
                    "dry_run": dry_run,
                    "mappings": mappings,  # List of mappings for asset creation
                    "include_resources": include_resources,
                },
                started_at=started_at,
                completed_at=completed_at,
            )

        # Execute with retry logic and circuit breaker protection
        return self._execute_with_retry(
            execute_sync_pull, "sync_pull", "Analytics Hub synchronization"
        )
