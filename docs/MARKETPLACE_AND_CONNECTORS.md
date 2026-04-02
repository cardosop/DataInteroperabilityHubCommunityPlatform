# Marketplace & Connectors

> Consolidated reference for marketplace integration, connector development, vendor guides, use cases, and connection validation.
>
> **Source**: Merged from 24 individual marketplace/connector docs during Phase 120C documentation consolidation.

---

## Table of Contents

1. [Integration Framework](#integration-framework)
2. [Connector Development Guide](#connector-development-guide)
3. [User Guide](#user-guide)
4. [Internal vs External Marketplaces](#internal-vs-external-marketplaces)
5. [Use Cases](#use-cases)
6. [User Journeys](#user-journeys)
7. [Connection Validation](#connection-validation)
8. [Vendor Reference Sheets](#vendor-reference-sheets)

---


---

## Integration Framework


Complete architecture documentation for the Data Interoperability Hub Marketplace Integration Framework.

**Last Updated**: 2026-03-22
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

The Marketplace Integration Framework enables bidirectional synchronization between the Data Interoperability Hub and external data marketplaces (CKAN, Snowflake Data Marketplace, AWS Data Exchange, Azure Data Share, GCP Marketplace, Databricks, etc.). All external marketplace APIs live under `/api/v1/integrations/marketplace/`. For the distinction between the Hub’s internal marketplace (listings, orders, entitlements under `/api/v1/marketplace/`) and these external integrations, see [Internal vs External Marketplace](MARKETPLACE_INTERNAL_VS_EXTERNAL.md).

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

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Connector Development Guide


Complete guide for developing marketplace connectors following the metadata-first architecture pattern.

**Last Updated**: 2026-03-22
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

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## User Guide


## Overview

The Data Interoperability Hub provides comprehensive marketplace integration capabilities that allow you to:

- **Publish assets** from the Hub to external data marketplaces (PUSH sync)
- **Discover and import assets** from external marketplaces into the Hub (PULL sync)
- **Manage bidirectional synchronization** between the Hub and marketplace platforms
- **Track sync jobs** and view detailed progress and error information
- **View asset mappings** between Hub assets and marketplace listings

This guide covers the complete workflow for marketplace integration, from creating connections to managing sync operations.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Creating Marketplace Connections](#creating-marketplace-connections)
3. [Testing Connections](#testing-connections)
4. [Syncing Assets to Marketplaces (PUSH)](#syncing-assets-to-marketplaces-push)
5. [Syncing Assets from Marketplaces (PULL)](#syncing-assets-from-marketplaces-pull)
6. [Managing Sync Jobs](#managing-sync-jobs)
7. [Viewing Mappings](#viewing-mappings)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

Before you can use marketplace integration, ensure:

1. **Tenant KYC Verification**: Your tenant must have `VERIFIED` KYC status to publish assets to marketplaces
2. **User Permissions**: You need one of the following roles:
   - `DATA_PROVIDER` - Can create connections and manage sync operations
   - `TENANT_ADMIN` - Full access to all marketplace integration features
3. **API Scopes**: You must have the `integrations:write` scope for write operations
4. **Active Assets**: Assets must be in `ACTIVE` status to be synced to marketplaces
5. **Valid Contracts**: Assets must have `ACTIVE` contracts with `VALID` or `WARNING_ONLY` validation status

## Creating Marketplace Connections

A marketplace connection stores the configuration and credentials needed to connect to an external marketplace platform.

### Step 1: Prepare Connection Configuration

Each marketplace type requires specific configuration parameters. Refer to the marketplace-specific guides for detailed configuration requirements:

- [CKAN Guide](MARKETPLACE_CKAN_GUIDE.md)
- [Snowflake Guide](MARKETPLACE_SNOWFLAKE_GUIDE.md)
- [AWS Data Exchange Guide](MARKETPLACE_AWS_GUIDE.md)
- [Azure Marketplace Guide](MARKETPLACE_AZURE_GUIDE.md)
- [GCP Marketplace Guide](MARKETPLACE_GCP_GUIDE.md)
- [Databricks Guide](MARKETPLACE_DATABRICKS_GUIDE.md)
- [SAP Guide](MARKETPLACE_SAP_GUIDE.md)
- [IBM Guide](MARKETPLACE_IBM_GUIDE.md)
- [Oracle Guide](MARKETPLACE_ORACLE_GUIDE.md)
- [Salesforce Guide](MARKETPLACE_SALESFORCE_GUIDE.md)
- [DataRade Guide](MARKETPLACE_DATARADE_GUIDE.md)
- [Dawex Guide](MARKETPLACE_DAWEX_GUIDE.md)
- [NASDAQ Guide](MARKETPLACE_NASDAQ_GUIDE.md)
- [Esri Guide](MARKETPLACE_ESRI_GUIDE.md)
- [Collibra Guide](MARKETPLACE_COLLIBRA_GUIDE.md)

### Step 2: Create Connection via API

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request Body**:
```json
{
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "My Snowflake Connection",
  "config": {
    "account_identifier": "your-account",
    "username": "your-username",
    "password": "your-password",
    "warehouse": "COMPUTE_WH",
    "database": "MARKETPLACE_DB"
  },
  "is_active": true
}
```

**Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "My Snowflake Connection",
  "is_active": true,
  "created_at": "2025-01-10T10:00:00Z",
  "updated_at": "2025-01-10T10:00:00Z"
}
```

**Important Notes**:
- Connection names must be unique within your tenant
- Configuration is automatically encrypted at rest for security
- The `config` field is never returned in API responses for security reasons
- Connections are tenant-scoped (you can only see connections in your tenant)

### Step 3: Verify Connection Creation

**Endpoint**: `GET /api/v1/integrations/marketplace/connections/{connection_id}/`

This retrieves the connection details (without sensitive config data).

## Testing Connections

Before using a connection for sync operations, always test it to ensure credentials are valid.

### Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

**Response**:
```json
{
  "success": true,
  "message": "Connection test successful",
  "tested_at": "2025-01-10T10:05:00Z",
  "details": {
    "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
    "response_time_ms": 245
  }
}
```

**Error Response**:
```json
{
  "success": false,
  "message": "Connection test failed: Invalid credentials",
  "tested_at": "2025-01-10T10:05:00Z",
  "error": "Authentication failed"
}
```

**Best Practice**: Always test connections after creation and before running sync jobs.

## Syncing Assets to Marketplaces (PUSH)

PUSH sync publishes your Hub assets to external marketplaces, making them discoverable and available for purchase or access.

### Prerequisites for PUSH Sync

1. **Asset Requirements**:
   - Asset status: `ACTIVE`
   - Contract status: `ACTIVE` with `VALID` or `WARNING_ONLY` validation
   - DQ status: `PASS` or `WARN` (if dataset exists)
   - Compliance status: `PASS` or `WARN` (if dataset exists)

2. **Tenant Requirements**:
   - KYC status: `VERIFIED`

### Step 1: Create Sync Job

**Endpoint**: `POST /api/v1/integrations/marketplace/sync-jobs/`

**Request Body**:
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PUSH",
  "asset_ids": [
    "660e8400-e29b-41d4-a716-446655440001",
    "660e8400-e29b-41d4-a716-446655440002"
  ],
  "options": {
    "skip_resource_downloads": false,
    "skip_semantic_mapping": false
  }
}
```

**Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PUSH",
  "status": "PENDING",
  "items_synced": 0,
  "items_failed": 0,
  "created_at": "2025-01-10T10:10:00Z"
}
```

### Step 2: Monitor Sync Job Progress

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/`

**Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "status": "RUNNING",
  "progress_percentage": 60,
  "current_step": "publish_to_marketplace",
  "items_synced": 1,
  "items_failed": 0,
  "metadata": {
    "progress_percentage": 60,
    "current_step": "publish_to_marketplace"
  },
  "started_at": "2025-01-10T10:10:05Z",
  "updated_at": "2025-01-10T10:10:30Z"
}
```

### PUSH Sync Workflow Steps

The PUSH sync workflow executes the following steps:

1. **Validate Connection**: Verifies connection is active and tested
2. **Validate Assets**: Checks asset eligibility (status, contracts, DQ, compliance)
3. **Map Assets to Marketplace**: Converts Hub asset format to marketplace listing format
4. **Publish to Marketplace**: Creates/updates listings in the external marketplace
5. **Create Mappings**: Records the mapping between Hub assets and marketplace listings
6. **Update Semantic Layer**: Updates semantic layer with federated asset properties
7. **Complete**: Marks sync job as completed

### Step 3: View Sync Results

Once the sync job completes, check the results:

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/`

**Completed Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "status": "COMPLETED",
  "progress_percentage": 100,
  "current_step": "complete",
  "items_synced": 2,
  "items_failed": 0,
  "completed_at": "2025-01-10T10:12:00Z",
  "errors": []
}
```

**Failed Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440003",
  "status": "FAILED",
  "progress_percentage": 40,
  "current_step": "publish_to_marketplace",
  "items_synced": 0,
  "items_failed": 2,
  "errors": [
    {
      "step": "publish_to_marketplace",
      "asset_id": "660e8400-e29b-41d4-a716-446655440001",
      "error": "Marketplace API rate limit exceeded"
    }
  ]
}
```

## Syncing Assets from Marketplaces (PULL)

PULL sync discovers and imports assets from external marketplaces into the Hub as federated assets.

### Step 1: Create PULL Sync Job

**Endpoint**: `POST /api/v1/integrations/marketplace/sync-jobs/`

**Request Body**:
```json
{
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "options": {
    "filters": {
      "domain": "finance",
      "category": "market-data"
    },
    "limit": 100,
    "data_strategy": "METADATA_ONLY",
    "skip_semantic_mapping": false
  }
}
```

**Data Strategy Options**:
- `METADATA_ONLY`: Import only metadata, no resource downloads (fastest)
- `DOWNLOAD_ALL`: Download all resources for all assets
- `DOWNLOAD_SELECTIVE`: Download resources for specific assets (use `download_resources` list)
- `download_resources_for_last_n`: Download resources only for the last N discovered assets

**Response**:
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440004",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "direction": "PULL",
  "status": "PENDING",
  "items_synced": 0,
  "items_failed": 0,
  "created_at": "2025-01-10T10:15:00Z"
}
```

### Step 2: Monitor PULL Sync Progress

Monitor progress the same way as PUSH sync:

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/`

### PULL Sync Workflow Steps

The PULL sync workflow executes the following steps:

1. **Validate Connection**: Verifies connection is active and tested
2. **Discover Listings**: Fetches listings from the marketplace (with optional filters)
3. **Map Listings to Assets**: Converts marketplace listing format to Hub asset format
4. **Create Federated Assets**: Creates assets with dual contracts (ODPS + ODCS)
5. **Download Resources**: Downloads resources from marketplace (if data_strategy allows)
6. **Create Mappings**: Records the mapping between marketplace listings and Hub assets
7. **Update Semantic Layer**: Updates semantic layer with federated asset properties
8. **Complete**: Marks sync job as completed

### Step 3: View Created Federated Assets

After PULL sync completes, federated assets are created in your tenant:

**Endpoint**: `GET /api/v1/assets/?source_type=FEDERATED`

Federated assets have:
- `source_type`: `FEDERATED`
- Dual contracts: ODPS (from marketplace) and ODCS (Hub-generated)
- `source_metadata`: Contains marketplace-specific metadata
- Resources: Downloaded from marketplace (if data_strategy allowed)

## Managing Sync Jobs

### List Sync Jobs

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/`

**Query Parameters**:
- `connection_id`: Filter by connection
- `direction`: Filter by direction (PUSH, PULL)
- `status`: Filter by status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL)
- `ordering`: Sort by field (default: `-created_at`)
- `page`: Page number for pagination
- `page_size`: Items per page

**Response**:
```json
{
  "count": 10,
  "next": "http://api.example.com/api/v1/integrations/marketplace/sync-jobs/?page=2",
  "previous": null,
  "results": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440003",
      "connection_id": "550e8400-e29b-41d4-a716-446655440000",
      "direction": "PUSH",
      "status": "COMPLETED",
      "items_synced": 2,
      "items_failed": 0,
      "created_at": "2025-01-10T10:10:00Z",
      "completed_at": "2025-01-10T10:12:00Z"
    }
  ]
}
```

### Cancel Sync Job

If a sync job is running and you need to stop it:

**Endpoint**: `POST /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/cancel/`

**Request Body**:
```json
{
  "reason": "User requested cancellation"
}
```

**Response**:
```json
{
  "cancelled": true,
  "cancelled_at": "2025-01-10T10:20:00Z",
  "reason": "User requested cancellation"
}
```

**Note**: Cancellation may take a few moments to process. The job status will update to `FAILED` with cancellation details in the errors field.

### View Sync Job Details

**Endpoint**: `GET /api/v1/integrations/marketplace/sync-jobs/{sync_job_id}/`

Returns full details including:
- Progress information
- Current step
- Items synced/failed
- Error details
- Metadata

## Viewing Mappings

Mappings track the relationship between Hub assets and marketplace listings.

### List Mappings

**Endpoint**: `GET /api/v1/integrations/marketplace/mappings/`

**Query Parameters**:
- `connection_id`: Filter by connection
- `hub_asset_id`: Filter by Hub asset ID
- `external_listing_id`: Filter by marketplace listing ID
- `ordering`: Sort by field (default: `-last_synced_at`)
- `page`: Page number
- `page_size`: Items per page

**Response**:
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440005",
      "connection_id": "550e8400-e29b-41d4-a716-446655440000",
      "hub_asset_id": "660e8400-e29b-41d4-a716-446655440001",
      "external_listing_id": "marketplace-listing-12345",
      "sync_metadata": {
        "sync_direction": "PUSH",
        "synced_at": "2025-01-10T10:12:00Z"
      },
      "last_synced_at": "2025-01-10T10:12:00Z"
    }
  ]
}
```

### Get Mapping Details

**Endpoint**: `GET /api/v1/integrations/marketplace/mappings/{mapping_id}/`

Returns detailed mapping information including:
- Hub asset details
- Marketplace listing ID
- Sync metadata
- Last sync timestamp

## Troubleshooting

### Connection Test Failures

**Problem**: Connection test fails with authentication error

**Solutions**:
1. Verify credentials are correct in the connection config
2. Check if credentials have expired
3. Ensure API keys have necessary permissions
4. Verify network connectivity to marketplace
5. Check marketplace-specific requirements (IP whitelisting, etc.)

### PUSH Sync Failures

**Problem**: Assets fail to sync to marketplace

**Common Causes**:
1. **Asset not eligible**: Check asset status, contract status, DQ/compliance status
2. **KYC not verified**: Tenant must have VERIFIED KYC status
3. **Marketplace API errors**: Check error details in sync job response
4. **Rate limiting**: Marketplace may have rate limits - wait and retry
5. **Invalid asset format**: Asset may not be compatible with marketplace requirements

**Solutions**:
- Review sync job error details
- Fix asset eligibility issues
- Retry sync job after resolving issues
- Check marketplace-specific limitations

### PULL Sync Failures

**Problem**: Assets fail to import from marketplace

**Common Causes**:
1. **Connection issues**: Marketplace API may be unavailable
2. **Invalid listing format**: Marketplace listing may not be compatible
3. **Resource download failures**: Resources may be inaccessible
4. **Contract creation failures**: ODPS/ODCS contract generation may fail

**Solutions**:
- Check connection test status
- Review sync job error details
- Verify marketplace listings are accessible
- Try with `METADATA_ONLY` data strategy first

### Sync Job Stuck in RUNNING Status

**Problem**: Sync job appears stuck and doesn't progress

**Solutions**:
1. Check workflow instance status in system logs
2. Verify marketplace API is responding
3. Cancel and retry the sync job
4. Contact support if issue persists

### Mapping Not Created

**Problem**: Sync job completes but no mapping is created

**Solutions**:
1. Verify sync job completed successfully (status: COMPLETED)
2. Check if assets/listings were actually synced (items_synced > 0)
3. Review sync job metadata for mapping creation details
4. Check if mapping already exists (may have been created in previous sync)

## Best Practices

1. **Always test connections** before creating sync jobs
2. **Start with small batches** when syncing many assets
3. **Use METADATA_ONLY for initial PULL syncs** to validate connectivity
4. **Monitor sync job progress** regularly for long-running operations
5. **Review error details** carefully to understand failure causes
6. **Keep connection credentials secure** - they are encrypted but should still be protected
7. **Use appropriate data strategies** based on your needs (METADATA_ONLY vs DOWNLOAD_ALL)
8. **Schedule regular syncs** for keeping marketplace listings up-to-date
9. **Review mappings periodically** to ensure sync accuracy
10. **Document connection configurations** for team knowledge sharing

## API Reference

For complete API documentation, see:
- [Marketplace Connections API](../../docs/api/marketplace-connections.md)
- [Marketplace Sync Jobs API](../../docs/api/marketplace-sync-jobs.md)
- [Marketplace Mappings API](../../docs/api/marketplace-mappings.md)

## Additional Resources

- [Marketplace-Specific Guides](./) - Detailed configuration for each marketplace
- [Workflow Documentation](../../docs/workflows/marketplace-sync.md)
- [Security Best Practices](../../docs/security/marketplace-integration.md)
- **CLI Usage**: [Marketplace CLI Usage Guide](../cli/docs/MARKETPLACE_USAGE.md) - Complete CLI commands for marketplace integration
- **SDK Usage**: [Marketplace Python SDK Usage Guide](../sdk/python/docs/MARKETPLACE_USAGE.md) - Complete SDK APIs for marketplace integration

---

## Internal vs External Marketplaces


This document clearly separates the **internal marketplace** (Hub’s own catalog, orders, entitlements) from the **external marketplace** (integrations with third‑party data marketplaces). Each has a different URL prefix and purpose.

---

## Summary

| Aspect | Internal marketplace | External marketplace |
|--------|----------------------|----------------------|
| **Purpose** | Hub’s data product catalog, ordering, and entitlements | Connect to external marketplaces; sync and map listings |
| **Base URL** | `/api/v1/marketplace/` | `/api/v1/integrations/marketplace/` |
| **App** | `hub.apps.marketplace` | `hub.apps.integrations` (marketplace routes) |

---

## Internal marketplace — `/api/v1/marketplace/`

The **internal marketplace** is the Hub’s own marketplace: data product **listings**, **orders**, **entitlements**, **preview**, and related configuration. All of these live under `/api/v1/marketplace/`.

### Main resources

- **Listings** — Data product listings in the Hub catalog  
  - `GET/POST /api/v1/marketplace/listings/`  
  - `GET/PUT/PATCH/DELETE /api/v1/marketplace/listings/{id}/`  
  - `GET /api/v1/marketplace/listings/{id}/preview/` — time-limited preview  
  - `GET /api/v1/marketplace/listings/{id}/download/` — contract/download  

- **Orders** — Consumer orders for listings  
  - `GET/POST /api/v1/marketplace/orders/`  
  - `GET/PUT/PATCH /api/v1/marketplace/orders/{id}/`  
  - `POST /api/v1/marketplace/orders/{id}/approve/`  
  - `POST /api/v1/marketplace/orders/{id}/reject/`  

- **Entitlements** — Granted access after order approval  
  - `GET /api/v1/marketplace/entitlements/`  
  - `GET /api/v1/marketplace/entitlements/{id}/`  

- **Configuration**  
  - Trust signals: `GET/POST/PUT/PATCH/DELETE /api/v1/marketplace/config/trust-signals/`  
  - Payment gateways: `/api/v1/marketplace/payment-gateways/`  

### When to use

Use internal marketplace APIs when you work with the Hub’s **own** catalog: publishing listings, placing or approving orders, checking entitlements, or getting preview/download URLs.

### Order → Entitlement Lifecycle (Phase 117B)

The internal marketplace supports two order flows based on the listing’s `pricing_model`:

#### FREE_AUTO_APPROVE Flow

1. Consumer creates order → `POST /api/v1/marketplace/orders/` with `listing_id`
2. Service detects `listing.pricing_model == FREE_AUTO_APPROVE`
3. Order auto-transitions: `REQUESTED → APPROVED → FULFILLED` (atomic)
4. `_create_entitlement_for_order()` creates `Entitlement(status=ACTIVE)` for consumer tenant + asset
5. Response includes both `order` (status=FULFILLED) and `entitlement` data
6. Consumer can immediately access the asset via `require_entitlement()` checks

#### REQUEST_APPROVAL Flow

1. Consumer creates order → status stays `REQUESTED`
2. Provider reviews order in their dashboard
3. Provider approves: `POST /api/v1/marketplace/orders/{id}/approve/`
   - `order.approve()` validates `REQUESTED → APPROVED` transition
   - `_create_entitlement_for_order()` creates `Entitlement(status=ACTIVE)`
   - `order.fulfill()` transitions to `FULFILLED`
4. Or provider rejects: `POST /api/v1/marketplace/orders/{id}/reject/` with `reason`
   - Order transitions to `REJECTED` (terminal state)
   - No entitlement created

#### Entitlement Status Values

| Status | Meaning | Cross-Tenant Access |
|--------|---------|---------------------|
| `ACTIVE` | Consumer has access | Allowed |
| `REVOKED` | Provider revoked access | Denied (403 `ENTITLEMENT_REVOKED`) |
| `EXPIRED` | Past `expires_at` date | Denied (403 `ENTITLEMENT_EXPIRED`) |

#### Implementation

- **Service**: `hub/apps/marketplace/services.py` — `MarketplaceService._create_order_impl()`, `_approve_order_impl()`, `_create_entitlement_for_order()`
- **Views**: `hub/apps/marketplace/order_views.py` — `OrderViewSet.create()`, `approve()`, `reject()`
- **Access check**: `hub/apps/marketplace/entitlement_check.py` — `require_entitlement(consumer_tenant_id, asset_id, provider_tenant_id)`

### ML Model Marketplace Publishing (Integration-2)

ML models can be published to the internal marketplace as listings:

```
POST /api/v1/ml/models/{model_id}/marketplace-publish/
Body: {"pricing_model": "REQUEST_APPROVAL"}
```

This creates a marketplace `Listing` linked to the model’s asset with the specified `pricing_model`. The model must be in `TRAINED` or `DEPLOYED` status.

**CLI**: `datahub ml marketplace-publish <model_id> --pricing-model REQUEST_APPROVAL`

**Python SDK**: `client.ml.publish_to_marketplace(model_id, pricing_model="REQUEST_APPROVAL")`

**JS SDK**: `client.ml.publishToMarketplace(modelId, "REQUEST_APPROVAL")`

---

## External marketplace — `/api/v1/integrations/marketplace/`

The **external marketplace** APIs manage **connections** to third‑party data marketplaces (e.g. Snowflake, AWS Data Exchange, Databricks), **sync jobs** (PULL/PUSH), and **mappings** between Hub assets and external listings. All of these live under `/api/v1/integrations/marketplace/`.

### Main resources

- **Connections** — Configure and test connections to external marketplaces  
  - `GET/POST /api/v1/integrations/marketplace/connections/`  
  - `GET/PUT/PATCH/DELETE /api/v1/integrations/marketplace/connections/{id}/`  
  - `POST /api/v1/integrations/marketplace/connections/{id}/test/`  

- **Sync jobs** — Run and monitor PULL/PUSH sync  
  - `GET/POST /api/v1/integrations/marketplace/sync/`  
  - `GET /api/v1/integrations/marketplace/sync/{id}/`  
  - `POST /api/v1/integrations/marketplace/sync/{id}/cancel/`  

- **Mappings** — Hub asset ↔ external listing mapping  
  - `GET /api/v1/integrations/marketplace/mappings/`  
  - `GET/DELETE /api/v1/integrations/marketplace/mappings/{id}/`  

- **Connector metadata**  
  - `GET /api/v1/integrations/marketplace/connectors/`  
  - `GET /api/v1/integrations/marketplace/connectors/{connector_type}/`  

### When to use

Use external marketplace APIs when you **integrate with external marketplaces**: creating connections, running sync jobs, or inspecting mappings. See [Marketplace API Reference](MARKETPLACE_API_REFERENCE.md) for the full external API reference.

---

## Quick reference: URL prefixes

- **Internal (Hub catalog, orders, entitlements, preview):**  
  `/api/v1/marketplace/`

- **External (connections, sync, mappings):**  
  `/api/v1/integrations/marketplace/`

Do not confuse the two: e.g. `/api/v1/marketplace/connections/` does **not** exist; connections are under `/api/v1/integrations/marketplace/connections/`.

---

## Related documentation

- [Marketplace API Reference](MARKETPLACE_API_REFERENCE.md) — Full reference for **external** marketplace APIs (connections, sync, mappings).
- [Marketplace Integration Framework](MARKETPLACE_INTEGRATION_FRAMEWORK.md) — Architecture and concepts.
- [Marketplace Use Cases](MARKETPLACE_USE_CASES.md) — Use cases and flows.
- [Docs README](README.md) — Documentation index.

---

## Vendor Reference Sheets


### AWS


## Overview

This guide covers integration with AWS Data Exchange, a service that makes it easy to find, subscribe to, and use third-party data in the cloud.

## Marketplace Type

- **Type**: `AWS_DATA_EXCHANGE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: AWS IAM Credentials

## Connection Configuration

### Required Configuration Parameters

```json
{
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "aws_region": "us-east-1",
  "data_set_id": "optional-default-dataset-id"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `aws_access_key_id` | string | Yes | AWS access key ID |
| `aws_secret_access_key` | string | Yes | AWS secret access key |
| `aws_region` | string | Yes | AWS region (e.g., `us-east-1`) |
| `data_set_id` | string | No | Default dataset ID for publishing (optional) |

### Optional Configuration

```json
{
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "aws_region": "us-east-1",
  "data_set_id": "optional-default-dataset-id",
  "s3_bucket": "my-data-bucket",
  "s3_prefix": "marketplace/",
  "session_token": "optional-session-token"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `s3_bucket` | string | No | S3 bucket for storing data files |
| `s3_prefix` | string | No | S3 prefix for organizing files |
| `session_token` | string | No | AWS session token (for temporary credentials) |

## Creating an AWS Data Exchange Connection

### Step 1: Prepare AWS Account

1. Ensure you have an AWS account with Data Exchange access
2. Create IAM user or role with necessary permissions:
   - `dataexchange:GetDataSet`
   - `dataexchange:ListDataSets`
   - `dataexchange:CreateDataSet`
   - `dataexchange:UpdateDataSet`
   - `dataexchange:CreateRevision`
   - `dataexchange:UpdateRevision`
   - `dataexchange:CreateJob`
   - `dataexchange:GetJob`
   - `s3:GetObject`
   - `s3:PutObject`
   - `s3:ListBucket`
3. Create S3 bucket for storing data files (if not using existing bucket)
4. Configure bucket policies for Data Exchange access

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "AWS_DATA_EXCHANGE",
  "name": "My AWS Data Exchange",
  "config": {
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "aws_region": "us-east-1",
    "s3_bucket": "my-data-exchange-bucket",
    "s3_prefix": "marketplace/"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## AWS Data Exchange-Specific Features

### Product Publishing (PUSH)

When syncing assets to AWS Data Exchange:

1. **DataSet Creation**: Assets are published as AWS Data Exchange datasets
2. **Revision Creation**: Each sync creates a new revision
3. **S3 Upload**: Asset resources are uploaded to S3
4. **Export Job**: Creates export job for data delivery
5. **Metadata Publishing**: Asset metadata is published as product metadata

### Product Discovery (PULL)

When syncing from AWS Data Exchange:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Export Job Creation**: Creates export job to get data
4. **S3 Download**: Downloads data from S3 export location
5. **ODPS Generation**: Generates ODPS contracts from product metadata

## AWS Data Exchange-Specific Limitations

1. **Account Requirements**: Requires AWS account with Data Exchange enabled
2. **IAM Permissions**: Requires extensive IAM permissions for Data Exchange and S3
3. **Revision Model**: Each update creates a new revision (immutable)
4. **Export Jobs**: Data access requires export job creation and completion
5. **S3 Dependencies**: All data must be stored in S3
6. **Region Constraints**: Data Exchange operations are region-specific
7. **Subscription Model**: PULL operations require product subscription
8. **Job Status**: Export jobs are asynchronous and may take time to complete

## Best Practices

1. **IAM Roles**: Use IAM roles instead of access keys when possible
2. **S3 Organization**: Use S3 prefixes to organize marketplace data
3. **Revision Management**: Understand that revisions are immutable
4. **Export Job Monitoring**: Monitor export job status before downloading
5. **Cost Optimization**: Be aware of S3 storage and data transfer costs
6. **Error Handling**: Implement retry logic for export job polling
7. **Metadata Quality**: Ensure complete metadata for better product discoverability
8. **Security**: Use least-privilege IAM policies

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify AWS access key ID and secret access key are correct

**Issue**: PUSH sync fails with "Access Denied"
- **Solution**: Ensure IAM user/role has necessary Data Exchange permissions

**Issue**: Export job creation fails
- **Solution**: Verify S3 bucket exists and IAM user has S3 permissions

**Issue**: Export job stuck in "IN_PROGRESS"
- **Solution**: Export jobs can take time; implement polling with appropriate timeout

**Issue**: S3 download fails
- **Solution**: Verify S3 bucket policy allows Data Exchange service access

**Issue**: Revision creation fails
- **Solution**: Ensure dataset exists and you have revision creation permissions

## Additional Resources

- [AWS Data Exchange Documentation](https://docs.aws.amazon.com/data-exchange/)
- [AWS Data Exchange API Reference](https://docs.aws.amazon.com/data-exchange/latest/apireference/)
- [AWS Data Exchange User Guide](https://docs.aws.amazon.com/data-exchange/latest/userguide/)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### AZURE


## Overview

This guide covers integration with Azure Marketplace, Microsoft's cloud marketplace for data products and services.

## Marketplace Type

- **Type**: `AZURE_MARKETPLACE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: Azure Service Principal

## Connection Configuration

### Required Configuration Parameters

```json
{
  "tenant_id": "your-azure-tenant-id",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "subscription_id": "your-subscription-id"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tenant_id` | string | Yes | Azure Active Directory tenant ID |
| `client_id` | string | Yes | Azure service principal client ID |
| `client_secret` | string | Yes | Azure service principal client secret |
| `subscription_id` | string | Yes | Azure subscription ID |

### Optional Configuration

```json
{
  "tenant_id": "your-azure-tenant-id",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "subscription_id": "your-subscription-id",
  "resource_group": "marketplace-rg",
  "storage_account": "marketplacestorage",
  "location": "eastus"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `resource_group` | string | No | Azure resource group for marketplace resources |
| `storage_account` | string | No | Azure Storage account for data files |
| `location` | string | No | Azure region (default: `eastus`) |

## Creating an Azure Marketplace Connection

### Step 1: Prepare Azure Service Principal

1. Create Azure Service Principal in Azure Active Directory
2. Assign necessary roles:
   - `Marketplace Publisher` (for PUSH)
   - `Storage Blob Data Contributor` (for data access)
   - `Reader` (for PULL operations)
3. Grant API permissions for Azure Marketplace API
4. Note down tenant ID, client ID, and client secret

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "AZURE_MARKETPLACE",
  "name": "My Azure Marketplace",
  "config": {
    "tenant_id": "12345678-1234-1234-1234-123456789012",
    "client_id": "87654321-4321-4321-4321-210987654321",
    "client_secret": "your-client-secret",
    "subscription_id": "11111111-2222-3333-4444-555555555555",
    "resource_group": "marketplace-rg",
    "storage_account": "marketplacestorage"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Azure Marketplace-Specific Features

### Offer Publishing (PUSH)

When syncing assets to Azure Marketplace:

1. **Offer Creation**: Assets are published as Azure Marketplace offers
2. **Plan Configuration**: Creates plans for different pricing models
3. **Blob Storage**: Uploads asset resources to Azure Blob Storage
4. **Metadata Publishing**: Publishes asset metadata as offer metadata
5. **ODPS Integration**: Uses ODPS contracts for offer descriptions

### Offer Discovery (PULL)

When syncing from Azure Marketplace:

1. **Offer Discovery**: Lists available offers in the marketplace
2. **Subscription**: Subscribes to selected offers
3. **Blob Access**: Accesses data from Azure Blob Storage
4. **ODPS Generation**: Generates ODPS contracts from offer metadata

## Azure Marketplace-Specific Limitations

1. **Service Principal Requirements**: Requires Azure AD service principal
2. **Publisher Account**: PUSH operations require publisher account setup
3. **Certification Process**: Offers may require certification before publishing
4. **Blob Storage**: All data must be stored in Azure Blob Storage
5. **Region Constraints**: Operations are region-specific
6. **Subscription Model**: PULL operations require offer subscription
7. **Pricing Configuration**: Offers require pricing plan configuration

## Best Practices

1. **Service Principal Security**: Use managed identities when possible
2. **Resource Group Organization**: Use dedicated resource groups for marketplace
3. **Blob Storage Organization**: Use container prefixes for organization
4. **Role-Based Access**: Use least-privilege role assignments
5. **Cost Monitoring**: Monitor Azure storage and data transfer costs
6. **Offer Certification**: Understand certification requirements before publishing
7. **Metadata Quality**: Ensure complete metadata for offer discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify service principal credentials and permissions

**Issue**: PUSH sync fails with "Publisher account not found"
- **Solution**: Ensure publisher account is set up in Azure Marketplace

**Issue**: Blob upload fails
- **Solution**: Verify storage account exists and service principal has blob contributor role

**Issue**: Offer creation fails
- **Solution**: Check certification requirements and publisher account status

**Issue**: Subscription fails
- **Solution**: Verify subscription has necessary permissions and quotas

## Additional Resources

- [Azure Marketplace Documentation](https://docs.microsoft.com/azure/marketplace/)
- [Azure Marketplace Publisher Guide](https://docs.microsoft.com/azure/marketplace/marketplace-publishers-guide)
- [Azure Storage Documentation](https://docs.microsoft.com/azure/storage/)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### CKAN


## Overview

This guide covers integration with CKAN (Comprehensive Knowledge Archive Network) instances. CKAN is an open-source data management platform used by many government and organizational data portals.

## Marketplace Type

- **Type**: `CKAN_INSTANCE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "base_url": "https://data.example.com",
  "api_key": "your-ckan-api-key"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base_url` | string | Yes | Base URL of the CKAN instance (e.g., `https://data.example.com`) |
| `api_key` | string | Yes | CKAN API key for authentication |

### Optional Configuration

```json
{
  "base_url": "https://data.example.com",
  "api_key": "your-ckan-api-key",
  "instance_id": "optional-instance-identifier",
  "organization": "default-organization",
  "verify_ssl": true
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_id` | string | No | Optional identifier for this CKAN instance |
| `organization` | string | No | Default organization to publish datasets to |
| `verify_ssl` | boolean | No | Whether to verify SSL certificates (default: true) |

## Creating a CKAN Connection

### Step 1: Obtain API Key

1. Log in to your CKAN instance
2. Navigate to your user profile
3. Generate or copy your API key
4. Ensure the API key has permissions to:
   - Create/update datasets (for PUSH)
   - Read datasets (for PULL)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "CKAN_INSTANCE",
  "name": "My CKAN Data Portal",
  "config": {
    "base_url": "https://data.example.com",
    "api_key": "your-ckan-api-key",
    "organization": "my-organization"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## CKAN-Specific Features

### Dataset Publishing (PUSH)

When syncing assets to CKAN:

1. **Dataset Creation**: Assets are published as CKAN datasets
2. **Resource Mapping**: Hub asset resources are mapped to CKAN resources
3. **Metadata Mapping**: Asset metadata is mapped to CKAN dataset fields:
   - `title` → CKAN dataset title
   - `description` → CKAN dataset notes
   - `domain` → CKAN dataset groups/tags
   - `tags` → CKAN dataset tags

### Dataset Discovery (PULL)

When syncing from CKAN:

1. **Dataset Discovery**: Lists datasets from the CKAN instance
2. **Resource Download**: Downloads resources from CKAN datasets
3. **Metadata Extraction**: Extracts CKAN metadata to Hub asset format

## CKAN-Specific Limitations

1. **Organization Requirements**: Some CKAN instances require datasets to belong to an organization
2. **Resource Formats**: CKAN supports various formats, but some may require conversion
3. **File Size Limits**: CKAN instances may have file size limits for resource uploads
4. **API Rate Limits**: CKAN instances may enforce rate limits on API calls
5. **Authentication**: API key must have sufficient permissions for desired operations

## Best Practices

1. **Use Organizations**: Specify an organization in config for better dataset organization
2. **Verify Permissions**: Ensure API key has create/read permissions before syncing
3. **Handle Large Files**: For large resources, consider using external URLs instead of direct uploads
4. **Monitor Rate Limits**: Be aware of CKAN instance rate limits when syncing many assets
5. **Test with Small Datasets**: Start with small datasets to validate the connection

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Unauthorized"
- **Solution**: Verify API key is correct and has necessary permissions

**Issue**: PUSH sync fails with "Organization not found"
- **Solution**: Ensure the organization exists in CKAN or remove organization from config

**Issue**: Resource upload fails
- **Solution**: Check file size limits and resource format compatibility

**Issue**: PULL sync returns no datasets
- **Solution**: Verify API key has read permissions and check organization filters

## Additional Resources

- [CKAN API Documentation](https://docs.ckan.org/en/latest/api/)
- [CKAN DataStore API](https://docs.ckan.org/en/latest/maintaining/datastore.html)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### COLLIBRA


## Overview

This guide covers integration with Collibra Data Marketplace, a platform for discovering and accessing data products within the Collibra Data Intelligence Cloud ecosystem.

## Marketplace Type

- **Type**: `COLLIBRA_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Collibra API Token / OAuth 2.0

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://your-instance.collibra.com",
  "username": "your-collibra-username",
  "password": "your-collibra-password"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | Collibra API endpoint (e.g., `https://your-instance.collibra.com`) |
| `username` | string | Yes | Collibra username |
| `password` | string | Yes | Collibra password |

### Optional Configuration

```json
{
  "api_endpoint": "https://your-instance.collibra.com",
  "username": "your-collibra-username",
  "password": "your-collibra-password",
  "api_token": "optional-api-token",
  "community_id": "your-community-id"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_token` | string | No | Collibra API token (alternative to username/password) |
| `community_id` | string | No | Collibra community ID |

## Creating a Collibra Data Marketplace Connection

### Step 1: Prepare Collibra Account

1. Ensure you have a Collibra Data Intelligence Cloud account
2. Generate API token (optional):
   - Go to User Settings → API Tokens
   - Generate new token
   - Note down the token
3. Note your community ID (if applicable)
4. Ensure user has necessary permissions:
   - Data Marketplace Admin
   - API access enabled

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "COLLIBRA_DATA_MARKETPLACE",
  "name": "My Collibra Data Marketplace",
  "config": {
    "api_endpoint": "https://your-instance.collibra.com",
    "username": "your-collibra-username",
    "password": "your-collibra-password",
    "community_id": "your-community-id"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Collibra Data Marketplace-Specific Features

### Asset Publishing (PUSH)

When syncing assets to Collibra:

1. **Asset Creation**: Assets are published as Collibra data assets
2. **Metadata Publishing**: Asset metadata is published with data governance information
3. **ODPS Integration**: Uses ODPS contracts for asset descriptions
4. **Data Governance**: Integrates with Collibra data governance framework

### Asset Discovery (PULL)

When syncing from Collibra:

1. **Asset Discovery**: Lists available data assets in the marketplace
2. **Subscription**: Subscribes to selected assets
3. **Data Access**: Accesses data assets via Collibra
4. **ODPS Generation**: Generates ODPS contracts from asset metadata

## Collibra Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires Collibra Data Intelligence Cloud account
2. **Data Governance**: Requires understanding of Collibra data governance model
3. **Community Scope**: Assets may be community-scoped
4. **API Token Management**: API tokens must be managed securely
5. **Subscription Model**: PULL operations require asset subscription
6. **Governance Integration**: Requires integration with Collibra governance framework

## Best Practices

1. **API Token Security**: Store API tokens securely
2. **Community Management**: Use community ID for proper scoping
3. **Data Governance**: Understand Collibra data governance model
4. **Metadata Quality**: Ensure complete metadata with governance information
5. **Governance Integration**: Integrate with Collibra governance workflows

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify username and password are correct, or use API token

**Issue**: PUSH sync fails with "Community not found"
- **Solution**: Ensure community ID is correct or remove from config

**Issue**: Asset creation fails
- **Solution**: Check asset requirements and data governance permissions

**Issue**: Governance integration errors
- **Solution**: Verify governance framework configuration

## Additional Resources

- [Collibra Data Marketplace Documentation](https://documentation.collibra.com/data-marketplace)
- [Collibra API Documentation](https://developer.collibra.com/)
- [Collibra Data Governance Documentation](https://documentation.collibra.com/data-governance)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### DATABRICKS


## Overview

This guide covers integration with Databricks Marketplace, a platform for discovering and sharing data products within the Databricks ecosystem.

## Marketplace Type

- **Type**: `DATABRICKS_MARKETPLACE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: Databricks Personal Access Token

## Connection Configuration

### Required Configuration Parameters

```json
{
  "workspace_url": "https://your-workspace.cloud.databricks.com",
  "personal_access_token": "your-databricks-token"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workspace_url` | string | Yes | Databricks workspace URL (e.g., `https://your-workspace.cloud.databricks.com`) |
| `personal_access_token` | string | Yes | Databricks personal access token |

### Optional Configuration

```json
{
  "workspace_url": "https://your-workspace.cloud.databricks.com",
  "personal_access_token": "your-databricks-token",
  "catalog": "marketplace_catalog",
  "schema": "marketplace_schema",
  "cluster_id": "optional-cluster-id"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `catalog` | string | No | Unity Catalog catalog name for marketplace data |
| `schema` | string | No | Unity Catalog schema name (default: `default`) |
| `cluster_id` | string | No | Databricks cluster ID for operations (optional) |

## Creating a Databricks Marketplace Connection

### Step 1: Prepare Databricks Workspace

1. Ensure you have a Databricks workspace with Marketplace access
2. Create personal access token:
   - Go to User Settings → Access Tokens
   - Generate new token with appropriate permissions
   - Note down the token (it won't be shown again)
3. Ensure workspace has Unity Catalog enabled (recommended)
4. Create catalog and schema for marketplace data (optional)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "DATABRICKS_MARKETPLACE",
  "name": "My Databricks Marketplace",
  "config": {
    "workspace_url": "https://your-workspace.cloud.databricks.com",
    "personal_access_token": "dapi1234567890abcdef",
    "catalog": "marketplace_catalog",
    "schema": "marketplace_schema"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Databricks Marketplace-Specific Features

### Listing Publishing (PUSH)

When syncing assets to Databricks:

1. **Delta Table Creation**: Assets are published as Delta tables
2. **Unity Catalog Integration**: Tables are registered in Unity Catalog
3. **Metadata Publishing**: Asset metadata is published as listing metadata
4. **ODPS Integration**: Uses ODPS contracts for listing descriptions
5. **Sharing**: Shares Delta tables via Databricks sharing

### Listing Discovery (PULL)

When syncing from Databricks:

1. **Listing Discovery**: Lists available listings in the marketplace
2. **Delta Table Access**: Accesses shared Delta tables
3. **Schema Extraction**: Extracts table schemas from Delta tables
4. **ODPS Generation**: Generates ODPS contracts from listing metadata

## Databricks Marketplace-Specific Limitations

1. **Workspace Requirements**: Requires Databricks workspace with Marketplace access
2. **Unity Catalog**: Unity Catalog is recommended for table management
3. **Delta Format**: Only Delta format is supported for tabular data
4. **Cluster Requirements**: Some operations may require running cluster
5. **Sharing Permissions**: PUSH operations require sharing permissions
6. **Region Constraints**: Workspace region affects data locality
7. **Compute Costs**: Querying Delta tables incurs compute costs

## Best Practices

1. **Unity Catalog**: Use Unity Catalog for better table organization
2. **Token Security**: Store personal access tokens securely
3. **Delta Optimization**: Use Delta table optimization for better performance
4. **Schema Organization**: Organize tables in dedicated catalogs/schemas
5. **Cost Monitoring**: Monitor compute costs when querying marketplace data
6. **Metadata Quality**: Ensure complete metadata for discoverability
7. **Sharing Configuration**: Configure sharing settings appropriately

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid token"
- **Solution**: Verify personal access token is correct and not expired

**Issue**: PUSH sync fails with "Catalog not found"
- **Solution**: Ensure catalog exists in Unity Catalog or remove catalog from config

**Issue**: Delta table creation fails
- **Solution**: Verify workspace has Unity Catalog enabled and necessary permissions

**Issue**: Sharing fails
- **Solution**: Ensure workspace has sharing enabled and you have sharing permissions

**Issue**: PULL sync fails with "Table not accessible"
- **Solution**: Verify you have access to the shared Delta table

## Additional Resources

- [Databricks Marketplace Documentation](https://docs.databricks.com/marketplace/)
- [Databricks Unity Catalog Documentation](https://docs.databricks.com/data-governance/unity-catalog/)
- [Databricks Delta Tables Documentation](https://docs.databricks.com/delta/)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### DATARADE


## Overview

This guide covers integration with DataRade, a data marketplace platform for discovering and trading data products.

## Marketplace Type

- **Type**: `DATARADE_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: DataRade API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://api.datarade.com",
  "api_key": "your-datarade-api-key"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | DataRade API endpoint (default: `https://api.datarade.com`) |
| `api_key` | string | Yes | DataRade API key |

### Optional Configuration

```json
{
  "api_endpoint": "https://api.datarade.com",
  "api_key": "your-datarade-api-key",
  "organization_id": "your-organization-id",
  "environment": "production"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `organization_id` | string | No | DataRade organization ID |
| `environment` | string | No | Environment (production, sandbox) |

## Creating a DataRade Connection

### Step 1: Prepare DataRade Account

1. Ensure you have a DataRade account with API access
2. Generate API key:
   - Go to Account Settings → API Keys
   - Generate new API key
   - Note down the API key
3. Note your organization ID (if applicable)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "DATARADE_MARKETPLACE",
  "name": "My DataRade Marketplace",
  "config": {
    "api_endpoint": "https://api.datarade.com",
    "api_key": "your-datarade-api-key",
    "organization_id": "your-organization-id"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## DataRade-Specific Features

### Product Publishing (PUSH)

When syncing assets to DataRade:

1. **Product Creation**: Assets are published as DataRade products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **Pricing Configuration**: Supports various pricing models

### Product Discovery (PULL)

When syncing from DataRade:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Data Access**: Accesses product data
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## DataRade-Specific Limitations

1. **Account Requirements**: Requires DataRade account with API access
2. **API Key Management**: API keys must be managed securely
3. **Organization Scope**: Products may be organization-scoped
4. **Pricing Models**: Supports specific pricing models
5. **Subscription Model**: PULL operations require product subscription

## Best Practices

1. **API Key Security**: Store API keys securely
2. **Organization Management**: Use organization ID for better organization
3. **Metadata Quality**: Ensure complete metadata for discoverability
4. **Pricing Configuration**: Configure appropriate pricing models

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid API key"
- **Solution**: Verify API key is correct and has necessary permissions

**Issue**: PUSH sync fails with "Organization not found"
- **Solution**: Ensure organization ID is correct or remove from config

**Issue**: Product creation fails
- **Solution**: Check product requirements and account permissions

## Additional Resources

- [DataRade API Documentation](https://docs.datarade.com/api)
- [DataRade Marketplace Documentation](https://docs.datarade.com/marketplace)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### DAWEX


## Overview

This guide covers integration with Dawex, a data exchange platform for discovering and trading data products.

## Marketplace Type

- **Type**: `DAWEX_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Dawex API Key / OAuth 2.0

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://api.dawex.com",
  "api_key": "your-dawex-api-key",
  "organization_id": "your-organization-id"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | Dawex API endpoint (default: `https://api.dawex.com`) |
| `api_key` | string | Yes | Dawex API key |
| `organization_id` | string | Yes | Dawex organization ID |

### Optional Configuration

```json
{
  "api_endpoint": "https://api.dawex.com",
  "api_key": "your-dawex-api-key",
  "organization_id": "your-organization-id",
  "environment": "production",
  "region": "eu-west"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `environment` | string | No | Environment (production, sandbox) |
| `region` | string | No | Dawex region |

## Creating a Dawex Connection

### Step 1: Prepare Dawex Account

1. Ensure you have a Dawex account with API access
2. Generate API key:
   - Go to Account Settings → API Keys
   - Generate new API key
   - Note down the API key
3. Note your organization ID

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "DAWEX_MARKETPLACE",
  "name": "My Dawex Marketplace",
  "config": {
    "api_endpoint": "https://api.dawex.com",
    "api_key": "your-dawex-api-key",
    "organization_id": "your-organization-id",
    "environment": "production"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Dawex-Specific Features

### Product Publishing (PUSH)

When syncing assets to Dawex:

1. **Product Creation**: Assets are published as Dawex products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **Data Exchange**: Supports Dawex data exchange protocols

### Product Discovery (PULL)

When syncing from Dawex:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Data Access**: Accesses product data via Dawex protocols
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## Dawex-Specific Limitations

1. **Account Requirements**: Requires Dawex account with API access
2. **Organization Scope**: Products are organization-scoped
3. **API Key Management**: API keys must be managed securely
4. **Data Exchange Protocols**: Requires understanding of Dawex protocols
5. **Subscription Model**: PULL operations require product subscription

## Best Practices

1. **API Key Security**: Store API keys securely
2. **Organization Management**: Use organization ID for proper scoping
3. **Metadata Quality**: Ensure complete metadata for discoverability
4. **Protocol Understanding**: Understand Dawex data exchange protocols

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid API key"
- **Solution**: Verify API key is correct and has necessary permissions

**Issue**: PUSH sync fails with "Organization not found"
- **Solution**: Ensure organization ID is correct

**Issue**: Product creation fails
- **Solution**: Check product requirements and account permissions

## Additional Resources

- [Dawex API Documentation](https://docs.dawex.com/api)
- [Dawex Marketplace Documentation](https://docs.dawex.com/marketplace)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### ESRI


## Overview

This guide covers integration with Esri Marketplace (ArcGIS Marketplace), a platform for discovering and accessing geospatial data products and services.

## Marketplace Type

- **Type**: `ESRI_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Esri OAuth 2.0 / API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "portal_url": "https://your-organization.maps.arcgis.com",
  "client_id": "your-esri-client-id",
  "client_secret": "your-esri-client-secret"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `portal_url` | string | Yes | Esri Portal URL (e.g., `https://your-org.maps.arcgis.com`) |
| `client_id` | string | Yes | Esri OAuth client ID |
| `client_secret` | string | Yes | Esri OAuth client secret |

### Optional Configuration

```json
{
  "portal_url": "https://your-organization.maps.arcgis.com",
  "client_id": "your-esri-client-id",
  "client_secret": "your-esri-client-secret",
  "organization_id": "your-organization-id",
  "api_key": "optional-api-key"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `organization_id` | string | No | Esri organization ID |
| `api_key` | string | No | Esri API key (for some operations) |

## Creating an Esri Marketplace Connection

### Step 1: Prepare Esri Account

1. Ensure you have an Esri account with Marketplace access
2. Register application in Esri Developer Portal:
   - Go to https://developers.arcgis.com
   - Create new application
   - Configure OAuth redirect URLs
   - Note down client ID and client secret
3. Note your organization ID (if applicable)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "ESRI_MARKETPLACE",
  "name": "My Esri Marketplace",
  "config": {
    "portal_url": "https://your-organization.maps.arcgis.com",
    "client_id": "your-esri-client-id",
    "client_secret": "your-esri-client-secret",
    "organization_id": "your-organization-id"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Esri Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to Esri:

1. **Item Creation**: Assets are published as Esri items (layers, services, etc.)
2. **Geospatial Metadata**: Asset metadata is published with geospatial information
3. **ODPS Integration**: Uses ODPS contracts for item descriptions
4. **ArcGIS Integration**: Integrates with ArcGIS Online/Enterprise

### Product Discovery (PULL)

When syncing from Esri:

1. **Item Discovery**: Lists available items in the marketplace
2. **Subscription**: Subscribes to selected items
3. **Geospatial Access**: Accesses geospatial data and services
4. **ODPS Generation**: Generates ODPS contracts from item metadata

## Esri Marketplace-Specific Limitations

1. **Account Requirements**: Requires Esri account with Marketplace access
2. **Geospatial Formats**: Requires understanding of geospatial data formats (GeoJSON, Shapefile, etc.)
3. **Portal Requirements**: Requires ArcGIS Online or Enterprise portal
4. **Coordinate Systems**: Must handle various coordinate reference systems
5. **Subscription Model**: PULL operations require item subscription
6. **Service Types**: Supports various service types (Feature Services, Map Services, etc.)

## Best Practices

1. **Geospatial Standards**: Understand geospatial data standards (OGC, ISO)
2. **Coordinate Systems**: Handle coordinate reference system transformations
3. **Service Types**: Understand different ArcGIS service types
4. **Metadata Quality**: Ensure complete geospatial metadata
5. **Portal Configuration**: Configure portal settings appropriately

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify client ID and client secret are correct

**Issue**: PUSH sync fails with "Organization not found"
- **Solution**: Ensure organization ID is correct or remove from config

**Issue**: Geospatial data format errors
- **Solution**: Verify geospatial data formats are compatible with Esri

**Issue**: Service creation fails
- **Solution**: Check service type requirements and portal permissions

## Additional Resources

- [Esri ArcGIS Marketplace Documentation](https://doc.arcgis.com/en/marketplace/)
- [Esri REST API Documentation](https://developers.arcgis.com/rest/)
- [Esri OAuth Documentation](https://developers.arcgis.com/documentation/mapping-apis-and-services/security/oauth-2.0/)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### GCP


## Overview

This guide covers integration with Google Cloud Platform (GCP) Marketplace, a platform for discovering and deploying data products and services on GCP.

## Marketplace Type

- **Type**: `GOOGLE_CLOUD_MARKETPLACE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: GCP Service Account

## Connection Configuration

### Required Configuration Parameters

```json
{
  "project_id": "your-gcp-project-id",
  "service_account_key": {
    "type": "service_account",
    "project_id": "your-gcp-project-id",
    "private_key_id": "key-id",
    "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
    "client_email": "service-account@project.iam.gserviceaccount.com",
    "client_id": "client-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  }
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | string | Yes | GCP project ID |
| `service_account_key` | object | Yes | Service account key JSON (can be file path or JSON object) |

### Optional Configuration

```json
{
  "project_id": "your-gcp-project-id",
  "service_account_key": {...},
  "bucket_name": "marketplace-data-bucket",
  "dataset_id": "marketplace_dataset",
  "location": "us-central1"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `bucket_name` | string | No | GCS bucket for storing data files |
| `dataset_id` | string | No | BigQuery dataset ID for tabular data |
| `location` | string | No | GCP region (default: `us-central1`) |

## Creating a GCP Marketplace Connection

### Step 1: Prepare GCP Service Account

1. Create GCP service account in your project
2. Grant necessary roles:
   - `roles/marketplace.publisher` (for PUSH)
   - `roles/storage.objectAdmin` (for Cloud Storage)
   - `roles/bigquery.dataEditor` (for BigQuery)
   - `roles/marketplace.viewer` (for PULL)
3. Create and download service account key (JSON)
4. Enable required APIs:
   - Cloud Marketplace API
   - Cloud Storage API
   - BigQuery API

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "GOOGLE_CLOUD_MARKETPLACE",
  "name": "My GCP Marketplace",
  "config": {
    "project_id": "my-gcp-project",
    "service_account_key": {
      "type": "service_account",
      "project_id": "my-gcp-project",
      "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
      "client_email": "marketplace@my-gcp-project.iam.gserviceaccount.com"
    },
    "bucket_name": "marketplace-data-bucket",
    "dataset_id": "marketplace_dataset"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## GCP Marketplace-Specific Features

### Listing Publishing (PUSH)

When syncing assets to GCP Marketplace:

1. **Listing Creation**: Assets are published as GCP Marketplace listings
2. **Cloud Storage Upload**: Uploads asset resources to GCS buckets
3. **BigQuery Integration**: For tabular data, creates BigQuery tables
4. **Metadata Publishing**: Publishes asset metadata as listing metadata
5. **ODPS Integration**: Uses ODPS contracts for listing descriptions

### Listing Discovery (PULL)

When syncing from GCP Marketplace:

1. **Listing Discovery**: Lists available listings in the marketplace
2. **Deployment**: Deploys selected listings to your project
3. **GCS Access**: Accesses data from Cloud Storage buckets
4. **BigQuery Access**: Accesses data from BigQuery datasets
5. **ODPS Generation**: Generates ODPS contracts from listing metadata

## GCP Marketplace-Specific Limitations

1. **Service Account Requirements**: Requires GCP service account with JSON key
2. **Publisher Account**: PUSH operations require publisher account setup
3. **API Enablement**: Requires Cloud Marketplace API to be enabled
4. **Storage Dependencies**: Data must be stored in Cloud Storage or BigQuery
5. **Region Constraints**: Operations are region-specific
6. **Deployment Model**: PULL operations require listing deployment
7. **BigQuery Schema**: Tabular data requires compatible BigQuery schemas

## Best Practices

1. **Service Account Security**: Use least-privilege IAM roles
2. **Bucket Organization**: Use bucket prefixes for organization
3. **BigQuery Optimization**: Use appropriate partitioning and clustering
4. **Cost Monitoring**: Monitor GCS storage and BigQuery query costs
5. **Listing Certification**: Understand certification requirements
6. **Metadata Quality**: Ensure complete metadata for discoverability
7. **Schema Compatibility**: Verify BigQuery schema compatibility

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid service account"
- **Solution**: Verify service account key JSON is correct and valid

**Issue**: PUSH sync fails with "Publisher account not found"
- **Solution**: Ensure publisher account is set up in GCP Marketplace

**Issue**: GCS upload fails
- **Solution**: Verify bucket exists and service account has storage.objectAdmin role

**Issue**: BigQuery table creation fails
- **Solution**: Check dataset exists and service account has bigquery.dataEditor role

**Issue**: Listing deployment fails
- **Solution**: Verify project has necessary quotas and APIs enabled

## Additional Resources

- [GCP Marketplace Documentation](https://cloud.google.com/marketplace/docs)
- [GCP Marketplace Publisher Guide](https://cloud.google.com/marketplace/docs/partners/)
- [Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### IBM


## Overview

This guide covers integration with IBM Data Marketplace, a platform for discovering and accessing data products within the IBM ecosystem.

## Marketplace Type

- **Type**: `IBM_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: IBM Cloud API Key / IAM Token

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_key": "your-ibm-cloud-api-key",
  "region": "us-south",
  "resource_group": "default"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_key` | string | Yes | IBM Cloud API key |
| `region` | string | Yes | IBM Cloud region (e.g., `us-south`) |
| `resource_group` | string | Yes | IBM Cloud resource group |

### Optional Configuration

```json
{
  "api_key": "your-ibm-cloud-api-key",
  "region": "us-south",
  "resource_group": "default",
  "cos_bucket": "marketplace-data-bucket",
  "cos_endpoint": "s3.us-south.cloud-object-storage.appdomain.cloud"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cos_bucket` | string | No | Cloud Object Storage bucket name |
| `cos_endpoint` | string | No | Cloud Object Storage endpoint |

## Creating an IBM Data Marketplace Connection

### Step 1: Prepare IBM Cloud Account

1. Ensure you have an IBM Cloud account with Data Marketplace access
2. Create API key in IBM Cloud:
   - Go to Manage → Access (IAM) → API Keys
   - Create new API key
   - Note down the API key
3. Create resource group for marketplace resources
4. Create Cloud Object Storage instance (if needed)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "IBM_DATA_MARKETPLACE",
  "name": "My IBM Data Marketplace",
  "config": {
    "api_key": "your-ibm-cloud-api-key",
    "region": "us-south",
    "resource_group": "default",
    "cos_bucket": "marketplace-data-bucket"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## IBM Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to IBM:

1. **Product Creation**: Assets are published as IBM Data Marketplace products
2. **Cloud Object Storage**: Uploads asset resources to IBM COS
3. **Metadata Publishing**: Asset metadata is published as product metadata
4. **ODPS Integration**: Uses ODPS contracts for product descriptions

### Product Discovery (PULL)

When syncing from IBM:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **COS Access**: Accesses data from Cloud Object Storage
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## IBM Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires IBM Cloud account with Data Marketplace access
2. **API Key Management**: API keys must be managed securely
3. **Cloud Object Storage**: Data must be stored in IBM COS
4. **Region Constraints**: Operations are region-specific
5. **Subscription Model**: PULL operations require product subscription
6. **Resource Group**: Resources must belong to a resource group

## Best Practices

1. **API Key Security**: Store API keys securely and rotate regularly
2. **Resource Group Organization**: Use dedicated resource groups
3. **COS Organization**: Use bucket prefixes for organization
4. **Cost Monitoring**: Monitor COS storage and data transfer costs
5. **Metadata Quality**: Ensure complete metadata for discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid API key"
- **Solution**: Verify IBM Cloud API key is correct and has necessary permissions

**Issue**: PUSH sync fails with "Resource group not found"
- **Solution**: Ensure resource group exists in IBM Cloud

**Issue**: COS upload fails
- **Solution**: Verify COS bucket exists and API key has object storage permissions

## Additional Resources

- [IBM Data Marketplace Documentation](https://www.ibm.com/docs/en/data-marketplace)
- [IBM Cloud Object Storage Documentation](https://cloud.ibm.com/docs/cloud-object-storage)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### NASDAQ


## Overview

This guide covers integration with NASDAQ Data Marketplace, a platform for discovering and accessing financial and market data products.

## Marketplace Type

- **Type**: `NASDAQ_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: NASDAQ API Key / OAuth 2.0

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://api.nasdaq.com/data-marketplace",
  "api_key": "your-nasdaq-api-key",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | NASDAQ Data Marketplace API endpoint |
| `api_key` | string | Yes | NASDAQ API key |
| `client_id` | string | Yes | OAuth client ID |
| `client_secret` | string | Yes | OAuth client secret |

### Optional Configuration

```json
{
  "api_endpoint": "https://api.nasdaq.com/data-marketplace",
  "api_key": "your-nasdaq-api-key",
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "environment": "production",
  "data_feed": "equities"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `environment` | string | No | Environment (production, sandbox) |
| `data_feed` | string | No | Data feed type (equities, options, etc.) |

## Creating a NASDAQ Data Marketplace Connection

### Step 1: Prepare NASDAQ Account

1. Ensure you have a NASDAQ Data Marketplace account
2. Register for API access:
   - Go to Developer Portal
   - Create application
   - Generate API key and OAuth credentials
3. Note down API key, client ID, and client secret

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "NASDAQ_DATA_MARKETPLACE",
  "name": "My NASDAQ Data Marketplace",
  "config": {
    "api_endpoint": "https://api.nasdaq.com/data-marketplace",
    "api_key": "your-nasdaq-api-key",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "environment": "production"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## NASDAQ Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to NASDAQ:

1. **Product Creation**: Assets are published as NASDAQ data products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **Financial Data Standards**: Supports financial data standards (FIX, FpML, etc.)

### Product Discovery (PULL)

When syncing from NASDAQ:

1. **Product Discovery**: Lists available data products in the marketplace
2. **Subscription**: Subscribes to selected data feeds
3. **Data Access**: Accesses financial data via NASDAQ protocols
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## NASDAQ Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires NASDAQ Data Marketplace account
2. **Financial Data Standards**: Requires understanding of financial data formats
3. **Real-time Data**: Real-time data may require special subscriptions
4. **API Rate Limits**: NASDAQ enforces rate limits on API calls
5. **Subscription Model**: PULL operations require data feed subscription
6. **Compliance**: Financial data may have compliance requirements

## Best Practices

1. **API Key Security**: Store API keys securely
2. **Financial Standards**: Understand financial data standards (FIX, FpML)
3. **Rate Limiting**: Implement rate limiting and retry logic
4. **Compliance**: Ensure compliance with financial data regulations
5. **Metadata Quality**: Ensure complete metadata for discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify API key, client ID, and client secret are correct

**Issue**: PUSH sync fails with "Product creation failed"
- **Solution**: Check product requirements and financial data standards

**Issue**: Rate limit errors
- **Solution**: Implement rate limiting and retry with exponential backoff

**Issue**: Subscription fails
- **Solution**: Verify subscription has necessary permissions and quotas

## Additional Resources

- [NASDAQ Data Marketplace Documentation](https://www.nasdaq.com/docs/data-marketplace)
- [NASDAQ API Documentation](https://developer.nasdaq.com)
- [Financial Data Standards](https://www.fixprotocol.org)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### ORACLE


## Overview

This guide covers integration with Oracle Data Marketplace, a platform for discovering and accessing data products within the Oracle Cloud ecosystem.

## Marketplace Type

- **Type**: `ORACLE_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Oracle Cloud Infrastructure (OCI) API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "tenancy_ocid": "ocid1.tenancy.oc1..your-tenancy-ocid",
  "user_ocid": "ocid1.user.oc1..your-user-ocid",
  "fingerprint": "your-api-key-fingerprint",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "region": "us-ashburn-1"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tenancy_ocid` | string | Yes | OCI tenancy OCID |
| `user_ocid` | string | Yes | OCI user OCID |
| `fingerprint` | string | Yes | API key fingerprint |
| `private_key` | string | Yes | RSA private key (PEM format) |
| `region` | string | Yes | OCI region (e.g., `us-ashburn-1`) |

### Optional Configuration

```json
{
  "tenancy_ocid": "ocid1.tenancy.oc1..your-tenancy-ocid",
  "user_ocid": "ocid1.user.oc1..your-user-ocid",
  "fingerprint": "your-api-key-fingerprint",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "region": "us-ashburn-1",
  "compartment_id": "ocid1.compartment.oc1..your-compartment-ocid",
  "bucket_name": "marketplace-data-bucket"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `compartment_id` | string | No | OCI compartment OCID |
| `bucket_name` | string | No | Object Storage bucket name |

## Creating an Oracle Data Marketplace Connection

### Step 1: Prepare OCI Account

1. Ensure you have an OCI account with Data Marketplace access
2. Create API key:
   - Go to Identity → Users → Your User → API Keys
   - Add API key and download private key
   - Note down fingerprint
3. Create compartment for marketplace resources (optional)
4. Create Object Storage bucket (if needed)
5. Ensure user has necessary IAM policies:
   - `Allow group DataMarketplaceAdmins to manage data-marketplace-products`
   - `Allow group DataMarketplaceAdmins to manage object-family`

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "ORACLE_DATA_MARKETPLACE",
  "name": "My Oracle Data Marketplace",
  "config": {
    "tenancy_ocid": "ocid1.tenancy.oc1..your-tenancy-ocid",
    "user_ocid": "ocid1.user.oc1..your-user-ocid",
    "fingerprint": "aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
    "region": "us-ashburn-1",
    "compartment_id": "ocid1.compartment.oc1..your-compartment-ocid"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Oracle Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to Oracle:

1. **Product Creation**: Assets are published as Oracle Data Marketplace products
2. **Object Storage**: Uploads asset resources to OCI Object Storage
3. **Metadata Publishing**: Asset metadata is published as product metadata
4. **ODPS Integration**: Uses ODPS contracts for product descriptions

### Product Discovery (PULL)

When syncing from Oracle:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Object Storage Access**: Accesses data from OCI Object Storage
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## Oracle Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires OCI account with Data Marketplace access
2. **API Key Management**: RSA private keys must be managed securely
3. **Object Storage**: Data must be stored in OCI Object Storage
4. **Region Constraints**: Operations are region-specific
5. **Compartment Organization**: Resources must belong to a compartment
6. **Subscription Model**: PULL operations require product subscription
7. **IAM Policies**: Requires specific IAM policies for marketplace operations

## Best Practices

1. **Private Key Security**: Store RSA private keys securely (encrypted)
2. **Compartment Organization**: Use dedicated compartments for marketplace
3. **Object Storage Organization**: Use bucket prefixes for organization
4. **IAM Policies**: Use least-privilege IAM policies
5. **Cost Monitoring**: Monitor Object Storage and data transfer costs
6. **Metadata Quality**: Ensure complete metadata for discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify OCIDs, fingerprint, and private key are correct

**Issue**: PUSH sync fails with "Compartment not found"
- **Solution**: Ensure compartment exists and user has access

**Issue**: Object Storage upload fails
- **Solution**: Verify bucket exists and IAM policies allow object-family operations

**Issue**: Product creation fails
- **Solution**: Check IAM policies for data-marketplace-products permissions

## Additional Resources

- [Oracle Data Marketplace Documentation](https://docs.oracle.com/en/cloud/paas/data-marketplace/)
- [OCI Object Storage Documentation](https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm)
- [OCI IAM Documentation](https://docs.oracle.com/en-us/iaas/Content/Identity/Concepts/overview.htm)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### SALESFORCE


## Overview

This guide covers integration with Salesforce Data Marketplace, a platform for discovering and accessing data products within the Salesforce ecosystem.

## Marketplace Type

- **Type**: `SALESFORCE_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: Salesforce OAuth 2.0

## Connection Configuration

### Required Configuration Parameters

```json
{
  "instance_url": "https://your-instance.salesforce.com",
  "client_id": "your-salesforce-client-id",
  "client_secret": "your-salesforce-client-secret",
  "username": "your-salesforce-username",
  "password": "your-salesforce-password",
  "security_token": "your-security-token"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `instance_url` | string | Yes | Salesforce instance URL |
| `client_id` | string | Yes | Connected App client ID |
| `client_secret` | string | Yes | Connected App client secret |
| `username` | string | Yes | Salesforce username |
| `password` | string | Yes | Salesforce password |
| `security_token` | string | Yes | Salesforce security token |

### Optional Configuration

```json
{
  "instance_url": "https://your-instance.salesforce.com",
  "client_id": "your-salesforce-client-id",
  "client_secret": "your-salesforce-client-secret",
  "username": "your-salesforce-username",
  "password": "your-salesforce-password",
  "security_token": "your-security-token",
  "api_version": "58.0",
  "sandbox": false
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_version` | string | No | Salesforce API version (default: latest) |
| `sandbox` | boolean | No | Whether using Salesforce sandbox (default: false) |

## Creating a Salesforce Data Marketplace Connection

### Step 1: Prepare Salesforce Account

1. Ensure you have a Salesforce account with Data Marketplace access
2. Create Connected App:
   - Setup → App Manager → New Connected App
   - Enable OAuth Settings
   - Set callback URL
   - Note down client ID and client secret
3. Get security token:
   - Setup → My Personal Information → Reset My Security Token
4. Ensure user has necessary permissions:
   - Data Marketplace Admin
   - API access enabled

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "SALESFORCE_DATA_MARKETPLACE",
  "name": "My Salesforce Data Marketplace",
  "config": {
    "instance_url": "https://your-instance.salesforce.com",
    "client_id": "your-salesforce-client-id",
    "client_secret": "your-salesforce-client-secret",
    "username": "your-salesforce-username",
    "password": "your-salesforce-password",
    "security_token": "your-security-token",
    "api_version": "58.0"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Salesforce Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to Salesforce:

1. **Product Creation**: Assets are published as Salesforce Data Marketplace products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **Salesforce Integration**: Integrates with Salesforce Data Cloud

### Product Discovery (PULL)

When syncing from Salesforce:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Data Access**: Accesses data via Salesforce Data Cloud
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## Salesforce Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires Salesforce account with Data Marketplace access
2. **OAuth Setup**: Requires Connected App configuration
3. **Security Token**: Security token is required for authentication
4. **API Version**: API version compatibility must be maintained
5. **Subscription Model**: PULL operations require product subscription
6. **Data Cloud Integration**: Requires Salesforce Data Cloud for data delivery

## Best Practices

1. **Security Token Management**: Store security tokens securely
2. **Connected App Configuration**: Use appropriate OAuth scopes
3. **API Version**: Keep API version up to date
4. **Metadata Quality**: Ensure complete metadata for discoverability
5. **Data Cloud Integration**: Understand Data Cloud integration requirements

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify username, password, and security token are correct

**Issue**: OAuth authentication fails
- **Solution**: Check Connected App configuration and callback URL

**Issue**: PUSH sync fails with "Insufficient permissions"
- **Solution**: Ensure user has Data Marketplace Admin permissions

**Issue**: API version errors
- **Solution**: Update API version in configuration

## Additional Resources

- [Salesforce Data Marketplace Documentation](https://help.salesforce.com/s/articleView?id=sf.data_marketplace.htm)
- [Salesforce Data Cloud Documentation](https://help.salesforce.com/s/articleView?id=sf.data_cloud.htm)
- [Salesforce Connected Apps Documentation](https://help.salesforce.com/s/articleView?id=sf.connected_app_overview.htm)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### SAP


## Overview

This guide covers integration with SAP Data Marketplace, a platform for discovering and accessing data products within the SAP ecosystem.

## Marketplace Type

- **Type**: `SAP_DATA_MARKETPLACE` (Note: May need to be added to MarketplaceType enum)
- **Supported Operations**: PUSH, PULL
- **Authentication**: SAP OAuth 2.0 / API Key

## Connection Configuration

### Required Configuration Parameters

```json
{
  "api_endpoint": "https://api.sap.com/data-marketplace",
  "client_id": "your-sap-client-id",
  "client_secret": "your-sap-client-secret",
  "tenant_id": "your-sap-tenant-id"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `api_endpoint` | string | Yes | SAP Data Marketplace API endpoint |
| `client_id` | string | Yes | SAP OAuth client ID |
| `client_secret` | string | Yes | SAP OAuth client secret |
| `tenant_id` | string | Yes | SAP tenant ID |

### Optional Configuration

```json
{
  "api_endpoint": "https://api.sap.com/data-marketplace",
  "client_id": "your-sap-client-id",
  "client_secret": "your-sap-client-secret",
  "tenant_id": "your-sap-tenant-id",
  "environment": "production",
  "region": "us-east"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `environment` | string | No | SAP environment (production, sandbox) |
| `region` | string | No | SAP region (default: us-east) |

## Creating an SAP Data Marketplace Connection

### Step 1: Prepare SAP Account

1. Ensure you have an SAP account with Data Marketplace access
2. Create OAuth application in SAP Cloud Platform
3. Grant necessary scopes:
   - `DataMarketplace.Read`
   - `DataMarketplace.Write`
   - `DataMarketplace.Publish`
4. Note down client ID, client secret, and tenant ID

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "SAP_DATA_MARKETPLACE",
  "name": "My SAP Data Marketplace",
  "config": {
    "api_endpoint": "https://api.sap.com/data-marketplace",
    "client_id": "your-sap-client-id",
    "client_secret": "your-sap-client-secret",
    "tenant_id": "your-sap-tenant-id",
    "environment": "production"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## SAP Data Marketplace-Specific Features

### Product Publishing (PUSH)

When syncing assets to SAP:

1. **Product Creation**: Assets are published as SAP Data Marketplace products
2. **Metadata Publishing**: Asset metadata is published as product metadata
3. **ODPS Integration**: Uses ODPS contracts for product descriptions
4. **SAP Integration**: Integrates with SAP Data Intelligence for data delivery

### Product Discovery (PULL)

When syncing from SAP:

1. **Product Discovery**: Lists available products in the marketplace
2. **Subscription**: Subscribes to selected products
3. **Data Access**: Accesses data via SAP Data Intelligence
4. **ODPS Generation**: Generates ODPS contracts from product metadata

## SAP Data Marketplace-Specific Limitations

1. **Account Requirements**: Requires SAP account with Data Marketplace access
2. **OAuth Authentication**: Requires OAuth 2.0 setup
3. **SAP Integration**: Requires SAP Data Intelligence for data delivery
4. **Region Constraints**: Operations are region-specific
5. **Subscription Model**: PULL operations require product subscription
6. **Certification**: Products may require certification before publishing

## Best Practices

1. **OAuth Security**: Store OAuth credentials securely
2. **Environment Management**: Use separate connections for production and sandbox
3. **Metadata Quality**: Ensure complete metadata for product discoverability
4. **SAP Integration**: Understand SAP Data Intelligence integration requirements
5. **Certification Process**: Understand product certification requirements

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid credentials"
- **Solution**: Verify OAuth client ID and secret are correct

**Issue**: PUSH sync fails with "Product creation failed"
- **Solution**: Check product certification requirements and account permissions

**Issue**: Subscription fails
- **Solution**: Verify subscription has necessary permissions and quotas

## Additional Resources

- [SAP Data Marketplace Documentation](https://help.sap.com/docs/data-marketplace)
- [SAP Data Intelligence Documentation](https://help.sap.com/docs/data-intelligence)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

### SNOWFLAKE


## Overview

This guide covers integration with Snowflake Data Marketplace, a platform for discovering and accessing third-party data products within the Snowflake ecosystem.

## Marketplace Type

- **Type**: `SNOWFLAKE_DATA_MARKETPLACE`
- **Supported Operations**: PUSH, PULL
- **Authentication**: Snowflake Account Credentials

## Connection Configuration

### Required Configuration Parameters

```json
{
  "account_identifier": "your-account-identifier",
  "username": "your-username",
  "password": "your-password",
  "warehouse": "COMPUTE_WH",
  "database": "MARKETPLACE_DB"
}
```

### Configuration Details

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_identifier` | string | Yes | Snowflake account identifier (e.g., `xy12345.us-east-1`) |
| `username` | string | Yes | Snowflake username |
| `password` | string | Yes | Snowflake password |
| `warehouse` | string | Yes | Snowflake warehouse name (e.g., `COMPUTE_WH`) |
| `database` | string | Yes | Database name for marketplace operations |

### Optional Configuration

```json
{
  "account_identifier": "your-account-identifier",
  "username": "your-username",
  "password": "your-password",
  "warehouse": "COMPUTE_WH",
  "database": "MARKETPLACE_DB",
  "role": "ACCOUNTADMIN",
  "schema": "PUBLIC",
  "region": "us-east-1"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `role` | string | No | Snowflake role to use (default: account default role) |
| `schema` | string | No | Schema name (default: `PUBLIC`) |
| `region` | string | No | Snowflake region (auto-detected from account_identifier if not specified) |

## Creating a Snowflake Connection

### Step 1: Prepare Snowflake Account

1. Ensure you have a Snowflake account with Data Marketplace access
2. Create a dedicated warehouse for marketplace operations (recommended)
3. Create a database for storing marketplace listings
4. Ensure your user has necessary permissions:
   - `CREATE DATABASE` (if creating new database)
   - `CREATE SCHEMA`
   - `CREATE TABLE`
   - `CREATE SHARE` (for PUSH operations)
   - `IMPORT SHARE` (for PULL operations)

### Step 2: Create Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/`

**Request**:
```json
{
  "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
  "name": "My Snowflake Marketplace",
  "config": {
    "account_identifier": "xy12345.us-east-1",
    "username": "marketplace_user",
    "password": "secure-password",
    "warehouse": "MARKETPLACE_WH",
    "database": "MARKETPLACE_DB",
    "role": "ACCOUNTADMIN"
  },
  "is_active": true
}
```

### Step 3: Test Connection

**Endpoint**: `POST /api/v1/integrations/marketplace/connections/{connection_id}/test/`

## Snowflake-Specific Features

### Listing Publishing (PUSH)

When syncing assets to Snowflake:

1. **Share Creation**: Assets are published as Snowflake shares
2. **Table Mapping**: Hub asset datasets are mapped to Snowflake tables
3. **Metadata Publishing**: Asset metadata is published as listing metadata
4. **ODPS Integration**: ODPS contracts are used to generate Snowflake listing descriptions

### Listing Discovery (PULL)

When syncing from Snowflake:

1. **Share Discovery**: Lists available shares in the marketplace
2. **Table Schema Extraction**: Extracts table schemas from Snowflake shares
3. **Data Access**: Creates federated assets with access to Snowflake tables
4. **ODPS Generation**: Generates ODPS contracts from Snowflake listing metadata

## Snowflake-Specific Limitations

1. **Account Requirements**: Requires a Snowflake account with Data Marketplace enabled
2. **Share Permissions**: PUSH operations require share creation permissions
3. **Table Format**: Only tabular data can be published (CSV, Parquet, etc.)
4. **Region Constraints**: Shares must be in the same region as the consumer account
5. **Compute Costs**: Querying Snowflake tables incurs compute costs
6. **Data Types**: Some Hub data types may not map directly to Snowflake types

## Best Practices

1. **Dedicated Warehouse**: Use a dedicated warehouse for marketplace operations
2. **Role-Based Access**: Use specific roles with minimal required permissions
3. **Schema Organization**: Organize listings in dedicated schemas
4. **Cost Monitoring**: Monitor compute costs when querying marketplace data
5. **Data Type Mapping**: Verify data type compatibility before syncing
6. **Share Naming**: Use descriptive share names that match asset names
7. **Metadata Quality**: Ensure asset metadata is complete for better discoverability

## Troubleshooting

### Common Issues

**Issue**: Connection test fails with "Invalid account identifier"
- **Solution**: Verify account identifier format (e.g., `xy12345.us-east-1`)

**Issue**: PUSH sync fails with "Insufficient privileges"
- **Solution**: Ensure user has `CREATE SHARE` and `CREATE DATABASE` permissions

**Issue**: PULL sync fails with "Share not found"
- **Solution**: Verify share exists and is accessible from your account

**Issue**: Table schema extraction fails
- **Solution**: Ensure you have `SELECT` permissions on the share tables

**Issue**: Data type conversion errors
- **Solution**: Review data type mappings and convert incompatible types before syncing

## Additional Resources

- [Snowflake Data Marketplace Documentation](https://docs.snowflake.com/en/user-guide/data-marketplace-intro.html)
- [Snowflake Shares Documentation](https://docs.snowflake.com/en/user-guide/data-sharing-intro.html)
- [Main Marketplace Integration Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)

---

## Use Cases


Complete use cases documentation for the Marketplace Integration Framework.

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Use Case 1: Publish Hub Assets to External Marketplace](#use-case-1-publish-hub-assets-to-external-marketplace)
3. [Use Case 2: Discover and Import Datasets from External Marketplace](#use-case-2-discover-and-import-datasets-from-external-marketplace)
4. [Use Case 3: Bidirectional Sync with External Marketplace](#use-case-3-bidirectional-sync-with-external-marketplace)
5. [Use Case 4: Scheduled Sync with External Marketplace](#use-case-4-scheduled-sync-with-external-marketplace)
6. [Use Case 5: Multi-Marketplace Distribution](#use-case-5-multi-marketplace-distribution)
7. [Use Case 6: Federated Asset with Dual Contracts](#use-case-6-federated-asset-with-dual-contracts)
8. [Use Case 7: Semantic Layer Discovery of Federated Assets](#use-case-7-semantic-layer-discovery-of-federated-assets)

---

## Overview

The Marketplace Integration Framework enables organizations to seamlessly integrate with external data marketplaces, enabling bidirectional data exchange, federated asset management, and automated synchronization.

### Key Capabilities

- **Publish Assets**: Publish Hub assets to external marketplaces with full metadata and contracts
- **Import Datasets**: Discover and import datasets from external marketplaces as federated assets
- **Bidirectional Sync**: Keep Hub assets and marketplace listings synchronized automatically
- **Scheduled Sync**: Automate recurring synchronization operations
- **Multi-Marketplace**: Distribute assets across multiple marketplaces simultaneously
- **Federated Assets**: Import marketplace listings as federated assets with ODPS and ODCS contracts
- **Semantic Discovery**: Discover federated assets through semantic layer queries

---

## Use Case 1: Publish Hub Assets to External Marketplace

### Description

A Data Product Owner wants to publish an active Hub asset to an external marketplace (e.g., Snowflake Data Marketplace, AWS Data Exchange) to make it available to external consumers.

### Actors

- **Primary Actor**: Data Product Owner
- **Secondary Actors**:
  - Marketplace Integration Service
  - External Marketplace Platform
  - Hub Asset Management System
  - Contract Management System

### Goals

- Publish Hub asset to external marketplace
- Maintain asset metadata and contracts in marketplace listing
- Track marketplace listing status and performance
- Enable external consumers to discover and access the asset

### Preconditions

- Hub asset exists and is in ACTIVE status
- Asset has valid ODPS contract (for marketplace metadata)
- Marketplace connection is configured and tested
- User has DATA_PROVIDER or TENANT_ADMIN role
- User has `integrations:write` scope

### Main Success Scenario

1. **User Initiates Publish**
   - User navigates to asset details page
   - User clicks "Publish to Marketplace" button
   - System validates asset eligibility (ACTIVE status, valid contract, dataset attached)

2. **Select Marketplace Connection**
   - System displays list of available marketplace connections
   - User selects target marketplace connection (e.g., Snowflake Data Marketplace)
   - System validates connection is active and tested

3. **Configure Marketplace Listing**
   - System extracts asset metadata (name, description, domain, tags)
   - System extracts ODPS contract metadata (product details, pricing plans, access methods)
   - System generates marketplace listing preview
   - User reviews and optionally modifies listing details

4. **Create Sync Job**
   - System creates PUSH sync job via `MarketplaceIntegrationService.sync_assets_to_marketplace()`
   - Sync job is created with status PENDING
   - System enqueues sync job for asynchronous processing

5. **Workflow Execution**
   - Workflow: `marketplace_sync_push` is triggered
   - Workflow validates connection and assets
   - Workflow maps Hub asset to marketplace listing format via `connector.map_from_hub_asset()`
   - Workflow publishes listing to marketplace via `connector.create_listing()` or `connector.update_listing()`
   - Workflow creates MarketplaceMapping record linking Hub asset to marketplace listing

6. **Completion**
   - Sync job status updated to COMPLETED
   - MarketplaceMapping record created
   - User receives notification of successful publication
   - Asset is now discoverable in external marketplace

### Alternative Flows

#### A1: Asset Not Eligible

- **Trigger**: Asset fails eligibility checks
- **Action**: System displays error message with specific reasons
- **Resolution**: User must fix issues (activate asset, attach contract, etc.) before retrying

#### A2: Connection Test Fails

- **Trigger**: Marketplace connection test fails
- **Action**: System displays connection error
- **Resolution**: User must fix connection configuration and retest before publishing

#### A3: Marketplace Rejects Listing

- **Trigger**: Marketplace platform rejects listing (invalid data, quota exceeded, etc.)
- **Action**: Sync job status updated to FAILED with error details
- **Resolution**: User reviews error, fixes issues, and retries publication

### Postconditions

- Marketplace listing created in external marketplace
- MarketplaceMapping record created linking Hub asset to marketplace listing
- Sync job status is COMPLETED
- Asset metadata synchronized to marketplace

### Business Rules

- Only ACTIVE assets can be published
- Asset must have valid ODPS contract for marketplace metadata
- Marketplace connection must be active and tested
- User must have DATA_PROVIDER or TENANT_ADMIN role
- User must have `integrations:write` scope

### Performance Requirements

- Sync job creation: < 1 second
- Workflow execution: < 5 minutes (depends on marketplace API response time)
- Total publication time: < 10 minutes

---

## Use Case 2: Discover and Import Datasets from External Marketplace

### Description

A Data Consumer wants to discover and import datasets from an external marketplace (e.g., Data.gov, Snowflake Data Marketplace) into the Hub as federated assets with dual contracts (ODPS and ODCS).

### Actors

- **Primary Actor**: Data Consumer
- **Secondary Actors**:
  - Marketplace Integration Service
  - External Marketplace Platform
  - Hub Asset Management System
  - Contract Management System
  - Semantic Layer Service

### Goals

- Discover marketplace listings
- Import selected listings as federated assets
- Create ODPS and ODCS contracts automatically
- Enable on-demand resource downloads
- Make federated assets discoverable through semantic layer

### Preconditions

- Marketplace connection is configured and tested
- User has DATA_CONSUMER or higher role
- User has `integrations:read` scope (for discovery)
- User has `integrations:write` scope (for import)

### Main Success Scenario

1. **User Initiates Discovery**
   - User navigates to marketplace integration page
   - User selects marketplace connection (e.g., Data.gov)
   - User clicks "Discover Listings" button

2. **Discover Listings**
   - System calls `connector.list_listings()` with optional filters
   - Connector discovers listings from marketplace (metadata-only, no data download)
   - System displays list of discovered listings with metadata (title, description, category, tags)

3. **User Selects Listings**
   - User browses/search/filters discovered listings
   - User selects one or more listings to import
   - User optionally configures import options:
     - Data strategy: METADATA_ONLY, DOWNLOAD_SELECTIVE, or DOWNLOAD_ALL
     - Resource selection (if DOWNLOAD_SELECTIVE)

4. **Create Sync Job**
   - System creates PULL sync job via `MarketplaceIntegrationService.sync_from_marketplace()`
   - Sync job includes selected listing IDs or filters
   - Sync job includes data strategy and options
   - Sync job is created with status PENDING

5. **Workflow Execution (Metadata-First Pattern)**
   - Workflow: `marketplace_sync_pull` is triggered
   - **Step 1: Discover Listings**
     - Workflow calls `connector.list_listings()` or `connector.get_listing()` for selected listings
     - Returns list of `MarketplaceListing` objects
   - **Step 2: Map Listings to Assets**
     - Workflow calls `connector.map_to_hub_asset()` for each listing
     - Connector extracts asset metadata, ODPS metadata, ODCS metadata
     - Connector includes external resource references (NO data download)
     - Returns `MarketplaceAssetMapping` objects
   - **Step 3: Create Federated Assets**
     - Workflow calls `create_federated_asset_with_contracts()` for each mapping
     - Creates federated asset with `source_type=FEDERATED`
     - Creates ODPS contract from `odps_metadata` (if available)
     - Creates ODCS contract from `odcs_metadata` (if available)
     - Links ODPS and ODCS contracts bidirectionally
     - Based on `data_strategy`:
       - **METADATA_ONLY**: Store external resource references only (default, fast)
       - **DOWNLOAD_SELECTIVE**: Download specific resources via `connector.download_resource()`
       - **DOWNLOAD_ALL**: Download all resources via `connector.download_resource()`
   - **Step 4: Create Mappings**
     - Workflow creates MarketplaceMapping records linking Hub assets to marketplace listings
   - **Step 5: Update Semantic Layer**
     - Workflow maps federated assets to semantic layer via `map_asset_to_semantic()`
     - Semantic layer includes external resource references for discovery

6. **Completion**
   - Sync job status updated to COMPLETED
   - Federated assets created with dual contracts
   - MarketplaceMapping records created
   - Semantic layer updated with federated asset metadata
   - User receives notification of successful import

### Alternative Flows

#### A1: Listing Not Found

- **Trigger**: Selected listing ID not found in marketplace
- **Action**: Sync job marks listing as failed, continues with other listings
- **Resolution**: User reviews failed listings and retries if needed

#### A2: Mapping Fails

- **Trigger**: `map_to_hub_asset()` fails for a listing (invalid data, missing required fields)
- **Action**: Listing is skipped, error logged, sync continues with other listings
- **Resolution**: User reviews errors, fixes marketplace data if possible, retries

#### A3: Contract Creation Fails

- **Trigger**: ODPS or ODCS contract creation fails (validation error, missing data)
- **Action**: Asset created without contract, error logged
- **Resolution**: User can manually create contracts later or retry import

#### A4: Resource Download Fails

- **Trigger**: `download_resource()` fails (network error, permission denied, etc.)
- **Action**: Resource download skipped, error logged, asset created with metadata only
- **Resolution**: User can retry resource download later via asset details page

### Postconditions

- Federated assets created in Hub with `source_type=FEDERATED`
- ODPS contracts created (if metadata available)
- ODCS contracts created (if metadata available)
- ODPS and ODCS contracts linked bidirectionally
- MarketplaceMapping records created
- External resource references stored (for on-demand download)
- Resources downloaded (if `data_strategy != METADATA_ONLY`)
- Semantic layer updated with federated asset metadata

### Business Rules

- Marketplace connection must be active and tested
- User must have DATA_CONSUMER or higher role
- User must have `integrations:read` scope (for discovery)
- User must have `integrations:write` scope (for import)
- Federated assets always have `source_type=FEDERATED`
- ODPS and ODCS contracts are optional (created if metadata available)
- Resources are downloaded only if `data_strategy != METADATA_ONLY`

### Performance Requirements

- Listing discovery: < 5 seconds (metadata-only)
- Asset creation (METADATA_ONLY): < 1 second per asset
- Asset creation (DOWNLOAD_ALL): < 5 minutes per asset (depends on resource size)
- Total import time (100 listings, METADATA_ONLY): < 2 minutes
- Total import time (100 listings, DOWNLOAD_ALL): < 8 hours (depends on resource sizes)

### Metadata-First Benefits

- **Fast Harvesting**: Import 1000+ listings in seconds (METADATA_ONLY)
- **Scalability**: No storage overhead for metadata-only assets
- **Lazy Data Access**: Download data only when explicitly requested
- **Governance/Compliance**: All layers work with metadata-first federated assets

---

## Use Case 3: Bidirectional Sync with External Marketplace

### Description

A Data Product Owner wants to keep Hub assets and external marketplace listings synchronized bidirectionally, ensuring changes in either system are reflected in the other.

### Actors

- **Primary Actor**: Data Product Owner
- **Secondary Actors**:
  - Marketplace Integration Service
  - External Marketplace Platform
  - Hub Asset Management System
  - Contract Management System

### Goals

- Keep Hub assets and marketplace listings synchronized
- Handle updates from both directions (Hub → Marketplace, Marketplace → Hub)
- Resolve conflicts when both systems have changes
- Maintain data consistency across systems

### Preconditions

- Marketplace connection is configured and tested
- Hub assets are published to marketplace (MarketplaceMapping records exist)
- User has DATA_PROVIDER or TENANT_ADMIN role
- User has `integrations:write` scope

### Main Success Scenario

1. **User Initiates Bidirectional Sync**
   - User navigates to marketplace connection details
   - User clicks "Sync Bidirectionally" button
   - User selects assets to sync (or sync all mapped assets)

2. **Create Sync Job**
   - System creates BIDIRECTIONAL sync job
   - Sync job includes asset IDs or mapping IDs
   - Sync job is created with status PENDING

3. **Workflow Execution**
   - Workflow: `marketplace_sync_bidirectional` is triggered
   - **Step 1: Validate Connection and Assets**
     - Workflow validates connection is active
     - Workflow validates assets exist and are accessible
   - **Step 2: PUSH Sync (Hub → Marketplace)**
     - Workflow maps Hub assets to marketplace listings
     - Workflow publishes/updates listings in marketplace
     - Workflow updates MarketplaceMapping records
   - **Step 3: PULL Sync (Marketplace → Hub)**
     - Workflow discovers marketplace listings
     - Workflow compares marketplace listings with Hub assets
     - Workflow updates Hub assets if marketplace has newer changes
     - Workflow creates new federated assets if new listings found
   - **Step 4: Conflict Resolution**
     - Workflow detects conflicts (both systems have changes)
     - Workflow applies conflict resolution strategy (Hub wins, Marketplace wins, or manual resolution)
   - **Step 5: Update Mappings**
     - Workflow updates MarketplaceMapping records with latest sync metadata

4. **Completion**
   - Sync job status updated to COMPLETED
   - Hub assets and marketplace listings are synchronized
   - MarketplaceMapping records updated
   - User receives notification of successful sync

### Alternative Flows

#### A1: Conflict Detected

- **Trigger**: Both Hub and marketplace have changes to same asset/listing
- **Action**: Workflow applies conflict resolution strategy
- **Resolution**:
  - If "Hub wins": Marketplace listing updated with Hub asset data
  - If "Marketplace wins": Hub asset updated with marketplace listing data
  - If "Manual resolution": Sync job status set to PARTIAL, user notified to resolve manually

#### A2: Marketplace Listing Deleted

- **Trigger**: Marketplace listing was deleted externally
- **Action**: Workflow marks MarketplaceMapping as inactive, optionally deletes Hub asset
- **Resolution**: User can reactivate mapping or create new listing

#### A3: Hub Asset Deleted

- **Trigger**: Hub asset was deleted
- **Action**: Workflow deletes marketplace listing (if configured) or marks mapping as inactive
- **Resolution**: Marketplace listing removed or marked inactive

### Postconditions

- Hub assets and marketplace listings are synchronized
- MarketplaceMapping records updated with latest sync metadata
- Conflicts resolved according to strategy
- Sync job status is COMPLETED

### Business Rules

- Marketplace connection must be active and tested
- User must have DATA_PROVIDER or TENANT_ADMIN role
- User must have `integrations:write` scope
- Conflict resolution strategy must be configured
- Bidirectional sync requires MarketplaceMapping records

### Performance Requirements

- Sync job creation: < 1 second
- Workflow execution: < 10 minutes (depends on number of assets and marketplace API response time)
- Conflict resolution: < 30 seconds per conflict

---

## Use Case 4: Scheduled Sync with External Marketplace

### Description

A Data Product Owner wants to schedule automatic recurring synchronization operations with an external marketplace (daily, weekly, monthly, or custom cron schedule).

### Actors

- **Primary Actor**: Data Product Owner
- **Secondary Actors**:
  - Marketplace Integration Service
  - Job Queue System
  - Scheduled Task Scheduler

### Goals

- Schedule recurring sync operations
- Automate marketplace synchronization
- Reduce manual intervention
- Maintain data freshness

### Preconditions

- Marketplace connection is configured and tested
- User has DATA_PROVIDER or TENANT_ADMIN role
- User has `integrations:write` scope

### Main Success Scenario

1. **User Creates Schedule**
   - User navigates to marketplace connection details
   - User clicks "Schedule Sync" button
   - User configures schedule:
     - **Schedule Type**: DAILY, WEEKLY, MONTHLY, or CUSTOM_CRON
     - **Schedule Config**:
       - DAILY: `{"time": "02:00"}`
       - WEEKLY: `{"days_of_week": [0,1,2], "time": "02:00"}` (0=Monday)
       - MONTHLY: `{"day_of_month": 1, "time": "02:00"}`
       - CUSTOM_CRON: `{"cron": "0 2 * * *", "timezone": "UTC"}`
     - **Sync Direction**: PULL, PUSH, or BIDIRECTIONAL
     - **Sync Options**:
       - For PULL: `{"filters": {...}, "options": {"data_strategy": "METADATA_ONLY"}}`
       - For PUSH: `{"asset_ids": [...], "options": {...}}`
     - **Name**: Unique name for scheduled sync
     - **Description**: Optional description

2. **Create Scheduled Sync**
   - System creates `ScheduledMarketplaceSync` record via `MarketplaceIntegrationService.schedule_sync()`
   - Scheduled sync is created with status ACTIVE
   - System calculates `next_run_at` based on schedule

3. **Scheduled Task Processing**
   - Scheduled task `process_scheduled_syncs()` runs periodically (e.g., every minute)
   - Task queries for active scheduled syncs where `next_run_at <= now`
   - For each due scheduled sync:
     - Task creates sync job based on sync direction and options
     - Task triggers sync job execution
     - Task updates `next_run_at` for next occurrence
     - Task updates scheduled sync status and metadata

4. **Sync Job Execution**
   - Sync job executes asynchronously (same as manual sync)
   - Sync job status tracked in MarketplaceSyncJob
   - Scheduled sync metadata updated with last run results

5. **Completion**
   - Sync job completes successfully
   - Scheduled sync `next_run_at` updated for next occurrence
   - User receives notification of successful scheduled sync (optional)

### Alternative Flows

#### A1: Sync Job Fails

- **Trigger**: Sync job execution fails
- **Action**: Scheduled sync status updated, error logged
- **Resolution**:
  - Scheduled sync continues with next scheduled run
  - User can review errors and fix issues
  - User can pause/resume scheduled sync

#### A2: Connection Becomes Inactive

- **Trigger**: Marketplace connection becomes inactive
- **Action**: Scheduled sync status set to ERROR
- **Resolution**: User must reactivate connection and resume scheduled sync

#### A3: Schedule Expires

- **Trigger**: Scheduled sync has end date and it's reached
- **Action**: Scheduled sync status set to EXPIRED
- **Resolution**: User can extend schedule or create new scheduled sync

### Postconditions

- Scheduled sync created and active
- Sync jobs created automatically based on schedule
- Sync jobs execute asynchronously
- Scheduled sync metadata updated with run history

### Business Rules

- Marketplace connection must be active and tested
- User must have DATA_PROVIDER or TENANT_ADMIN role
- User must have `integrations:write` scope
- Scheduled sync name must be unique per tenant
- Schedule must have valid configuration for schedule type

### Performance Requirements

- Scheduled sync creation: < 1 second
- Scheduled task processing: < 10 seconds per due sync
- Sync job execution: Same as manual sync (depends on direction and options)

---

## Use Case 5: Multi-Marketplace Distribution

### Description

A Data Product Owner wants to distribute a single Hub asset across multiple external marketplaces simultaneously (e.g., Snowflake Data Marketplace, AWS Data Exchange, Azure Data Share).

### Actors

- **Primary Actor**: Data Product Owner
- **Secondary Actors**:
  - Marketplace Integration Service
  - Multiple External Marketplace Platforms
  - Hub Asset Management System

### Goals

- Publish single asset to multiple marketplaces
- Maintain consistent metadata across marketplaces
- Track distribution across all marketplaces
- Manage marketplace-specific configurations

### Preconditions

- Hub asset exists and is in ACTIVE status
- Multiple marketplace connections are configured and tested
- User has DATA_PROVIDER or TENANT_ADMIN role
- User has `integrations:write` scope

### Main Success Scenario

1. **User Initiates Multi-Marketplace Distribution**
   - User navigates to asset details page
   - User clicks "Distribute to Marketplaces" button
   - System displays list of available marketplace connections

2. **Select Marketplaces**
   - User selects multiple marketplace connections (e.g., Snowflake, AWS, Azure)
   - User optionally configures marketplace-specific settings:
     - Pricing model per marketplace
     - Access methods per marketplace
     - Listing metadata per marketplace

3. **Create Sync Jobs**
   - System creates separate PUSH sync job for each selected marketplace
   - Each sync job is created with status PENDING
   - Sync jobs are enqueued for parallel execution

4. **Parallel Workflow Execution**
   - Multiple `marketplace_sync_push` workflows execute in parallel
   - Each workflow:
     - Validates connection and asset
     - Maps Hub asset to marketplace-specific listing format
     - Publishes listing to marketplace
     - Creates MarketplaceMapping record

5. **Completion**
   - All sync jobs complete (some may succeed, some may fail)
   - MarketplaceMapping records created for successful publications
   - User receives summary notification:
     - Number of successful publications
     - Number of failed publications
     - Details for each marketplace

### Alternative Flows

#### A1: Some Marketplaces Fail

- **Trigger**: Some marketplace publications fail (connection error, API error, etc.)
- **Action**: Failed sync jobs marked as FAILED, successful ones marked as COMPLETED
- **Resolution**: User reviews failures, fixes issues, retries failed marketplaces

#### A2: Marketplace-Specific Validation Fails

- **Trigger**: Marketplace rejects listing due to marketplace-specific requirements
- **Action**: Sync job for that marketplace marked as FAILED with error details
- **Resolution**: User fixes marketplace-specific issues and retries

### Postconditions

- Asset published to selected marketplaces (where successful)
- MarketplaceMapping records created for successful publications
- Sync jobs completed (some COMPLETED, some FAILED)
- Asset distributed across multiple marketplaces

### Business Rules

- Hub asset must be ACTIVE
- All selected marketplace connections must be active and tested
- User must have DATA_PROVIDER or TENANT_ADMIN role
- User must have `integrations:write` scope
- Each marketplace gets separate sync job and mapping

### Performance Requirements

- Sync job creation: < 1 second per marketplace
- Parallel workflow execution: < 10 minutes (depends on slowest marketplace)
- Total distribution time: < 15 minutes for 5 marketplaces

---

## Use Case 6: Federated Asset with Dual Contracts

### Description

A Data Consumer imports a marketplace listing as a federated asset with both ODPS (marketplace) and ODCS (technical) contracts automatically generated from marketplace metadata.

### Actors

- **Primary Actor**: Data Consumer
- **Secondary Actors**:
  - Marketplace Integration Service
  - External Marketplace Platform
  - Contract Management System
  - Hub Asset Management System

### Goals

- Import marketplace listing as federated asset
- Generate ODPS contract from marketplace product metadata
- Generate ODCS contract from marketplace technical metadata
- Link ODPS and ODCS contracts bidirectionally
- Enable governance and compliance layers to work with federated assets

### Preconditions

- Marketplace connection is configured and tested
- Marketplace listing has ODPS and/or ODCS metadata
- User has DATA_CONSUMER or higher role
- User has `integrations:write` scope

### Main Success Scenario

1. **User Imports Listing**
   - User discovers marketplace listing (see Use Case 2)
   - User selects listing to import
   - User initiates import with data strategy (METADATA_ONLY, DOWNLOAD_SELECTIVE, or DOWNLOAD_ALL)

2. **Workflow Maps Listing**
   - Workflow calls `connector.map_to_hub_asset(listing)`
   - Connector extracts:
     - Asset metadata (name, description, domain, tags)
     - ODPS metadata (product details, pricing plans, access methods, payment gateways)
     - ODCS metadata (schema hints, quality hints, SLA hints)
     - External resource references

3. **Create Federated Asset**
   - Workflow calls `create_federated_asset_with_contracts()`
   - System creates federated asset with:
     - `source_type=FEDERATED`
     - `source_metadata` with marketplace connection and listing information
     - External resource references stored (for on-demand download)

4. **Generate ODPS Contract**
   - If `odps_metadata` is available:
     - System creates ODPS contract from `odps_metadata`
     - Contract includes:
       - Product details (productID, product_name, product_description)
       - Pricing plans
       - Access methods
       - Payment gateways
     - Contract status set to VALIDATED
     - Contract linked to asset

5. **Generate ODCS Contract**
   - If `odcs_metadata` is available:
     - System creates ODCS contract from `odcs_metadata`
     - Contract includes:
       - Schema hints (column names, types, constraints)
       - Quality hints (data quality expectations)
       - SLA hints (availability, performance)
     - Contract status set to VALIDATED
     - Contract linked to asset

6. **Link Contracts**
   - System links ODPS and ODCS contracts bidirectionally
   - Link validation ensures contracts are compatible
   - Link metadata stored in both contracts

7. **Download Resources (Optional)**
   - If `data_strategy != METADATA_ONLY`:
     - System calls `connector.download_resource()` for selected/all resources
     - Resources downloaded to Hub storage
     - Datasets created and attached to asset

8. **Completion**
   - Federated asset created with dual contracts
   - Contracts linked bidirectionally
   - Resources downloaded (if requested)
   - Asset ready for use in governance, compliance, and semantic layers

### Alternative Flows

#### A1: ODPS Metadata Not Available

- **Trigger**: Marketplace listing has no ODPS metadata
- **Action**: ODPS contract not created, asset created without ODPS contract
- **Resolution**: User can manually create ODPS contract later or retry import with different marketplace

#### A2: ODCS Metadata Not Available

- **Trigger**: Marketplace listing has no ODCS metadata
- **Action**: ODCS contract not created, asset created without ODCS contract
- **Resolution**: User can manually create ODCS contract later or retry import with different marketplace

#### A3: Contract Validation Fails

- **Trigger**: ODPS or ODCS contract validation fails
- **Action**: Contract creation skipped, error logged, asset created without contract
- **Resolution**: User reviews errors, fixes metadata if possible, retries import

#### A4: Contract Linking Fails

- **Trigger**: ODPS and ODCS contracts cannot be linked (incompatible)
- **Action**: Contracts created but not linked, error logged
- **Resolution**: User reviews linking errors, fixes contracts if needed, manually links contracts

### Postconditions

- Federated asset created with `source_type=FEDERATED`
- ODPS contract created (if metadata available)
- ODCS contract created (if metadata available)
- ODPS and ODCS contracts linked bidirectionally (if both available)
- External resource references stored
- Resources downloaded (if `data_strategy != METADATA_ONLY`)
- Asset ready for governance, compliance, and semantic layers

### Business Rules

- Federated assets always have `source_type=FEDERATED`
- ODPS and ODCS contracts are optional (created if metadata available)
- Contracts must be validated before linking
- Contract linking requires both contracts to be compatible
- Resources downloaded only if `data_strategy != METADATA_ONLY`

### Performance Requirements

- Asset creation: < 1 second (METADATA_ONLY)
- ODPS contract creation: < 500ms
- ODCS contract creation: < 500ms
- Contract linking: < 200ms
- Resource download: < 5 minutes per resource (depends on size)

---

## Use Case 7: Semantic Layer Discovery of Federated Assets

### Description

A Data Consumer wants to discover federated assets with external resources through semantic layer queries, enabling federated queries and cross-marketplace data discovery.

### Actors

- **Primary Actor**: Data Consumer
- **Secondary Actors**:
  - Semantic Layer Service
  - Marketplace Integration Service
  - Hub Asset Management System

### Goals

- Discover federated assets through semantic queries
- Query external resource metadata
- Enable federated queries across marketplaces
- Support cross-marketplace data discovery

### Preconditions

- Federated assets exist with external resource references
- Federated assets are mapped to semantic layer
- Semantic layer service is available
- User has DATA_CONSUMER or higher role

### Main Success Scenario

1. **Federated Asset Creation**
   - User imports marketplace listing as federated asset (see Use Case 2)
   - Workflow creates federated asset with external resource references
   - Workflow maps asset to semantic layer via `map_asset_to_semantic()`
   - Semantic layer includes:
     - Asset metadata (name, description, status)
     - External resource references (resource_id, name, url, format, size_bytes)
     - Marketplace connection information
     - Contract metadata (ODPS, ODCS)

2. **Semantic Layer Mapping**
   - System calls semantic service `map_asset()` with:
     - Asset UUID, name, description, status
     - Source type: "FEDERATED"
     - Source metadata: marketplace connection and listing information
     - External resources: list of external resource references
   - Semantic service creates RDF triples:
     - Asset as `hub:DataAsset` with `hub:isFederated true`
     - External resources as `dcat:Distribution` with `hub:isExternal true`
     - Marketplace connection as `hub:MarketplaceConnection`
   - Semantic resource created/updated in Hub

3. **Semantic Discovery Query**
   - User queries semantic layer via SPARQL:
     ```sparql
     PREFIX dcat: <http://www.w3.org/ns/dcat#>
     PREFIX hub: <https://hub.example.com/ontology#>
     PREFIX dct: <http://purl.org/dc/terms/>

     SELECT DISTINCT ?asset ?assetName ?marketplaceType
     WHERE {
         ?asset a hub:DataAsset .
         ?asset hub:isFederated true .
         ?asset dct:title ?assetName .
         ?asset hub:fromMarketplace ?marketplaceType .
         ?asset dcat:distribution ?distribution .
         ?distribution hub:isExternal true .
     }
     LIMIT 100
     ```
   - Semantic service executes query and returns results
   - Results include federated assets with external resources

4. **External Resource Metadata Query**
   - User queries external resource metadata:
     ```sparql
     PREFIX dcat: <http://www.w3.org/ns/dcat#>
     PREFIX hub: <https://hub.example.com/ontology#>

     SELECT ?distribution ?resourceId ?name ?url ?format ?size
     WHERE {
         <asset_uri> dcat:distribution ?distribution .
         ?distribution hub:isExternal true .
         ?distribution hub:resourceId ?resourceId .
         ?distribution dct:title ?name .
         ?distribution dcat:downloadURL ?url .
         ?distribution dcat:mediaType ?format .
         ?distribution dcat:byteSize ?size .
     }
     ```
   - Semantic service returns external resource metadata
   - User can use metadata for on-demand resource downloads

5. **Federated Query Execution**
   - User executes federated query across multiple federated assets
   - Query planner identifies external resources
   - Query executor downloads resources on-demand via `connector.download_resource()`
   - Query results combined from multiple marketplaces

### Alternative Flows

#### A1: Semantic Service Unavailable

- **Trigger**: Semantic service is unavailable (circuit breaker open)
- **Action**: Asset mapping skipped, error logged, asset created without semantic mapping
- **Resolution**: User can retry semantic mapping later when service is available

#### A2: Semantic Mapping Fails

- **Trigger**: Semantic mapping fails (invalid RDF, service error)
- **Action**: Asset created, semantic mapping skipped, error logged
- **Resolution**: User can retry semantic mapping later

#### A3: Query Returns No Results

- **Trigger**: SPARQL query returns no federated assets
- **Action**: Query returns empty result set
- **Resolution**: User reviews query, checks if federated assets exist and are mapped

### Postconditions

- Federated assets mapped to semantic layer
- External resource references included in semantic layer
- SPARQL queries can discover federated assets
- External resource metadata queryable
- Federated queries can execute across marketplaces

### Business Rules

- Federated assets must be mapped to semantic layer for discovery
- External resource references must be included in semantic mapping
- Semantic service must be available for mapping and queries
- SPARQL queries must follow semantic layer schema

### Performance Requirements

- Semantic mapping: < 20 seconds per asset
- SPARQL query execution: < 5 seconds
- Federated query execution: < 10 minutes (depends on resource downloads)

---

## Additional Resources

- **Framework Architecture**: `docs/MARKETPLACE_INTEGRATION_FRAMEWORK.md` - Complete architecture documentation
- **Connector Development Guide**: `docs/MARKETPLACE_CONNECTOR_DEVELOPMENT_GUIDE.md` - Connector implementation guide
- **API Reference**: `docs/MARKETPLACE_API_REFERENCE.md` - Complete API documentation
- **User Journeys**: `docs/MARKETPLACE_USER_JOURNEYS.md` - Detailed user journey maps

---

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## User Journeys


Complete user journey maps for marketplace integration operations.

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [JOURNEY-MP-001: Connect to External Marketplace](#journey-mp-001-connect-to-external-marketplace)
3. [JOURNEY-MP-002: Publish Asset to Marketplace](#journey-mp-002-publish-asset-to-marketplace)
4. [JOURNEY-MP-003: Import Dataset from Marketplace](#journey-mp-003-import-dataset-from-marketplace)
5. [JOURNEY-MP-004: Sync Assets Bidirectionally](#journey-mp-004-sync-assets-bidirectionally)
6. [JOURNEY-MP-005: Schedule Automatic Sync](#journey-mp-005-schedule-automatic-sync)
7. [JOURNEY-MP-006: Manage Marketplace Mappings](#journey-mp-006-manage-marketplace-mappings)
8. [JOURNEY-MP-007: Monitor Sync Jobs](#journey-mp-007-monitor-sync-jobs)

---

## Overview

This document provides detailed user journey maps for marketplace integration operations. All journeys follow the metadata-first architecture pattern and support bidirectional synchronization with external data marketplaces.

**Journey Statistics**:
- **Total Journeys**: 7
- **Total Steps**: ~80+
- **Average Steps per Journey**: ~11
- **Target Completion Rate**: 100%
- **Target Success Rate**: 95%+

---

## JOURNEY-MP-001: Connect to External Marketplace

**Journey ID**: JOURNEY-MP-001
**Title**: Connect to External Marketplace
**Persona**: Data Product Owner, Tenant Admin
**Goal**: Configure and test a connection to an external marketplace

**Steps**:
1. Navigate to marketplace integrations page
2. Click "Create Connection" button
3. Select marketplace type (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE, CKAN_INSTANCE)
4. Enter connection name (unique per tenant)
5. Configure connection credentials:
   - **Snowflake**: account, user, token, warehouse (optional), role (optional)
   - **AWS Data Exchange**: aws_access_key_id, aws_secret_access_key, region_name (optional)
   - **CKAN**: base_url, api_key
   - **GCP Marketplace**: project_id, credentials_json (optional), location (optional)
   - **Databricks**: host, token, cluster_id (optional)
6. Set connection as active/inactive
7. Save connection (credentials encrypted at rest)
8. Test connection
9. Review test results
10. Connection ready for use

**Success Criteria**:
- Connection created successfully
- Credentials encrypted at rest
- Connection test passes
- Connection appears in connections list
- Connection can be used for sync operations

**Performance Targets**:
- Total duration: < 2 minutes
- Connection creation: < 1 second
- Connection test: < 10 seconds
- Credential encryption: < 100ms

**API Endpoints**:
- `POST /api/v1/integrations/marketplace/connections/` - Create connection
- `POST /api/v1/integrations/marketplace/connections/{id}/test/` - Test connection
- `GET /api/v1/integrations/marketplace/connections/{id}/` - Get connection details

**Error Scenarios**:
- Invalid marketplace type → 400 Bad Request
- Duplicate connection name → 409 Conflict
- Invalid credentials → 400 Bad Request
- Connection test fails → 500 Internal Server Error (with error details)

---

## JOURNEY-MP-002: Publish Asset to Marketplace

**Journey ID**: JOURNEY-MP-002
**Title**: Publish Asset to Marketplace
**Persona**: Data Product Owner
**Goal**: Publish an active Hub asset to an external marketplace

**Steps**:
1. Navigate to asset details page
2. Verify asset is ACTIVE
3. Click "Publish to Marketplace" button
4. System validates asset eligibility:
   - Asset status is ACTIVE
   - Asset has valid ODPS contract (for marketplace metadata)
   - Asset has dataset attached (optional)
5. Select marketplace connection
6. System validates connection is active and tested
7. Review marketplace listing preview:
   - Asset metadata (name, description, domain, tags)
   - ODPS contract metadata (product details, pricing plans, access methods)
8. Optionally modify listing details
9. Click "Publish" button
10. System creates PUSH sync job via `MarketplaceIntegrationService.sync_assets_to_marketplace()`
11. Sync job enqueued for asynchronous processing
12. Workflow `marketplace_sync_push` executes:
    - Validates connection and assets
    - Maps Hub asset to marketplace listing format via `connector.map_from_hub_asset()`
    - Publishes listing to marketplace via `connector.create_listing()` or `connector.update_listing()`
    - Creates MarketplaceMapping record
13. Monitor sync job progress
14. Receive notification of successful publication
15. View marketplace listing in external marketplace

**Success Criteria**:
- Asset is in ACTIVE status
- Asset passes eligibility checks
- Connection is active and tested
- Sync job created successfully
- Workflow executes successfully
- Marketplace listing created in external marketplace
- MarketplaceMapping record created
- Sync job status is COMPLETED

**Performance Targets**:
- Total duration: < 10 minutes
- Asset validation: < 1 second
- Connection validation: < 1 second
- Sync job creation: < 1 second
- Workflow execution: < 5 minutes (depends on marketplace API response time)
- Marketplace listing creation: < 2 minutes

**API Endpoints**:
- `GET /api/v1/assets/{id}/` - Get asset details
- `POST /api/v1/integrations/marketplace/sync/` - Create sync job (direction=PUSH)
- `GET /api/v1/integrations/marketplace/sync/{id}/` - Get sync job status

**Error Scenarios**:
- Asset not ACTIVE → 400 Bad Request (asset must be active)
- Asset has no ODPS contract → 400 Bad Request (ODPS contract required)
- Connection not active → 400 Bad Request (connection must be active)
- Connection test fails → 400 Bad Request (connection test failed)
- Marketplace rejects listing → 500 Internal Server Error (with marketplace error details)

---

## JOURNEY-MP-003: Import Dataset from Marketplace

**Journey ID**: JOURNEY-MP-003
**Title**: Import Dataset from Marketplace
**Persona**: Data Consumer
**Goal**: Discover and import datasets from external marketplace as federated assets with dual contracts

**Steps**:
1. Navigate to marketplace integrations page
2. Select marketplace connection (e.g., Data.gov, Snowflake Data Marketplace)
3. Click "Discover Listings" button
4. System calls `connector.list_listings()` with optional filters
5. Browse/search/filter discovered listings
6. Select one or more listings to import
7. Configure import options:
   - **Data Strategy**: METADATA_ONLY (default, fast), DOWNLOAD_SELECTIVE, or DOWNLOAD_ALL
   - **Resource Selection**: Select specific resources (if DOWNLOAD_SELECTIVE)
   - **Filters**: Category, tags, provider (optional)
8. Click "Import" button
9. System creates PULL sync job via `MarketplaceIntegrationService.sync_from_marketplace()`
10. Sync job enqueued for asynchronous processing
11. Workflow `marketplace_sync_pull` executes:
    - **Step 1: Discover Listings**
      - Calls `connector.list_listings()` or `connector.get_listing()` for selected listings
      - Returns list of `MarketplaceListing` objects
    - **Step 2: Map Listings to Assets**
      - Calls `connector.map_to_hub_asset()` for each listing
      - Connector extracts:
        - Asset metadata (name, description, domain, tags)
        - ODPS metadata (product details, pricing plans, access methods)
        - ODCS metadata (schema hints, quality hints, SLA hints)
        - External resource references (NO data download)
      - Returns `MarketplaceAssetMapping` objects
    - **Step 3: Create Federated Assets**
      - Calls `create_federated_asset_with_contracts()` for each mapping
      - Creates federated asset with `source_type=FEDERATED`
      - Creates ODPS contract from `odps_metadata` (if available)
      - Creates ODCS contract from `odcs_metadata` (if available)
      - Links ODPS and ODCS contracts bidirectionally
      - Based on `data_strategy`:
        - **METADATA_ONLY**: Store external resource references only (default, fast)
        - **DOWNLOAD_SELECTIVE**: Download specific resources via `connector.download_resource()`
        - **DOWNLOAD_ALL**: Download all resources via `connector.download_resource()`
    - **Step 4: Create Mappings**
      - Creates MarketplaceMapping records linking Hub assets to marketplace listings
    - **Step 5: Update Semantic Layer**
      - Maps federated assets to semantic layer via `map_asset_to_semantic()`
      - Includes external resource references for discovery
12. Monitor sync job progress
13. Receive notification of successful import
14. View imported federated assets in Hub
15. Access federated assets through governance, compliance, and semantic layers

**Success Criteria**:
- Listings discovered successfully
- Federated assets created with `source_type=FEDERATED`
- ODPS contracts created (if metadata available)
- ODCS contracts created (if metadata available)
- ODPS and ODCS contracts linked bidirectionally (if both available)
- External resource references stored
- Resources downloaded (if `data_strategy != METADATA_ONLY`)
- MarketplaceMapping records created
- Semantic layer updated with federated asset metadata
- Sync job status is COMPLETED

**Performance Targets**:
- Total duration: < 15 minutes (METADATA_ONLY) or < 2 hours (DOWNLOAD_ALL)
- Listing discovery: < 5 seconds (metadata-only)
- Asset creation (METADATA_ONLY): < 1 second per asset
- Asset creation (DOWNLOAD_ALL): < 5 minutes per asset (depends on resource size)
- ODPS contract creation: < 500ms per contract
- ODCS contract creation: < 500ms per contract
- Contract linking: < 200ms per link
- Resource download: < 5 minutes per resource (depends on size)
- Semantic mapping: < 20 seconds per asset

**API Endpoints**:
- `GET /api/v1/integrations/marketplace/connections/{id}/` - Get connection details
- `POST /api/v1/integrations/marketplace/sync/` - Create sync job (direction=PULL)
- `GET /api/v1/integrations/marketplace/sync/{id}/` - Get sync job status
- `GET /api/v1/assets/{id}/` - Get federated asset details

**Error Scenarios**:
- Connection not active → 400 Bad Request (connection must be active)
- Listing not found → 404 Not Found (listing ID invalid)
- Mapping fails → 500 Internal Server Error (with error details, continues with other listings)
- Contract creation fails → 500 Internal Server Error (asset created without contract)
- Resource download fails → 500 Internal Server Error (asset created with metadata only)

**Journey Steps for Federated Asset Creation**:
- **Create Federated Asset**: Asset created with `source_type=FEDERATED` and `source_metadata` with marketplace connection and listing information
- **Generate ODPS Contract**: ODPS contract created from `odps_metadata` with product details, pricing plans, access methods, payment gateways
- **Generate ODCS Contract**: ODCS contract created from `odcs_metadata` with schema hints, quality hints, SLA hints
- **Link Contracts**: ODPS and ODCS contracts linked bidirectionally with link validation
- **Download Resources**: Resources downloaded on-demand via `connector.download_resource()` if `data_strategy != METADATA_ONLY`
- **Map to Semantic Layer**: Federated asset mapped to semantic layer with external resource references for discovery

---

## JOURNEY-MP-004: Sync Assets Bidirectionally

**Journey ID**: JOURNEY-MP-004
**Title**: Sync Assets Bidirectionally
**Persona**: Data Product Owner
**Goal**: Keep Hub assets and external marketplace listings synchronized bidirectionally

**Steps**:
1. Navigate to marketplace connection details
2. Click "Sync Bidirectionally" button
3. Select assets to sync (or sync all mapped assets)
4. Configure sync options:
   - **Conflict Resolution**: Hub wins, Marketplace wins, or Manual resolution
   - **Force Update**: Overwrite changes even if conflicts exist
5. Click "Start Sync" button
6. System creates BIDIRECTIONAL sync job
7. Sync job enqueued for asynchronous processing
8. Workflow `marketplace_sync_bidirectional` executes:
    - **Step 1: Validate Connection and Assets**
      - Validates connection is active
      - Validates assets exist and are accessible
    - **Step 2: PUSH Sync (Hub → Marketplace)**
      - Maps Hub assets to marketplace listings via `connector.map_from_hub_asset()`
      - Publishes/updates listings in marketplace via `connector.create_listing()` or `connector.update_listing()`
      - Updates MarketplaceMapping records
    - **Step 3: PULL Sync (Marketplace → Hub)**
      - Discovers marketplace listings via `connector.list_listings()`
      - Compares marketplace listings with Hub assets
      - Updates Hub assets if marketplace has newer changes
      - Creates new federated assets if new listings found
    - **Step 4: Conflict Resolution**
      - Detects conflicts (both systems have changes)
      - Applies conflict resolution strategy:
        - **Hub wins**: Marketplace listing updated with Hub asset data
        - **Marketplace wins**: Hub asset updated with marketplace listing data
        - **Manual resolution**: Sync job status set to PARTIAL, user notified
    - **Step 5: Update Mappings**
      - Updates MarketplaceMapping records with latest sync metadata
9. Monitor sync job progress
10. Review conflict resolution results (if any)
11. Receive notification of successful sync
12. Verify Hub assets and marketplace listings are synchronized

**Success Criteria**:
- Connection is active and tested
- Assets exist and are accessible
- PUSH sync completes successfully
- PULL sync completes successfully
- Conflicts resolved according to strategy
- MarketplaceMapping records updated
- Sync job status is COMPLETED

**Performance Targets**:
- Total duration: < 15 minutes
- Sync job creation: < 1 second
- Workflow execution: < 10 minutes (depends on number of assets and marketplace API response time)
- Conflict resolution: < 30 seconds per conflict

**API Endpoints**:
- `POST /api/v1/integrations/marketplace/sync/` - Create sync job (direction=BIDIRECTIONAL)
- `GET /api/v1/integrations/marketplace/sync/{id}/` - Get sync job status
- `GET /api/v1/integrations/marketplace/mappings/` - List marketplace mappings

**Error Scenarios**:
- Connection not active → 400 Bad Request (connection must be active)
- Asset not found → 404 Not Found (asset ID invalid)
- Conflict detected → 200 OK (sync job status PARTIAL, conflicts require manual resolution)
- Marketplace API error → 500 Internal Server Error (with marketplace error details)

---

## JOURNEY-MP-005: Schedule Automatic Sync

**Journey ID**: JOURNEY-MP-005
**Title**: Schedule Automatic Sync
**Persona**: Data Product Owner, Tenant Admin
**Goal**: Schedule recurring synchronization operations with external marketplace

**Steps**:
1. Navigate to marketplace connection details
2. Click "Schedule Sync" button
3. Configure schedule:
   - **Schedule Type**: DAILY, WEEKLY, MONTHLY, or CUSTOM_CRON
   - **Schedule Config**:
     - **DAILY**: `{"time": "02:00"}` (e.g., run daily at 2:00 AM)
     - **WEEKLY**: `{"days_of_week": [0,1,2], "time": "02:00"}` (e.g., run Monday, Tuesday, Wednesday at 2:00 AM)
     - **MONTHLY**: `{"day_of_month": 1, "time": "02:00"}` (e.g., run on 1st of month at 2:00 AM)
     - **CUSTOM_CRON**: `{"cron": "0 2 * * *", "timezone": "UTC"}` (e.g., run daily at 2:00 AM UTC)
   - **Sync Direction**: PULL, PUSH, or BIDIRECTIONAL
   - **Sync Options**:
     - **For PULL**: `{"filters": {...}, "options": {"data_strategy": "METADATA_ONLY"}}`
     - **For PUSH**: `{"asset_ids": [...], "options": {...}}`
   - **Name**: Unique name for scheduled sync (per tenant)
   - **Description**: Optional description
4. Click "Create Schedule" button
5. System creates `ScheduledMarketplaceSync` record via `MarketplaceIntegrationService.schedule_sync()`
6. Scheduled sync created with status ACTIVE
7. System calculates `next_run_at` based on schedule
8. Scheduled task `process_scheduled_syncs()` runs periodically (e.g., every minute)
9. Task queries for active scheduled syncs where `next_run_at <= now`
10. For each due scheduled sync:
    - Task creates sync job based on sync direction and options
    - Task triggers sync job execution
    - Task updates `next_run_at` for next occurrence
    - Task updates scheduled sync status and metadata
11. Sync job executes asynchronously (same as manual sync)
12. Monitor scheduled sync history
13. Receive notifications of scheduled sync results (optional)

**Success Criteria**:
- Scheduled sync created successfully
- Scheduled sync status is ACTIVE
- `next_run_at` calculated correctly
- Sync jobs created automatically based on schedule
- Sync jobs execute successfully
- Scheduled sync metadata updated with run history

**Performance Targets**:
- Total duration: < 2 minutes
- Scheduled sync creation: < 1 second
- Scheduled task processing: < 10 seconds per due sync
- Sync job execution: Same as manual sync (depends on direction and options)

**API Endpoints**:
- `POST /api/v1/integrations/marketplace/schedules/` - Create scheduled sync (if API exists)
- `GET /api/v1/integrations/marketplace/schedules/{id}/` - Get scheduled sync details (if API exists)
- `GET /api/v1/integrations/marketplace/sync/` - List sync jobs (includes scheduled sync jobs)

**Error Scenarios**:
- Invalid schedule configuration → 400 Bad Request (schedule config invalid)
- Duplicate schedule name → 409 Conflict (schedule name already exists)
- Connection becomes inactive → Scheduled sync status set to ERROR
- Sync job fails → Scheduled sync continues with next scheduled run

---

## JOURNEY-MP-006: Manage Marketplace Mappings

**Journey ID**: JOURNEY-MP-006
**Title**: Manage Marketplace Mappings
**Persona**: Data Product Owner, Tenant Admin
**Goal**: View and manage mappings between Hub assets and external marketplace listings

**Steps**:
1. Navigate to marketplace integrations page
2. Click "Marketplace Mappings" tab
3. View list of marketplace mappings:
   - Filter by connection, hub asset, external listing ID
   - Sort by created_at, updated_at, last_synced_at
   - Search by external listing ID
4. Click on mapping to view details:
   - Hub asset information
   - External marketplace listing information
   - Sync metadata (last sync status, errors)
   - External resource IDs
   - Last synced timestamp
5. View mapping history (sync job history)
6. Optionally delete mapping:
   - Click "Delete Mapping" button
   - Confirm deletion
   - System deletes MarketplaceMapping record
   - Note: Does NOT delete Hub asset or marketplace listing
7. Optionally resync mapping:
   - Click "Resync" button
   - System creates new sync job for this mapping
   - Sync job executes asynchronously
8. Monitor resync progress

**Success Criteria**:
- Mappings list displayed correctly
- Mapping details displayed correctly
- Mapping history accessible
- Mapping deletion successful (if requested)
- Mapping resync successful (if requested)

**Performance Targets**:
- Total duration: < 1 minute
- Mappings list: < 300ms p95
- Mapping details: < 200ms p95
- Mapping deletion: < 1 second
- Mapping resync: Same as manual sync (depends on direction)

**API Endpoints**:
- `GET /api/v1/integrations/marketplace/mappings/` - List marketplace mappings
- `GET /api/v1/integrations/marketplace/mappings/{id}/` - Get mapping details
- `DELETE /api/v1/integrations/marketplace/mappings/{id}/` - Delete mapping

**Error Scenarios**:
- Mapping not found → 404 Not Found (mapping ID invalid)
- Insufficient permissions → 403 Forbidden (user lacks permissions)

**Note**: Mappings are created automatically during sync operations. They cannot be created manually via API.

---

## JOURNEY-MP-007: Monitor Sync Jobs

**Journey ID**: JOURNEY-MP-007
**Title**: Monitor Sync Jobs
**Persona**: Data Product Owner, Data Consumer, Tenant Admin
**Goal**: Monitor progress and status of marketplace synchronization jobs

**Steps**:
1. Navigate to marketplace integrations page
2. Click "Sync Jobs" tab
3. View list of sync jobs:
   - Filter by connection, direction, status
   - Sort by created_at, updated_at, completed_at
   - Search by sync job ID
4. Click on sync job to view details:
   - Connection information
   - Sync direction (PULL, PUSH, BIDIRECTIONAL)
   - Sync status (PENDING, RUNNING, COMPLETED, FAILED, PARTIAL, CANCELLED)
   - Progress information:
     - Items synced
     - Items failed
     - Errors list
   - Metadata (data_strategy, filters, options)
   - Timestamps (created_at, updated_at, completed_at)
5. View sync job progress in real-time (if RUNNING)
6. Review errors (if FAILED or PARTIAL)
7. Optionally cancel sync job (if PENDING or RUNNING):
   - Click "Cancel" button
   - Enter cancellation reason (optional)
   - System cancels sync job
   - Sync job status set to CANCELLED
8. Optionally retry sync job (if FAILED):
   - Click "Retry" button
   - System creates new sync job with same configuration
   - Sync job executes asynchronously
9. Export sync job results (if COMPLETED)

**Success Criteria**:
- Sync jobs list displayed correctly
- Sync job details displayed correctly
- Progress information accurate
- Errors displayed correctly
- Sync job cancellation successful (if requested)
- Sync job retry successful (if requested)

**Performance Targets**:
- Total duration: < 1 minute
- Sync jobs list: < 300ms p95
- Sync job details: < 200ms p95
- Sync job cancellation: < 2 seconds
- Sync job retry: < 1 second

**API Endpoints**:
- `GET /api/v1/integrations/marketplace/sync/` - List sync jobs
- `GET /api/v1/integrations/marketplace/sync/{id}/` - Get sync job details
- `POST /api/v1/integrations/marketplace/sync/{id}/cancel/` - Cancel sync job

**Error Scenarios**:
- Sync job not found → 404 Not Found (sync job ID invalid)
- Sync job cannot be cancelled → 400 Bad Request (sync job already completed/failed/cancelled)
- Insufficient permissions → 403 Forbidden (user lacks permissions)

**Sync Job Statuses**:
- **PENDING**: Sync job created, waiting to be processed
- **RUNNING**: Sync job currently executing
- **COMPLETED**: Sync job completed successfully
- **FAILED**: Sync job failed with errors
- **PARTIAL**: Sync job completed with some failures (some items synced, some failed)
- **CANCELLED**: Sync job cancelled by user

---

## Journey Map Matrix

| Journey ID | Title | Persona | Steps | Success Rate Target | Performance Target |
|------------|-------|---------|-------|---------------------|-------------------|
| JOURNEY-MP-001 | Connect to External Marketplace | Data Product Owner, Tenant Admin | 10 | 95%+ | < 2 minutes |
| JOURNEY-MP-002 | Publish Asset to Marketplace | Data Product Owner | 15 | 95%+ | < 10 minutes |
| JOURNEY-MP-003 | Import Dataset from Marketplace | Data Consumer | 15 | 95%+ | < 15 minutes (METADATA_ONLY) |
| JOURNEY-MP-004 | Sync Assets Bidirectionally | Data Product Owner | 12 | 90%+ | < 15 minutes |
| JOURNEY-MP-005 | Schedule Automatic Sync | Data Product Owner, Tenant Admin | 13 | 95%+ | < 2 minutes |
| JOURNEY-MP-006 | Manage Marketplace Mappings | Data Product Owner, Tenant Admin | 8 | 100% | < 1 minute |
| JOURNEY-MP-007 | Monitor Sync Jobs | Data Product Owner, Data Consumer, Tenant Admin | 9 | 100% | < 1 minute |

---

## Additional Resources

- **Use Cases**: `docs/MARKETPLACE_USE_CASES.md` - Complete use cases documentation
- **Framework Architecture**: `docs/MARKETPLACE_INTEGRATION_FRAMEWORK.md` - Architecture documentation
- **Connector Development Guide**: `docs/MARKETPLACE_CONNECTOR_DEVELOPMENT_GUIDE.md` - Connector implementation guide
- **API Reference**: `docs/MARKETPLACE_API_REFERENCE.md` - Complete API documentation

---

**Last Updated**: 2026-03-22
**Version**: 1.0.0

---

## Connection Validation


### Implementation Summary


## Overview

Successfully implemented task 9.10.1.3.4.2 "Implement connection validation rules" with comprehensive, engineering-grade implementation following all best practices.

## Implementation Status

✅ **COMPLETE** - All methods implemented, tested, and validated

## Implemented Methods

### 1. `validate_connection_config()`

**Location**: `hub/apps/integrations/business_rules.py:1501`

**Purpose**: Validates marketplace connection configuration before creation/update

**Validations**:
- ✅ Marketplace type is supported (via `MarketplaceConnectorFactory.is_supported()`)
- ✅ Config structure matches marketplace requirements (via `validate_marketplace_config()`)
- ✅ Authentication credentials format (api_key, api_secret, etc. must be non-empty strings)
- ✅ Connection name uniqueness within tenant (with support for update operations)

**Returns**: `ValidationResult` with errors/warnings

### 2. `validate_connection_access()`

**Location**: `hub/apps/integrations/business_rules.py:1655`

**Purpose**: Validates user permissions and tenant access for connection management

**Validations**:
- ✅ User has permission (DATA_PROVIDER or TENANT_ADMIN role, or platform admin)
- ✅ Tenant has marketplace integration enabled (`tenant.can_publish_to_marketplace()`)
- ✅ Resource quotas (max 50 connections per tenant, with 80% warning threshold)

**Returns**: `ValidationResult` with errors/warnings

### 3. `validate_connection_test()`

**Location**: `hub/apps/integrations/business_rules.py:1813`

**Purpose**: Validates connection can be tested and test results are valid

**Validations**:
- ✅ Connection is active
- ✅ Config is valid and decryptable
- ✅ Test results are valid (success/error indicators, latency warnings)

**Returns**: `ValidationResult` with errors/warnings

## Test Coverage

### Unit Tests (`test_connection_validation_rules.py`)

**20+ comprehensive test cases** covering:

1. **validate_connection_config()** (7 tests):
   - Successful validation
   - Invalid marketplace type
   - Invalid config type
   - Empty connection name
   - Name uniqueness (duplicate)
   - Name uniqueness on update
   - Invalid credentials format

2. **validate_connection_access()** (8 tests):
   - Successful validation with DATA_PROVIDER role
   - User not found
   - No permission (missing role)
   - Tenant mismatch
   - Platform admin access
   - Tenant not verified (KYC)
   - Quota exceeded (50 connections)
   - Quota warning (40 connections)

3. **validate_connection_test()** (6 tests):
   - Successful test validation
   - Inactive connection
   - Failed test results
   - High latency warning
   - Invalid config type
   - No test results provided

### Integration Tests (`test_connection_validation_integration.py`)

**6 comprehensive integration tests** covering:

1. **GovernanceService Integration** (3 tests):
   - Permission pattern matches GovernanceService
   - Missing permissions match GovernanceService behavior
   - Platform admin handling matches GovernanceService

2. **TenantService Integration** (3 tests):
   - Tenant verification via TenantService
   - Unverified tenant handling
   - Quota checking with TenantService

## Key Features

### Engineering Best Practices

✅ **No Mocks/Stubs**: All tests use real services and models
✅ **Root Cause Fixes**: Proper error handling and validation
✅ **DRY Principle**: Reusable validation logic
✅ **SOLID Principles**: Single responsibility, proper abstraction
✅ **Clean Code**: Comprehensive error messages with context
✅ **Comprehensive Coverage**: All scenarios tested

### Error Handling

- All methods return `ValidationResult` with detailed errors/warnings
- Comprehensive error messages with context
- Proper exception handling for edge cases
- Detailed `details` dictionary for debugging

### Integration

- Integrates with `GovernanceService` for permission checks
- Integrates with `TenantService` for tenant verification
- Uses `MarketplaceConnectorFactory` for marketplace type validation
- Uses `validate_marketplace_config()` utility for config validation

## Running Tests

### Using Docker Compose (Recommended)

```bash
# Run unit tests
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules --verbosity=2

# Run integration tests
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_integration --verbosity=2

# Run both
./scripts/run_connection_validation_tests.sh
```

### Expected Results

All tests should pass. The implementation:
- Handles all edge cases
- Provides comprehensive error messages
- Follows Django and coding best practices
- Integrates properly with existing services

## Files Modified/Created

### Implementation Files
- `hub/apps/integrations/business_rules.py` - Added 3 validation methods (~400 lines)

### Test Files
- `hub/apps/integrations/tests/test_connection_validation_rules.py` - Unit tests (~450 lines)
- `hub/apps/integrations/tests/test_connection_validation_integration.py` - Integration tests (~290 lines)

### Documentation Files
- `docs/TEST_CONNECTION_VALIDATION_RULES.md` - Test execution guide
- `docs/CONNECTION_VALIDATION_IMPLEMENTATION_SUMMARY.md` - This file

### Scripts
- `scripts/run_connection_validation_tests.sh` - Test runner script
- `scripts/validate_connection_validation_tests.py` - Validation script

## Next Steps

1. ✅ Run tests in docker compose environment
2. ✅ Verify all tests pass
3. ✅ Fix any failures (if any)
4. ✅ Update tasks.md (completed)

## Notes

- All methods follow the existing business rules pattern
- All tests follow the existing test patterns (no mocks/stubs)
- Implementation is production-ready and follows all best practices
- Comprehensive error handling and validation
- Proper integration with existing services


### Validation Rules


This document provides instructions for running and validating the connection validation rules tests.

## Overview

The connection validation rules implementation includes three main validation methods:
1. `validate_connection_config()` - Validates marketplace connection configuration
2. `validate_connection_access()` - Validates user permissions and tenant access
3. `validate_connection_test()` - Validates connection testability and test results

## Test Files

- **Unit Tests**: `hub/apps/integrations/tests/test_connection_validation_rules.py`
- **Integration Tests**: `hub/apps/integrations/tests/test_connection_validation_integration.py`

## Running Tests

### Using Docker Compose (Recommended)

Since services run in Docker Compose, use the following commands:

```bash
# Run unit tests
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules --verbosity=2

# Run integration tests
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_integration --verbosity=2

# Run both test files
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules hub.apps.integrations.tests.test_connection_validation_integration --verbosity=2
```

### Using pytest (if configured)

```bash
# Run unit tests
pytest hub/apps/integrations/tests/test_connection_validation_rules.py -v

# Run integration tests
pytest hub/apps/integrations/tests/test_connection_validation_integration.py -v

# Run with coverage
pytest hub/apps/integrations/tests/test_connection_validation_rules.py --cov=hub.apps.integrations.business_rules --cov-report=html
```

### Using Makefile

```bash
# Run all tests
make test

# Run specific test file
pytest hub/apps/integrations/tests/test_connection_validation_rules.py -v
```

## Test Coverage

### Unit Tests (`test_connection_validation_rules.py`)

The unit tests cover:

1. **validate_connection_config()**:
   - ✅ Successful validation
   - ✅ Invalid marketplace type
   - ✅ Invalid config type
   - ✅ Empty connection name
   - ✅ Name uniqueness (duplicate name)
   - ✅ Name uniqueness on update (should pass)
   - ✅ Invalid credentials format

2. **validate_connection_access()**:
   - ✅ Successful validation with DATA_PROVIDER role
   - ✅ User not found
   - ✅ No permission (missing role)
   - ✅ Tenant mismatch
   - ✅ Platform admin access
   - ✅ Tenant not verified (KYC)
   - ✅ Quota exceeded (50 connections)
   - ✅ Quota warning (40 connections, 80% threshold)

3. **validate_connection_test()**:
   - ✅ Successful test validation
   - ✅ Inactive connection
   - ✅ Failed test results
   - ✅ High latency warning
   - ✅ Invalid config type
   - ✅ No test results provided

### Integration Tests (`test_connection_validation_integration.py`)

The integration tests cover:

1. **GovernanceService Integration**:
   - ✅ Permission pattern matches GovernanceService
   - ✅ Missing permissions match GovernanceService behavior
   - ✅ Platform admin handling matches GovernanceService

2. **TenantService Integration**:
   - ✅ Tenant verification via TenantService
   - ✅ Unverified tenant handling
   - ✅ Quota checking with TenantService

## Expected Test Results

All tests should pass. The tests are designed to:
- Use real services (no mocks/stubs)
- Test actual behavior, not implementation details
- Follow engineering best practices
- Fix root causes, not symptoms

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure Django is properly installed and configured
2. **Database Errors**: Ensure PostgreSQL is running and migrations are applied
3. **Permission Errors**: Ensure test user has proper roles assigned
4. **Encryption Errors**: Ensure connection configs are properly encrypted/decrypted

### Debugging Failed Tests

```bash
# Run with verbose output
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules --verbosity=3

# Run specific test
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules.ConnectionValidationRulesTest.test_validate_connection_config_success --verbosity=2

# Run with pdb debugger
docker compose exec web python manage.py test hub.apps.integrations.tests.test_connection_validation_rules --pdb
```

## Implementation Details

### Method Signatures

```python
def validate_connection_config(
    self,
    marketplace_type: str,
    config: Dict[str, Any],
    connection_name: str,
    tenant_id: str,
    connection_id: Optional[str] = None
) -> ValidationResult

def validate_connection_access(
    self,
    user_id: str,
    tenant_id: str
) -> ValidationResult

def validate_connection_test(
    self,
    connection: MarketplaceConnection,
    test_results: Optional[Dict[str, Any]] = None
) -> ValidationResult
```

### Validation Rules

1. **Connection Config**:
   - Marketplace type must be supported by MarketplaceConnectorFactory
   - Config must be a dictionary
   - Config structure must match marketplace requirements
   - Credentials must be non-empty strings
   - Connection name must be unique within tenant

2. **Connection Access**:
   - User must have DATA_PROVIDER or TENANT_ADMIN role
   - Tenant must have VERIFIED KYC status and ACTIVE status
   - Tenant must not exceed max connections limit (50 default)

3. **Connection Test**:
   - Connection must be active
   - Config must be valid and decryptable
   - Test results must indicate success/failure
   - High latency (>5000ms) generates warning

## Next Steps

After running tests:
1. Review any failures and fix root causes
2. Ensure all tests pass
3. Update tasks.md to mark implementation complete
4. Document any edge cases discovered


---

## Connector Development (Detailed)


Complete guide for developing marketplace connectors following the metadata-first architecture pattern.

**Last Updated**: 2026-03-22
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

**Last Updated**: 2026-03-22
**Version**: 1.0.0

