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
9. [Disaster Recovery](#disaster-recovery)
10. [Backup and Recovery](#backup-and-recovery)

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

## References

- [Database Indexes Documentation](./DATABASE_INDEXES.md)
- [Monitoring & Observability](./MONITORING_OBSERVABILITY.md)
- [Infrastructure Parity](./INFRASTRUCTURE_PARITY.md)

