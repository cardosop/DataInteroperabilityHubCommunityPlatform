# RB-FLAG-004 — Datasets & Files Feature Flags

**Flags:** `datasets_enabled`, `files_enabled`
**Stage:** GA (both)
**Owner:** data-plane-eng@meshant.com
**Created:** 2026-05-16 (Phase 283.6.4)

## Scope

These are per-tenant kill-switches for the Dataset and File REST surfaces. Both default ON for all tenants. Disabling either flag hides the corresponding REST endpoints, UI pages, and SDK methods for that tenant.

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Dataset list returns 403 `FEATURE_DISABLED` | `datasets_enabled=False` for tenant | `GET /api/v1/admin/tenants/{id}/feature-flags/` |
| File upload returns 403 | `files_enabled=False` for tenant | Same check; `files_enabled` flag |
| Dataset/File pages missing from sidebar | Flag disabled → CapabilityRoute hides page | Feature flags response; frontend capability gate |
| SDK `client.datasets.list()` fails | Flag disabled → API rejects request | Check flag state; verify tenant context |
| New tenant can't access datasets | Tenant onboarding incomplete; flag not yet enabled | Tenant onboarding status; `datasets_enabled` flag |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/data-plane.json`
- **Primary:** `dataset_operations_total{operation}`, `file_operations_total{operation}`
- **Error rate:** `dataset_operation_errors_total`, `file_operation_errors_total`
- **Audit:** `DATASET_ACCESSED`, `FILE_ACCESSED`, `FEATURE_DISABLED_ACCESS_ATTEMPTED`

## Execution Checklist

1. Verify flag state: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Test REST surface: `GET /api/v1/datasets/` and `GET /api/v1/files/` with tenant auth
3. Verify UI: sidebar shows Datasets and Files entries when flags are ON
4. Verify SDK: `datahub datasets list` and file operations succeed
5. Flag flip audit: `TENANT_FEATURE_FLAG_FLIPPED` with `flag=datasets_enabled` or `files_enabled`
6. If disabling: confirm no active ingestion/exports in flight; notify tenant

## Escalation

- **P3** — Flag accidentally disabled for single tenant (re-enable; audit reason)
- **P2** — Both flags disabled across multiple tenants (investigate bulk-update cause)
- **P1** — Flag state mismatch between API and DB (investigate cache/staleness)

## Related

- `docs/runbooks/datasets-files-dr.md` — Disaster recovery procedures
- `docs/runbooks/file-quota-exhaustion.md` — File quota response
- `docs/runbooks/file-retention.md` — File retention enforcement

## Maintenance

- **Owner:** Data Plane Engineering
- **Last reviewed:** 2026-05-16
- **Next review:** 2026-08-16
