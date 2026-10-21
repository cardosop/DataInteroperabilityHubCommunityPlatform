# ADR-AST-002 — Federated import per-tenant flag + compliance MUST run + DQ skipped for METADATA_ONLY

**Status**: Accepted
**Date**: 2026-05-03
**Phase**: 250.5.A
**Decision in design.md**: D250.3, D250.16
**Owners**: Asset-Creation Eng, Compliance Lead, Privacy Counsel

## Context

Federated import lets a tenant register an asset whose data lives in another marketplace (CKAN, AWS Data Exchange, dados.gov.br, etc.) without copying the payload. Today's federated path:

1. Has NO explicit per-tenant feature flag — any tenant with marketplace integration enabled can federate.
2. Skips both compliance AND DQ unconditionally (no payload to scan).
3. Has no documented behaviour for source-tenant deletion (orphan consumer-side metadata).

These are gaps:

- **Compliance is mandatory by regulation** even for federated assets — the metadata + URL itself may carry compliance obligations (e.g. cross-border transfer of personally-identifying URLs).
- **DQ is irrelevant for METADATA_ONLY** — there's no payload to scan.
- **Source-tenant deletion** must not orphan consumer-side data without notice.

## Decision

1. **New per-tenant flag** `Tenant.federated_import_enabled = BooleanField(default=False)` — default OFF on all tenants. Flip per-tenant after explicit DPO + Legal sign-off (federated import has cross-tenant data-sharing implications).
2. **Compliance MUST run** on every federated import via `ComplianceService.scan_inmemory(...)` against the asset metadata + tenant policy. The "in-memory" scan does NOT need the payload — it scans the URL, marketplace_type, classification labels, and tenant-policy compatibility.
3. **DQ skipped for `data_strategy=METADATA_ONLY`** — tracked via `DQRun.skipped=True` audit (so the absence of DQ is itself auditable).
4. **Cross-tenant read returns HTTP 404** (existence-leak protection) — a tenant attempting to read a federated asset's source-tenant assets sees nothing.
5. **AUDITOR role** receives read-only access on federated assets across tenants (governance use case).
6. **Source-tenant deletion cascade** (D250.16): adds `Asset.source_tenant_deleted_at` field; on source-tenant deletion, consumer-side federated copies are tombstoned (not deleted) for 90 days, allowing the consumer tenant to export. After 90 days, hard-delete cascades.

## Consequences

### Positive

- Federated import is opt-in + auditable.
- Compliance gate covers the regulatory blind spot.
- Cross-tenant existence-leak closed.
- Source-tenant lifecycle documented.

### Negative

- Tenants with prior implicit federated access lose it on Phase 250 deploy. Mitigation: 30-day notice email to all tenants who currently have `MarketplaceConnection` rows; explicit flag-flip request UI.
- AUDITOR cross-tenant read is a new privileged surface; logging + rate-limit + audit-trail required.

### Tenant-deletion grace period

90 days is chosen as the standard SaaS data-retention grace; aligns with [Tenant.deletion_grace_period_days = 90](../../../hub/apps/tenants/models.py) (already set elsewhere). Re-uses the existing tenant-deletion machinery.

## Alternatives considered

1. **Auto-enable federated import for all tenants** — rejected on regulatory grounds; cross-tenant data-sharing requires opt-in.
2. **Skip compliance on federated** — rejected; even URL + marketplace_type are compliance-relevant.
3. **Hard-delete federated copies immediately on source-tenant deletion** — rejected; gives consumer tenant no time to export.

## Verification

- Unit: `test_federated_import_blocked_when_flag_disabled` (default tenants).
- Unit: `test_federated_import_runs_compliance_skips_dq`.
- Unit: `test_federated_cross_tenant_read_returns_404`.
- Unit: `test_auditor_can_read_federated_assets_cross_tenant_with_audit`.
- Unit: `test_source_tenant_deletion_tombstones_consumer_with_90d_grace`.
- Integration: end-to-end federated import from a fixture marketplace; assert compliance ran; assert DQ skipped; assert cross-tenant 404.
