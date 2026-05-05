# ADR-AST-004 — Optimistic locking on every PATCH (`If-Match` required)

**Status**: Accepted
**Date**: 2026-05-03
**Phase**: 250.7.B
**Decision in design.md**: D250.5
**Owners**: Asset-Creation Eng, API Eng, Frontend Eng

## Context

Today's `Asset` PATCH endpoint accepts arbitrary writes without concurrency control. Two TENANT_ADMINs editing the same asset simultaneously can silently overwrite each other (last-write-wins). Drawbacks:

1. **Silent data loss** — admin A updates `description`; admin B updates `tags`; B's PATCH lands second and overwrites A's `description` change.
2. **No retry-with-merge UX** — frontend has no signal that a stale-version write happened.
3. **Activation race** — Phase 250.1.A makes activation default-ON; concurrent edits during activation can land in undefined order.

## Decision

Every `PATCH /api/v1/assets/{id}/` (and related sub-resource patches) requires an `If-Match: <etag>` header where `<etag>` is the asset's current `version` field (monotonic integer incremented on every save). Mismatch → HTTP 412 `Precondition Failed` with `{"code": "ASSET_VERSION_MISMATCH", "current_version": N}`.

### Scope

Optimistic locking applies to:
- `PATCH /api/v1/assets/{id}/`
- `POST /api/v1/assets/{id}/activate/`
- `POST /api/v1/assets/{id}/archive/`
- `PATCH /api/v1/assets/{id}/contracts/{contract_id}/`
- `PATCH /api/v1/assets/{id}/datasets/{dataset_id}/`
- `DELETE /api/v1/assets/{id}/external-resources/{ref_id}/`

NOT applied to:
- POST creation endpoints (no prior version exists)
- GET reads (no write conflict)
- Webhook delivery retries (idempotent retry layer handles this)

### Rolling-deploy-safe rollout

Per D250.5, env var `OPTIMISTIC_LOCK_REQUIRE_IF_MATCH` (default `False` for first 7 days post-deploy) controls strict enforcement:

- `False` (soak): missing `If-Match` → log warning audit `ASSET_PATCH_MISSING_IF_MATCH` but allow PATCH (last-write-wins falls back).
- `True` (enforced): missing `If-Match` → HTTP 428 `Precondition Required` with `{"code": "ASSET_IF_MATCH_REQUIRED"}`.

7-day soak gives backend + frontend + SDK time to converge on the new contract; flip to `True` after telemetry confirms zero `ASSET_PATCH_MISSING_IF_MATCH` events for 7 consecutive days.

### Frontend retry-with-merge UX

Per Figma sign-off requirement (F2-7), the frontend `useUpdateAsset` mutation:

1. Sends `If-Match: <known-version>` on every PATCH.
2. On 412 response: fetches the current asset; computes the diff between known-baseline + current-server-state + local-uncommitted-changes; renders a 3-way merge dialog: "Asset was updated by <other-user> since you started editing. Pick: keep yours, accept theirs, or merge".
3. On user merge selection: re-PATCH with new `If-Match: <fresh-version>`.

Default merge picks the LATER timestamp value field-by-field; user can override.

## Consequences

### Positive

- Concurrent-edit safety.
- Explicit conflict surface = better UX than silent loss.
- Standard HTTP semantics (RFC 7232 If-Match).

### Negative

- Every PATCH client (frontend, SDK, CLI, internal-API consumers) MUST send `If-Match`. Migration cost. Mitigation: 7-day soak + clear deprecation telemetry.
- 3-way merge UX is non-trivial frontend work. Mitigation: Figma sign-off required before implementation; Phase 250.7.B deliverable.
- Webhook subscribers reading via the API must handle 412. Mitigation: documented in [docs/mvpdocs/api-reference/concurrency.md](../../mvpdocs/api-reference/concurrency.md).

## Alternatives considered

1. **Pessimistic locking** (`SELECT ... FOR UPDATE`) — rejected; serialises edits across all clients; bad UX for hot tenants.
2. **CRDTs** — overkill; Asset is not a long-running collaborative document.
3. **Last-write-wins with conflict history** — rejected; gives no signal at write time.

## Verification

- Unit: `test_patch_with_correct_if_match_succeeds_increments_version`.
- Unit: `test_patch_with_stale_if_match_returns_412`.
- Unit: `test_patch_without_if_match_in_soak_mode_logs_warning_succeeds`.
- Unit: `test_patch_without_if_match_when_enforced_returns_428`.
- Integration: simulate concurrent PATCH from 2 clients; assert exactly one succeeds (the other gets 412).
- Frontend E2E: 3-way merge dialog renders on 412; user can pick + re-submit.
