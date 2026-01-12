# Connector End-to-End Testing Guide

## Overview

This guide provides comprehensive documentation for end-to-end (E2E) testing of marketplace connectors in the Data Interoperability Hub. E2E tests validate the complete workflow from connection establishment through asset creation and verification, using **real marketplace instances and real connections** - no mocks or stubs.

### Purpose

E2E tests verify that:
- Connectors can successfully connect to external marketplace instances
- Discovery mechanisms correctly retrieve listings and metadata
- Workflows orchestrate asset creation correctly
- Assets are created with proper contracts (ODPS/ODCS) and external resource references
- The complete integration pipeline works end-to-end

### What E2E Tests Validate

1. **Connection Layer**: Credential validation, connection establishment, circuit breaker behavior
2. **Discovery Layer**: Listing retrieval, metadata extraction, resource identification
3. **Workflow Layer**: Orchestration, parallel processing, error handling
4. **Asset Creation Layer**: Asset creation, contract generation, external resource mapping
5. **Verification Layer**: Data integrity, contract completeness, reference accuracy

## Prerequisites

### Environment Variables

#### dados.gov.br Connector

Required environment variables:
- `DADOS_GOV_BR_API_KEY`: JWT Bearer token for dados.gov.br API authentication
  - Alternative (deprecated): `CKAN_DADOS_GOV_BR_API_KEY`
  - Format: JWT token string (e.g., `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`)

#### Snowflake Connector

Required environment variables:
- `SNOWFLAKE_ACCOUNT`: Snowflake account identifier (e.g., `WCGKMGD-XC16102` or `LT43750.us-east-1`)
- `SNOWFLAKE_USER`: Snowflake username
- `SNOWFLAKE_TOKEN`: Programmatic Access Token (PAT) for OAuth authentication
- `SNOWFLAKE_WAREHOUSE`: (Optional) Snowflake warehouse name
- `SNOWFLAKE_ROLE`: (Optional) Snowflake role name
- `SNOWFLAKE_DATABASE`: (Optional) Snowflake database name

### Database Setup

- Database migrations must be applied:
  ```bash
  docker compose exec api-service python hub/manage.py migrate
  ```

- At least one tenant must exist in the database
- At least one user must exist in the database (preferably with tenant association)

### Service Dependencies

All required services must be running:

```bash
# Check service status
docker compose ps

# Required services:
# - api-service (Django application)
# - redis (cache, channels, events)
# - semantic-service (for semantic mapping, if enabled)
```

### Network Access

- Outbound HTTPS access to marketplace instances:
  - `https://dados.gov.br` (dados.gov.br connector)
  - `https://*.snowflakecomputing.com` (Snowflake connector)
- Firewall rules must allow outbound HTTPS connections
- DNS resolution must work correctly

## Test Plan Structure

E2E tests follow a structured four-phase approach:

### Phase 1: Connection Testing

**Objective**: Verify connectors can establish connections to marketplace instances.

**What is tested**:
- Credential validation
- Connection establishment
- Connection test method (`test_connection()`)
- Error handling for invalid credentials
- Circuit breaker behavior (if applicable)

**Success Criteria**:
- Connection test returns `True`
- No connection errors or authentication failures
- Proper error messages for invalid credentials

### Phase 2: Discovery Testing

**Objective**: Verify connectors can discover listings and extract metadata.

**What is tested**:
- Listing discovery (`list_listings()`)
- Metadata extraction (title, description, resources)
- Resource identification (URLs, download links)
- Limit parameter handling
- Metadata-first pattern (no assets created during discovery)

**Success Criteria**:
- Listings are discovered successfully
- Listing metadata is complete (title, marketplace_id, marketplace_type)
- Resources have external URLs or download links
- No assets are created during discovery phase

### Phase 3: Asset Creation Testing

**Objective**: Verify complete workflow from sync job creation to asset creation.

**What is tested**:
- Sync job creation (`sync_from_marketplace()`)
- Workflow orchestration (`marketplace_sync_pull` workflow)
- Asset creation with proper source metadata
- Contract creation (ODPS and ODCS contracts)
- External resource reference creation
- Workflow completion status

