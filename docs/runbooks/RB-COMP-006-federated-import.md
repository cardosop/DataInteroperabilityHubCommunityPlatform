# RB-COMP-006 — Federated Import (Phase 284.A)

**Flag:** `federated_import_enabled`
**Stage:** GA
**Owner:** asset-creation-eng@meshant.com
**Created:** 2026-05-17 (Phase 284.A.8)

## Scope

Federated marketplace import allows tenants to discover and import data products
from external marketplaces (Snowflake, AWS Data Exchange, Databricks, Google
Analytics Hub) into their Meshant catalogue. Import jobs are async (enqueued via
the Job model) and respect the tenant's `federated_import_enabled` flag plus
cross-region consent requirements.

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Import creation returns 403 | `federated_import_enabled=False` | Flag state; `GET /api/v1/admin/tenants/{id}/feature-flags/` |
| Import creation returns 403 `CROSS_REGION_CONSENT_REQUIRED` | Source/consumer regions differ; no consent | Source tenant `data_residency_region` vs consumer; pass `cross_region_consent=true` |
| Import stuck in PENDING >1h | Worker queue backlog; provider unreachable | `federated_import` job queue depth; worker health; provider connectivity |
| Import fails with credential error | SM ARN invalid; secret rotated; IAM permission missing | AWS Secrets Manager: verify ARN, secret exists, worker IAM role has `secretsmanager:GetSecretValue` |
| Provider list empty | Static allowlist; backend unreachable | `GET /api/v1/integrations/federated-import/providers/` returns 4 providers |
| Job cancellation returns 409 | Job already in terminal state (COMPLETED/FAILED/CANCELLED) | Job status; only PENDING/RUNNING jobs can be cancelled |

## Credential Rotation

1. **Rotate in AWS SM:** Update the secret value; keep the same ARN.
2. **No Hub-side action needed:** The worker resolves the ARN at each job exec
   via `hub.aws_secrets_loader.load_secret()`. New jobs pick up the new value
   automatically.
3. **Cancel stale jobs:** Jobs created with the old credential (before rotation)
   that are still PENDING will fail on exec. Cancel them and re-create.
4. **Audit:** Every credential resolution emits `FEDERATED_IMPORT_CREDENTIAL_RESOLVED`
   (success) or `FEDERATED_IMPORT_CREDENTIAL_RESOLUTION_FAILED` (failure).

## Provider Connectivity

| Provider | Connectivity check | Common issues |
|----------|-------------------|---------------|
| Snowflake Marketplace | SNOWFLAKE_SAMPLE_DATA share access | Account locator/region mismatch; PAT expiry |
| AWS Data Exchange | `dataexchange.list_data_sets` | IAM permission; region mismatch |
| Databricks Marketplace | Unity Catalog `list_exchange_listings` | PAT expiry; workspace URL incorrect |
| Google Analytics Hub | `analyticshub.list_listings` | Service account permission; project mismatch |

## Cross-Region Consent Debugging

1. Identify source tenant: `asset_mapping.source_metadata["source_tenant_id"]`
2. Compare `data_residency_region` of source vs consumer tenant
3. If regions differ → `cross_region_consent=True` required
4. Audit: `FEDERATED_IMPORT_CROSS_REGION_BLOCKED` and `FEDERATED_IMPORT_REJECTED` events
5. Dashboard: `monitoring/grafana/dashboards/federated-import.json`

## Escalation

- **P3** — Single import job failure (credential or provider-specific)
- **P2** — All imports for a provider failing (provider outage)
- **P1** — All federated imports failing across all providers (worker down; gate misconfiguration)

## Related

- `hub/apps/integrations/services/discovery_service.py:35` — Pre-import refusal gates
- `hub/apps/integrations/federated_import_views.py` — REST surface
- `hub/apps/jobs/models.py` — `FEDERATED_IMPORT` JobType
- `hub/aws_secrets_loader.py` — Worker credential resolution
- `docs/runbooks/feature-flag-lifecycle.md` — Flag lifecycle policy

## Maintenance

- **Owner:** Asset Creation Engineering
- **Last reviewed:** 2026-05-17
- **Next review:** 2026-08-17
