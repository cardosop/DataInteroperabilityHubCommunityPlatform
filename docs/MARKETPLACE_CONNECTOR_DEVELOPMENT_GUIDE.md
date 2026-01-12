# Marketplace Connector Development Guide

Complete guide for developing marketplace connectors following the metadata-first architecture pattern.

**Last Updated**: 2026-01-10
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Connector Interface Requirements](#connector-interface-requirements)
4. [Authentication Patterns](#authentication-patterns)
5. [Metadata Mapping Patterns](#metadata-mapping-patterns)
6. [Error Handling Patterns](#error-handling-patterns)
7. [Testing Requirements](#testing-requirements)
8. [Code Examples](#code-examples)
9. [Best Practices](#best-practices)
10. [Common Mistakes](#common-mistakes)
11. [Reference Implementations](#reference-implementations)

---

## Overview

Marketplace connectors enable bidirectional synchronization between the Data Interoperability Hub and external data marketplaces (CKAN, Snowflake Data Marketplace, AWS Data Exchange, Azure Data Share, GCP Marketplace, Databricks, etc.).

All connectors follow a **metadata-first architecture pattern** that ensures:
- **Fast Harvesting**: Create thousands of federated assets quickly without downloading data (seconds vs hours)
- **Scalability**: Harvest large marketplaces without storage overhead (metadata-only assets are lightweight)
- **Clear Separation**: Federated assets (external metadata) vs Virtualized assets (virtual queries)
- **Lazy Data Access**: Download data only when explicitly requested (reduces storage costs, improves performance)
- **Governance/Compliance/Semantic Layers**: All layers work with metadata-first federated assets

### Connector Responsibilities

Connectors have four main responsibilities:

1. **Discovery**: `list_listings()`, `get_listing()`, `list_resources()` - Discover marketplace listings
2. **Mapping**: `map_to_hub_asset()` → `MarketplaceAssetMapping` - Convert marketplace listing to Hub asset format
3. **Harvest**: `sync_pull()` → `SyncResult` with mappings - Discover listings and map to `MarketplaceAssetMapping`
4. **Download**: `download_resource()` → On-demand resource download - Handle marketplace-specific operations

### Connector Must NOT

- ❌ Create assets directly (workflow handles this via `create_federated_asset_with_contracts()`)
- ❌ Download data in `sync_pull()` (only map resources with external references)
- ❌ Access external data sources in `sync_pull()` (only store references)

---

## Getting Started

### Step 1: Create Connector File

Create a new file in `hub/apps/integrations/connectors/`:

```python
# hub/apps/integrations/connectors/my_marketplace_connector.py
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceType,
    SyncDirection,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceAssetMapping,
    SyncResult,
    SyncStatus
)
from hub.apps.assets.models import AssetSourceType
from typing import Dict, Any, List, Optional
from datetime import datetime

class MyMarketplaceConnector(DataMarketplaceConnector):
    """Connector for My Marketplace platform."""

    def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def marketplace_type(self) -> MarketplaceType:
        return MarketplaceType.CUSTOM  # or appropriate type

    @property
    def supported_sync_directions(self) -> List[SyncDirection]:
        return [SyncDirection.PULL]  # or [SyncDirection.PULL, SyncDirection.PUSH]
```

### Step 2: Implement Required Methods

Implement all abstract methods from `DataMarketplaceConnector`:

```python
def authenticate(self, credentials: Dict[str, Any]) -> bool:
    """Authenticate with the marketplace."""
    pass

def test_connection(self) -> bool:
    """Test the connection to the marketplace."""
    pass

def list_listings(self, filters=None, limit=None, offset=None) -> List[MarketplaceListing]:
    """List available listings from the marketplace."""
    pass

def get_listing(self, listing_id: str) -> MarketplaceListing:
    """Get a specific listing by its marketplace ID."""
    pass

def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
    """List resources associated with a marketplace listing."""
    pass

def map_to_hub_asset(self, listing: MarketplaceListing, sync_job_id: Optional[str] = None) -> MarketplaceAssetMapping:
    """Map a marketplace listing to a Hub asset representation."""
    pass

def sync_pull(self, listing_ids=None, filters=None, options=None) -> SyncResult:
    """Perform bulk pull synchronization (Marketplace → Hub)."""
    pass

def download_resource(self, resource_id: str, destination_path: str) -> str:
    """Download a resource from the marketplace on-demand."""
    pass

# For PUSH support:
def create_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
    """Create a new listing in the marketplace."""
    pass

def update_listing(self, listing_id: str, listing: MarketplaceListing) -> MarketplaceListing:
    """Update an existing listing in the marketplace."""
    pass

def publish_resource(self, listing_id: str, resource: MarketplaceResource) -> MarketplaceResource:
    """Publish a resource to a marketplace listing."""
    pass

def sync_push(self, asset_ids: List[str], options: Optional[Dict[str, Any]] = None) -> SyncResult:
    """Perform bulk push synchronization (Hub → Marketplace)."""
    pass

def map_from_hub_asset(self, asset_data: Dict[str, Any], odps_metadata=None, odcs_metadata=None) -> MarketplaceListing:
    """Map a Hub asset to a marketplace listing representation."""
    pass
```

### Step 3: Register Connector

Register the connector in `hub/apps/integrations/apps.py`:

```python
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.connectors.my_marketplace_connector import MyMarketplaceConnector

class IntegrationsConfig(AppConfig):
    def ready(self):
        # Register connectors
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.CUSTOM,
            MyMarketplaceConnector
        )
```

---

## Connector Interface Requirements

### Required Properties

#### `marketplace_type`

Returns the marketplace type this connector supports.

```python
@property
def marketplace_type(self) -> MarketplaceType:
    return MarketplaceType.CKAN_INSTANCE
```

#### `supported_sync_directions`

Returns the list of sync directions supported by this connector.

```python
@property
def supported_sync_directions(self) -> List[SyncDirection]:
    return [SyncDirection.PULL]  # Harvest-only connector
    # or
    return [SyncDirection.PULL, SyncDirection.PUSH]  # Bidirectional connector
```

### Required Methods

All methods from `DataMarketplaceConnector` must be implemented. See `hub/apps/integrations/base.py` for complete interface documentation.

---

## Authentication Patterns

### Pattern 1: API Key Authentication

```python
def __init__(self, api_key: str, base_url: str):
    self.api_key = api_key
    self.base_url = base_url
    self._session = None

def authenticate(self, credentials: Dict[str, Any]) -> bool:
    """Authenticate with API key."""
    api_key = credentials.get('api_key')
    if not api_key:
        raise ValueError("api_key is required")

    self.api_key = api_key
    return self.test_connection()

def test_connection(self) -> bool:
    """Test connection with API key."""
    import httpx
    try:
        response = httpx.get(
            f"{self.base_url}/api/test",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10.0
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False
```

### Pattern 2: OAuth 2.0 Authentication

```python
def __init__(self, client_id: str, client_secret: str, base_url: str):
    self.client_id = client_id
    self.client_secret = client_secret
    self.base_url = base_url
    self._access_token = None

def authenticate(self, credentials: Dict[str, Any]) -> bool:
    """Authenticate with OAuth 2.0."""
    client_id = credentials.get('client_id')
    client_secret = credentials.get('client_secret')

    if not client_id or not client_secret:
        raise ValueError("client_id and client_secret are required")

    self.client_id = client_id
    self.client_secret = client_secret

    # Get access token
    self._access_token = self._get_access_token()
    return self._access_token is not None

def _get_access_token(self) -> Optional[str]:
    """Get OAuth 2.0 access token."""
    import httpx
    try:
        response = httpx.post(
            f"{self.base_url}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            },
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        logger.error(f"Failed to get access token: {e}")
        return None

def test_connection(self) -> bool:
    """Test connection with OAuth token."""
    if not self._access_token:
        return False

    import httpx
    try:
        response = httpx.get(
            f"{self.base_url}/api/test",
            headers={"Authorization": f"Bearer {self._access_token}"},
            timeout=10.0
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False
```

### Pattern 3: AWS Credentials Authentication

```python
def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, region_name: str = "us-east-1"):
    self.aws_access_key_id = aws_access_key_id
    self.aws_secret_access_key = aws_secret_access_key
    self.region_name = region_name
    self._client = None

def authenticate(self, credentials: Dict[str, Any]) -> bool:
    """Authenticate with AWS credentials."""
    aws_access_key_id = credentials.get('aws_access_key_id')
    aws_secret_access_key = credentials.get('aws_secret_access_key')
    region_name = credentials.get('region_name', 'us-east-1')

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("aws_access_key_id and aws_secret_access_key are required")

    self.aws_access_key_id = aws_access_key_id
    self.aws_secret_access_key = aws_secret_access_key
    self.region_name = region_name

    return self.test_connection()

def test_connection(self) -> bool:
    """Test connection with AWS credentials."""
    import boto3
    try:
        client = boto3.client(
            'dataexchange',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        # Test with a lightweight operation
        client.list_data_sets(MaxResults=1)
        self._client = client
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False
```

---

## Metadata Mapping Patterns

### Pattern 1: Basic Mapping

```python
def map_to_hub_asset(
    self,
    listing: MarketplaceListing,
    sync_job_id: Optional[str] = None
) -> MarketplaceAssetMapping:
    """Map marketplace listing to Hub asset representation."""

    # Extract asset metadata
    asset_data = {
        "name": listing.title,
        "description": listing.description or "",
        "domain": listing.category or "general",
        "tags": listing.tags or [],
        "status": "DRAFT",
        "visibility": "INTERNAL"
    }

    # Build source metadata
    source_metadata = {
        "marketplace_type": self.marketplace_type.value,
        "marketplace_id": listing.marketplace_id,
        "listing_id": listing.marketplace_id,
        "listing_url": listing.url or "",
        "synced_at": datetime.now().isoformat()
    }

    if sync_job_id:
        source_metadata["sync_job_id"] = sync_job_id

    # Map resources with external references
    resources = [
        MarketplaceResource(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            name=resource.name,
            description=resource.description,
            url=resource.url,  # External reference
            format=resource.format,
            size_bytes=resource.size_bytes,
            metadata={
                "external": True,  # Mark as external
                "download_url": resource.url  # For on-demand download
            }
        )
        for resource in listing.resources
    ]

    # Extract ODPS metadata (if available)
    odps_metadata = None
    if listing.pricing_plans or listing.access_methods:
        odps_metadata = {
            "product_details": {
                "productID": listing.product_id or listing.marketplace_id,
                "product_name": listing.title,
                "product_description": listing.description or ""
            },
            "pricing_plans": listing.pricing_plans or [],
            "access_methods": listing.access_methods or {}
        }

    # Extract ODCS metadata (if available)
    odcs_metadata = None
    if listing.metadata and listing.metadata.get("odcs_metadata"):
        odcs_metadata = listing.metadata["odcs_metadata"]

    return MarketplaceAssetMapping(
        asset_data=asset_data,
        source_type=AssetSourceType.FEDERATED,
        source_metadata=source_metadata,
        odps_metadata=odps_metadata,
        odcs_metadata=odcs_metadata,
        resources=resources
    )
```

### Pattern 2: Advanced Mapping with Schema Extraction

```python
def map_to_hub_asset(
    self,
    listing: MarketplaceListing,
    sync_job_id: Optional[str] = None
) -> MarketplaceAssetMapping:
    """Map marketplace listing with schema hints."""

    # Basic mapping
    mapping = self._basic_mapping(listing, sync_job_id)

    # Extract schema hints from listing metadata
    if listing.metadata and listing.metadata.get("schema"):
        schema_hints = listing.metadata["schema"]
        odcs_metadata = mapping.odcs_metadata or {}
        odcs_metadata.setdefault("schema", {}).update({
            "hints": schema_hints
        })
        mapping.odcs_metadata = odcs_metadata

    return mapping
```

### Pattern 3: Mapping with Quality Hints

```python
def map_to_hub_asset(
    self,
    listing: MarketplaceListing,
    sync_job_id: Optional[str] = None
) -> MarketplaceAssetMapping:
    """Map marketplace listing with quality hints."""

    # Basic mapping
    mapping = self._basic_mapping(listing, sync_job_id)

    # Extract quality hints
    if listing.metadata and listing.metadata.get("quality"):
        quality_hints = listing.metadata["quality"]
        odcs_metadata = mapping.odcs_metadata or {}
        odcs_metadata.setdefault("quality", {}).update({
            "hints": quality_hints
        })
        mapping.odcs_metadata = odcs_metadata

    return mapping
```

---

## Error Handling Patterns

### Pattern 1: Circuit Breaker

```python
from hub.apps.core.resilience.circuit_breaker import circuit_breaker

@circuit_breaker(failure_threshold=5, timeout=60)
def _request_marketplace_api(self, endpoint: str, method: str = "GET", **kwargs):
    """Make API request with circuit breaker."""
    import httpx
    try:
        response = httpx.request(
            method,
            f"{self.base_url}{endpoint}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
            **kwargs
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise NotFoundError(f"Resource not found: {endpoint}")
        elif e.response.status_code == 403:
            raise PermissionError(f"Permission denied: {endpoint}")
        else:
            raise ConnectionError(f"API request failed: {e}")
    except httpx.RequestError as e:
        raise ConnectionError(f"Connection error: {e}")
```

### Pattern 2: Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def _request_with_retry(self, endpoint: str):
    """Make API request with retry logic."""
    return self._request_marketplace_api(endpoint)
```

### Pattern 3: Distributed Tracing

```python
from hub.apps.core.tracing import trace

@trace(operation_name="connector.list_listings")
def list_listings(
    self,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[MarketplaceListing]:
    """List available listings with distributed tracing."""
    # Implementation
    pass
```

### Pattern 4: Comprehensive Error Handling

```python
def list_listings(
    self,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[MarketplaceListing]:
    """List available listings with comprehensive error handling."""
    import structlog
    logger = structlog.get_logger(__name__)

    try:
        # Validate parameters
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")
        if offset is not None and offset < 0:
            raise ValueError("offset must be non-negative")

        # Make API request
        response = self._request_marketplace_api(
            "/api/listings",
            params={
                "filters": filters or {},
                "limit": limit,
                "offset": offset
            }
        )

        # Parse response
        listings = []
        for item in response.get("data", []):
            try:
                listing = self._parse_listing(item)
                listings.append(listing)
            except Exception as e:
                logger.warning(
                    "failed_to_parse_listing",
                    listing_id=item.get("id"),
                    error=str(e)
                )
                continue

        return listings

    except NotFoundError:
        raise
    except PermissionError:
        raise
    except ConnectionError:
        raise
    except ValueError:
        raise
    except Exception as e:
        logger.error(
            "list_listings_error",
            error=str(e),
            exc_info=True
        )
        raise ConnectionError(f"Failed to list listings: {e}") from e
```

---

## Testing Requirements

### Unit Tests

All connectors must have comprehensive unit tests.

#### Test Structure

```python
# tests/integrations/connectors/test_my_marketplace_connector.py
import pytest
from hub.apps.integrations.connectors.my_marketplace_connector import MyMarketplaceConnector
from hub.apps.integrations.base import MarketplaceType, SyncDirection

class TestMyMarketplaceConnector:
    def test_marketplace_type(self):
        """Test marketplace type property."""
        connector = MyMarketplaceConnector(api_key="test", base_url="https://test.com")
        assert connector.marketplace_type == MarketplaceType.CUSTOM

    def test_supported_sync_directions(self):
        """Test supported sync directions."""
        connector = MyMarketplaceConnector(api_key="test", base_url="https://test.com")
        assert SyncDirection.PULL in connector.supported_sync_directions

    def test_authenticate_success(self):
        """Test successful authentication."""
        connector = MyMarketplaceConnector(api_key="test", base_url="https://test.com")
        result = connector.authenticate({"api_key": "valid-key"})
        assert result is True

    def test_authenticate_failure(self):
        """Test failed authentication."""
        connector = MyMarketplaceConnector(api_key="test", base_url="https://test.com")
        with pytest.raises(ValueError):
            connector.authenticate({})

    def test_sync_pull_returns_mappings_only(self):
        """Test that sync_pull() returns mappings only."""
        connector = MyMarketplaceConnector(api_key="test", base_url="https://test.com")
        result = connector.sync_pull()

        assert result.status == SyncStatus.COMPLETED
        assert "mappings" in result.metadata
        assert isinstance(result.metadata["mappings"], list)

    def test_map_to_hub_asset_includes_external_resources(self):
        """Test that map_to_hub_asset() includes external resource references."""
        connector = MyMarketplaceConnector(api_key="test", base_url="https://test.com")
        listing = MarketplaceListing(...)

        mapping = connector.map_to_hub_asset(listing)

        assert mapping.source_type == AssetSourceType.FEDERATED
        assert len(mapping.resources) > 0
        for resource in mapping.resources:
            assert resource.metadata.get("external") is True
            assert resource.url is not None
```

#### Pattern Verification Tests

Use the pattern verification tests from `hub/apps/integrations/tests/test_connector_pattern.py`:

```python
# Run pattern verification tests
pytest hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullDoesNotCreateAssets::test_my_connector_sync_pull_does_not_create_assets
pytest hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullReturnsMappingsOnly::test_my_connector_sync_pull_returns_mappings_only
pytest hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullDoesNotDownloadData::test_my_connector_sync_pull_does_not_download_data
```

### Integration Tests

Integration tests should use real marketplace instances (or test instances):

```python
@pytest.mark.integration
def test_integration_sync_pull_with_real_marketplace(self):
    """Integration test with real marketplace instance."""
    connector = MyMarketplaceConnector(
        api_key=os.getenv("TEST_API_KEY"),
        base_url=os.getenv("TEST_BASE_URL", "https://test-marketplace.example.com")
    )

    # Execute sync_pull with real marketplace
    result = connector.sync_pull(options={"limit": 10})

    # Verify results
    assert result.status == SyncStatus.COMPLETED
    assert result.successful_count > 0
    assert "mappings" in result.metadata
```

---

## Code Examples

### Complete Connector Example

```python
"""
My Marketplace Connector

Connector for My Marketplace platform following metadata-first architecture.
"""
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceAssetMapping,
    SyncResult
)
from hub.apps.assets.models import AssetSourceType
from hub.apps.core.resilience.circuit_breaker import circuit_breaker
from hub.apps.core.tracing import trace

logger = logging.getLogger(__name__)


class MyMarketplaceConnector(DataMarketplaceConnector):
    """Connector for My Marketplace platform."""

    def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
        self.api_key = api_key
        self.base_url = base_url
        self._session = None

    @property
    def marketplace_type(self) -> MarketplaceType:
        return MarketplaceType.CUSTOM

    @property
    def supported_sync_directions(self) -> List[SyncDirection]:
        return [SyncDirection.PULL]  # Harvest-only connector

    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with API key."""
        api_key = credentials.get('api_key')
        if not api_key:
            raise ValueError("api_key is required")

        self.api_key = api_key
        return self.test_connection()

    def test_connection(self) -> bool:
        """Test connection to marketplace."""
        try:
            response = httpx.get(
                f"{self.base_url}/api/health",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10.0
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    @circuit_breaker(failure_threshold=5, timeout=60)
    @trace(operation_name="connector.list_listings")
    def list_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[MarketplaceListing]:
        """List available listings from marketplace."""
        try:
            response = httpx.get(
                f"{self.base_url}/api/listings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={
                    "filters": filters or {},
                    "limit": limit,
                    "offset": offset
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            listings = []
            for item in data.get("items", []):
                listing = MarketplaceListing(
                    marketplace_id=item["id"],
                    marketplace_type=self.marketplace_type,
                    title=item["title"],
                    description=item.get("description"),
                    category=item.get("category"),
                    tags=item.get("tags", []),
                    url=item.get("url"),
                    created_at=datetime.fromisoformat(item["created_at"]) if item.get("created_at") else None,
                    updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else None,
                    metadata=item.get("metadata", {})
                )
                listings.append(listing)

            return listings

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError("Listings not found")
            elif e.response.status_code == 403:
                raise PermissionError("Permission denied")
            else:
                raise ConnectionError(f"API request failed: {e}")
        except Exception as e:
            logger.error(f"Failed to list listings: {e}", exc_info=True)
            raise ConnectionError(f"Failed to list listings: {e}") from e

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        """Get a specific listing by ID."""
        # Similar implementation to list_listings
        pass

    def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
        """List resources associated with a listing."""
        # Implementation
        pass

    def map_to_hub_asset(
        self,
        listing: MarketplaceListing,
        sync_job_id: Optional[str] = None
    ) -> MarketplaceAssetMapping:
        """Map marketplace listing to Hub asset representation."""
        # Extract asset metadata
        asset_data = {
            "name": listing.title,
            "description": listing.description or "",
            "domain": listing.category or "general",
            "tags": listing.tags or [],
            "status": "DRAFT",
            "visibility": "INTERNAL"
        }

        # Build source metadata
        source_metadata = {
            "marketplace_type": self.marketplace_type.value,
            "marketplace_id": listing.marketplace_id,
            "listing_id": listing.marketplace_id,
            "listing_url": listing.url or "",
            "synced_at": datetime.now().isoformat()
        }

        if sync_job_id:
            source_metadata["sync_job_id"] = sync_job_id

        # Get resources (metadata-only, no download)
        marketplace_resources = self.list_resources(listing.marketplace_id)

        # Map resources with external references
        resources = [
            MarketplaceResource(
                resource_id=resource.resource_id,
                resource_type=resource.resource_type,
                name=resource.name,
                description=resource.description,
                url=resource.url,  # External reference
                format=resource.format,
                size_bytes=resource.size_bytes,
                metadata={
                    "external": True,
                    "download_url": resource.url
                }
            )
            for resource in marketplace_resources
        ]

        # Extract ODPS metadata (if available)
        odps_metadata = None
        if listing.pricing_plans or listing.access_methods:
            odps_metadata = {
                "product_details": {
                    "productID": listing.product_id or listing.marketplace_id,
                    "product_name": listing.title,
                    "product_description": listing.description or ""
                },
                "pricing_plans": listing.pricing_plans or [],
                "access_methods": listing.access_methods or {}
            }

        return MarketplaceAssetMapping(
            asset_data=asset_data,
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata,
            odps_metadata=odps_metadata,
            odcs_metadata=None,
            resources=resources
        )

    def sync_pull(
        self,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """Perform bulk pull synchronization (Marketplace → Hub)."""
        started_at = datetime.now()
        mappings = []
        errors = []

        try:
            # Discover listings
            if listing_ids:
                listings = [self.get_listing(id) for id in listing_ids]
            else:
                limit = options.get("limit") if options else None
                listings = self.list_listings(filters=filters, limit=limit)

            # Map listings to MarketplaceAssetMapping
            for listing in listings:
                try:
                    mapping = self.map_to_hub_asset(listing)
                    mappings.append(mapping)
                except Exception as e:
                    error_msg = f"Failed to map listing {listing.marketplace_id}: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Return mappings (NOT assets)
            return SyncResult(
                status=SyncStatus.COMPLETED if not errors else SyncStatus.PARTIAL,
                total_items=len(listings),
                successful_items=len(mappings),
                failed_items=len(errors),
                errors=errors,
                metadata={
                    "mappings": [mapping.__dict__ for mapping in mappings]  # Serialize as dicts
                },
                started_at=started_at,
                completed_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"sync_pull failed: {e}", exc_info=True)
            return SyncResult(
                status=SyncStatus.FAILED,
                total_items=0,
                successful_items=0,
                failed_items=0,
                errors=[str(e)],
                started_at=started_at,
                completed_at=datetime.now()
            )

    def download_resource(self, resource_id: str, destination_path: str) -> str:
        """Download a resource from marketplace on-demand."""
        import os
        import shutil

        try:
            # Create destination directory if needed
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            # Download resource
            response = httpx.get(
                f"{self.base_url}/api/resources/{resource_id}/download",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=300.0,
                follow_redirects=True
            )
            response.raise_for_status()

            # Save to destination
            with open(destination_path, "wb") as f:
                f.write(response.content)

            return destination_path

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Resource not found: {resource_id}")
            elif e.response.status_code == 403:
                raise PermissionError(f"Permission denied: {resource_id}")
            else:
                raise ConnectionError(f"Download failed: {e}")
        except Exception as e:
            logger.error(f"Failed to download resource: {e}", exc_info=True)
            raise ConnectionError(f"Failed to download resource: {e}") from e

    # Push operations (not supported for harvest-only connector)
    def create_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
        raise NotImplementedError("This connector is harvest-only (PULL only)")

    def update_listing(self, listing_id: str, listing: MarketplaceListing) -> MarketplaceListing:
        raise NotImplementedError("This connector is harvest-only (PULL only)")

    def publish_resource(self, listing_id: str, resource: MarketplaceResource) -> MarketplaceResource:
        raise NotImplementedError("This connector is harvest-only (PULL only)")

    def sync_push(self, asset_ids: List[str], options: Optional[Dict[str, Any]] = None) -> SyncResult:
        raise NotImplementedError("This connector is harvest-only (PULL only)")

    def map_from_hub_asset(
        self,
        asset_data: Dict[str, Any],
        odps_metadata: Optional[Dict[str, Any]] = None,
        odcs_metadata: Optional[Dict[str, Any]] = None
    ) -> MarketplaceListing:
        raise NotImplementedError("This connector is harvest-only (PULL only)")
```

---

## Best Practices

### 1. Follow the Metadata-First Pattern

Always separate listing discovery/mapping from asset creation and data downloading:
- `sync_pull()` → Maps listings only
- `map_to_hub_asset()` → Includes external resource references
- `download_resource()` → Handles on-demand downloads

### 2. Use Proper Error Handling

```python
from hub.apps.integrations.exceptions import NotFoundError, ConnectionError, PermissionError

def download_resource(self, resource_id: str, destination_path: str) -> str:
    try:
        # Marketplace-specific operations
        ...
    except NotFoundError:
        raise  # Re-raise NotFoundError
    except PermissionError:
        raise  # Re-raise PermissionError
    except Exception as e:
        logger.error(f"Failed to download resource: {e}", exc_info=True)
        raise ConnectionError(f"Unable to download resource: {e}") from e
```

### 3. Use Circuit Breaker for External API Calls

```python
from hub.apps.core.resilience.circuit_breaker import circuit_breaker

@circuit_breaker(failure_threshold=5, timeout=60)
def _request_marketplace_api(self, endpoint: str):
    response = httpx.get(f"{self.base_url}{endpoint}")
    response.raise_for_status()
    return response.json()
```

### 4. Use Distributed Tracing

```python
from hub.apps.core.tracing import trace

@trace(operation_name="connector.sync_pull")
def sync_pull(self, ...):
    # Your implementation
    ...
```

### 5. Log Appropriately

```python
import logging

logger = logging.getLogger(__name__)

def sync_pull(self, ...):
    logger.info(f"Starting sync_pull for {self.marketplace_type}")
    try:
        # Your implementation
        ...
        logger.info(f"Completed sync_pull: {result.successful_count} mappings")
    except Exception as e:
        logger.error(f"Failed sync_pull: {e}", exc_info=True)
        raise
```

### 6. Handle Optional Metadata Fields

```python
def map_to_hub_asset(self, listing):
    # odps_metadata and odcs_metadata are optional
    odps_metadata = None
    if hasattr(listing, 'pricing_plans') and listing.pricing_plans:
        odps_metadata = {
            "pricing": {"plans": listing.pricing_plans}
        }

    odcs_metadata = None
    if hasattr(listing, 'schema_hints') and listing.schema_hints:
        odcs_metadata = {
            "schema": {"hints": listing.schema_hints}
        }

    return MarketplaceAssetMapping(
        odps_metadata=odps_metadata,  # Can be None
        odcs_metadata=odcs_metadata,  # Can be None
        ...
    )
```

### 7. Serialize Mappings Properly

```python
def sync_pull(self, ...):
    mappings = []
    for listing in listings:
        mapping = self.map_to_hub_asset(listing)
        mappings.append(mapping)

    # Serialize MarketplaceAssetMapping objects as dicts
    return SyncResult(
        metadata={
            "mappings": [mapping.__dict__ for mapping in mappings]
        }
    )
```

---

## Common Mistakes

### ❌ Mistake 1: Creating Assets in `sync_pull()`

**Wrong**:
```python
def sync_pull(self, ...):
    listings = self.list_listings()
    for listing in listings:
        # ❌ Don't create assets here
        asset = Asset.objects.create(
            name=listing.title,
            source_type=AssetSourceType.FEDERATED,
            ...
        )
```

**Correct**:
```python
def sync_pull(self, ...):
    listings = self.list_listings()
    mappings = []
    for listing in listings:
        # ✅ Map listings only
        mapping = self.map_to_hub_asset(listing)
        mappings.append(mapping)

    return SyncResult(
        metadata={"mappings": [m.__dict__ for m in mappings]}
    )
```

### ❌ Mistake 2: Downloading Data in `sync_pull()`

**Wrong**:
```python
def sync_pull(self, ...):
    listings = self.list_listings()
    for listing in listings:
        # ❌ Don't download data here
        for resource in listing.resources:
            data = httpx.get(resource.url).content
            File.objects.create(asset=asset, data=data, ...)
```

**Correct**:
```python
def sync_pull(self, ...):
    listings = self.list_listings()
    mappings = []
    for listing in listings:
        # ✅ Map resources with external references only
        mapping = self.map_to_hub_asset(listing)
        mappings.append(mapping)

    return SyncResult(
        metadata={"mappings": [m.__dict__ for m in mappings]}
    )
```

### ❌ Mistake 3: Accessing External Data Sources in `map_to_hub_asset()`

**Wrong**:
```python
def map_to_hub_asset(self, listing):
    # ❌ Don't access external data sources
    data = httpx.get(listing.resource_url).content
    schema = extract_schema_from_data(data)
```

**Correct**:
```python
def map_to_hub_asset(self, listing):
    # ✅ Store external references only
    resources = [
        MarketplaceResource(
            resource_id=resource.id,
            url=resource.external_url,  # Reference only
            metadata={"external": True, "download_url": resource.external_url}
        )
        for resource in listing.resources
    ]

    return MarketplaceAssetMapping(
        resources=resources,  # External references
        ...
    )
```

---

## Reference Implementations

### CKAN Connector

**Location**: `hub/apps/integrations/connectors/ckan_connector.py`

**Key Patterns**:
- ✅ `sync_pull()` maps listings only, returns mappings in `SyncResult.metadata["mappings"]`
- ✅ `map_to_hub_asset()` includes external resource references with `metadata.external = True`
- ✅ `download_resource()` handles on-demand downloads using `httpx.stream()`
- ✅ Push operations raise `NotImplementedError` (harvest-only connector)

### Snowflake Connector

**Location**: `hub/apps/integrations/connectors/snowflake_connector.py`

**Key Patterns**:
- ✅ `sync_pull()` maps listings only, returns mappings in `SyncResult.metadata["mappings"]`
- ✅ `map_to_hub_asset()` includes external resource references with `metadata.external = True`
- ✅ `download_resource()` handles deferred operations:
  - Listing ID: Request listing, accept legal terms, create database, extract schema, download all tables
  - Table identifier: Download specific table (database already exists)
- ✅ Push operations raise `NotImplementedError` (harvest-only connector)

### AWS Data Exchange Connector

**Location**: `hub/apps/integrations/connectors/aws_data_exchange_connector.py`

**Key Patterns**:
- ✅ `sync_pull()` maps listings only, returns mappings in `SyncResult.metadata["mappings"]`
- ✅ `map_to_hub_asset()` includes external resource references with `metadata.external = True`
- ✅ `download_resource()` handles AWS Data Exchange subscription and export:
  - Subscribe to dataset if not subscribed
  - Create export job
  - Wait for job completion
  - Download from S3
- ✅ Push operations raise `NotImplementedError` (harvest-only connector)

---

## Additional Resources

- **Base Connector Interface**: `hub/apps/integrations/base.py` - Complete interface documentation
- **Framework Architecture**: `docs/MARKETPLACE_INTEGRATION_FRAMEWORK.md` - Architecture documentation
- **API Reference**: `docs/MARKETPLACE_API_REFERENCE.md` - Complete API documentation
- **Pattern Verification Tests**: `hub/apps/integrations/tests/test_connector_pattern.py` - Test suite for pattern compliance
- **Workflow Integration**: `hub/apps/orchestration/workflows/marketplace_sync.py` - Workflow implementation
- **Service Layer**: `hub/apps/integrations/services.py` - `create_federated_asset_with_contracts()` implementation

---

**Last Updated**: 2026-01-10
**Version**: 1.0.0