**Success Criteria**:
- Sync job is created successfully
- Workflow completes (COMPLETED or FAILED with proper error)
- Assets are created with `source_type=FEDERATED`
- Each asset has ODPS and ODCS contracts
- Each asset has external resource references
- Asset metadata includes sync job ID and listing information

### Phase 4: Data Verification

**Objective**: Verify data integrity and completeness of created assets.

**What is tested**:
- Asset metadata completeness
- Contract structure and content
- External resource reference accuracy
- Asset status (DRAFT or ACTIVE)
- Data strategy compliance (METADATA_ONLY, DOWNLOAD_SELECTIVE, DOWNLOAD_ALL)

**Success Criteria**:
- All assets have complete metadata
- Contracts are properly structured and linked
- External resource references point to valid URLs
- Asset status is appropriate for the workflow stage
- Data strategy is correctly applied

## Detailed Test Scenarios

### Test 1: dados.gov.br Connection & Discovery

**Purpose**: Verify dados.gov.br connector can connect and discover listings.

**Steps**:
1. Create `DadosGovBrConnector` instance with credentials
2. Call `test_connection()` - should return `True`
3. Call `list_listings(limit=5)` - should return list of listings
4. Verify listing structure (marketplace_id, title, marketplace_type)
5. Verify resources have external URLs

**Expected Results**:
- Connection successful
- 5 or fewer listings returned
- Each listing has required fields
- Resources have URLs

**Command**:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source dados_gov_br \
  --limit 5 \
  --no-wait \
  --no-verify-assets
```

**Pytest**:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E::test_connection_and_discovery \
  -v
```

### Test 2: dados.gov.br Asset Creation via Workflow

**Purpose**: Verify complete workflow creates assets with contracts and references.

**Steps**:
1. Create `MarketplaceConnection` for dados.gov.br
2. Call `sync_from_marketplace()` with limit=3
3. Wait for workflow completion (timeout: 10 minutes)
4. Verify sync job status is COMPLETED
5. Verify assets were created (check via sync_job_id or mappings)
6. For each asset:
   - Verify ODPS contract exists
   - Verify ODCS contract exists
   - Verify external resource references exist

**Expected Results**:
- Sync job created successfully
- Workflow completes within timeout
- Assets created (1-3 assets, depending on discovered listings)
- Each asset has ODPS and ODCS contracts
- Each asset has external resource references

**Command**:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source dados_gov_br \
  --limit 3 \
  --wait \
  --verify-assets \
  --data-strategy METADATA_ONLY
```

**Pytest**:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E::test_asset_creation_via_workflow \
  -v
```

### Test 3: Snowflake Connection & Discovery

**Purpose**: Verify Snowflake connector can connect and discover listings.

**Steps**:
1. Create `SnowflakeConnector` instance with credentials
2. Call `test_connection()` - should return `True`
3. Call `list_listings(limit=5)` - should return list of listings
4. Verify listing structure (marketplace_id, title, marketplace_type)
5. Verify resources have external references

**Expected Results**:
- Connection successful
- 5 or fewer listings returned
- Each listing has required fields
- Resources have external references

**Command**:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source snowflake \
  --limit 5 \
  --no-wait \
  --no-verify-assets
```

**Pytest**:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestSnowflakeConnectorE2E::test_connection_and_discovery \
  -v
```

### Test 4: Snowflake Asset Creation via Workflow

**Purpose**: Verify complete workflow creates assets with contracts and references.

**Steps**:
1. Create `MarketplaceConnection` for Snowflake
2. Call `sync_from_marketplace()` with limit=3
3. Wait for workflow completion (timeout: 10 minutes)
4. Verify sync job status is COMPLETED
5. Verify assets were created
6. For each asset:
   - Verify ODPS contract exists
   - Verify ODCS contract exists
   - Verify external resource references exist

