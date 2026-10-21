# ADR-AST-006 — Semantic mapping is async + graceful-degrade (`semantic_status` field)

**Status**: Accepted
**Date**: 2026-05-03
**Phase**: 250.7.A
**Decision in design.md**: D250.6
**Owners**: Asset-Creation Eng, Semantic-Service Lead

## Context

Today's asset-creation workflow includes a `index_for_search` step + a `contract-remap-for-semantic` step. Both depend on the semantic-service availability. Failures today block the entire workflow:

- semantic-service down → asset creation fails
- contract→semantic remap fails → asset creation fails
- search-index OpenSearch hiccup → asset creation fails

But semantic discoverability is **non-essential for asset usability**. A tenant with a freshly-uploaded CSV can still query / download / contract-validate it without it appearing in semantic search. Blocking creation on a non-essential subsystem is too aggressive.

## Decision

Semantic mapping becomes async + graceful-degrade. New field on `Asset`:

```python
semantic_status = models.CharField(
    max_length=16,
    choices=[
        ("UNKNOWN", "Unknown — semantic step has not run yet"),
        ("PASS", "Semantic mapping completed successfully"),
        ("WARN", "Partial mapping — asset is searchable but some properties unmapped"),
        ("FAIL", "Mapping failed — asset is active but NOT in semantic search"),
    ],
    default="UNKNOWN",
)
```

### Workflow behaviour

`index_for_search` and `contract-remap-for-semantic` run AFTER asset persistence (in the post-activate phase). On failure:

1. Emit `ASSET_SEMANTIC_DEGRADED` audit event with full diagnostics.
2. Set `Asset.semantic_status = "FAIL"`.
3. **Allow the workflow to complete successfully** (Asset remains `ACTIVE`, accessible to user, downloadable).
4. Frontend `AssetDetailPage` renders a banner: "This asset is active but not yet discoverable in semantic search. [Retry mapping] [Why this happened]".
5. Tenant-admin can click `[Retry mapping]` → enqueues `WAREHOUSE_SEMANTIC_RETRY` job (per Phase 240 job-naming convention) which re-runs the semantic step.

### Async retry strategy

- Initial attempt during workflow execution.
- On FAIL: enqueue retry job with exponential backoff (1m / 5m / 30m / 1h / 2h / dead-letter after 5 attempts).
- Tenant-admin manual retry resets the backoff.
- Dead-letter triggers `ASSET_SEMANTIC_DEAD_LETTER` audit + ops PagerDuty (NOT customer-facing PagerDuty per D240.8 precedent).

## Consequences

### Positive

- Asset usability decoupled from semantic-service availability.
- Tenants get a clear, actionable signal (banner + retry button).
- Ops gets dead-letter alerting for sustained failures.

### Negative

- Tenants may not notice the banner; assets technically usable but not discoverable. Mitigation: banner is dismissible-but-persistent (re-shows on every page load until status changes or tenant explicitly accepts WARN/FAIL).
- Retry jobs add load to semantic-service during recovery from outages. Mitigation: retry uses exponential backoff + per-tenant rate-limit (max 10 retries per minute per tenant).
- `semantic_status=UNKNOWN` is the initial state — frontend MUST handle it (treat as WARN visually, don't show "fail" banner).

## Alternatives considered

1. **Block creation on semantic failure** — rejected; too aggressive.
2. **Skip semantic on failure with no UI signal** — rejected; tenants surprised when search doesn't find their asset.
3. **Synchronous retry with shorter backoff** — rejected; ties up workflow worker; async is the right pattern.

## Verification

- Unit: `test_workflow_completes_when_semantic_step_fails_emits_degraded_audit`.
- Unit: `test_asset_semantic_status_set_to_fail_on_indexing_error`.
- Unit: `test_retry_semantic_via_action_succeeds_updates_status_to_pass`.
- Integration: simulate semantic-service down; assert workflow completes; assert banner renders; assert retry succeeds when service recovers.
- Frontend E2E: banner visible on AssetDetailPage when `semantic_status=FAIL`; retry button enqueues job; status updates to PASS within 30s under healthy semantic-service.
