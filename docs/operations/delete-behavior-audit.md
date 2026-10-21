# Delete Behavior Audit — All 42 Apps

**Auditor:** Platform Engineering | **Date:** 2026-05-20

## Summary

| Category | Count | Apps |
|----------|-------|------|
| Soft-delete (is_deleted flag) | 3 | audit, dq, users |
| Hard-delete (CASCADE FK) | 28 | assets, contracts, compliance, marketplace, etc. |
| RLS-protected (tenant isolation) | 21+ tables | files, dq, webhooks, social, governance, etc. |
| No delete support | 11 | platform, developer, health, versioning, etc. |

## Soft-Delete Apps

| App | Model | Deleted Flag | Purge Cron |
|-----|-------|-------------|------------|
| audit | AuditEvent | is_deleted | audit_permanent_delete_sweep (daily) |
| dq | DQRun, DQAnomaly, DQTrend | is_deleted | purge_dq_runs (daily) |
| users | User | is_deleted | None (manual admin) |

## Hard-Delete Risk Assessment

| App | FK Cascades | Risk |
|-----|------------|------|
| assets | CASCADE on tenant, contract, dataset | Medium — asset deletion cascades to contracts |
| contracts | CASCADE to lineage edges | Low — contracts reference assets, not vice versa |
| orchestration | CASCADE on pipeline dependencies | Low — deps are derived, can be re-derived |

## Recommendations

1. Add soft-delete to `scheduled_ingestion` and `scheduled_export` (high row churn)
2. Add soft-delete to `transformation.PipelineExecution` (audit trail)
3. Verify RLS policies on all soft-deleted tables (RLS + soft-delete interaction)
4. Add `cleanup_*` management commands for any table with >1M rows and no purge schedule