**Expected Results**:
- Sync job created successfully
- Workflow completes within timeout
- Assets created
- Each asset has ODPS and ODCS contracts
- Each asset has external resource references

**Command**:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source snowflake \
  --limit 3 \
  --wait \
  --verify-assets \
  --data-strategy METADATA_ONLY
```

**Pytest**:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestSnowflakeConnectorE2E::test_asset_creation_via_workflow \
  -v
```

### Test 5: Selective Resource Download (dados.gov.br)

**Purpose**: Verify selective resource download workflow.

**Steps**:
1. Create assets via workflow with `METADATA_ONLY` strategy
2. Wait for workflow completion
3. Get external resource references for created asset
4. Call `download_resource()` for a specific resource
5. Verify file was created (if download succeeds)

**Expected Results**:
- Assets created successfully
- External resource references exist
- Resource download may succeed or fail (network/permissions dependent)
- If download succeeds, file is created in system

**Note**: Resource download may fail for various reasons (network, permissions, resource type). This is acceptable - the test validates the workflow, not the download itself.

**Command**:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source dados_gov_br \
  --limit 1 \
  --wait \
  --verify-assets \
  --data-strategy DOWNLOAD_SELECTIVE \
  --download-resources "resource_id_1,resource_id_2"
```

**Pytest**:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E::test_selective_resource_download \
  -v
```

### Test 6: Asset Activation Workflow

**Purpose**: Verify asset activation workflow.

**Steps**:
1. Create assets via workflow with `METADATA_ONLY` strategy
2. Wait for workflow completion
3. Verify asset is in DRAFT status (or ACTIVE if auto-activated)
4. If DRAFT, trigger asset activation workflow
5. Verify asset status after activation attempt

**Expected Results**:
- Assets created successfully
- Asset is in DRAFT or ACTIVE status
- Activation may succeed or fail (depends on contract validation)
- If activation succeeds, asset moves to ACTIVE status

**Note**: Activation may fail if contracts are not validated or checks fail. This is acceptable - the test validates the workflow, not the activation itself.

**Command**:
```bash
# Asset activation is tested via pytest, not management command
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E::test_asset_activation_workflow \
  -v
```

## Verification Checklist

### Connection Level

- [ ] Connection test succeeds (`test_connection()` returns `True`)
- [ ] Credentials are validated before connection attempt
- [ ] Proper error messages for invalid credentials
- [ ] Circuit breaker behaves correctly (if applicable)
- [ ] Connection errors are handled gracefully

### Discovery Level

- [ ] Listings are discovered successfully (`list_listings()` returns list)
- [ ] Listing metadata is complete:
  - [ ] `marketplace_id` is present
  - [ ] `title` is present
  - [ ] `marketplace_type` is correct
  - [ ] `description` is present (if available)
- [ ] Resources have external references:
  - [ ] `url` or `download_url` is present
  - [ ] Resource metadata is complete
- [ ] Limit parameter is respected
- [ ] No assets are created during discovery (metadata-first pattern)

### Asset Creation Level

- [ ] Sync job is created successfully (`MarketplaceSyncJob` record exists)
- [ ] Workflow is triggered (`workflow_instance_id` in sync job metadata)
- [ ] Workflow completes (status: COMPLETED or FAILED with proper error)
- [ ] Assets are created:
  - [ ] `source_type` is `FEDERATED`
  - [ ] `source_metadata` includes sync job ID
  - [ ] `source_metadata` includes listing information
- [ ] Contracts are created:
  - [ ] ODPS contract exists (`original_spec_type=ODPS`)
  - [ ] ODCS contract exists (`original_spec_type=ODCS`)
  - [ ] Contracts are linked to assets
- [ ] External resource references are created:
  - [ ] `ExternalResourceReference` records exist for each resource
  - [ ] References are linked to assets
  - [ ] Resource IDs and URLs are correct

### Metadata Level

- [ ] Asset names are set correctly (from listing title)
- [ ] Asset descriptions are set correctly (from listing description)
- [ ] Source metadata includes:
  - [ ] Sync job ID
  - [ ] Listing ID
  - [ ] Marketplace type
  - [ ] Connection ID
