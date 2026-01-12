# Marketplace Connector Development Guide

Complete guide for developing marketplace connectors following the metadata-first architecture pattern.

**Last Updated**: 2026-01-08
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Metadata-First Architecture](#metadata-first-architecture)
3. [Connector Implementation Checklist](#connector-implementation-checklist)
4. [Testing Requirements](#testing-requirements)
5. [Reference Implementations](#reference-implementations)
6. [Common Mistakes to Avoid](#common-mistakes-to-avoid)
7. [Best Practices](#best-practices)

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
2. **Mapping**: `map_to_hub_asset()` → MarketplaceAssetMapping - Convert marketplace listing to Hub asset format
3. **Harvest**: `sync_pull()` → SyncResult with mappings - Discover listings and map to MarketplaceAssetMapping
4. **Download**: `download_resource()` → On-demand resource download - Handle marketplace-specific operations

### Connector Must NOT

- ❌ Create assets directly (workflow handles this via `create_federated_asset_with_contracts()`)
- ❌ Download data in `sync_pull()` (only map resources with external references)
- ❌ Access external data sources in `sync_pull()` (only store references)

---

## Metadata-First Architecture

The metadata-first architecture pattern separates listing discovery/mapping from asset creation and data downloading. This ensures fast harvesting, clear separation of concerns, and scalable marketplace integration.

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Connector Layer                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  sync_pull()                                                     │
│  ├─ Discovers listings from marketplace                         │
│  ├─ Maps listings to MarketplaceAssetMapping                    │
│  └─ Returns mappings in SyncResult.metadata["mappings"]         │
│                                                                   │
│  map_to_hub_asset()                                              │
│  ├─ Extracts asset metadata                                      │
│  ├─ Extracts ODPS/ODCS contract metadata                        │
│  └─ Includes external resource references (NO data download)     │
│                                                                   │
│  download_resource()                                             │
│  ├─ Handles marketplace-specific operations                      │
│  ├─ Downloads resource data on-demand                            │
│  └─ Returns path to downloaded file                              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow Layer                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  marketplace_sync_pull workflow                                  │
│  ├─ discover_listings_task → Calls connector.list_listings()    │
│  ├─ map_listings_to_assets_task → Calls connector.map_to_hub_asset() │
│  └─ create_federated_assets_task → Calls create_federated_asset_with_contracts() │
│      └─ Based on data_strategy:                                  │
│          - METADATA_ONLY: Store external references only        │
│          - DOWNLOAD_SELECTIVE: Download specific resources       │
│          - DOWNLOAD_ALL: Download all resources                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

#### 1. `sync_pull()` Maps Listings Only

**What `sync_pull()` Does**:
- ✅ Discovers listings from marketplace (by IDs or via filters)
- ✅ Maps each listing to `MarketplaceAssetMapping` using `map_to_hub_asset()`
- ✅ Returns mappings in `SyncResult.metadata["mappings"]` for workflow processing

**What `sync_pull()` Does NOT Do**:
- ❌ Create assets (workflow handles this)
- ❌ Download data (only maps resources with external references)
- ❌ Access external data sources (only stores references)
- ❌ Create databases, subscribe to datasets, trigger snapshots, etc. (these happen in `download_resource()`)

**Example - Correct Implementation**:
```python
def sync_pull(
    self,
    listing_ids: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None
) -> SyncResult:
    """Correct: Map listings only, return mappings"""
    # Discover listings
    if listing_ids:
        listings = [self.get_listing(id) for id in listing_ids]
    else:
        listings = self.list_listings(filters=filters)

    # Map listings to MarketplaceAssetMapping
    mappings = []
    errors = []

    for listing in listings:
        try:
            mapping = self.map_to_hub_asset(listing)
            mappings.append(mapping)
        except Exception as e:
            errors.append(f"Failed to map listing {listing.marketplace_id}: {e}")

    # Return mappings (NOT assets)
    return SyncResult(
        status=SyncStatus.COMPLETED if not errors else SyncStatus.PARTIAL,
        successful_count=len(mappings),
        failed_count=len(errors),
        metadata={
            "mappings": [mapping.__dict__ for mapping in mappings],  # Serialize as dicts
            "errors": errors
        },
        started_at=timezone.now(),
        completed_at=timezone.now()
    )
```

**Example - Incorrect Implementation**:
```python
def sync_pull(self, ...):
    """Wrong: Creating assets or downloading data"""
    listings = self.list_listings()

    for listing in listings:
        # ❌ Don't do this: Creating assets directly
        asset = Asset.objects.create(
            name=listing.title,
            source_type=AssetSourceType.FEDERATED,
            ...
        )

        # ❌ Don't do this: Downloading data
        for resource in listing.resources:
            download_path = self.download_resource(resource.id, "/tmp/data.csv")
            File.objects.create(asset=asset, path=download_path, ...)

    # ❌ Don't do this: Returning asset IDs
    return SyncResult(
        successful_count=len(assets),
        metadata={"asset_ids": [asset.id for asset in assets]}  # Wrong!
    )
```

#### 2. `map_to_hub_asset()` Includes External Resource References

**What `map_to_hub_asset()` Does**:
- ✅ Extracts asset metadata (name, description, domain, tags, status, visibility)
- ✅ Extracts ODPS contract metadata (product details, pricing plans, access methods, payment gateways)
- ✅ Extracts ODCS contract metadata (schema hints, quality hints, SLA hints) if available
- ✅ Builds `source_metadata` with marketplace connection and listing information
- ✅ Includes external resource references in `resources` list (does NOT download resources)

**What `map_to_hub_asset()` Does NOT Do**:
- ❌ Access external data sources (only stores references)
- ❌ Download data (only maps resources with external URLs/identifiers)
- ❌ Create assets (workflow handles this via `create_federated_asset_with_contracts()`)
- ❌ Create databases, subscribe to datasets, trigger snapshots, etc. (these happen in `download_resource()`)

**Example - Correct Implementation**:
```python
def map_to_hub_asset(
    self,
    listing: MarketplaceListing,
    sync_job_id: Optional[str] = None
) -> MarketplaceAssetMapping:
    """Correct: Extract metadata and store external references"""
    # Get resources (metadata-only, no download)
    marketplace_resources = self.list_resources(listing.marketplace_id)

    # Map resources with external references
    resources = [
        MarketplaceResource(
            resource_id=resource.id,
            name=resource.name,
            url=resource.external_url,  # Store reference, don't download
            format=resource.format,
            size_bytes=resource.size_bytes,
            resource_type=ResourceType.FILE,
            metadata={
                "external": True,  # Mark as external
                "download_url": resource.external_url,  # For on-demand download
                "marketplace_resource_id": resource.id
            }
        )
        for resource in marketplace_resources
    ]

    # Extract ODPS metadata (if available)
    odps_metadata = {
        "product": {
            "name": listing.title,
            "description": listing.description,
            "category": listing.category,
            "tags": listing.tags
        },
        "pricing": {
            "plans": listing.pricing_plans if hasattr(listing, 'pricing_plans') else []
        },
        "access": {
            "methods": ["API", "DOWNLOAD"] if resources else ["DOWNLOAD"]
        }
    }

    # Extract ODCS metadata (if available)
    odcs_metadata = {
        "schema": {
            "hints": listing.schema_hints if hasattr(listing, 'schema_hints') else {}
        },
        "quality": {
            "hints": listing.quality_hints if hasattr(listing, 'quality_hints') else {}
        }
    }

    return MarketplaceAssetMapping(
        asset_data={
            "name": listing.title,
            "description": listing.description,
            "domain": listing.domain,
            "tags": listing.tags or [],
            "status": AssetStatus.DRAFT,
            "visibility": AssetVisibility.INTERNAL
        },
        source_type=AssetSourceType.FEDERATED,
        source_metadata={
            "marketplace_type": self.marketplace_type.value,
            "marketplace_id": listing.marketplace_id,
            "listing_id": listing.marketplace_id,
            "listing_url": listing.url,
            "synced_at": timezone.now().isoformat(),
            "sync_job_id": sync_job_id
        },
        odps_metadata=odps_metadata,
        odcs_metadata=odcs_metadata,
        resources=resources  # External references only
    )
```

**Example - Incorrect Implementation**:
```python
def map_to_hub_asset(self, listing, sync_job_id=None):
    """Wrong: Accessing external data sources or downloading data"""
    # ❌ Don't do this: Downloading data
    for resource in listing.resources:
        data = httpx.get(resource.url).content  # Wrong!
        schema = extract_schema_from_data(data)  # Wrong!

    # ❌ Don't do this: Creating database or subscribing
    if listing.marketplace_type == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE:
        self._create_database_from_listing(listing.id)  # Wrong! This belongs in download_resource()

    # ❌ Don't do this: Accessing external APIs for schema
    schema = self._extract_schema_metadata(listing.database_name)  # Wrong!
```

#### 3. `download_resource()` Handles On-Demand Downloads

**What `download_resource()` Does**:
- ✅ Handles marketplace-specific operations required to access the resource:
  - **Snowflake**: Request listing, accept legal terms, create database from listing, extract schema
  - **AWS Data Exchange**: Subscribe to dataset, create export job, wait for completion, download from S3
  - **Azure Data Share**: Accept invitation, trigger snapshot, wait for completion, access shared data
  - **GCP Marketplace**: Subscribe to listing, create linked dataset, extract schema from BigQuery
  - **Databricks**: Consume share, create catalog from share, extract schema
- ✅ Downloads resource data to `destination_path`
- ✅ Returns path to downloaded file

**When `download_resource()` Is Called**:
- Called by workflow when `data_strategy == "DOWNLOAD_SELECTIVE"` (specific resources)
- Called by workflow when `data_strategy == "DOWNLOAD_ALL"` (all resources)
- NOT called when `data_strategy == "METADATA_ONLY"` (default, metadata-only harvesting)

**Example - Correct Implementation (Snowflake)**:
```python
def download_resource(
    self,
    resource_id: str,
    destination_path: str
) -> str:
    """Correct: Handle marketplace-specific operations and download"""
    import os
    import re

    # Parse resource_id to determine type
    parts = resource_id.split(".")

    if len(parts) == 1:
        # Case 1: Listing ID (e.g., "SNOWFLAKE_SAMPLE_DATA")
        # Need to request listing, accept terms, create database, extract schema, download
        listing_id = resource_id

        # Step 1: Request listing and wait for fulfillment
        self._request_listing(listing_id)

        # Step 2: Accept legal terms if required
        try:
            self._accept_legal_terms(listing_id)
        except Exception as e:
            logger.debug(f"Legal terms acceptance failed: {e}")

        # Step 3: Create database from listing
        database_name = self._create_database_from_listing(listing_id)

        # Step 4: Extract schema metadata (for reference)
        schema_metadata = self._extract_schema_metadata(database_name)

        # Step 5: Download all tables from the database
        tables_sql = f"""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM {database_name}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE' OR TABLE_TYPE = 'VIEW'
        """
        tables_results = self._execute_sql(tables_sql)

        downloaded_files = []
        for table_row in tables_results:
            schema = table_row.get("TABLE_SCHEMA", "")
            table = table_row.get("TABLE_NAME", "")
            full_table_name = f"{database_name}.{schema}.{table}"

            table_path = os.path.join(
                os.path.dirname(destination_path),
                f"{table}.csv"
            )

            downloaded_file = self._download_table(full_table_name, table_path, "CSV")
            downloaded_files.append(downloaded_file)

        return downloaded_files[0] if len(downloaded_files) == 1 else os.path.dirname(destination_path)

    elif len(parts) == 3:
        # Case 2: Table identifier (e.g., "DB.SCHEMA.TABLE")
        # Table already exists, download it
        return self._download_table(resource_id, destination_path, "CSV")

    else:
        raise ValueError(f"Invalid resource_id format: {resource_id}")
```

**Example - Correct Implementation (AWS Data Exchange)**:
```python
def download_resource(
    self,
    resource_id: str,
    destination_path: str
) -> str:
    """Correct: Handle AWS Data Exchange subscription and export"""
    # Step 1: Subscribe to dataset if not subscribed
    dataset_id = resource_id
    if not self._is_subscribed(dataset_id):
        self._subscribe_to_dataset(dataset_id)

    # Step 2: Create export job
    job_id = self._create_export_job(dataset_id)

    # Step 3: Wait for job completion
    self._wait_for_job_completion(job_id)

    # Step 4: Get export job details (S3 location)
    job_details = self._get_export_job_details(job_id)
    s3_bucket = job_details["S3Bucket"]
    s3_key = job_details["S3Key"]

    # Step 5: Download from S3
    self._download_from_s3(s3_bucket, s3_key, destination_path)

    return destination_path
```

### Workflow Integration

Connectors are integrated into the workflow system:

```python
# Service layer calls connector
sync_job = service.sync_from_marketplace(
    connection_id=connection.id,
    tenant_id=tenant.id,
    user_id=user.id,
    options={"dry_run": False, "data_strategy": "METADATA_ONLY"}
)

# Workflow: marketplace_sync_pull
# 1. discover_listings_task → Calls connector.list_listings()
# 2. map_listings_to_assets_task → Calls connector.map_to_hub_asset()
# 3. create_federated_assets_task → Calls create_federated_asset_with_contracts()
#    └─ Based on data_strategy:
#        - METADATA_ONLY: Store external references only
#        - DOWNLOAD_SELECTIVE: Download specific resources via connector.download_resource()
#        - DOWNLOAD_ALL: Download all resources via connector.download_resource()
```

### Benefits of Metadata-First Architecture

1. **Fast Harvesting**: Create thousands of federated assets quickly without downloading data (seconds vs hours)
2. **Scalability**: Harvest large marketplaces without storage overhead (metadata-only assets are lightweight)
3. **Clear Separation**: Federated assets (external metadata) vs Virtualized assets (virtual queries)
4. **Lazy Data Access**: Download data only when explicitly requested (reduces storage costs, improves performance)
5. **Governance/Compliance/Semantic Layers**: All layers work with metadata-first federated assets

---

## Connector Implementation Checklist

Use this checklist when implementing a new connector to ensure compliance with the metadata-first architecture pattern.

### ✅ `sync_pull()` Implementation

- [ ] `sync_pull()` maps listings only, does NOT create assets or download data
- [ ] `sync_pull()` returns `SyncResult` with mappings in `metadata["mappings"]`
- [ ] Mappings are `MarketplaceAssetMapping` objects (serialized as dicts)
- [ ] No asset IDs or contract IDs in return value
- [ ] Does NOT call `create_federated_asset_with_contracts()` or asset creation methods
- [ ] Does NOT call `download_resource()` or file download methods
- [ ] Does NOT access external data sources (only stores references)
- [ ] Does NOT perform marketplace-specific operations (database creation, subscriptions, snapshots, etc.)

### ✅ `map_to_hub_asset()` Implementation

- [ ] `map_to_hub_asset()` returns `MarketplaceAssetMapping` with external resource references
- [ ] Mapping includes all required fields:
  - `asset_data`: Dictionary with Hub asset fields (name, description, domain, tags, status, visibility)
  - `source_type`: `AssetSourceType.FEDERATED` (always FEDERATED for marketplace assets)
  - `source_metadata`: Dictionary with marketplace connection and listing information
  - `odps_metadata`: Optional dictionary with ODPS contract data (can be None)
  - `odcs_metadata`: Optional dictionary with ODCS contract data (can be None)
  - `resources`: List of `MarketplaceResource` objects with external references
- [ ] Resources have `metadata.external = True` flag
- [ ] Resources have external URLs or identifiers (for on-demand download)
- [ ] Does NOT access external data sources (only stores references)
- [ ] Does NOT download data (only maps resources with external URLs/identifiers)
- [ ] Does NOT perform marketplace-specific operations (database creation, subscriptions, snapshots, etc.)

### ✅ `download_resource()` Implementation

- [ ] `download_resource()` handles on-demand downloads with marketplace-specific operations
- [ ] Marketplace-specific operations happen here (NOT in `sync_pull()`):
  - Snowflake: Request listing, accept legal terms, create database, extract schema
  - AWS Data Exchange: Subscribe to dataset, create export job, download from S3
  - Azure Data Share: Accept invitation, trigger snapshot, access shared data
  - GCP Marketplace: Subscribe to listing, create linked dataset, extract schema
  - Databricks: Consume share, create catalog, extract schema
- [ ] Downloads resource data to `destination_path`
- [ ] Returns path to downloaded file
- [ ] Handles errors appropriately (NotFoundError, ConnectionError, PermissionError, ValueError)

### ✅ Push Operations (Harvest-Only Connectors)

- [ ] Push operations raise `NotImplementedError` for harvest-only connectors
- [ ] `sync_push()`, `create_listing()`, `update_listing()`, `publish_resource()` raise `NotImplementedError`
- [ ] Error message explains that connector is harvest-only

### ✅ Error Handling

- [ ] All methods follow error handling patterns:
  - Circuit breaker for external API calls
  - Retry logic for transient failures
  - Distributed tracing for observability
  - Proper exception types (NotFoundError, ConnectionError, PermissionError, ValueError)
- [ ] Errors are logged with appropriate log levels
- [ ] Error messages are clear and actionable

### ✅ Testing

- [ ] Unit tests for metadata-only `sync_pull()`
- [ ] Unit tests for `download_resource()` with marketplace-specific operations
- [ ] Integration tests with real marketplace instances
- [ ] Pattern verification tests (see `hub/apps/integrations/tests/test_connector_pattern.py`)

---

## Testing Requirements

All connectors must have comprehensive test coverage following TDD principles.

### Unit Tests

#### Test `sync_pull()` Metadata-Only Behavior

```python
def test_sync_pull_does_not_create_assets(self):
    """Test that sync_pull() does not create assets"""
    connector = MyConnector(...)

    # Track asset creation
    initial_asset_count = Asset.objects.count()

    # Execute sync_pull
    result = connector.sync_pull()

    # Verify no assets were created
    self.assertEqual(Asset.objects.count(), initial_asset_count)
    self.assertIsInstance(result, SyncResult)
    self.assertIn("mappings", result.metadata)

def test_sync_pull_returns_mappings_only(self):
    """Test that sync_pull() returns mappings only"""
    connector = MyConnector(...)

    result = connector.sync_pull()

    # Verify mappings are returned
    self.assertIn("mappings", result.metadata)
    mappings = result.metadata["mappings"]
    self.assertIsInstance(mappings, list)

    # Verify mappings are MarketplaceAssetMapping objects (or dicts)
    if mappings:
        mapping = mappings[0]
        if isinstance(mapping, dict):
            self.assertIn("asset_data", mapping)
            self.assertIn("source_type", mapping)
        elif isinstance(mapping, MarketplaceAssetMapping):
            self.assertIsNotNone(mapping.asset_data)
            self.assertIsNotNone(mapping.source_type)

def test_sync_pull_does_not_download_data(self):
    """Test that sync_pull() does not download data"""
    connector = MyConnector(...)

    # Track download_resource calls
    download_called = {"called": False}
    original_download = connector.download_resource

    def track_download(*args, **kwargs):
        download_called["called"] = True
        return original_download(*args, **kwargs)

    connector.download_resource = track_download

    # Execute sync_pull
    result = connector.sync_pull()

    # Verify download_resource was NOT called
    self.assertFalse(download_called["called"])
```

#### Test `map_to_hub_asset()` External Resource References

```python
def test_map_to_hub_asset_returns_marketplace_asset_mapping(self):
    """Test that map_to_hub_asset() returns MarketplaceAssetMapping"""
    connector = MyConnector(...)
    listing = MarketplaceListing(...)

    mapping = connector.map_to_hub_asset(listing)

    # Verify mapping structure
    self.assertIsInstance(mapping, MarketplaceAssetMapping)
    self.assertIsNotNone(mapping.asset_data)
    self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
    self.assertIsNotNone(mapping.source_metadata)
    self.assertIsNotNone(mapping.resources)
    self.assertIsInstance(mapping.resources, list)

def test_map_to_hub_asset_includes_external_resources(self):
    """Test that map_to_hub_asset() includes external resource references"""
    connector = MyConnector(...)
    listing = MarketplaceListing(...)

    mapping = connector.map_to_hub_asset(listing)

    # Verify external resources are included
    self.assertGreater(len(mapping.resources), 0)
    for resource in mapping.resources:
        self.assertIsNotNone(resource.url)
        self.assertTrue(resource.metadata.get("external", False))
```

#### Test `download_resource()` On-Demand Downloads

```python
def test_download_resource_handles_on_demand_downloads(self):
    """Test that download_resource() handles on-demand downloads"""
    connector = MyConnector(...)

    import tempfile
    import os

    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        destination_path = tmp_file.name

    try:
        # Execute download_resource
        result_path = connector.download_resource(
            resource_id="test-resource",
            destination_path=destination_path
        )

        # Verify download_resource returns path
        self.assertIsNotNone(result_path)
        self.assertEqual(result_path, destination_path)
        self.assertTrue(os.path.exists(result_path))
    finally:
        # Cleanup
        if os.path.exists(destination_path):
            os.unlink(destination_path)
```

### Integration Tests

Integration tests should use real marketplace instances (or test instances) to verify end-to-end behavior:

```python
def test_integration_sync_pull_with_real_marketplace(self):
    """Integration test with real marketplace instance"""
    connector = MyConnector(base_url="https://test-marketplace.example.com")

    # Execute sync_pull with real marketplace
    result = connector.sync_pull(options={"limit": 10})

    # Verify results
    self.assertEqual(result.status, SyncStatus.COMPLETED)
    self.assertGreater(result.successful_count, 0)
    self.assertIn("mappings", result.metadata)
```

### Pattern Verification Tests

Use the pattern verification tests from `hub/apps/integrations/tests/test_connector_pattern.py`:

```python
# Run pattern verification tests
pytest hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullDoesNotCreateAssets::test_my_connector_sync_pull_does_not_create_assets
pytest hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullReturnsMappingsOnly::test_my_connector_sync_pull_returns_mappings_only
pytest hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullDoesNotDownloadData::test_my_connector_sync_pull_does_not_download_data
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

**Example Usage**:
```python
from hub.apps.integrations.connectors.ckan_connector import CKANConnector

connector = CKANConnector(base_url="https://data.gov")

# Sync pull (metadata-only)
result = connector.sync_pull(options={"limit": 100})
mappings = result.metadata["mappings"]

# Map single listing
listing = connector.get_listing("dataset-id")
mapping = connector.map_to_hub_asset(listing)

# Download resource on-demand
download_path = connector.download_resource(
    resource_id="resource-id",
    destination_path="/tmp/resource.csv"
)
```

### DadosGovBr Connector

**Location**: `hub/apps/integrations/connectors/dados_gov_br_connector.py`

**Key Patterns**:
- ✅ `sync_pull()` maps listings only, returns mappings in `SyncResult.metadata["mappings"]`
- ✅ `map_to_hub_asset()` includes external resource references with `metadata.external = True`
- ✅ `download_resource()` handles on-demand downloads using Swagger API endpoints
- ✅ Push operations raise `NotImplementedError` (harvest-only connector)
- ✅ Uses Swagger API specification for endpoint discovery and validation

**Example Usage**:
```python
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector

connector = DadosGovBrConnector(base_url="https://dados.gov.br")

# Sync pull (metadata-only)
result = connector.sync_pull(options={"limit": 100})
mappings = result.metadata["mappings"]

# Map single listing
listing = connector.get_listing("dataset-id")
mapping = connector.map_to_hub_asset(listing)

# Download resource on-demand
download_path = connector.download_resource(
    resource_id="resource-id",
    destination_path="/tmp/resource.csv"
)
```

### Snowflake Connector

**Location**: `hub/apps/integrations/connectors/snowflake_connector.py`

**Key Patterns**:
- ✅ `sync_pull()` maps listings only, returns mappings in `SyncResult.metadata["mappings"]`
- ✅ `map_to_hub_asset()` includes external resource references with `metadata.external = True`
- ✅ `download_resource()` handles deferred operations:
  - Listing ID: Request listing, accept legal terms, create database, extract schema, download all tables
  - Table identifier: Download specific table (database already exists)
- ✅ Push operations raise `NotImplementedError` (harvest-only connector)

**Example Usage**:
```python
from hub.apps.integrations.connectors.snowflake_connector import SnowflakeConnector

connector = SnowflakeConnector(
    account="test_account",
    user="test_user",
    token="test_token"
)

# Sync pull (metadata-only)
result = connector.sync_pull(options={"limit": 100})
mappings = result.metadata["mappings"]

# Map single listing
listing = connector.get_listing("SNOWFLAKE_SAMPLE_DATA")
mapping = connector.map_to_hub_asset(listing)

# Download resource on-demand (creates database if needed)
download_path = connector.download_resource(
    resource_id="SNOWFLAKE_SAMPLE_DATA",  # Listing ID
    destination_path="/tmp/database.csv"
)

# Download specific table (database already exists)
download_path = connector.download_resource(
    resource_id="SNOWFLAKE_SAMPLE_DATA.SCHEMA.TABLE",  # Table identifier
    destination_path="/tmp/table.csv"
)
```

---

## Common Mistakes to Avoid

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

### ❌ Mistake 3: Performing Marketplace-Specific Operations in `sync_pull()`

**Wrong**:
```python
def sync_pull(self, ...):
    listings = self.list_listings()
    for listing in listings:
        # ❌ Don't create databases or subscribe here
        if listing.marketplace_type == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE:
            self._create_database_from_listing(listing.id)
            schema = self._extract_schema_metadata(listing.database_name)
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

# Marketplace-specific operations happen in download_resource()
def download_resource(self, resource_id, destination_path):
    # ✅ Create database here when data is requested
    self._create_database_from_listing(resource_id)
    schema = self._extract_schema_metadata(resource_id)
    # ... download data
```

### ❌ Mistake 4: Accessing External Data Sources in `map_to_hub_asset()`

**Wrong**:
```python
def map_to_hub_asset(self, listing):
    # ❌ Don't access external data sources
    data = httpx.get(listing.resource_url).content
    schema = extract_schema_from_data(data)

    return MarketplaceAssetMapping(
        odcs_metadata={"schema": schema},  # Wrong!
        ...
    )
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

### ❌ Mistake 5: Returning Asset IDs in `sync_pull()`

**Wrong**:
```python
def sync_pull(self, ...):
    assets = []
    for listing in listings:
        asset = create_asset(listing)  # Wrong!
        assets.append(asset)

    return SyncResult(
        metadata={"asset_ids": [a.id for a in assets]}  # Wrong!
    )
```

**Correct**:
```python
def sync_pull(self, ...):
    mappings = []
    for listing in listings:
        mapping = self.map_to_hub_asset(listing)
        mappings.append(mapping)

    return SyncResult(
        metadata={"mappings": [m.__dict__ for m in mappings]}  # Correct!
    )
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

def download_resource(self, resource_id, destination_path):
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
def _request_marketplace_api(self, endpoint):
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

## Additional Resources

- **Base Connector Class**: `hub/apps/integrations/base.py` - Complete interface documentation
- **Pattern Verification Tests**: `hub/apps/integrations/tests/test_connector_pattern.py` - Test suite for pattern compliance
- **Workflow Integration**: `hub/apps/orchestration/workflows/marketplace_sync.py` - Workflow implementation
- **Service Layer**: `hub/apps/integrations/services.py` - `create_federated_asset_with_contracts()` implementation

---

**Last Updated**: 2026-01-08
**Version**: 1.0.0

