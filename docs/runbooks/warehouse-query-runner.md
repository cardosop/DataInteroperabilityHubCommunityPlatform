# Warehouse Query Runner — Operational Runbook

**Phase 275.E** — Query execution troubleshooting.

## 1. Symptom
Warehouse queries time out or return errors. `WarehouseQueryTimeoutError` in logs.

## 2. Impact
Records API returns 504. DQ/Compliance warehouse scans fail.

## 3. Diagnosis
```bash
# Check active query count
python hub/manage.py shell -c "
from hub.apps.warehouses.views import _active_queries
print(_active_queries)
"
# Check stuck RQ jobs
python hub/manage.py shell -c "
from hub.apps.jobs.models import Job, JobStatus
for j in Job.objects.filter(type='WAREHOUSE_QUERY', status=JobStatus.RUNNING):
    print(j.id, j.created_at)
"
```

## 4. Common Causes
| Cause | Fix |
|-------|-----|
| Query timeout | Increase `warehouseConfig.query_timeout_seconds` or optimize query |
| Concurrency exhausted | Increase `_MAX_CONCURRENT_QUERIES` or scale workers |
| Warehouse overloaded | Scale up warehouse size in provider console |

## 5. Recovery
1. Cancel stuck queries via `POST /api/v1/jobs/{id}/cancel/`.
2. Reduce concurrency by setting lower `_MAX_CONCURRENT_QUERIES`.
3. Re-submit queries.

## 6. Prevention
Monitor `warehouse_active_queries` and `warehouse_query_duration_seconds` metrics.

## 7. Escalation
If queries consistently time out, escalate to data platform team for warehouse sizing review.