- [ ] External resource URLs are accessible (or at least valid format)

### Workflow Level

- [ ] Workflow progress is tracked correctly
- [ ] Workflow steps execute in correct order
- [ ] Error handling works correctly:
  - [ ] Workflow fails gracefully on errors
  - [ ] Error messages are logged
  - [ ] Sync job status reflects workflow status
- [ ] Workflow completion is detected correctly
- [ ] Timeout handling works (workflow times out if stuck)

## Troubleshooting Guide

### Connection Failures

#### Symptom: Connection test fails with authentication error

**Possible Causes**:
- Invalid or expired credentials
- Incorrect environment variable name
- Credentials not loaded correctly

**Resolution Steps**:
1. Verify environment variables are set:
   ```bash
   docker compose exec api-service env | grep -E "DADOS_GOV_BR_API_KEY|SNOWFLAKE"
   ```
2. Check credential format:
   - dados.gov.br: JWT token string
   - Snowflake: Account identifier, username, PAT token
3. Regenerate credentials if expired
4. Verify credentials have correct permissions in marketplace instance

#### Symptom: Connection test fails with network error

**Possible Causes**:
- Network connectivity issues
- Firewall blocking outbound HTTPS
- DNS resolution failure
- Marketplace instance is down

**Resolution Steps**:
1. Test network connectivity:
   ```bash
   # For dados.gov.br
   curl https://dados.gov.br/v3/api-docs

   # For Snowflake (check account URL)
   curl https://WCGKMGD-XC16102.snowflakecomputing.com
   ```
2. Check firewall rules allow outbound HTTPS
3. Verify DNS resolution:
   ```bash
   nslookup dados.gov.br
   nslookup WCGKMGD-XC16102.snowflakecomputing.com
   ```
4. Check marketplace instance status page

#### Symptom: Snowflake connection fails with "Invalid OAuth access token"

**Possible Causes**:
- PAT token is expired or invalid
- Account-level security policies blocking PATs
- Network policy restrictions
- Role permissions issues

**Resolution Steps**:
1. Verify PAT token is not expired (check Snowflake UI)
2. Check Snowflake account settings:
   ```sql
   -- Check if ACCOUNTADMIN role is blocked
   SHOW PARAMETERS LIKE 'OAUTH_ADD_PRIVILEGED_ROLES_TO_BLOCKED_LIST';

   -- If blocked, unblock (requires ACCOUNTADMIN)
   ALTER ACCOUNT SET OAUTH_ADD_PRIVILEGED_ROLES_TO_BLOCKED_LIST = FALSE;
   ```
3. Check network policy:
   ```sql
   -- Check network policy
   SHOW NETWORK POLICIES;

   -- If network policy exists, allow bypass or add IP to whitelist
   ```
4. Verify PAT has correct permissions
5. Contact Snowflake Support if issue persists (may be account-level restriction)

### Discovery Failures

#### Symptom: No listings discovered

**Possible Causes**:
- API endpoint changed
- Rate limiting
- Filter parameters too restrictive
- Marketplace instance has no listings

**Resolution Steps**:
1. Test API endpoint directly:
   ```bash
   # For dados.gov.br (Swagger API)
   curl -H "Authorization: Bearer $DADOS_GOV_BR_API_KEY" \
     https://dados.gov.br/api/datasets?limit=5
   ```
2. Check rate limiting (may need to wait)
3. Verify filter parameters are correct
4. Check marketplace instance has listings available

#### Symptom: Listings discovered but missing metadata

**Possible Causes**:
- API response format changed
- Connector parsing logic needs update
- Marketplace instance returns incomplete data

**Resolution Steps**:
1. Inspect raw API response:
   ```bash
   curl -H "Authorization: Bearer $DADOS_GOV_BR_API_KEY" \
     https://dados.gov.br/api/datasets?limit=1 | jq
   ```
