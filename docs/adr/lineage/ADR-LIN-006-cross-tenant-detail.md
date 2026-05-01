# ADR-LIN-006 — Cross-tenant lineage detail granularity

**Status:** Accepted (Phase 228 Foundations)
**Date:** 2026-04-30
**Related:** Phase 228 F1 (cross-tenant marketplace lineage, capability flag `lineage.cross_tenant_marketplace`)

## Context

Phase 228 F1 ships cross-tenant lineage visibility: a marketplace consumer (tenant B) can see the lineage of a tenant A contract they are evaluating or have purchased. The privacy / commercial-value tradeoff is non-obvious:

- Pre-purchase, showing the **full** lineage gives the consumer enough information to bypass the marketplace and reach out to upstream contracts directly — eroding the producer's commercial position.
- Pre-purchase, showing **nothing** prevents the consumer from evaluating whether the contract suits their needs — eroding marketplace conversion.
- Post-purchase, the consumer has a contractual right to the data; the lineage is now in scope for the consumer to inspect.

## Decision

**Two-tier detail grant:**

### Pre-purchase (browse-only)

The consumer sees a **summary** view:

- Edge count (e.g., "this contract has 3 upstream sources, 12 downstream consumers").
- Edge-type histogram (e.g., "2 derivation edges, 1 reference edge").
- Source/target tenant counts (e.g., "from 2 tenants, to 5 tenants") — but not tenant identities.
- The Meshant-internal `LINEAGE_VIEWED_CROSS_TENANT` audit row records the access for the producer's audit log, with `consumer_tenant_id` populated.

Contract IDs, model names, field names, and `transformation_ref` are **not** disclosed pre-purchase.

### Post-purchase (entitled)

The consumer sees the **full** lineage that any tenant-A user would see:

- Per-edge source/target contract IDs (resolved to display names if the consumer's tenant has its own contracts in the chain; otherwise displayed as opaque IDs).
- Model + field names.
- `transformation_ref`, `job_ref`.
- Audit row carries `consumer_tenant_id`, `provider_tenant_id`, `entitlement_id`.

Eligibility is checked against the existing `Entitlement` model (the same model that gates marketplace data access).

## Consequences

**Positive:**

- The marketplace producer's commercial information (specifically "which upstream contracts feed mine") is protected pre-purchase, while still letting the consumer evaluate scope.
- Post-purchase access is governed by the same `Entitlement` row that gates the data access, so there is no separate access-control surface to keep in sync.
- The audit trail (`LINEAGE_VIEWED_CROSS_TENANT`) is required by REQ-LIN-007 and naturally satisfied by this design.

**Negative:**

- The summary view requires a separate read path in `LineageService` (returns aggregated counts, not edge rows). Implemented as `LineageService.get_cross_tenant_summary(contract_id, viewer_tenant_id)` — a separate method so the existing detail-returning methods don't need a "mode" parameter.
- A consumer who only wants the summary must still pass through the same `Entitlement` check as the full-detail view (the check has two outcomes: summary-eligible vs. full-eligible), keeping the access-control surface uniform.

**Neutral:**

- The summary view's edge-count is an O(1) aggregation against `LineageEdge` so the cross-tenant browse is not an attack surface for resource exhaustion (an attacker enumerating millions of contract IDs would still hit the existing rate limits on `GET /contracts/`).

## Alternatives Considered

- **Always-full-detail (no two-tier):** rejected because it eliminates the commercial value of the marketplace as a discovery layer.
- **Always-summary (even post-purchase):** rejected because the consumer cannot perform forensic tracing on a contract they own — the contractual deliverable is full visibility.
- **Producer-controlled per-edge visibility flag:** rejected because the per-edge config burden falls on the producer, who has no incentive to invest in fine-grained lineage tagging. The two-tier rule keeps the configuration entirely automatic.
