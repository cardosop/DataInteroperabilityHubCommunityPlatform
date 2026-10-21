# ADR-AST-001 — Fail-closed asset persistence (gates run BEFORE Asset row materialises)

**Status**: Accepted
**Date**: 2026-05-03
**Phase**: 250.1.A
**Decision in design.md**: D250.2
**Owners**: Asset-Creation Engineering Lead, Compliance Lead

## Context

Today's asset-creation workflow ([hub/apps/orchestration/workflows/asset_creation.py:639](../../../hub/apps/orchestration/workflows/asset_creation.py#L639)) creates the `Asset` row FIRST, then runs compliance + DQ gates against the persisted asset. If a gate fails, the workflow attempts compensating delete operations. Drawbacks:

1. **Failure → orphan** — compensation paths are non-trivial; partial failures (e.g. delete succeeds but search-index removal does not) leave orphan rows and a violation of [User_Journeys.md:49-59](../../../InputDocs/User_Journeys.md#L49-L59) which states "an asset MUST exist only when intake validates".
2. **Webhook noise** — `asset.created` fires before gates run; subscribers receive an event for an asset that may be deleted moments later.
3. **Quota leakage** — tenant asset count increments before compliance verifies allowed-to-store; a tenant attempting to import 1 000 PII-laden assets all rejected by compliance still counts (briefly) toward their quota.
4. **Audit ambiguity** — `ASSET_CREATED` audit event written before the asset is "really" created.

## Decision

The workflow re-sequences to run gates BEFORE Asset persistence:

```
schema-infer → ODCS-generate → ODCS-validate → ODCS-normalise →
contract-create → compliance-check (in-memory) → DQ-check (in-memory) →
asset-create (only on PASS/WARN) → contract-attach → dataset-create →
dataset-attach → contract-validate → odps-link → activate (default ON
per D250.2) → search-index → notifications
```

The compliance + DQ gates execute against the file payload + tenant policy via two new methods that DO NOT persist an Asset:

- `ComplianceService.scan_inmemory(file_id, tenant, legal_basis) → ComplianceResult`
- `DQService.scan_inmemory(file_id, tenant, profile_key) → DQResult`

Both methods persist a `ComplianceRun` / `DQRun` row (so tenants can see why a creation failed) but DO NOT create an `Asset`. Only on PASS/WARN does the workflow proceed to `asset-create`.

## Consequences

### Positive

- Asset row exists ⟺ gates passed. Strong invariant; no orphan rows.
- `asset.created` webhook fires only when the asset is real.
- Tenant quota increments only after gates pass.
- `ASSET_FAIL_CLOSED_REJECTED` audit event captures the rejection with full diagnostics.
- Compensation paths shrink to one direction (rollback before persist is trivial; rollback after persist is 7-step saga).

### Negative

- Latency shifts: API call returns `WorkflowRun.id` immediately; Asset materialises 5–30 s later. Frontend + SDK MUST poll `WorkflowRun.state`. Phase 250.4 owns SDK migration; Phase 250.1.B covers frontend.
- Webhook subscribers expecting fast `asset.created` see latency change. Documented in [audit-reports/b2-6-asset-webhook-timing-2026-05-03.md](../../audit-reports/b2-6-asset-webhook-timing-2026-05-03.md).
- 30-day soak with `tenant.compliance_fail_closed_enabled` default-FALSE on existing tenants per D250.12 to prevent surprise.

### Compensation map (post-persist failures)

After Asset persists, downstream-step failures use a Saga pattern:

| Failed step | Compensation |
|---|---|
| `attach_dataset` fails | DELETE dataset; remove FK from asset; emit `ASSET_WORKFLOW_ROLLED_BACK` audit |
| `validate_contract` fails (after attach) | Keep asset in DRAFT status; emit WARN audit; Asset usable only by creator |
| `odps_link` fails | Keep asset; emit WARN audit + `ASSET_ODPS_DEGRADED` event; Asset usable normally |
| `activate` fails | Keep asset DRAFT; user retries via PATCH |
| `search_index` fails | Keep asset; emit WARN + `ASSET_SEMANTIC_DEGRADED` (per ADR-AST-006) |
| `notifications` fails | Best-effort; do not roll back asset |

## Alternatives considered

1. **Two-phase commit across compliance + DQ + Asset** — overkill; compliance and DQ are separate microservices; XA across them is complex and slow. Rejected.
2. **Synchronous Asset creation; async gate check; soft-delete on fail** — leaves orphan rows visible to tenant queries during the gate window. Rejected on UX + quota grounds.
3. **Always require manual activation after gates pass** — friction; D250.2 chose `auto_activate=True` default; tenant override available.

## Verification

- Unit: `test_workflow_creates_asset_after_gates_pass`
- Unit: `test_workflow_rejects_when_compliance_fails_closed_emits_asset_fail_closed_rejected_audit`
- Integration: `test_compensation_map_partial_failure_attach_dataset` — reproduce attach failure; assert dataset deleted + asset DRAFT + audit fired.
- Production smoke: ingest 100 valid + 10 invalid files; confirm 100 assets exist + 10 `ASSET_FAIL_CLOSED_REJECTED` events; zero orphan rows.