2. Check connector parsing logic matches API response format
3. Update connector if API format changed
4. Report issue if marketplace instance returns incomplete data

### Asset Creation Failures

#### Symptom: Workflow fails to start

**Possible Causes**:
- Workflow engine not initialized
- Redis unavailable
- Workflow registry not configured

**Resolution Steps**:
1. Check Redis is running:
   ```bash
   docker compose ps redis
   docker compose exec api-service python -c "import redis; r=redis.Redis(host='redis', port=6379); r.ping()"
   ```
2. Check workflow engine logs:
   ```bash
   docker compose logs api-service | grep -i workflow
   ```
3. Verify workflow is registered:
   ```bash
   docker compose exec api-service python hub/manage.py shell
   >>> from hub.apps.orchestration.registry import WorkflowRegistry
   >>> registry = WorkflowRegistry()
   >>> registry.list_workflows()
   ```

#### Symptom: Workflow completes but no assets created

**Possible Causes**:
- Workflow failed silently
- Asset creation logic has errors
- Database transaction rolled back
- Duplicate mapping detected (workflow skipped)

**Resolution Steps**:
1. Check workflow status:
   ```bash
   docker compose exec api-service python hub/manage.py shell
   >>> from hub.apps.orchestration.models import WorkflowInstance
   >>> wi = WorkflowInstance.objects.latest('created_at')
   >>> print(wi.status, wi.error_message)
   ```
2. Check workflow state for errors:
   ```python
   >>> print(wi.state)  # Check for error details
   ```
3. Check sync job status:
   ```python
   >>> from hub.apps.integrations.models import MarketplaceSyncJob
   >>> sj = MarketplaceSyncJob.objects.latest('created_at')
   >>> print(sj.status, sj.metadata)
   ```
4. Check for duplicate mappings:
   ```python
   >>> from hub.apps.integrations.models import MarketplaceMapping
   >>> mappings = MarketplaceMapping.objects.filter(connection=sj.connection)
   >>> print(mappings.count())
   ```
5. Review workflow logs for errors

#### Symptom: Assets created but missing contracts

**Possible Causes**:
- Contract creation logic failed
- Schema validation failed
- Semantic mapping failed (if enabled)

**Resolution Steps**:
1. Check asset contracts:
   ```python
   >>> from hub.apps.assets.models import Asset
   >>> asset = Asset.objects.latest('created_at')
   >>> print(asset.contracts.count())
   >>> print(asset.contracts.all())
   ```
2. Check contract creation logs:
   ```bash
   docker compose logs api-service | grep -i contract
   ```
3. Check semantic service (if enabled):
   ```bash
   docker compose ps semantic-service
   docker compose logs semantic-service | tail -50
   ```
4. Review contract creation logic in `create_federated_asset_with_contracts()`

#### Symptom: Assets created but missing external resource references

**Possible Causes**:
- Resource reference creation logic failed
- Resources not included in discovery
- Resource metadata incomplete

**Resolution Steps**:
1. Check external resource references:
   ```python
   >>> from hub.apps.assets.models import ExternalResourceReference
   >>> refs = ExternalResourceReference.objects.filter(asset=asset)
   >>> print(refs.count())
   >>> print(refs.all())
   ```
2. Check listing resources:
   ```python
   >>> print(asset.source_metadata.get('resources', []))
   ```
3. Review resource reference creation logic
4. Verify resources were included in sync options (`include_resources=True`)

### Contract Creation Failures

#### Symptom: Contracts not created

**Possible Causes**:
- Contract creation logic has errors
- Schema validation failed
- Required fields missing

**Resolution Steps**:
1. Check contract creation logs:
   ```bash
   docker compose logs api-service | grep -i "create.*contract"
   ```
2. Review `create_federated_asset_with_contracts()` method
3. Check asset metadata completeness
4. Verify schema validation logic

#### Symptom: Contracts created but invalid

**Possible Causes**:
- Schema validation logic incorrect
- Contract structure doesn't match schema
- Required fields missing

