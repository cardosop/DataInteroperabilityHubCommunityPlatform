# Marketplace Integration Use Cases

Complete use cases documentation for the Marketplace Integration Framework.

**Last Updated**: 2026-01-10
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

**Last Updated**: 2026-01-10
**Version**: 1.0.0
