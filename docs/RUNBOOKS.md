# Operational Runbooks

Complete troubleshooting and operational procedures for the Data Interoperability Hub.

## Table of Contents

1. [Normalization Failures](#normalization-failures)
2. [Lineage Issues](#lineage-issues)
3. [Scheduled Ingestion Failures](#scheduled-ingestion-failures)
4. [Prefect Server Issues](#prefect-server-issues)
5. [Prefect Workers Issues](#prefect-workers-issues)
6. [Search Service Issues](#search-service-issues)
7. [Observability Service Issues](#observability-service-issues)
8. [Webhook Service Issues](#webhook-service-issues)
9. [Marketplace Connector Pattern Violations](#marketplace-connector-pattern-violations)
10. [Disaster Recovery](#disaster-recovery)
11. [Backup and Recovery](#backup-and-recovery)

---

## Normalization Failures

### Symptoms
- Contracts fail to normalize
- Normalization status is `NORMALIZATION_FAILED`
- Normalization errors in contract record

### Diagnosis

1. **Check Normalization Errors**:
```python
from hub.apps.contracts.models import Contract

contract = Contract.objects.get(id='<contract-id>')
print(contract.normalization_errors)
print(contract.normalization_warnings)
```

2. **Check Contract JSON Size**:
```python
import json

size_bytes = len(json.dumps(contract.hub_contract_json).encode('utf-8'))
print(f"Contract JSON size: {size_bytes} bytes")
```

3. **Check Prometheus Metrics**:
```bash
curl http://localhost:8000/metrics | grep normalization
```

### Common Issues

#### Issue: Large Contract JSON Size (>1MB)
**Symptoms**: Alert `LargeContractJSONSize` triggered
**Resolution**:
1. Review contract structure for unnecessary data
2. Move large data to external storage
3. Consider splitting contract into multiple contracts

#### Issue: Missing Objects
**Symptoms**: Alert `HighMissingObjectsRate` triggered
**Resolution**:
1. Check ODCS contract structure
2. Verify normalization logic for missing objects
3. Review normalization coverage metrics

#### Issue: Broken Lineage Links
**Symptoms**: Alert `BrokenLineageLinksDetected` triggered
**Resolution**:
1. Check referenced contracts exist
2. Verify contract names/IDs in lineage references
3. Review lineage reference resolution logic

### Resolution Steps

1. **Review Normalization Logs**:
```bash
docker-compose logs api-service | grep -i normalization
```

2. **Test Normalization Manually**:
```python
from hub.apps.contracts.normalization import normalize_contract

result = normalize_contract(raw_contract, format='JSON')
print(result)
```

3. **Fix Contract Data**:
- Update ODCS contract to fix errors
- Re-normalize contract
- Verify normalization status

---

## Lineage Issues

### Symptoms
- Lineage queries timeout
- Broken lineage links detected
- Lineage visualization fails

### Diagnosis

1. **Check Lineage Query Performance**:
```sql
EXPLAIN ANALYZE
SELECT id FROM contracts_contract
WHERE hub_contract_json->'lineage' IS NOT NULL;
```

2. **Check Broken Links**:
```python
from hub.apps.contracts.lineage import LineageReference, resolve_lineage_reference

ref = LineageReference(namespace='ns', name='contract1', model_name='model1')
result = resolve_lineage_reference(ref)
print(result)
```

3. **Check Lineage Indexes**:
```sql
SELECT indexname, idx_scan
FROM pg_stat_user_indexes
WHERE indexname LIKE '%lineage%';
```

### Common Issues

#### Issue: Slow Lineage Queries
**Symptoms**: Lineage queries take >1 second
**Resolution**:
1. Verify GIN indexes exist on lineage JSONB paths
2. Run `VACUUM ANALYZE contracts_contract`
3. Check for missing indexes (see `docs/DATABASE_INDEXES.md`)

#### Issue: Broken Lineage Links
**Symptoms**: Lineage references point to non-existent contracts
**Resolution**:
1. Identify broken links using `contract_broken_lineage_links_total` metric
2. Update lineage references to point to existing contracts
3. Re-normalize affected contracts

### Resolution Steps

1. **Rebuild Lineage Indexes**:
```sql
REINDEX INDEX contracts_hub_contract_json_lineage_gin;
REINDEX INDEX contracts_hub_contract_json_models_lineage_gin;
REINDEX INDEX contracts_hub_contract_json_models_fields_lineage_gin;
```

2. **Fix Broken Links**:
```python
# Update lineage references in contracts
from hub.apps.contracts.models import Contract

contract = Contract.objects.get(id='<contract-id>')
# Update hub_contract_json['lineage'] references
contract.save()
```

---

## Scheduled Ingestion Failures

### Symptoms
- Scheduled ingestion runs fail
- No datasets created
- Prefect workflows fail

### Diagnosis

1. **Check Prefect UI**:
- Navigate to `http://localhost:4200`
- Check workflow runs for failures

2. **Check Scheduled Ingestion Status**:
```python
from hub.apps.scheduled_ingestion.models import ScheduledIngestion, ScheduledIngestionRun

ingestion = ScheduledIngestion.objects.get(id='<id>')
runs = ScheduledIngestionRun.objects.filter(scheduled_ingestion=ingestion).order_by('-created_at')[:10]
for run in runs:
    print(f"{run.status}: {run.error_message}")
```

3. **Check Prometheus Metrics**:
```bash
curl http://localhost:8000/metrics | grep scheduled_ingestion
```

### Common Issues

#### Issue: Prefect Server Connection Failure
**Symptoms**: `PREFECT_API_URL` connection error
**Resolution**:
1. Verify Prefect Server is running: `docker-compose ps prefect-server`
2. Check `PREFECT_API_URL` environment variable
3. Verify network connectivity

#### Issue: Source Connector Failure
**Symptoms**: File discovery or download fails
**Resolution**:
1. Check source credentials
2. Verify source path/URL is accessible
3. Check network connectivity to source

### Resolution Steps

1. **Restart Prefect Integration Service**:
```bash
docker-compose restart prefect-integration-service
```

2. **Manually Trigger Ingestion**:
```python
from hub.apps.scheduled_ingestion.models import ScheduledIngestion

ingestion = ScheduledIngestion.objects.get(id='<id>')
# Trigger manually via API or Prefect UI
```

---

## Prefect Server Issues

### Symptoms
- Prefect Server not responding
- Workflows not executing
- API connection errors

### Diagnosis

1. **Check Prefect Server Health**:
```bash
curl http://localhost:4200/api/health
```

2. **Check Prefect Server Logs**:
```bash
docker-compose logs prefect-server
```

3. **Check Database Connection**:
```bash
docker-compose exec prefect-server psql -U prefect -d prefect -c "SELECT 1;"
```

### Resolution Steps

1. **Restart Prefect Server**:
```bash
docker-compose restart prefect-server
```

2. **Check Database**:
```bash
docker-compose exec postgres psql -U prefect -d prefect -c "\dt"
```

3. **Reset Prefect Server** (if needed):
```bash
docker-compose down prefect-server
docker-compose up -d prefect-server
```

---

## Prefect Workers Issues

### Symptoms
- Workers not processing jobs
- Workflows stuck in "Running" state
- Worker connection errors

### Diagnosis

1. **Check Worker Status**:
```bash
docker-compose ps prefect-worker
```

2. **Check Worker Logs**:
```bash
docker-compose logs prefect-worker
```

3. **Check Worker Connection**:
```bash
docker-compose exec prefect-worker prefect worker status
```

### Resolution Steps

1. **Restart Workers**:
```bash
docker-compose restart prefect-worker
```

2. **Scale Workers**:
```bash
docker-compose up -d --scale prefect-worker=3
```

---

## Search Service Issues

### Symptoms
- Search queries fail
- Search index not updating
- Search results incorrect

### Diagnosis

1. **Check Search Index Status**:
```python
from hub.apps.search.models import SearchIndex

indices = SearchIndex.objects.filter(tenant_id='<tenant-id>')[:10]
for idx in indices:
    print(f"{idx.resource_type} {idx.resource_id}: {idx.indexed_at}")
```

2. **Check Search Query Performance**:
```sql
EXPLAIN ANALYZE
SELECT * FROM search_index
WHERE tenant_id = '<tenant-id>' AND search_vector @@ to_tsquery('english', 'test');
```

### Resolution Steps

1. **Rebuild Search Index**:
```python
from hub.apps.search.tasks import update_search_index

update_search_index.delay(resource_type='CONTRACT', resource_id='<id>')
```

2. **Reindex All Resources**:
```python
from hub.apps.search.tasks import reindex_all_resources

reindex_all_resources.delay()
```

---

## Observability Service Issues

### Symptoms
- Observability metrics not updating
- Dashboards show no data
- Alerts not triggering

### Diagnosis

1. **Check Metrics Endpoint**:
```bash
curl http://localhost:8000/metrics | head -20
```

2. **Check Observability Models**:
```python
from hub.apps.observability.models import DataObservabilityMetric

metrics = DataObservabilityMetric.objects.filter(tenant_id='<tenant-id>')[:10]
for metric in metrics:
    print(f"{metric.recorded_at}: {metric.is_stale}")
```

### Resolution Steps

1. **Restart Observability Service**:
```bash
docker-compose restart observability-service
```

2. **Check Prometheus Scraping**:
```bash
curl http://localhost:9090/api/v1/targets
```

---

## Webhook Service Issues

### Symptoms
- Webhooks not delivering
- Webhook delivery failures
- Webhook retries exhausted

### Diagnosis

1. **Check Webhook Deliveries**:
```python
from hub.apps.webhooks.models import Webhook, WebhookDelivery

webhook = Webhook.objects.get(id='<id>')
deliveries = WebhookDelivery.objects.filter(webhook=webhook).order_by('-created_at')[:10]
for delivery in deliveries:
    print(f"{delivery.status}: {delivery.error_message}")
```

2. **Check Webhook Service Logs**:
```bash
docker-compose logs webhook-service
```

### Resolution Steps

1. **Retry Failed Deliveries**:
```python
from hub.apps.webhooks.tasks import retry_failed_deliveries

retry_failed_deliveries.delay()
```

2. **Restart Webhook Service**:
```bash
docker-compose restart webhook-service
```

---

## Marketplace Connector Pattern Violations

### Symptoms

- Connectors create assets directly instead of returning mappings
- `sync_pull()` downloads data instead of mapping listings only
- `sync_pull()` performs marketplace-specific operations (database creation, subscriptions, snapshots)
- `map_to_hub_asset()` accesses external data sources instead of storing references
- Assets are created during sync instead of being created by workflow
- Slow sync performance (hours instead of seconds)
- High storage usage during initial sync

### Diagnosis

#### 1. Check if Connector Creates Assets in `sync_pull()`

```python
from hub.apps.integrations.models import MarketplaceSyncJob
from hub.apps.assets.models import Asset
from django.utils import timezone
from datetime import timedelta

# Get recent sync job
sync_job = MarketplaceSyncJob.objects.filter(
    direction="PULL",
    created_at__gte=timezone.now() - timedelta(hours=1)
).first()

if sync_job:
    # Count assets created during sync window
    assets_created_during_sync = Asset.objects.filter(
        created_at__gte=sync_job.created_at,
        created_at__lte=sync_job.completed_at if sync_job.completed_at else timezone.now()
    ).count()

    print(f"Assets created during sync: {assets_created_during_sync}")
    print(f"Sync job successful items: {sync_job.successful_items}")

    # If assets created > successful items, connector may be creating assets directly
    if assets_created_during_sync > sync_job.successful_items:
        print("⚠️  WARNING: Connector may be creating assets directly in sync_pull()")
```

#### 2. Check if `sync_pull()` Returns Mappings Only

```python
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection

# Get connector
connection = MarketplaceConnection.objects.get(id="<connection-id>")
connector = MarketplaceConnectorFactory.create_connector(connection)

# Execute sync_pull
result = connector.sync_pull(options={"limit": 10, "dry_run": True})

# Verify result structure
print(f"Result type: {type(result)}")
print(f"Has metadata: {'metadata' in result.metadata if hasattr(result, 'metadata') else False}")
print(f"Has mappings: {'mappings' in result.metadata if hasattr(result, 'metadata') else False}")

if hasattr(result, 'metadata') and 'mappings' in result.metadata:
    mappings = result.metadata['mappings']
    print(f"Number of mappings: {len(mappings)}")
    if mappings:
        print(f"First mapping type: {type(mappings[0])}")
        print(f"First mapping keys: {mappings[0].keys() if isinstance(mappings[0], dict) else 'Not a dict'}")

    # Check for asset IDs (should NOT be present)
    if 'asset_ids' in result.metadata:
        print("❌ ERROR: sync_pull() returns asset_ids (should return mappings only)")

    # Check for contract IDs (should NOT be present)
    if 'contract_ids' in result.metadata:
        print("❌ ERROR: sync_pull() returns contract_ids (should return mappings only)")
else:
    print("❌ ERROR: sync_pull() does not return mappings in metadata")
```

#### 3. Check if `sync_pull()` Downloads Data

```python
import os
import tempfile
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection

# Get connector
connection = MarketplaceConnection.objects.get(id="<connection-id>")
connector = MarketplaceConnectorFactory.create_connector(connection)

# Track file creation during sync_pull
initial_files = set()
temp_dir = tempfile.gettempdir()
for root, dirs, files in os.walk(temp_dir):
    for file in files:
        initial_files.add(os.path.join(root, file))

# Execute sync_pull
result = connector.sync_pull(options={"limit": 10, "dry_run": True})

# Check for new files
new_files = set()
for root, dirs, files in os.walk(temp_dir):
    for file in files:
        file_path = os.path.join(root, file)
        if file_path not in initial_files:
            new_files.add(file_path)

if new_files:
    print(f"⚠️  WARNING: {len(new_files)} files created during sync_pull()")
    print("Files created:")
    for file_path in list(new_files)[:10]:  # Show first 10
        print(f"  - {file_path}")
    print("❌ ERROR: sync_pull() should not download data")
else:
    print("✅ OK: sync_pull() does not download data")
```

#### 4. Check if `map_to_hub_asset()` Accesses External Data Sources

```python
import httpx
from unittest.mock import patch
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceListing
from hub.apps.integrations.base import MarketplaceType

# Get connector
connection = MarketplaceConnection.objects.get(id="<connection-id>")
connector = MarketplaceConnectorFactory.create_connector(connection)

# Create test listing
listing = MarketplaceListing(
    marketplace_id="test-listing",
    marketplace_type=MarketplaceType.CKAN_INSTANCE,
    title="Test Listing"
)

# Track HTTP requests
http_requests = []

def track_request(*args, **kwargs):
    http_requests.append((args, kwargs))
    return httpx.get(*args, **kwargs)

# Execute map_to_hub_asset with HTTP tracking
with patch('httpx.get', side_effect=track_request):
    mapping = connector.map_to_hub_asset(listing)

if http_requests:
    print(f"⚠️  WARNING: {len(http_requests)} HTTP requests made during map_to_hub_asset()")
    print("HTTP requests:")
    for args, kwargs in http_requests[:5]:  # Show first 5
        print(f"  - {args[0] if args else 'N/A'}")
    print("❌ ERROR: map_to_hub_asset() should not access external data sources")
else:
    print("✅ OK: map_to_hub_asset() does not access external data sources")
```

#### 5. Run Pattern Verification Tests

```bash
# Run pattern verification tests for all connectors
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connector_pattern.py \
  -v \
  --tb=short

# Run tests for specific connector
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullDoesNotCreateAssets::test_ckan_sync_pull_does_not_create_assets \
  -v \
  --tb=short
```

### Common Issues

#### Issue: Connector Creates Assets in `sync_pull()`

**Symptoms**:
- Assets are created during sync instead of after workflow execution
- `sync_pull()` returns asset IDs instead of mappings
- Sync performance is slow (assets created synchronously)

**Root Cause**:
Connector is calling `create_federated_asset_with_contracts()` or `Asset.objects.create()` directly in `sync_pull()`.

**Resolution**:
1. Refactor `sync_pull()` to return mappings only:
   ```python
   # Wrong
   def sync_pull(self, ...):
       for listing in listings:
           asset = create_federated_asset_with_contracts(...)  # ❌

   # Correct
   def sync_pull(self, ...):
       mappings = []
       for listing in listings:
           mapping = self.map_to_hub_asset(listing)  # ✅
           mappings.append(mapping)
       return SyncResult(metadata={"mappings": [m.__dict__ for m in mappings]})
   ```

2. Verify workflow handles asset creation:
   - Check `hub/apps/orchestration/workflows/marketplace_sync.py`
   - Verify `create_federated_assets_task` calls `create_federated_asset_with_contracts()`

#### Issue: Connector Downloads Data in `sync_pull()`

**Symptoms**:
- Files are created during sync
- High storage usage during initial sync
- Slow sync performance (downloading data synchronously)

**Root Cause**:
Connector is calling `download_resource()` or file download methods in `sync_pull()`.

**Resolution**:
1. Remove data download logic from `sync_pull()`:
   ```python
   # Wrong
   def sync_pull(self, ...):
       for listing in listings:
           for resource in listing.resources:
               download_path = self.download_resource(resource.id, "/tmp/data.csv")  # ❌

   # Correct
   def sync_pull(self, ...):
       mappings = []
       for listing in listings:
           mapping = self.map_to_hub_asset(listing)  # ✅ Maps resources with external references
           mappings.append(mapping)
       return SyncResult(metadata={"mappings": [m.__dict__ for m in mappings]})
   ```

2. Ensure `map_to_hub_asset()` includes external resource references:
   ```python
   def map_to_hub_asset(self, listing):
       resources = [
           MarketplaceResource(
               resource_id=resource.id,
               url=resource.external_url,  # ✅ Store reference
               metadata={"external": True, "download_url": resource.external_url}
           )
           for resource in listing.resources
       ]
       return MarketplaceAssetMapping(resources=resources, ...)
   ```

#### Issue: Connector Performs Marketplace-Specific Operations in `sync_pull()`

**Symptoms**:
- Database creation happens during sync (Snowflake)
- Subscriptions happen during sync (AWS Data Exchange)
- Snapshots are triggered during sync (Azure Data Share)
- Slow sync performance

**Root Cause**:
Connector is performing marketplace-specific operations in `sync_pull()` instead of deferring them to `download_resource()`.

**Resolution**:
1. Move marketplace-specific operations to `download_resource()`:
   ```python
   # Wrong (Snowflake example)
   def sync_pull(self, ...):
       for listing in listings:
           self._create_database_from_listing(listing.id)  # ❌
           schema = self._extract_schema_metadata(listing.database_name)  # ❌

   # Correct
   def sync_pull(self, ...):
       mappings = []
       for listing in listings:
           mapping = self.map_to_hub_asset(listing)  # ✅ Maps only
           mappings.append(mapping)
       return SyncResult(metadata={"mappings": [m.__dict__ for m in mappings]})

   def download_resource(self, resource_id, destination_path):
       # ✅ Marketplace-specific operations happen here
       if len(resource_id.split(".")) == 1:  # Listing ID
           self._create_database_from_listing(resource_id)
           schema = self._extract_schema_metadata(resource_id)
           # ... download data
   ```

#### Issue: `map_to_hub_asset()` Accesses External Data Sources

**Symptoms**:
- HTTP requests are made during mapping
- Schema extraction happens during mapping
- Slow mapping performance

**Root Cause**:
Connector is accessing external data sources in `map_to_hub_asset()` instead of storing references.

**Resolution**:
1. Remove external data access from `map_to_hub_asset()`:
   ```python
   # Wrong
   def map_to_hub_asset(self, listing):
       data = httpx.get(listing.resource_url).content  # ❌
       schema = extract_schema_from_data(data)  # ❌

   # Correct
   def map_to_hub_asset(self, listing):
       resources = [
           MarketplaceResource(
               resource_id=resource.id,
               url=resource.external_url,  # ✅ Store reference
               metadata={"external": True, "download_url": resource.external_url}
           )
           for resource in listing.resources
       ]
       return MarketplaceAssetMapping(resources=resources, ...)
   ```

### Diagnostic Commands

#### Verify Connector Pattern Compliance

```bash
# Run all pattern verification tests
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connector_pattern.py \
  -v \
  --tb=short

# Check specific connector
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullDoesNotCreateAssets::test_ckan_sync_pull_does_not_create_assets \
  -v \
  --tb=short
```

#### Check Sync Job Results

```python
from hub.apps.integrations.models import MarketplaceSyncJob
from django.utils import timezone
from datetime import timedelta

# Get recent sync jobs
sync_jobs = MarketplaceSyncJob.objects.filter(
    direction="PULL",
    created_at__gte=timezone.now() - timedelta(hours=24)
).order_by('-created_at')[:10]

for job in sync_jobs:
    print(f"Sync Job: {job.id}")
    print(f"  Status: {job.status}")
    print(f"  Successful Items: {job.successful_items}")
    print(f"  Failed Items: {job.failed_items}")
    print(f"  Metadata Keys: {list(job.metadata.keys()) if job.metadata else 'None'}")
    if job.metadata and 'mappings' in job.metadata:
        print(f"  Mappings Count: {len(job.metadata['mappings'])}")
    print()
```

#### Check Asset Creation Timing

```python
from hub.apps.assets.models import Asset
from hub.apps.integrations.models import MarketplaceSyncJob
from django.utils import timezone
from datetime import timedelta

# Get recent sync job
sync_job = MarketplaceSyncJob.objects.filter(
    direction="PULL",
    created_at__gte=timezone.now() - timedelta(hours=1)
).first()

if sync_job:
    # Count assets created during sync window
    assets_created = Asset.objects.filter(
        created_at__gte=sync_job.created_at,
        created_at__lte=sync_job.completed_at if sync_job.completed_at else timezone.now(),
        source_type="FEDERATED"
    ).count()

    print(f"Sync Job: {sync_job.id}")
    print(f"  Created At: {sync_job.created_at}")
    print(f"  Completed At: {sync_job.completed_at}")
    print(f"  Successful Items: {sync_job.successful_items}")
    print(f"  Assets Created During Sync: {assets_created}")

    if assets_created > sync_job.successful_items:
        print("⚠️  WARNING: More assets created than successful items (connector may be creating assets directly)")
```

### Resolution Steps

1. **Identify the Violation**:
   - Run pattern verification tests
   - Check sync job results
   - Review connector code

2. **Refactor Connector**:
   - Move asset creation logic out of `sync_pull()`
   - Move data download logic to `download_resource()`
   - Move marketplace-specific operations to `download_resource()`
   - Ensure `map_to_hub_asset()` only stores references

3. **Verify Fix**:
   - Run pattern verification tests
   - Test sync with dry_run=True
   - Verify workflow handles asset creation

4. **Monitor**:
   - Check sync performance (should be fast for metadata-only)
   - Check storage usage (should be low for metadata-only)
   - Verify assets are created by workflow, not connector

### Prevention

- Always follow the metadata-first architecture pattern
- Use pattern verification tests during development
- Review connector code before deployment
- Monitor sync performance and storage usage
- See [Connector Development Guide](./connectors/DEVELOPMENT.md) for detailed implementation guidelines

---

## Disaster Recovery

### Recovery Procedures

1. **Database Recovery**:
```bash
# Restore from backup
pg_restore -d hub_db backup.dump
```

2. **Service Recovery**:
```bash
# Restart all services
docker-compose down
docker-compose up -d
```

3. **Data Recovery**:
```bash
# Restore from S3/MinIO backup
aws s3 cp s3://backup-bucket/backup.tar.gz .
tar -xzf backup.tar.gz
```

---

## Backup and Recovery

### Backup Procedures

1. **Database Backup**:
```bash
pg_dump -Fc hub_db > backup_$(date +%Y%m%d).dump
```

2. **File Storage Backup**:
```bash
# Backup MinIO data
mc mirror minio/backup-bucket s3://backup-bucket/
```

3. **Configuration Backup**:
```bash
# Backup configuration files
tar -czf config_backup_$(date +%Y%m%d).tar.gz config/
```

### Recovery Procedures

1. **Database Recovery**:
```bash
pg_restore -d hub_db backup_20250115.dump
```

2. **File Storage Recovery**:
```bash
mc mirror s3://backup-bucket/ minio/backup-bucket/
```

---

## CKAN Connector Issues

### Symptoms
- CKAN connector connection failures
- Harvest operations failing
- Circuit breaker open
- API key authentication errors

### Diagnosis

1. **Check Connector Configuration**:
```python
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config

config = get_marketplace_instance_config('dados.gov.br')
print(f"Base URL: {config.base_url}")
print(f"Connector Type: {config.connector_type}")  # "swagger" for dados.gov.br
print(f"API Key Set: {config.get_api_key() is not None}")
```

2. **Test Connection**:
```python
from hub.apps.integrations.factory import MarketplaceConnectorFactory

# Use new method name (recommended)
connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance('dados.gov.br')
# Or use backward-compatible method (deprecated):
# connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance('dados.gov.br')
result = connector.test_connection()
print(f"Connection test: {result}")
```

3. **Check Circuit Breaker State**:
```bash
docker compose exec api-service python -c "
from hub.apps.core.services.redis import get_redis_client
redis = get_redis_client()
state = redis.get('circuit_breaker:ckan-connector:state')
print(f'Circuit Breaker State: {state}')
"
```

### Common Issues

#### Issue: Connection Errors
**Symptoms**: `ConnectionError` when accessing marketplace instances

**Resolution**:
1. Verify network connectivity:
   - For Swagger API (dados.gov.br): `curl https://dados.gov.br/v3/api-docs`
   - For CKAN API (demo.ckan.org, data.gov): `curl https://demo.ckan.org/api/3/action/status_show`
2. Check firewall rules allow outbound HTTPS
3. Verify DNS resolution
4. Check marketplace instance status

#### Issue: API Key Not Working
**Symptoms**: Permission errors even with API key set

**Resolution**:
1. Verify API key format:
   - For Swagger API (dados.gov.br): JWT Bearer token format (`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`)
   - For CKAN API (demo.ckan.org, data.gov): Standard API key string
2. Check environment variable name:
   - For dados.gov.br: Use `DADOS_GOV_BR_API_KEY` (primary) or `CKAN_DADOS_GOV_BR_API_KEY` (deprecated)
   - For CKAN instances: Use `CKAN_TEST_API_KEY`
3. Check API key permissions in marketplace instance
4. Regenerate API key if needed
5. Verify environment variable is loaded correctly

#### Issue: Circuit Breaker Open
**Symptoms**: Requests fail immediately without attempting connection

**Resolution**:
1. Reset circuit breaker: Delete Redis key `circuit_breaker:ckan-connector:state`
2. Wait for automatic recovery (60 seconds timeout)
3. Check underlying connectivity issues
4. Verify Redis is healthy

### Resolution Steps

1. **Check Logs**:
```bash
docker compose logs api-service | grep -i ckan
```

2. **Verify Environment Variables**:
```bash
# Check all marketplace-related environment variables
docker compose exec api-service env | grep -E "DADOS_GOV_BR_API_KEY|CKAN"
```

3. **Test Connector**:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_marketplace_instances_config.py \
  -v
```

4. **Reset Circuit Breaker** (if needed):
```bash
docker compose exec api-service python -c "
from hub.apps.core.services.redis import get_redis_client
redis = get_redis_client()
redis.delete('circuit_breaker:ckan-connector:state')
print('Circuit breaker reset')
"
```

For detailed troubleshooting, see [Marketplace Connector Deployment Runbook](./runbooks/marketplace-connector-deployment.md).

---

## References

- [Database Indexes Documentation](./DATABASE_INDEXES.md)
- [Monitoring & Observability](./MONITORING.md)
- [Marketplace Connector Deployment Runbook](./runbooks/marketplace-connector-deployment.md)
- [Marketplace Connector Development Guide](./connectors/DEVELOPMENT.md)
- [Marketplace Test Documentation](../hub/apps/integrations/tests/README_MARKETPLACE_TESTS.md)