**Resolution Steps**:
1. Inspect contract structure:
   ```python
   >>> contract = asset.contracts.first()
   >>> print(contract.spec)
   >>> print(contract.original_spec_type)
   ```
2. Validate contract against schema
3. Review contract creation logic
4. Check semantic mapping (if enabled)

## Running Tests

### Running E2E Tests via Pytest

Run all E2E tests:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py \
  -v \
  -m integration
```

Run specific test class:
```bash
# dados.gov.br tests
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E \
  -v

# Snowflake tests
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestSnowflakeConnectorE2E \
  -v
```

Run specific test:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E::test_connection_and_discovery \
  -v
```

### Running Manual Tests via Management Command

Test both connectors:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source both \
  --limit 5 \
  --wait \
  --verify-assets
```

Test only dados.gov.br:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source dados_gov_br \
  --limit 10 \
  --wait \
  --verify-assets \
  --data-strategy METADATA_ONLY
```

Test Snowflake with selective download:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source snowflake \
  --limit 3 \
  --wait \
  --verify-assets \
  --data-strategy DOWNLOAD_SELECTIVE \
  --download-resources "res1,res2"
```

Test without waiting for workflow:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source dados_gov_br \
  --limit 5 \
  --no-wait \
  --no-verify-assets
```

Test with custom tenant and user:
```bash
docker compose exec api-service python hub/manage.py test_connectors_e2e \
  --source dados_gov_br \
  --tenant my-tenant-slug \
  --user admin@example.com \
  --limit 5
```

### Interpreting Test Results

#### Pytest Output

**Passing Test**:
```
hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E::test_connection_and_discovery PASSED
```

**Skipped Test** (missing credentials):
```
hub/apps/integrations/tests/test_connectors_e2e.py::TestSnowflakeConnectorE2E::test_connection_and_discovery SKIPPED [1] DADOS_GOV_BR_API_KEY not set - skipping E2E tests
```

**Failed Test**:
```
hub/apps/integrations/tests/test_connectors_e2e.py::TestDadosGovBrConnectorE2E::test_connection_and_discovery FAILED
...
AssertionError: Connection test should succeed
```

#### Management Command Output

**Success**:
```
Marketplace Connector E2E Testing
✓ Tenant: Debug Tenant (uuid)
✓ User: debug@example.com (uuid)

Testing: DADOS_GOV_BR
1. Testing connection...
   ✓ Connection successful
2. Discovering listings (limit: 5)...
   ✓ Discovered 5 listings
3. Syncing from marketplace...
   ✓ Workflow completed successfully
   ✓ Sync job completed: COMPLETED
4. Verifying asset creation...
   ✓ Asset uuid: "Title" (ODPS: 1, ODCS: 1, Resources: 2)
   ✓ All 5 asset(s) verified successfully

Overall Summary
✓ DADOS_GOV_BR: PASSED
  - Connection tested: True
  - Sync status: COMPLETED
  - Assets created: 5
  - Assets verified: True
✓ All tests PASSED
```

**Failure**:
```
Testing: SNOWFLAKE
1. Testing connection...
   ✗ Connection failed: Invalid OAuth access token

Overall Summary
✗ SNOWFLAKE: FAILED
  - Connection tested: False
  - Error: Invalid OAuth access token
✗ Some tests FAILED
```

## Best Practices

### Use Real Connections

**Always use real marketplace instances and real connections** - no mocks or stubs of connector behavior. This ensures tests validate actual integration behavior.

**Rationale**:
- Mocks can hide integration issues
- Real connections catch API changes early
- Tests validate actual production behavior

**Exception**: Unit tests may use mocks for isolated component testing, but E2E tests must use real connections.

### Test Root Causes, Not Symptoms

When tests fail, investigate and fix root causes, not just symptoms.

**Example**:
- ❌ **Symptom Fix**: Catch exception and skip test
- ✅ **Root Cause Fix**: Fix connection logic, credential handling, or error propagation

**Approach**:
1. Identify the root cause of the failure
2. Fix the underlying issue
3. Verify the fix with tests
4. Document the fix and prevention measures

