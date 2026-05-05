# Semantic graceful-degrade — runbook

**Phase**: 250.0.19 (250.7.A operational support)

## Scope

Manage assets in `semantic_status=FAIL` (or stuck UNKNOWN) — the graceful-degrade path defined by D250.6 / ADR-AST-006.

## Symptoms

- AssetDetailPage banner: "This asset is active but not yet discoverable in semantic search."
- Audit events `ASSET_SEMANTIC_DEGRADED` volume spikes.
- Tenant ticket: "I can't find my asset in search."
- Grafana panel "Semantic-status distribution": FAIL > 5%.

## Diagnosis

```
from hub.apps.assets.models import Asset
fails = Asset.objects.filter(semantic_status='FAIL').count()
unknowns_old = Asset.objects.filter(
    semantic_status='UNKNOWN',
    created_at__lt=timezone.now() - timedelta(hours=1),
).count()
print(f"FAIL: {fails}; stuck UNKNOWN: {unknowns_old}")
```

If both > 0 → semantic-service may be unhealthy. Check:
```
kubectl logs deployment/semantic-service -n hub-staging --tail=200
kubectl get pods -n hub-staging -l app=semantic-service
```

## Remediation paths

### Path A: Tenant-driven retry (single asset)

Tenant clicks "Retry mapping" on the AssetDetailPage banner. Backend enqueues a retry job with exponential backoff (1m / 5m / 30m / 1h / 2h / dead-letter after 5 attempts).

### Path B: Bulk retry after semantic-service recovery

After semantic-service is restored, bulk-retry all FAIL assets:
```
python manage.py retry_semantic_mapping --tenant-id=<uuid> --status=FAIL --limit=1000
```

Per-tenant rate-limit: max 10 retries per minute per tenant (avoids re-overloading a fragile service).

### Path C: Permanent FAIL → manual reconciliation

Some assets may have semantic mappings impossible to compute (malformed contracts, unsupported types). For these:

1. Identify:
   ```
   python manage.py list_dead_letter_semantic_assets --tenant-id=<uuid>
   ```

2. For each, decide:
   - **Fix the contract** → re-trigger semantic mapping after contract update.
   - **Accept FAIL permanently** → tenant clicks "Accept FAIL" button on banner; sets `semantic_status_acknowledged_at`; banner hides.

### Path D: Semantic-service outage rollback

If semantic-service is fully unavailable AND graceful-degrade isn't sufficient (e.g. customer demands semantic-search blocking the workflow):

1. **DO NOT** flip semantic to a hard-block. Phase 250.7.A is correct — semantic is non-essential to asset usability.
2. Communicate to affected tenants that semantic-search is degraded; assets are usable and downloadable.
3. Restore semantic-service per its own runbook.

## Verification

After remediation:
- `Asset.objects.filter(semantic_status='FAIL').count()` decreases.
- Grafana "Semantic-status distribution" returns toward PASS dominance.
- No new `ASSET_SEMANTIC_DEAD_LETTER` audit events for 30 min.

## Escalation

- Bulk FAIL across multiple tenants: SRE on-call → Semantic-Service Lead.
- Permanent dead-letter trend: Eng EM (likely a contract-shape regression).
