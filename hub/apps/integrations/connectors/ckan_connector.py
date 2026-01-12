"""
CKAN Marketplace Connector

Connector implementation for CKAN (Comprehensive Knowledge Archive Network) instances.
Supports bidirectional synchronization between the Hub and CKAN marketplaces.

Features:
- Circuit breaker protection
- Retry logic with exponential backoff
- Distributed tracing
- Full CRUD operations for datasets (packages) and resources
"""
import httpx
import logging
import time
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse

from django.conf import settings

from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
    MarketplaceListing,
    MarketplaceResource,
    SyncResult,
    MarketplaceAssetMapping,
)
from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)

logger = logging.getLogger(__name__)


class CKANConnector(DataMarketplaceConnector):
    """
    Connector for CKAN marketplace instances (Harvest-Only).

    Implements harvest (pull) operations for discovering and retrieving data from
    CKAN instances. This connector is read-only and does not support push operations
    (create, update, publish) as CKAN instances are public data portals that should
    be harvested FROM, not pushed TO.

    Supports:
    - Discovery: list_listings, get_listing, list_resources
    - Harvest: sync_pull (bulk synchronization from CKAN to Hub)
    - Mapping: map_to_hub_asset (CKAN packages → Hub assets)

    Does NOT support:
    - Push operations: create_listing, update_listing, publish_resource, sync_push
    - Write operations: All methods that modify CKAN instance data

    CKAN API Documentation: https://docs.ckan.org/en/latest/api/
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize CKAN connector.

        Args:
            base_url: Base URL of the CKAN instance (e.g., 'https://data.gov')
            api_key: CKAN API key for authentication (optional for read-only operations)
        """
        # Determine base URL
        if base_url:
            self.base_url = base_url.rstrip('/')
        else:
            self.base_url = getattr(settings, 'CKAN_DEFAULT_BASE_URL', '')
            if not self.base_url:
                raise ValueError("base_url must be provided or CKAN_DEFAULT_BASE_URL must be set")

        # Store API key
        self.api_key = api_key or getattr(settings, 'CKAN_DEFAULT_API_KEY', None)

        # HTTP client configuration
        self.timeout = getattr(settings, 'CKAN_CONNECTOR_TIMEOUT', 30)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize HTTP client
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_default_headers(),
            follow_redirects=True  # Follow redirects for instances that redirect API calls
        )

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="ckan-connector",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client()
        )

        # Track authentication state
        self._authenticated = False

    def _get_default_headers(self) -> Dict[str, str]:
        """Get default HTTP headers including API key if available."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if self.api_key:
            # Check if API key looks like a JWT token (starts with eyJ)
            # If so, use Bearer authentication; otherwise use as CKAN API key
            if self.api_key.startswith('eyJ'):
                # JWT token - use Bearer authentication
                headers['Authorization'] = f'Bearer {self.api_key}'
            else:
                # Standard CKAN API key
                headers['Authorization'] = self.api_key
            # CKAN also supports X-CKAN-API-Key header (for standard API keys)
            # For JWT tokens, we still set it but some instances may ignore it
            headers['X-CKAN-API-Key'] = self.api_key
        return headers

    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make HTTP request with retry logic and circuit breaker protection.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., '/api/3/action/package_list')
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: For HTTP errors
            httpx.RequestError: For network errors
            ConnectionError: If unable to connect after retries
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

        def execute_request() -> httpx.Response:
            """Execute HTTP request."""
            for attempt in range(self.max_retries + 1):
                try:
                    response = self.client.request(method, endpoint, **kwargs)
                    response.raise_for_status()
                    return response
                except httpx.HTTPStatusError as e:
                    # Retry on 5xx errors
                    if e.response.status_code >= 500 and attempt < self.max_retries:
                        delay = self.backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"CKAN API returned {e.response.status_code}. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries + 1})"
                        )
                        time.sleep(delay)
                        continue
                    # Don't retry on 4xx errors (client errors)
                    raise
                except httpx.RequestError as e:
                    # Retry on network errors
                    if attempt < self.max_retries:
                        delay = self.backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"Network error connecting to CKAN: {e}. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries + 1})"
                        )
                        time.sleep(delay)
                        continue
                    raise
            raise ConnectionError("Max retries exceeded for CKAN API request.")

        # Execute with circuit breaker protection
        try:
            return self._circuit_breaker.call(execute_request)
        except Exception as e:
            logger.error(f"CKAN connector request failed: {e}")
            raise

    @property
    def marketplace_type(self) -> MarketplaceType:
        """Get the marketplace type this connector supports."""
        return MarketplaceType.CKAN_INSTANCE

    @property
    def supported_sync_directions(self) -> List[SyncDirection]:
        """
        Get the list of sync directions supported by this connector.

        CKAN connector is harvest-only (PULL only) as CKAN instances are
        public data portals that should be harvested FROM, not pushed TO.
        """
        return [SyncDirection.PULL]

    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with the CKAN instance using provided credentials.

        Args:
            credentials: Dictionary containing:
                - api_key: CKAN API key (required)
                - base_url: CKAN base URL (optional, uses existing if not provided)

        Returns:
            True if authentication successful, False otherwise

        Raises:
            ValueError: If credentials are invalid or missing required fields
            ConnectionError: If unable to connect to CKAN instance
        """
        if not credentials:
            raise ValueError("Credentials dictionary is required")

        api_key = credentials.get('api_key')
        if not api_key:
            raise ValueError("api_key is required in credentials")

        # Update API key
        self.api_key = api_key

        # Update base URL if provided
        base_url = credentials.get('base_url')
        if base_url:
            self.base_url = base_url.rstrip('/')
            # Recreate client with new base URL
            self.client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._get_default_headers()
            )

        # Test authentication by calling status_show action
        try:
            response = self._request_with_retry('GET', '/api/3/action/status_show')
            data = response.json()
            if data.get('success') and 'site_title' in data.get('result', {}):
                self._authenticated = True
                logger.info(f"Successfully authenticated with CKAN instance at {self.base_url}")
                return True
            else:
                self._authenticated = False
                logger.warning("CKAN authentication failed: Invalid response format")
                return False
        except Exception as e:
            self._authenticated = False
            logger.error(f"CKAN authentication failed: {e}")
            raise ConnectionError(f"Unable to authenticate with CKAN instance: {e}") from e

    def test_connection(self) -> bool:
        """
        Test the connection to the CKAN instance.

        Performs a lightweight operation (package_search with minimal results) to verify connectivity.
        Uses package_search instead of status_show as some CKAN instances (like dados.gov.br)
        redirect status_show to signin pages.

        Returns:
            True if connection test successful, False otherwise

        Raises:
            ConnectionError: If unable to connect to CKAN instance
        """
        try:
            # Use package_search with rows=0 as it's more reliable across CKAN instances
            # Some instances redirect status_show to signin pages
            response = self._request_with_retry('GET', '/api/3/action/package_search', params={'rows': 0})
            data = response.json()
            if data.get('success') is not None:  # Accept any response with 'success' field
                logger.info(f"Connection test successful for CKAN instance at {self.base_url}")
                return True
            else:
                logger.warning("Connection test failed: Invalid response format")
                return False
        except Exception as e:
            logger.error(f"Connection test failed for CKAN instance: {e}")
            raise ConnectionError(f"Unable to connect to CKAN instance: {e}") from e

    def list_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[MarketplaceListing]:
        """
        List available datasets (packages) from the CKAN instance.

        Args:
            filters: Optional dictionary of filters:
                - q: Search query string
                - fq: Filter query (e.g., 'tags:environment')
                - organization: Organization name
            limit: Optional maximum number of listings to return
            offset: Optional offset for pagination

        Returns:
            List of MarketplaceListing objects

        Raises:
            ConnectionError: If unable to connect to CKAN instance
            ValueError: If filters or pagination parameters are invalid
        """
        # CKAN package_list action doesn't support limit/offset directly
        # We'll use package_search instead for pagination support
        if limit is not None or offset is not None or filters:
            return self._list_listings_via_search(filters, limit, offset)

        # Use package_list for simple listing
        try:
            response = self._request_with_retry('GET', '/api/3/action/package_list')
            data = response.json()

            if not data.get('success'):
                raise ValueError(f"CKAN API error: {data.get('error', 'Unknown error')}")

            package_ids = data.get('result', [])
            listings = []

            # Fetch details for each package (in batches to avoid overwhelming the API)
            batch_size = 10
            for i in range(0, len(package_ids), batch_size):
                batch = package_ids[i:i + batch_size]
                for package_id in batch:
                    try:
                        listing = self.get_listing(package_id)
                        listings.append(listing)
                    except Exception as e:
                        logger.warning(f"Failed to fetch package {package_id}: {e}")
                        continue

            return listings
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ConnectionError(f"CKAN API endpoint not found: {e}") from e
            raise ConnectionError(f"CKAN API error: {e}") from e
        except httpx.RequestError as e:
            # Handle connection errors (ConnectError, TimeoutException, etc.)
            raise ConnectionError(f"Unable to connect to CKAN instance: {e}") from e

    def _list_listings_via_search(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[MarketplaceListing]:
        """List listings using package_search API (supports pagination and filters)."""
        params: Dict[str, Any] = {
            'rows': limit or 100,  # Default to 100 if not specified
            'start': offset or 0,
        }

        if filters:
            if 'q' in filters:
                params['q'] = filters['q']

            # Build fq (filter query) parameter
            fq_parts = []
            if 'fq' in filters:
                fq_parts.append(filters['fq'])
            if 'organization' in filters:
                fq_parts.append(f"organization:{filters['organization']}")

            if fq_parts:
                # Join multiple filter queries with AND
                params['fq'] = ' AND '.join(fq_parts)  # type: ignore[assignment]

        try:
            response = self._request_with_retry('GET', '/api/3/action/package_search', params=params)
            data = response.json()

            if not data.get('success'):
                raise ValueError(f"CKAN API error: {data.get('error', 'Unknown error')}")

            results = data.get('result', {}).get('results', [])
            listings = []

            for package_data in results:
                try:
                    listing = self._package_to_listing(package_data)
                    listings.append(listing)
                except Exception as e:
                    logger.warning(f"Failed to convert package to listing: {e}")
                    continue

            return listings
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ConnectionError(f"CKAN API endpoint not found: {e}") from e
            raise ConnectionError(f"CKAN API error: {e}") from e
        except httpx.RequestError as e:
            # Handle connection errors (ConnectError, TimeoutException, etc.)
            raise ConnectionError(f"Unable to connect to CKAN instance: {e}") from e

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        """
        Get a specific dataset (package) by its ID.

        Args:
            listing_id: CKAN package ID or name

        Returns:
            MarketplaceListing object

        Raises:
            NotFoundError: If package not found
            ConnectionError: If unable to connect to CKAN instance
        """
        try:
            response = self._request_with_retry(
                'GET',
                '/api/3/action/package_show',
                params={'id': listing_id}
            )
            data = response.json()

            if not data.get('success'):
                error_msg = data.get('error', {}).get('message', 'Unknown error')
                if 'Not found' in error_msg or 'not found' in error_msg.lower():
                    raise NotFoundError(f"Package '{listing_id}' not found in CKAN instance")
                raise ValueError(f"CKAN API error: {error_msg}")

            package_data = data.get('result', {})
            return self._package_to_listing(package_data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Package '{listing_id}' not found in CKAN instance") from e
            raise ConnectionError(f"CKAN API error: {e}") from e
        except httpx.RequestError as e:
            # Handle connection errors (ConnectError, TimeoutException, etc.)
            raise ConnectionError(f"Unable to connect to CKAN instance: {e}") from e

    def _package_to_listing(self, package_data: Dict[str, Any]) -> MarketplaceListing:
        """Convert CKAN package data to MarketplaceListing."""
        package_id = package_data.get('id') or package_data.get('name', '')
        title = package_data.get('title', package_data.get('name', 'Untitled'))
        description = package_data.get('notes') or package_data.get('description', '')

        # Extract tags
        tags = [tag.get('name', tag) if isinstance(tag, dict) else tag for tag in package_data.get('tags', [])]

        # Extract organization
        organization = package_data.get('organization', {})
        category = organization.get('name', '') if organization else None

        # Extract timestamps
        created_at = None
        updated_at = None
        if package_data.get('metadata_created'):
            try:
                created_at = datetime.fromisoformat(package_data['metadata_created'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        if package_data.get('metadata_modified'):
            try:
                updated_at = datetime.fromisoformat(package_data['metadata_modified'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass

        # Build URL
        url = None
        if package_id:
            url = urljoin(self.base_url, f'/dataset/{package_id}')

        return MarketplaceListing(
            marketplace_id=package_id,
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title=title,
            description=description,
            category=category,
            tags=tags,
            metadata={
                'ckan_package': package_data,
                'organization': organization,
                'license_id': package_data.get('license_id'),
                'license_title': package_data.get('license_title'),
                'author': package_data.get('author'),
                'maintainer': package_data.get('maintainer'),
                'version': package_data.get('version'),
            },
            created_at=created_at,
            updated_at=updated_at,
            url=url
        )

    def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
        """
        List resources associated with a CKAN package.

        Args:
            listing_id: CKAN package ID or name

        Returns:
            List of MarketplaceResource objects

        Raises:
            NotFoundError: If package not found
            ConnectionError: If unable to connect to CKAN instance
        """
        # Get package to retrieve resources
        try:
            package = self.get_listing(listing_id)
        except NotFoundError:
            raise

        # Extract resources from package metadata
        package_data = package.metadata.get('ckan_package', {})
        resources_data = package_data.get('resources', [])

        # If resources not in package data, fetch them directly via package_show
        if not resources_data:
            try:
                response = self._request_with_retry(
                    'GET',
                    '/api/3/action/package_show',
                    params={'id': listing_id}
                )
                data = response.json()
                if data.get('success'):
                    package_data = data.get('result', {})
                    resources_data = package_data.get('resources', [])
            except Exception as e:
                logger.warning(f"Failed to fetch resources directly for package {listing_id}: {e}")

        resources = []
        for resource_data in resources_data:
            try:
                resource = self._ckan_resource_to_marketplace_resource(resource_data)
                resources.append(resource)
            except Exception as e:
                logger.warning(f"Failed to convert CKAN resource to MarketplaceResource: {e}")
                continue

        return resources

    def _ckan_resource_to_marketplace_resource(self, resource_data: Dict[str, Any]) -> MarketplaceResource:
        """Convert CKAN resource data to MarketplaceResource."""
        resource_id = resource_data.get('id', '')
        name = resource_data.get('name', resource_data.get('description', 'Unnamed Resource'))
        description = resource_data.get('description', '')
        url = resource_data.get('url', '')
        format_type = resource_data.get('format', '').upper() if resource_data.get('format') else None
        size_bytes = resource_data.get('size')

        return MarketplaceResource(
            resource_id=resource_id,
            resource_type='FILE' if url else 'API',
            name=name,
            description=description,
            url=url,
            format=format_type,
            size_bytes=size_bytes,
            metadata={
                'ckan_resource': resource_data,
                'mimetype': resource_data.get('mimetype'),
                'mimetype_inner': resource_data.get('mimetype_inner'),
                'hash': resource_data.get('hash'),
                'created': resource_data.get('created'),
                'last_modified': resource_data.get('last_modified'),
            }
        )

    def create_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
        """
        Create a new dataset (package) in the CKAN instance.

        **DEPRECATED**: CKAN connector is harvest-only (PULL only).
        CKAN instances are public data portals that should be harvested FROM,
        not pushed TO. This method raises NotImplementedError.

        Args:
            listing: MarketplaceListing object with package details

        Returns:
            Created MarketplaceListing object with CKAN-assigned ID

        Raises:
            NotImplementedError: CKAN connector does not support push operations
        """
        raise NotImplementedError(
            "CKAN connector is harvest-only (PULL only). "
            "CKAN instances are public data portals that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from CKAN instances."
        )

    def update_listing(
        self,
        listing_id: str,
        listing: MarketplaceListing
    ) -> MarketplaceListing:
        """
        Update an existing dataset (package) in the CKAN instance.

        **DEPRECATED**: CKAN connector is harvest-only (PULL only).
        CKAN instances are public data portals that should be harvested FROM,
        not pushed TO. This method raises NotImplementedError.

        Args:
            listing_id: ID of the package to update
            listing: MarketplaceListing object with updated package details

        Returns:
            Updated MarketplaceListing object

        Raises:
            NotImplementedError: CKAN connector does not support push operations
        """
        raise NotImplementedError(
            "CKAN connector is harvest-only (PULL only). "
            "CKAN instances are public data portals that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from CKAN instances."
        )

    def _listing_to_ckan_package(self, listing: MarketplaceListing, create: bool = False) -> Dict[str, Any]:
        """Convert MarketplaceListing to CKAN package format."""
        package_data: Dict[str, Any] = {
            'name': listing.marketplace_id or self._generate_package_name(listing.title),
            'title': listing.title,
        }

        if listing.description:
            package_data['notes'] = listing.description

        if listing.tags:
            # CKAN API expects tags as list of dicts with 'name' key
            package_data['tags'] = [{'name': str(tag)} for tag in listing.tags]  # type: ignore[assignment]

        if listing.category:
            package_data['owner_org'] = listing.category

        # Add metadata
        if listing.metadata:
            if 'license_id' in listing.metadata:
                package_data['license_id'] = listing.metadata['license_id']
            if 'author' in listing.metadata:
                package_data['author'] = listing.metadata['author']
            if 'maintainer' in listing.metadata:
                package_data['maintainer'] = listing.metadata['maintainer']
            if 'version' in listing.metadata:
                package_data['version'] = listing.metadata['version']

        return package_data

    def _generate_package_name(self, title: str) -> str:
        """Generate a valid CKAN package name from title."""
        import re
        # Convert to lowercase, replace spaces with hyphens, remove special chars
        name = re.sub(r'[^a-z0-9-]', '', title.lower().replace(' ', '-'))
        # Ensure it starts with a letter
        if name and not name[0].isalpha():
            name = 'pkg-' + name
        return name[:100]  # CKAN name limit

    def _extract_multilingual_field(
        self,
        package_data: Dict[str, Any],
        field_names: List[str],
        fallback_value: str
    ) -> str:
        """
        Extract multilingual field from CKAN package data.

        Handles multilingual fields that may be:
        - Simple string value
        - Dictionary keyed by language codes (e.g., {'en': 'English', 'fr': 'Français'})
        - List of dictionaries with language codes

        Prefers English ('en') when available, otherwise uses first available language.

        Args:
            package_data: CKAN package data dictionary
            field_names: List of field names to check (in order of preference)
            fallback_value: Value to use if field not found

        Returns:
            Extracted field value as string
        """
        for field_name in field_names:
            if field_name not in package_data:
                continue

            value = package_data[field_name]
            if value is None:
                continue

            # Handle string value
            if isinstance(value, str):
                return value.strip() if value.strip() else fallback_value

            # Handle dictionary keyed by language codes
            if isinstance(value, dict):
                # Check if keys look like language codes (2-letter lowercase)
                is_language_keyed = all(
                    isinstance(k, str) and len(k) == 2 and k.islower()
                    for k in value.keys()
                )

                if is_language_keyed:
                    # Prefer English, fallback to first available
                    if 'en' in value:
                        result = value['en']
                        if isinstance(result, str) and result.strip():
                            return result.strip()
                    # Fallback to first available language
                    for lang_value in value.values():
                        if isinstance(lang_value, str) and lang_value.strip():
                            return lang_value.strip()

                # Not language-keyed, try to extract string value
                if len(value) == 1:
                    first_value = next(iter(value.values()))
                    if isinstance(first_value, str) and first_value.strip():
                        return first_value.strip()

            # Handle list of dictionaries
            if isinstance(value, list) and value:
                # Try to extract from first item
                first_item = value[0]
                if isinstance(first_item, dict):
                    # Look for common language fields
                    for lang_code in ['en', 'name', 'title', 'value']:
                        if lang_code in first_item:
                            result = first_item[lang_code]
                            if isinstance(result, str) and result.strip():
                                return result.strip()

        return fallback_value

    def _extract_odps_metadata(
        self,
        listing: MarketplaceListing,
        ckan_package: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract ODPS contract metadata from CKAN package.

        Extracts:
        - Product details (name, description, version, categories, tags)
        - Pricing plans (if available in metadata)
        - Access methods (if available in metadata)
        - Payment gateways (if available in metadata)

        Args:
            listing: MarketplaceListing object
            ckan_package: Raw CKAN package data

        Returns:
            Dictionary with ODPS metadata or None if no ODPS data available
        """
        odps_metadata: Dict[str, Any] = {}

        # Extract basic product details
        product_details: Dict[str, Any] = {
            'product_name': listing.title,
            'product_description': listing.description or '',
        }

        # Extract version if available
        version = ckan_package.get('version') or listing.metadata.get('version') if listing.metadata else None
        if version:
            product_details['product_version'] = str(version)

        # Extract categories
        categories = []
        if listing.category:
            categories.append(listing.category)
        if ckan_package.get('organization'):
            org = ckan_package['organization']
            if isinstance(org, dict):
                org_name = org.get('name') or org.get('title')
                if org_name and org_name not in categories:
                    categories.append(org_name)
        if categories:
            product_details['categories'] = categories

        # Extract tags
        tags = listing.tags or []
        if tags:
            product_details['tags'] = tags

        # Extract license information
        license_id = ckan_package.get('license_id') or (listing.metadata.get('license_id') if listing.metadata else None)
        license_title = ckan_package.get('license_title') or (listing.metadata.get('license_title') if listing.metadata else None)
        if license_id:
            product_details['license_id'] = license_id
        if license_title:
            product_details['license_title'] = license_title

        # Extract author and maintainer
        author = ckan_package.get('author') or (listing.metadata.get('author') if listing.metadata else None)
        maintainer = ckan_package.get('maintainer') or (listing.metadata.get('maintainer') if listing.metadata else None)
        if author:
            product_details['author'] = author
        if maintainer:
            product_details['maintainer'] = maintainer

        # Track if we have any ODPS-specific data
        # ODPS-specific fields: pricing_plans, access_methods, payment_gateways,
        # version, license_id, author, maintainer
        # Basic fields (name, description, categories, tags) are NOT ODPS-specific
        has_odps_data = False

        # Extract pricing plans from listing metadata if available
        # CKAN doesn't natively support pricing, but it may be stored in custom metadata
        if listing.metadata:
            # Check for ODPS pricing plans in metadata
            pricing_plans = listing.metadata.get('pricing_plans') or listing.metadata.get('x_odps', {}).get('pricing_plans')
            if pricing_plans and isinstance(pricing_plans, list):
                odps_metadata['pricing_plans'] = pricing_plans
                has_odps_data = True

            # Extract access methods
            access_methods = listing.metadata.get('access_methods') or listing.metadata.get('x_odps', {}).get('access_methods')
            if access_methods and isinstance(access_methods, dict):
                odps_metadata['access_methods'] = access_methods
                has_odps_data = True

            # Extract payment gateways
            payment_gateways = listing.metadata.get('payment_gateways') or listing.metadata.get('x_odps', {}).get('payment_gateways')
            if payment_gateways and isinstance(payment_gateways, dict):
                odps_metadata['payment_gateways'] = payment_gateways
                has_odps_data = True

        # Check for ODPS-specific product details fields
        if version or license_id or author or maintainer:
            has_odps_data = True

        # Only return ODPS metadata if we have meaningful ODPS-specific data
        if has_odps_data:
            # Include product_details with all available fields
            odps_metadata['product_details'] = product_details
            return odps_metadata

        return None

    def _extract_odcs_metadata(
        self,
        ckan_package: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract ODCS contract metadata from CKAN package.

        Extracts:
        - Schema information (if available in resources or custom fields)
        - Quality rules (if available)
        - SLA information (if available)

        CKAN packages don't natively support ODCS, but metadata may be stored
        in custom fields or resource metadata.

        Args:
            ckan_package: Raw CKAN package data

        Returns:
            Dictionary with ODCS metadata or None if no ODCS data available
        """
        odcs_metadata: Dict[str, Any] = {}

        # Check for ODCS schema in custom fields
        # CKAN packages may have schema information in extras or custom fields
        extras = ckan_package.get('extras', [])
        if isinstance(extras, list):
            for extra in extras:
                if isinstance(extra, dict):
                    key = extra.get('key', '')
                    value = extra.get('value', '')

                    # Look for schema-related fields
                    if key in ['schema', 'odcs_schema', 'data_schema']:
                        try:
                            import json
                            if isinstance(value, str):
                                schema_data = json.loads(value)
                            else:
                                schema_data = value
                            if isinstance(schema_data, dict):
                                odcs_metadata['schema'] = schema_data
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # Look for quality rules
                    if key in ['quality', 'odcs_quality', 'quality_rules']:
                        try:
                            import json
                            if isinstance(value, str):
                                quality_data = json.loads(value)
                            else:
                                quality_data = value
                            if isinstance(quality_data, dict):
                                odcs_metadata['quality'] = quality_data
                        except (json.JSONDecodeError, TypeError):
                            pass

                    # Look for SLA information
                    if key in ['sla', 'odcs_sla', 'service_level']:
                        try:
                            import json
                            if isinstance(value, str):
                                sla_data = json.loads(value)
                            else:
                                sla_data = value
                            if isinstance(sla_data, dict):
                                odcs_metadata['sla'] = sla_data
                        except (json.JSONDecodeError, TypeError):
                            pass

        # Check for ODCS data in top-level custom fields
        for key in ['odcs_schema', 'odcs_quality', 'odcs_sla', 'schema', 'quality', 'sla']:
            if key in ckan_package:
                value = ckan_package[key]
                if isinstance(value, dict):
                    if key.startswith('odcs_'):
                        odcs_key = key.replace('odcs_', '')
                        odcs_metadata[odcs_key] = value
                    else:
                        odcs_metadata[key] = value

        # Only return ODCS metadata if we have meaningful data
        if odcs_metadata:
            return odcs_metadata

        return None

    def publish_resource(
        self,
        listing_id: str,
        resource: MarketplaceResource
    ) -> MarketplaceResource:
        """
        Publish a resource to a CKAN package.

        **DEPRECATED**: CKAN connector is harvest-only (PULL only).
        CKAN instances are public data portals that should be harvested FROM,
        not pushed TO. This method raises NotImplementedError.

        Args:
            listing_id: CKAN package ID or name
            resource: MarketplaceResource object with resource details

        Returns:
            Published MarketplaceResource object with CKAN-assigned ID

        Raises:
            NotImplementedError: CKAN connector does not support push operations
        """
        raise NotImplementedError(
            "CKAN connector is harvest-only (PULL only). "
            "CKAN instances are public data portals that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from CKAN instances."
        )

    def download_resource(self, resource_id: str, destination_path: str) -> str:
        """
        Download a resource from the CKAN instance.

        Args:
            resource_id: CKAN resource ID
            destination_path: Local filesystem path where resource should be saved

        Returns:
            Path to the downloaded file

        Raises:
            NotFoundError: If resource not found
            ConnectionError: If unable to connect to CKAN instance
            IOError: If unable to write to destination path
            PermissionError: If user lacks permission to download resource
        """
        # Get resource details
        try:
            response = self._request_with_retry(
                'GET',
                '/api/3/action/resource_show',
                params={'id': resource_id}
            )
            data = response.json()

            if not data.get('success'):
                error_msg = data.get('error', {}).get('message', 'Unknown error')
                if 'not found' in error_msg.lower():
                    raise NotFoundError(f"Resource '{resource_id}' not found")
                raise ValueError(f"CKAN API error: {error_msg}")

            resource_data = data.get('result', {})
            resource_url = resource_data.get('url')

            if not resource_url:
                raise ValueError("Resource has no URL")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Resource '{resource_id}' not found") from e
            if e.response.status_code == 403:
                raise PermissionError(f"Permission denied: Unable to access resource '{resource_id}'") from e
            raise ConnectionError(f"CKAN API error: {e}") from e
        except httpx.RequestError as e:
            # Handle connection errors (ConnectError, TimeoutException, etc.)
            raise ConnectionError(f"Unable to connect to CKAN instance: {e}") from e

        # Download the resource
        try:
            # Validate destination path
            if not destination_path:
                raise ValueError("destination_path cannot be empty")

            # Create destination directory if it doesn't exist
            dest_dir = os.path.dirname(destination_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            # Check if destination is a directory (invalid)
            if os.path.exists(destination_path) and os.path.isdir(destination_path):
                raise IOError(f"Destination path is a directory, not a file: {destination_path}")

            # Download file with retry logic
            download_response = None
            max_download_retries = 2
            for attempt in range(max_download_retries + 1):
                try:
                    download_response = httpx.get(
                        resource_url,
                        timeout=self.timeout,
                        follow_redirects=True,
                        headers=self._get_default_headers()  # Include API key if available
                    )
                    download_response.raise_for_status()
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500 and attempt < max_download_retries:
                        # Retry on server errors
                        delay = self.backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"Download failed with {e.response.status_code}. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{max_download_retries + 1})"
                        )
                        time.sleep(delay)
                        continue
                    elif e.response.status_code == 403:
                        raise PermissionError(f"Permission denied: Unable to download resource '{resource_id}'") from e
                    elif e.response.status_code == 404:
                        raise NotFoundError(f"Resource URL not found: {resource_url}") from e
                    raise ConnectionError(f"Failed to download resource: HTTP {e.response.status_code}") from e
                except httpx.RequestError as e:
                    if attempt < max_download_retries:
                        delay = self.backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"Network error downloading resource. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{max_download_retries + 1})"
                        )
                        time.sleep(delay)
                        continue
                    raise ConnectionError(f"Failed to download resource: {e}") from e

            if download_response is None:
                raise ConnectionError("Failed to download resource after retries")

            # Write to file atomically (write to temp file first, then rename)
            temp_path = destination_path + '.tmp'
            try:
                with open(temp_path, 'wb') as f:
                    # Write in chunks for large files
                    chunk_size = 8192  # 8KB chunks
                    for chunk in download_response.iter_bytes(chunk_size):
                        f.write(chunk)

                # Atomic rename
                os.replace(temp_path, destination_path)

                logger.info(
                    f"Downloaded resource {resource_id} to {destination_path} "
                    f"({len(download_response.content)} bytes)"
                )
                return destination_path
            except IOError as e:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
                raise IOError(f"Failed to write to destination path {destination_path}: {e}") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to download resource: {e}") from e
        except IOError:
            # Re-raise IOError as-is
            raise
        except Exception as e:
            # Catch any other exceptions and convert appropriately
            if isinstance(e, (NotFoundError, PermissionError, ConnectionError, IOError, ValueError)):
                raise
            raise ConnectionError(f"Unexpected error downloading resource: {e}") from e

    def map_to_hub_asset(
        self,
        listing: MarketplaceListing,
        sync_job_id: Optional[str] = None
    ) -> MarketplaceAssetMapping:
        """
        Map a CKAN package to a Hub asset representation.

        Extracts comprehensive metadata from CKAN package including:
        - Asset fields (name, description, domain, status, visibility, tags)
        - ODPS contract data (product details, pricing, access, payment)
        - ODCS contract data (schema, quality, SLA) if available
        - Marketplace source metadata
        - Resource information

        Handles multilingual fields gracefully, preferring English when available.

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

        # Get CKAN package data from metadata
        ckan_package = listing.metadata.get('ckan_package', {}) if listing.metadata else {}

        # Extract multilingual title and description
        title = self._extract_multilingual_field(
            ckan_package,
            ['title', 'name'],
            listing.title
        )
        description = self._extract_multilingual_field(
            ckan_package,
            ['notes', 'description'],
            listing.description or ''
        )

        # Extract domain from organization/category
        domain = None
        if listing.category:
            domain = listing.category
        elif ckan_package.get('organization'):
            org = ckan_package['organization']
            if isinstance(org, dict):
                domain = org.get('name') or org.get('title')
            elif isinstance(org, str):
                domain = org

        # Determine status and visibility from CKAN package state
        # CKAN packages don't have explicit status/visibility, so we infer from private flag
        status = 'DRAFT'  # Default to DRAFT for imported assets
        visibility = 'INTERNAL'  # Default to INTERNAL for imported assets

        # Check if package is private (CKAN has 'private' field)
        is_private = ckan_package.get('private', False)
        if not is_private:
            # Public packages can be mapped to PUBLIC visibility
            visibility = 'PUBLIC'
            # If public and has resources, can be ACTIVE
            if listing.metadata and listing.metadata.get('ckan_package', {}).get('resources'):
                status = 'ACTIVE'

        # Extract tags
        tags = listing.tags or []
        if not tags and ckan_package.get('tags'):
            tags = [
                tag.get('name', tag) if isinstance(tag, dict) else tag
                for tag in ckan_package.get('tags', [])
            ]

        # Build comprehensive asset_data
        asset_data: Dict[str, Any] = {
            'name': title,
            'description': description,
            'key': f"ckan-{listing.marketplace_id}",
            'tags': tags,
        }

        # Add optional fields if available
        if domain:
            asset_data['domain'] = domain
        if status:
            asset_data['status'] = status
        if visibility:
            asset_data['visibility'] = visibility

        # Extract source metadata
        source_metadata: Dict[str, Any] = {
            'marketplace_type': MarketplaceType.CKAN_INSTANCE.value,
            'marketplace_id': listing.marketplace_id,
            'listing_id': listing.marketplace_id,
            'listing_url': listing.url,
            'synced_at': datetime.now().isoformat(),
        }

        # Add sync_job_id if provided
        if sync_job_id:
            source_metadata['sync_job_id'] = sync_job_id

        # Extract comprehensive ODPS metadata
        odps_metadata = self._extract_odps_metadata(listing, ckan_package)

        # Extract ODCS metadata if available
        odcs_metadata = self._extract_odcs_metadata(ckan_package)

        # Get resources
        resources = []
        try:
            resources = self.list_resources(listing.marketplace_id)
        except Exception as e:
            logger.warning(f"Failed to fetch resources for mapping: {e}")

        return MarketplaceAssetMapping(
            asset_data=asset_data,
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata,
            odps_metadata=odps_metadata,
            odcs_metadata=odcs_metadata,
            resources=resources
        )

    def map_from_hub_asset(
        self,
        asset_data: Dict[str, Any],
        odps_metadata: Optional[Dict[str, Any]] = None,
        odcs_metadata: Optional[Dict[str, Any]] = None
    ) -> MarketplaceListing:
        """
        Map a Hub asset to a CKAN package representation.

        **DEPRECATED**: CKAN connector is harvest-only (PULL only).
        CKAN instances are public data portals that should be harvested FROM,
        not pushed TO. This method raises NotImplementedError.

        Args:
            asset_data: Dictionary containing Hub asset fields
            odps_metadata: Optional ODPS contract data
            odcs_metadata: Optional ODCS contract data

        Returns:
            MarketplaceListing object ready for CKAN operations

        Raises:
            NotImplementedError: CKAN connector does not support push operations
        """
        raise NotImplementedError(
            "CKAN connector is harvest-only (PULL only). "
            "CKAN instances are public data portals that should be harvested FROM, not pushed TO. "
            "Use map_to_hub_asset() to map CKAN packages TO Hub assets."
        )

    def sync_push(self, asset_ids: List[str], options: Optional[Dict[str, Any]] = None) -> SyncResult:
        """
        Perform bulk push synchronization (Hub → CKAN).

        **DEPRECATED**: CKAN connector is harvest-only (PULL only).
        CKAN instances are public data portals that should be harvested FROM,
        not pushed TO. This method raises NotImplementedError.

        Args:
            asset_ids: List of Hub asset IDs to synchronize
            options: Optional dictionary of sync options

        Returns:
            SyncResult object with operation details

        Raises:
            NotImplementedError: CKAN connector does not support push operations
        """
        raise NotImplementedError(
            "CKAN connector is harvest-only (PULL only). "
            "CKAN instances are public data portals that should be harvested FROM, not pushed TO. "
            "Use sync_pull() to harvest data from CKAN instances."
        )

    def _listing_changed(self, existing: MarketplaceListing, new: MarketplaceListing) -> bool:
        """
        Check if a listing has changed compared to existing version.

        Args:
            existing: Existing marketplace listing
            new: New marketplace listing

        Returns:
            True if listing has changed, False otherwise
        """
        # Compare key fields that would indicate a change
        if existing.title != new.title:
            return True
        if existing.description != new.description:
            return True
        if set(existing.tags or []) != set(new.tags or []):
            return True
        if existing.category != new.category:
            return True

        # Compare organization from metadata (CKAN stores organization in metadata)
        existing_org = existing.metadata.get('organization', {}).get('name', '') if existing.metadata else ''
        new_org = new.metadata.get('organization', {}).get('name', '') if new.metadata else ''
        if existing_org != new_org:
            return True

        # Compare metadata (simplified comparison)
        existing_metadata = existing.metadata or {}
        new_metadata = new.metadata or {}
        if existing_metadata != new_metadata:
            return True

        return False

    def sync_pull(
        self,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Perform bulk pull synchronization (CKAN → Hub).

        Synchronizes CKAN listings to Hub by:
        1. Fetching listings from CKAN (by IDs or via filters)
        2. Fetching resources for each listing
        3. Mapping listings to Hub asset format using map_to_hub_asset
        4. Returning mappings in SyncResult metadata for asset creation

        Args:
            listing_ids: Optional list of specific package IDs to sync.
                If None, syncs all packages matching filters.
            filters: Optional dictionary of filters to apply (passed to list_listings)
            options: Optional dictionary of sync options:
                - dry_run: If True, simulate sync without creating assets
                - limit: Maximum number of listings to sync (default: None, sync all)
                - include_resources: If True, fetch resources for each listing (default: True)

        Returns:
            SyncResult object with operation details and mappings in metadata

        Raises:
            ValueError: If filters or options are invalid
            ConnectionError: If unable to connect to CKAN instance
        """
        options = options or {}
        dry_run = options.get('dry_run', False)
        limit = options.get('limit')
        include_resources = options.get('include_resources', True)
        started_at = datetime.now()

        successful_items = 0
        failed_items = 0
        skipped_items = 0
        errors = []
        mappings = []

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
                        logger.error(error_msg)
            else:
                # Fetch listings using filters
                listings = self.list_listings(filters=filters, limit=limit)
        except Exception as e:
            error_msg = f"Failed to fetch listings: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
            return SyncResult(
                status=SyncStatus.FAILED,
                total_items=0,
                successful_items=0,
                failed_items=0,
                skipped_items=0,
                errors=errors,
                metadata={'dry_run': dry_run},
                started_at=started_at,
                completed_at=datetime.now()
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
                metadata={'dry_run': dry_run, 'reason': 'no_listings_found'},
                started_at=started_at,
                completed_at=datetime.now()
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
                metadata={'dry_run': dry_run, 'reason': 'no_listings_found'},
                started_at=started_at,
                completed_at=datetime.now()
            )

        # Process each listing
        for listing in listings:
            try:
                if dry_run:
                    logger.info(f"DRY RUN: Would pull listing {listing.marketplace_id} from CKAN")
                    successful_items += 1
                    continue

                # Fetch resources for the listing
                resources = []
                if include_resources:
                    try:
                        resources = self.list_resources(listing.marketplace_id)
                    except Exception as e:
                        logger.warning(f"Listing {listing.marketplace_id}: Failed to fetch resources: {e}")
                        # Continue without resources

                # Map listing to Hub asset format
                try:
                    # map_to_hub_asset doesn't accept resources parameter directly
                    # Resources are fetched separately and included in the mapping
                    mapping = self.map_to_hub_asset(listing)
                    # Add resources to the mapping if they were fetched
                    if resources:
                        mapping.resources = resources
                    mappings.append({
                        'listing_id': listing.marketplace_id,
                        'mapping': mapping,
                    })
                    successful_items += 1
                    logger.info(f"Listing {listing.marketplace_id}: Mapped to Hub asset format")
                except Exception as e:
                    failed_items += 1
                    error_msg = f"Listing {listing.marketplace_id}: Failed to map to Hub asset: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    continue

            except Exception as e:
                failed_items += 1
                error_msg = f"Listing {listing.marketplace_id}: Unexpected error: {e}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)

        completed_at = datetime.now()
        status = SyncStatus.COMPLETED if failed_items == 0 else SyncStatus.PARTIAL if successful_items > 0 else SyncStatus.FAILED

        return SyncResult(
            status=status,
            total_items=len(listings),
            successful_items=successful_items,
            failed_items=failed_items,
            skipped_items=skipped_items,
            errors=errors,
            metadata={
                'dry_run': dry_run,
                'mappings': mappings,  # List of mappings for asset creation
                'include_resources': include_resources,
            },
            started_at=started_at,
            completed_at=completed_at
        )