### Clean Up Test Data Properly

Tests should clean up created data to avoid conflicts and database bloat.

**Best Practices**:
- Use `tearDown()` or `tearDownClass()` to clean up
- Delete created sync jobs, connections, and assets
- Use unique identifiers to avoid conflicts
- Consider using database transactions for test isolation

**Example**:
```python
def tearDown(self):
    """Clean up test data"""
    # Delete created sync jobs
    for sync_job in self.created_sync_jobs:
        sync_job.delete()

    # Delete created connections
    for connection in self.created_connections:
        connection.delete()

    # Delete created assets (if not needed for verification)
    # Note: Assets may be kept for manual inspection
```

### Handle Edge Cases Gracefully

Tests should handle edge cases gracefully without failing unnecessarily.

**Edge Cases to Handle**:
- Missing credentials (skip test with clear message)
- Network failures (retry or skip with clear message)
- Empty results (verify gracefully)
- Partial failures (verify what succeeded)
- Timeouts (handle with appropriate timeout values)

**Example**:
```python
try:
    connector = DadosGovBrConnector(...)
    connection_result = connector.test_connection()
except (ValueError, ConnectionError) as e:
    # Handle authentication failures by skipping
    handle_auth_failure(e)
    raise
```

### Use Appropriate Timeouts

E2E tests involve real network calls and workflows, which can take time.

**Best Practices**:
- Use appropriate timeouts for workflow completion (default: 10 minutes)
- Use shorter timeouts for connection tests (default: 30 seconds)
- Make timeouts configurable
- Log timeout events for debugging

**Example**:
```python
workflow_instance = self._wait_for_workflow_completion(
    workflow_instance_id,
    timeout=600  # 10 minutes for real sync
)
```

### Verify Complete Workflows

E2E tests should verify complete workflows, not just individual steps.

**Complete Workflow Verification**:
1. Connection establishment
2. Discovery of listings
3. Workflow orchestration
4. Asset creation
5. Contract creation
6. External resource reference creation
7. Data integrity verification

**Example**:
```python
def test_complete_workflow(self):
    # 1. Connection
    connector = self._create_connector()
    self.assertTrue(connector.test_connection())

    # 2. Discovery
    listings = connector.list_listings(limit=5)
    self.assertGreater(len(listings), 0)

    # 3. Sync
    sync_job = self.service.sync_from_marketplace(...)

    # 4. Wait for completion
    workflow_instance = self._wait_for_workflow_completion(...)

    # 5. Verify assets
    assets = self._verify_asset_creation(sync_job)

    # 6. Verify contracts
    for asset in assets:
        self._verify_contracts_created(asset)

    # 7. Verify references
    for asset in assets:
        self._verify_external_resource_references(asset)
```

### Document Test Assumptions

Document assumptions and limitations of E2E tests.

**What to Document**:
- Required environment variables
- Service dependencies
- Network requirements
- Expected test duration
- Known limitations or edge cases

**Example**:
```python
"""
E2E test for dados.gov.br connector.

Requirements:
- DADOS_GOV_BR_API_KEY environment variable (JWT token)
- Network access to https://dados.gov.br
- Redis service running
- Semantic service running (if semantic mapping enabled)

Expected duration: 2-5 minutes per test

Known limitations:
- Tests may fail if API rate limits are exceeded
- Resource downloads may fail due to network/permissions
"""
```

## Additional Resources

- [Marketplace Connector Development Guide](../connectors/DEVELOPMENT.md)
- [Testing Guide](../TESTING_GUIDE.md)
- [Troubleshooting Guide](../TROUBLESHOOTING.md)
- [Runbooks](../RUNBOOKS.md)

## Support

For issues or questions:
1. Check this troubleshooting guide
2. Review test logs: `docker compose logs api-service`
3. Check workflow state: `WorkflowInstance.objects.latest('created_at').state`
4. Review connector implementation: `hub/apps/integrations/connectors/`
5. Open an issue with test logs and error details

