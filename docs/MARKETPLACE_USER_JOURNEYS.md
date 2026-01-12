# Marketplace Integration User Journeys

Complete user journey maps for marketplace integration operations.

**Last Updated**: 2026-01-10
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

**Last Updated**: 2026-01-10
**Version**: 1.0.0
