# Event-Emitter Decision Table — G7 (W4.1b)

**Date:** 2026-10-09 · **Change:** `openspec/changes/oss-release-remediation` (W4.1b) ·
**Gap:** G7 — "fixing the bus (W4.1) without deciding the emitters leaves the
pub/sub surface still empty" (plan review 2026-10-06, MEDIUM-HIGH).

**Method:** for each event type in the G7 scope, the audit compared the event
registry (`hub/apps/core/events/event_types.py`) against every publish call
site in `hub/` (excluding the publisher definitions themselves). Each row is
one of three decisions — **EMIT** (wired on the primary path + pinned),
**ABSENT** (documented as intentionally absent + pinned to stay absent), or
**EMITTED** (already wired — no change). Decisions are enforced by
`hub/apps/core/events/tests/test_w41b_event_emitters.py`.

## Decision table

| ID | Event type | Pre-fix status | Consumer | Decision | Action |
|---|---|---|---|---|---|
| C1 | `contract.created` | Emitted ONLY by the two ODPS auto-generation paths (ODCS→ODPS linking). The primary creation path (`ContractService.create_contract`) never emitted it. | contract.* subscribers; event log/replay | **EMIT** | Wired into `create_contract` via `run_side_effect` (fail-open, same pattern as search index/audit). Pin: create → exactly one row, payload carries `contract_id` + DRAFT status. |
| C2 | `MarketplaceEventPublisher` (core mixin) | Dead code — `MarketplaceService` inherits the mixin but NONE of its `publish_*` methods had a call site. The `notification_subscriber` consumes `marketplace.order.created/approved/rejected` — the consumer existed, the emitter never fired (order notifications structurally dead). | `notification_subscriber` (orders) | **WIRE** | Wired `publish_order_created/approved/rejected` into `create_order`/`approve_order`/`reject_order` via `run_side_effect`. Schema-type root fix on the way: `order_amount`/`currency` must be numbers/strings when present (FREE listings carry no price metadata → `0` / `"USD"`). The mixin stays as the wiring vehicle — it is no longer dead. Pins: 3 (one per order event). |
| C3 | `contract.updated` | Never emitted anywhere. | contract.* subscribers; event log | **EMIT** | Wired into `update_contract` (previous status captured before mutation; `changes` records raw-updated/status-updated). Pin: update → one row with previous/new status. |
| C4 | `contract.deleted` | Never emitted anywhere (`delete_contract` emitted only `odps.deleted` in the ODPS branch). | contract.* subscribers; event log | **EMIT** | Wired into `delete_contract` right after the RETIRED save (all spec types). Pin: delete → one row with the reason. |
| C5 | `contract.validated` | Never emitted. | none | **ABSENT (documented)** | Validation is a read-path check, not a lifecycle transition: results flow through API responses and the `_emit_validation_failed_observability` emitter; a per-validation event would be noise, not a lifecycle record. Pin: `validate_contract` → zero rows. |
| C6 | `contract.normalized` | EMITTED — rate-limited (`_NORMALIZED_EVENT_RATE_LIMIT_SECONDS` window) from `run_post_save_cascade` on the update path. | none (rate-limit defense documented in cache_invalidation.py) | **EMITTED (no change)** | Evidence: `hub/apps/contracts/cache_invalidation.py` (publisher call + dedup-key comment). |
| C7 | `marketplace.listing.published` | Never emitted (no call site). | none yet — canonical lifecycle record | **EMIT** | Wired into `_publish_listing_impl` after the publish audit. Pin: `publish_listing` → one row with listing/asset ids. |
| C7 | `marketplace.listing.unpublished` | Never emitted. | none | **ABSENT (documented)** | No unpublish primary path exists in the service layer (no UNPUBLISHED transition/method). If one ships later, this row flips to EMIT in a new decision revision. |
| C7 | `marketplace.order.fulfilled` | Never emitted. | none | **ABSENT (documented)** | Fulfillment is atomic with approval (approve/create-auto-approve call `order.fulfill()` inline); a separate fulfilled event would duplicate `order.approved`. Pin: auto-approved create → no fulfilled row. |
| C7 | `marketplace.entitlement.granted` / `revoked` | Never emitted. | none | **ABSENT (documented)** | No bus consumers; grants are derivable from order events + the Entitlement model; revocation is covered by the W2.6 `ENTITLEMENT_REVOKED` audit event. Pin: auto-approved create → no entitlement rows. |

## Scope note

The registry carries ~90 event types across ~20 families. This table decides the
G7-named items (C1 contract.created, C2 marketplace publisher) plus the
contract + marketplace LIFECYCLE families (C3–C7). The remaining families
(asset, dataset, file, ingestion, quality, compliance, access, workflow, ODPS,
mesh, virtualization, transformation, integration, billing, lineage) were
audit-checked for call-site existence in W4.1b but are out of the G7 decision
scope — a follow-up table (W4.1c or the W10 contract audit) can extend the same
EMIT/ABSENT/EMITTED discipline to them.

## Enforcement

`hub/apps/core/events/tests/test_w41b_event_emitters.py` — 10 pins, no mocks:
7 EMIT pins (row + payload shape per primary path), 3 ABSENT pins (validated,
order.fulfilled, entitlement.*) that keep documented-absent decisions honest —
a future wiring change is a DELIBERATE revision of this table, not silent drift.
