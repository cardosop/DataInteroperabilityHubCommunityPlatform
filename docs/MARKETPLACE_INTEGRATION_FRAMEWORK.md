# Marketplace Integration Framework Architecture

Complete architecture documentation for the Data Interoperability Hub Marketplace Integration Framework.

**Last Updated**: 2026-01-10
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [Core Components](#core-components)
4. [Metadata-First Architecture Pattern](#metadata-first-architecture-pattern)
5. [Factory Pattern](#factory-pattern)
6. [Service Layer](#service-layer)
7. [Database Models](#database-models)
8. [Event System Integration](#event-system-integration)
9. [Job Queue Integration](#job-queue-integration)
10. [Workflow Orchestration](#workflow-orchestration)
11. [Architecture Diagrams](#architecture-diagrams)
12. [Design Decisions](#design-decisions)

---

## Overview

The Marketplace Integration Framework enables bidirectional synchronization between the Data Interoperability Hub and external data marketplaces (CKAN, Snowflake Data Marketplace, AWS Data Exchange, Azure Data Share, GCP Marketplace, Databricks, etc.).

### Key Capabilities

- **Bidirectional Synchronization**: PUSH (Hub → Marketplace) and PULL (Marketplace → Hub)
- **Metadata-First Architecture**: Fast harvesting without downloading data
- **Extensible Connector System**: Easy addition of new marketplace connectors
- **Workflow Orchestration**: Comprehensive sync job management with progress tracking
- **Event-Driven Architecture**: Real-time notifications and audit trails
- **Multi-Tenant Support**: Tenant-scoped connections and sync jobs
- **Security**: Encrypted credentials, RBAC/ABAC authorization

### Supported Marketplaces

The framework supports 15+ marketplace types:

- **Cloud Data Marketplaces**: Snowflake Data Marketplace, AWS Data Exchange, Azure Data Share, GCP Marketplace, Databricks Marketplace
- **Open Data Portals**: CKAN instances, Data.gov, European Data Portal
- **API Marketplaces**: RapidAPI, APIs.guru, Programmable Web
- **Data Platforms**: Data World, Kaggle, Quandl
- **Custom**: Custom marketplace implementations

---

## Architecture Principles

### 1. Metadata-First Architecture

The framework follows a **metadata-first architecture pattern** that separates listing discovery/mapping from asset creation and data downloading:

- **Fast Harvesting**: Create thousands of federated assets quickly without downloading data (seconds vs hours)
- **Scalability**: Harvest large marketplaces without storage overhead (metadata-only assets are lightweight)
- **Clear Separation**: Federated assets (external metadata) vs Virtualized assets (virtual queries)
- **Lazy Data Access**: Download data only when explicitly requested (reduces storage costs, improves performance)
- **Governance/Compliance/Semantic Layers**: All layers work with metadata-first federated assets

### 2. Separation of Concerns

Clear separation between:
- **Connector Layer**: Marketplace-specific operations (discovery, mapping, download)
- **Service Layer**: Business logic, validation, orchestration
- **Workflow Layer**: Task orchestration, progress tracking, error handling
- **API Layer**: REST API endpoints, serialization, authorization

### 3. Extensibility

- **Factory Pattern**: Dynamic connector registration and retrieval
- **Abstract Base Classes**: Consistent interface for all connectors
- **Plugin Architecture**: Easy addition of new marketplace connectors

### 4. Resilience

- **Circuit Breakers**: Protect against cascading failures
- **Retry Logic**: Automatic retry for transient failures
- **Distributed Tracing**: Full observability across components
- **Error Handling**: Comprehensive error types and recovery strategies

---

## Core Components

### 1. Base Connector Interface

**Location**: `hub/apps/integrations/base.py`

The `DataMarketplaceConnector` abstract base class defines the interface that all marketplace connectors must implement.

#### Key Methods

- **Discovery**: `list_listings()`, `get_listing()`, `list_resources()` - Discover marketplace listings
- **Mapping**: `map_to_hub_asset()` → `MarketplaceAssetMapping` - Convert marketplace listing to Hub asset format
- **Harvest**: `sync_pull()` → `SyncResult` with mappings - Discover listings and map to `MarketplaceAssetMapping`
- **Download**: `download_resource()` → On-demand resource download - Handle marketplace-specific operations
- **Publish**: `create_listing()`, `update_listing()`, `publish_resource()`, `sync_push()` - Publish Hub assets to marketplace

#### Data Structures

- **`MarketplaceListing`**: Unified representation of a marketplace listing
- **`MarketplaceResource`**: Unified representation of a marketplace resource
- **`MarketplaceAssetMapping`**: Federated asset mapping result
- **`SyncResult`**: Result of a synchronization operation

#### Example

```python
from hub.apps.integrations.base import DataMarketplaceConnector, MarketplaceType

class MyConnector(DataMarketplaceConnector):
    @property
    def marketplace_type(self) -> MarketplaceType:
        return MarketplaceType.CUSTOM

    def list_listings(self, filters=None, limit=None, offset=None):
        # Implementation
        pass

    def map_to_hub_asset(self, listing, sync_job_id=None):
        # Implementation
        pass
```

### 2. Factory Pattern

**Location**: `hub/apps/integrations/factory.py`

The `MarketplaceConnectorFactory` provides a centralized registry for marketplace connector implementations.

#### Key Features

- **Dynamic Registration**: Register connectors at runtime
- **Type-Based Retrieval**: Get connectors by marketplace type
- **Configuration Support**: Create connectors with configuration
- **Instance Management**: Support for marketplace instance configurations (e.g., CKAN instances)

#### Usage

```python
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.base import MarketplaceType

# Register a connector
MarketplaceConnectorFactory.register_connector(
    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
    SnowflakeConnector
)

# Get a connector instance
connector = MarketplaceConnectorFactory.get_connector(
    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
)

# Create connector with configuration
connector = MarketplaceConnectorFactory.create_connector(
    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
    config={
        "account": "test_account",
        "user": "test_user",
        "token": "test_token"
    },
    tenant_id="tenant-123",
    user_id="user-456"
)
```

### 3. Service Layer

**Location**: `hub/apps/integrations/services.py`

The `MarketplaceIntegrationService` provides high-level business logic for marketplace operations.

#### Key Methods

- **Connection Management**: `create_connection()`, `update_connection()`, `test_connection()`, `delete_connection()`
- **Sync Operations**: `sync_from_marketplace()`, `sync_assets_to_marketplace()`, `cancel_sync_job()`
- **Asset Creation**: `create_federated_asset_with_contracts()` - Creates federated assets with ODPS/ODCS contracts

#### Features

- **Validation**: Comprehensive input validation
- **Authorization**: RBAC/ABAC checks
- **Event Publishing**: Publishes integration and marketplace events
- **Error Handling**: Proper exception types and error messages

### 4. Database Models

**Location**: `hub/apps/integrations/models.py`

#### MarketplaceConnection

Stores connection credentials and configuration for external marketplace integrations.

**Fields**:
- `id`: UUID primary key
- `tenant`: Foreign key to Tenant
- `marketplace_type`: Marketplace type (enum)
- `name`: Human-readable name (unique per tenant)
- `config`: Encrypted connection configuration (JSON)
- `is_active`: Whether connection is active
- `created_at`, `updated_at`: Timestamps

**Security**: The `config` field is encrypted at rest using Django's encryption utilities.

#### MarketplaceSyncJob

Tracks synchronization operations between the Hub and external marketplaces.

**Fields**:
- `id`: UUID primary key
- `tenant`: Foreign key to Tenant
- `connection`: Foreign key to MarketplaceConnection
- `direction`: Sync direction (PUSH, PULL, BIDIRECTIONAL)
- `status`: Sync status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL)
- `items_synced`: Number of items successfully synced
- `items_failed`: Number of items that failed to sync
- `errors`: List of error messages
- `metadata`: Additional metadata about the sync operation
- `created_at`, `updated_at`, `completed_at`: Timestamps

#### MarketplaceMapping

Maps Hub assets to external marketplace listings and resources.

**Fields**:
- `id`: UUID primary key
- `tenant`: Foreign key to Tenant
- `connection`: Foreign key to MarketplaceConnection
- `hub_asset`: Foreign key to Asset
- `external_listing_id`: External marketplace listing identifier
- `external_resource_ids`: List of external resource identifiers
- `sync_metadata`: Metadata about synchronization
- `last_synced_at`: Timestamp of last successful synchronization
- `created_at`, `updated_at`: Timestamps

**Constraints**: Unique constraint on `(connection, hub_asset)` to prevent duplicate mappings.

---

## Metadata-First Architecture Pattern

The metadata-first architecture pattern ensures fast harvesting, clear separation of concerns, and scalable marketplace integration.

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
│  marketplace_sync_pull workflow                                 │
│  ├─ discover_listings_task → Calls connector.list_listings()    │
│  ├─ map_listings_to_assets_task → Calls connector.map_to_hub_asset() │
│  └─ create_federated_assets_task → Calls create_federated_asset_with_contracts() │
│      └─ Based on data_strategy:                                  │
│          - METADATA_ONLY: Store external references only      │
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

### Benefits

1. **Fast Harvesting**: Create thousands of federated assets quickly without downloading data (seconds vs hours)
2. **Scalability**: Harvest large marketplaces without storage overhead (metadata-only assets are lightweight)
3. **Clear Separation**: Federated assets (external metadata) vs Virtualized assets (virtual queries)
4. **Lazy Data Access**: Download data only when explicitly requested (reduces storage costs, improves performance)
5. **Governance/Compliance/Semantic Layers**: All layers work with metadata-first federated assets

---

## Factory Pattern

The factory pattern provides a centralized registry for marketplace connector implementations.

### Registration

Connectors are registered at application startup (typically in `apps.py`):

```python
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.connectors.ckan_connector import CKANConnector

# Register connector
MarketplaceConnectorFactory.register_connector(
    MarketplaceType.CKAN_INSTANCE,
    CKANConnector
)
```

### Retrieval

Connectors are retrieved by marketplace type:

```python
# Get connector instance
connector = MarketplaceConnectorFactory.get_connector(
    MarketplaceType.CKAN_INSTANCE
)

# Create connector with configuration
connector = MarketplaceConnectorFactory.create_connector(
    MarketplaceType.CKAN_INSTANCE,
    config={
        "base_url": "https://data.gov",
        "api_key": "your-api-key"
    },
    tenant_id="tenant-123",
    user_id="user-456"
)
```

### Instance Management

The factory supports marketplace instance configurations (e.g., CKAN instances):

```python
# Create connector from instance configuration
connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance(
    instance_id="dados.gov.br",
    api_key="optional-api-key-override"
)
```

---

## Service Layer

The service layer provides high-level business logic for marketplace operations.

### MarketplaceIntegrationService

**Location**: `hub/apps/integrations/services.py`

#### Connection Management

```python
service = MarketplaceIntegrationService(
    tenant_id="tenant-123",
    user_id="user-456"
)

# Create connection
connection = service.create_connection(
    marketplace_type=MarketplaceType.CKAN_INSTANCE,
    name="Data.gov Connection",
    config={"base_url": "https://data.gov", "api_key": "key"},
    tenant_id="tenant-123",
    user_id="user-456"
)

# Test connection
test_result = service.test_connection(
    connection_id=connection.id,
    tenant_id="tenant-123",
    user_id="user-456"
)
```

#### Sync Operations

```python
# PULL: Sync from marketplace
sync_job = service.sync_from_marketplace(
    connection_id=connection.id,
    tenant_id="tenant-123",
    user_id="user-456",
    listing_ids=None,  # Sync all listings
    filters={"category": "health"},
    options={
        "dry_run": False,
        "data_strategy": "METADATA_ONLY"  # or "DOWNLOAD_SELECTIVE", "DOWNLOAD_ALL"
    }
)

# PUSH: Sync assets to marketplace
sync_job = service.sync_assets_to_marketplace(
    connection_id=connection.id,
    tenant_id="tenant-123",
    user_id="user-456",
    asset_ids=["asset-1", "asset-2"],
    options={"dry_run": False}
)
```

#### Asset Creation

The service provides `create_federated_asset_with_contracts()` which:
- Creates federated assets from `MarketplaceAssetMapping` objects
- Creates ODPS contracts from `odps_metadata`
- Creates ODCS contracts from `odcs_metadata`
- Handles resource downloads based on `data_strategy`
- Updates semantic layer with federated asset properties

---

## Database Models

### MarketplaceConnection

**Table**: `marketplace_connections`

Stores connection credentials and configuration for external marketplace integrations.

**Key Features**:
- Encrypted `config` field (encrypted at rest)
- Tenant-scoped (unique `name` per tenant)
- Active/inactive status tracking

**Indexes**:
- `(tenant, marketplace_type)`
- `(tenant, name)` (unique constraint)

### MarketplaceSyncJob

**Table**: `marketplace_sync_jobs`

Tracks synchronization operations between the Hub and external marketplaces.

**Key Features**:
- Progress tracking (`items_synced`, `items_failed`)
- Error collection (`errors` JSON field)
- Metadata storage (`metadata` JSON field)
- Status tracking (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL)

**Indexes**:
- `(tenant, connection)`
- `(tenant, status)`
- `(connection, status)`

### MarketplaceMapping

**Table**: `marketplace_mappings`

Maps Hub assets to external marketplace listings and resources.

**Key Features**:
- Bidirectional mapping (Hub asset ↔ External listing)
- External resource tracking (`external_resource_ids` JSON field)
- Sync metadata (`sync_metadata` JSON field)
- Last sync timestamp (`last_synced_at`)

**Indexes**:
- `(tenant, connection)`
- `(connection, hub_asset)`
- `(tenant, hub_asset)`
- `(external_listing_id)`

**Constraints**:
- Unique constraint on `(connection, hub_asset)` to prevent duplicate mappings

---

## Event System Integration

The framework integrates with the Hub's event system for real-time notifications and audit trails.

### Event Types

#### Integration Events

- **`integration.connection.created`**: Connection created
- **`integration.connection.updated`**: Connection updated
- **`integration.connection.deleted`**: Connection deleted
- **`integration.connection.tested`**: Connection tested

#### Marketplace Events

- **`marketplace.sync.started`**: Sync job started
- **`marketplace.sync.completed`**: Sync job completed
- **`marketplace.sync.failed`**: Sync job failed
- **`marketplace.sync.cancelled`**: Sync job cancelled
- **`marketplace.asset.mapped`**: Asset mapped to marketplace listing
- **`marketplace.asset.unmapped`**: Asset unmapped from marketplace listing

### Event Publishing

Events are published via the `IntegrationEventPublisher` and `MarketplaceEventPublisher` mixins:

```python
class MarketplaceIntegrationService(
    BaseService,
    IntegrationEventPublisher,
    MarketplaceEventPublisher
):
    def create_connection(self, ...):
        # Create connection
        connection = MarketplaceConnection.objects.create(...)

        # Publish event
        self.publish_integration_connection_created(
            connection_id=str(connection.id),
            marketplace_type=connection.marketplace_type,
            tenant_id=str(connection.tenant_id)
        )

        return connection
```

---

## Job Queue Integration

The framework integrates with the Hub's job queue system for asynchronous sync job execution.

### Job Definition

**Location**: `hub/apps/integrations/tasks.py`

```python
@job('job_default', timeout=3600)  # 1 hour timeout
def execute_marketplace_sync(sync_job_id: str, retry_count: int = 0):
    """
    Execute a marketplace synchronization job.

    Processes a MarketplaceSyncJob by:
    1. Loading the sync job and connection
    2. Creating the appropriate connector
    3. Executing sync operation (PUSH or PULL)
    4. Tracking progress and updating sync job status
    5. Handling errors with retry logic
    6. Using distributed tracing for observability
    """
    # Implementation
    pass
```

### Job Execution

Jobs are enqueued when sync jobs are created:

```python
# In MarketplaceIntegrationService.sync_from_marketplace()
sync_job = MarketplaceSyncJob.objects.create(...)

# Enqueue job
from hub.apps.integrations.tasks import execute_marketplace_sync
execute_marketplace_sync.delay(str(sync_job.id))
```

### Retry Logic

Jobs support automatic retry for transient failures:

```python
@job('job_default', timeout=3600, max_retries=3, retry_backoff=True)
def execute_marketplace_sync(sync_job_id: str, retry_count: int = 0):
    try:
        # Execute sync
        pass
    except TransientError as e:
        # Retry on transient errors
        raise self.retry(exc=e, countdown=60 * (retry_count + 1))
```

---

## Workflow Orchestration

The framework integrates with the Hub's workflow orchestration system for complex sync operations.

### Workflow Definition

**Location**: `hub/apps/orchestration/workflows/marketplace_sync.py`

The `MarketplaceSyncWorkflow` orchestrates marketplace synchronization:

#### PULL Sync Workflow

```
marketplace_sync_pull:
  1. discover_listings_task
     - Calls connector.list_listings() or connector.get_listing()
     - Returns list of MarketplaceListing objects
  2. map_listings_to_assets_task
     - Calls connector.map_to_hub_asset() for each listing
     - Returns list of MarketplaceAssetMapping objects
  3. create_federated_assets_task
     - Calls create_federated_asset_with_contracts() for each mapping
     - Based on data_strategy:
       - METADATA_ONLY: Store external references only
       - DOWNLOAD_SELECTIVE: Download specific resources via connector.download_resource()
       - DOWNLOAD_ALL: Download all resources via connector.download_resource()
  4. create_mappings_task
     - Creates MarketplaceMapping records
  5. update_semantic_layer_task
     - Updates semantic layer with federated asset properties
```

#### PUSH Sync Workflow

```
marketplace_sync_push:
  1. validate_assets_task
     - Validates source assets exist and accessible
  2. map_assets_to_listings_task
     - Calls connector.map_from_hub_asset() for each asset
     - Returns list of MarketplaceListing objects
  3. publish_listings_task
     - Calls connector.create_listing() or connector.update_listing()
  4. create_mappings_task
     - Creates MarketplaceMapping records
  5. update_semantic_layer_task
     - Updates semantic layer with federated asset properties
```

### Workflow Registration

Workflows are registered at application startup:

```python
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.marketplace_sync import MarketplaceSyncWorkflow

registry = WorkflowRegistry()
MarketplaceSyncWorkflow.register_workflow(registry)
```

### Workflow Execution

Workflows are executed when sync jobs are created:

```python
# In MarketplaceIntegrationService.sync_from_marketplace()
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
workflow_instance = engine.create_instance(
    workflow_name="marketplace_sync_pull",
    input_data={
        "connection_id": connection_id,
        "listing_ids": listing_ids,
        "filters": filters,
        "options": options,
        "sync_job_id": str(sync_job.id),
        "tenant_id": tenant_id,
        "user_id": user_id
    },
    tenant_id=tenant_id,
    created_by_id=user_id
)
```

---

## Architecture Diagrams

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  MarketplaceConnectionViewSet                            │   │
│  │  MarketplaceSyncJobViewSet                               │   │
│  │  MarketplaceMappingViewSet                               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  MarketplaceIntegrationService                          │   │
│  │  - Connection Management                                │   │
│  │  - Sync Operations                                      │   │
│  │  - Asset Creation                                        │   │
│  │  - Event Publishing                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│   Workflow Orchestration  │  │      Job Queue           │
│  ┌──────────────────────┐ │  │  ┌────────────────────┐ │
│  │ MarketplaceSyncWorkflow│ │  │  │ execute_marketplace_│ │
│  │ - PULL Workflow      │ │  │  │   sync()            │ │
│  │ - PUSH Workflow      │ │  │  └────────────────────┘ │
│  └──────────────────────┘ │  └──────────────────────────┘
└──────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Connector Layer                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  MarketplaceConnectorFactory                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│   │
│  │  │ CKANConnector │  │SnowflakeConn │  │ AWSConnector  ││   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘│   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│   │
│  │  │ GCPConnector  │  │DatabricksConn│  │ ...          ││   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘│   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  MarketplaceConnection                                   │   │
│  │  MarketplaceSyncJob                                      │   │
│  │  MarketplaceMapping                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Metadata-First Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Connector Layer                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. sync_pull()                                                  │
│     ├─ list_listings() → MarketplaceListing[]                  │
│     ├─ map_to_hub_asset() → MarketplaceAssetMapping[]         │
│     └─ Return SyncResult with mappings                          │
│                                                                   │
│  2. map_to_hub_asset()                                           │
│     ├─ Extract asset metadata                                   │
│     ├─ Extract ODPS/ODCS metadata                               │
│     └─ Include external resource references                    │
│                                                                   │
│  3. download_resource() (on-demand)                            │
│     ├─ Handle marketplace-specific operations                   │
│     ├─ Download resource data                                  │
│     └─ Return path to downloaded file                          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow Layer                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  marketplace_sync_pull:                                          │
│  1. discover_listings_task                                      │
│     └─ Calls connector.list_listings()                         │
│                                                                   │
│  2. map_listings_to_assets_task                                 │
│     └─ Calls connector.map_to_hub_asset()                      │
│                                                                   │
│  3. create_federated_assets_task                                │
│     └─ Calls create_federated_asset_with_contracts()            │
│         ├─ Create federated asset                              │
│         ├─ Create ODPS contract                                │
│         ├─ Create ODCS contract                                │
│         └─ Based on data_strategy:                             │
│             - METADATA_ONLY: Store references only             │
│             - DOWNLOAD_SELECTIVE: Download specific resources  │
│             - DOWNLOAD_ALL: Download all resources             │
│                                                                   │
│  4. create_mappings_task                                        │
│     └─ Create MarketplaceMapping records                       │
│                                                                   │
│  5. update_semantic_layer_task                                  │
│     └─ Update semantic layer with federated asset properties   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Decisions

### 1. Metadata-First Architecture

**Decision**: Separate listing discovery/mapping from asset creation and data downloading.

**Rationale**:
- Fast harvesting (seconds vs hours)
- Scalability (lightweight metadata-only assets)
- Clear separation of concerns
- Lazy data access (download only when needed)

**Trade-offs**:
- Slightly more complex architecture
- Requires careful implementation to avoid downloading data during sync

### 2. Factory Pattern

**Decision**: Use factory pattern for connector registration and retrieval.

**Rationale**:
- Dynamic connector registration
- Type-based retrieval
- Configuration support
- Instance management

**Trade-offs**:
- Requires registration at startup
- Slightly more complex than direct instantiation

### 3. Workflow Orchestration

**Decision**: Use workflow orchestration for complex sync operations.

**Rationale**:
- Progress tracking
- Error handling and recovery
- Task dependencies
- Compensation logic

**Trade-offs**:
- Additional complexity
- Requires workflow engine

### 4. Encrypted Configuration

**Decision**: Encrypt connection configuration at rest.

**Rationale**:
- Security best practice
- Protects sensitive credentials
- Compliance requirements

**Trade-offs**:
- Additional encryption/decryption overhead
- Requires key management

### 5. Event-Driven Architecture

**Decision**: Publish events for all marketplace operations.

**Rationale**:
- Real-time notifications
- Audit trails
- Integration with other systems
- Observability

**Trade-offs**:
- Additional event publishing overhead
- Requires event system

---

## Additional Resources

- **Base Connector Interface**: `hub/apps/integrations/base.py` - Complete interface documentation
- **Connector Development Guide**: `docs/MARKETPLACE_CONNECTOR_DEVELOPMENT_GUIDE.md` - Implementation guide
- **API Reference**: `docs/MARKETPLACE_API_REFERENCE.md` - Complete API documentation
- **Workflow Integration**: `hub/apps/orchestration/workflows/marketplace_sync.py` - Workflow implementation
- **Service Layer**: `hub/apps/integrations/services.py` - Service implementation

---

**Last Updated**: 2026-01-10
**Version**: 1.0.0
