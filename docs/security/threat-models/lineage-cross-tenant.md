# STRIDE Threat Model — Cross-Tenant Marketplace Lineage (Phase 228.F1)

> **Audience**: Platform security, Engineering leads, DPO.
> **Phase**: 228.F1 — REQ-LIN-F1-006 mandates this document precede implementation.
> **Last updated**: 2026-04-30.
> **Status**: Authored as a launch-prerequisite per the F1.1 spec gate. External pen-test (F1.25) follows; PIA/DPO (F1.26) follows.

This document is the security review backbone for the cross-tenant marketplace lineage feature. The endpoint exposes a **provider tenant's lineage graph to a consumer tenant's user** with two detail tiers: `summary` (pre-purchase, no transformation IP) and `full` (post-purchase, with `transformation_ref` / `job_ref` / column-level mappings). The two tiers are the load-bearing security boundary.

---

## System under threat

| Component | Description |
| --------- | ----------- |
| **Endpoint** | `GET /api/v1/listings/{listing_id}/lineage/?detail=summary\|full&max_depth=N` |
| **Code path** | `ListingViewSet.lineage()` action → `require_entitlement_or_summary()` permission helper → `LineageService.get_for_asset()` → `LineageGraphSummarySerializer` / `LineageGraphFullSerializer` |
| **Data** | `LineageEdge` rows (Phase 228.0) keyed by tenant — every edge owns a `tenant_id` enforced at the FK + RLS level |
| **Capability flag** | `lineage.cross_tenant_marketplace` — when OFF, endpoint returns 404 (information-leak hardened — NOT 403) |
| **Trust boundaries** | (a) consumer-tenant browser ↔ Hub API; (b) Hub API ↔ database; (c) consumer tenant ↔ provider tenant data — the **load-bearing boundary** |

---

## STRIDE analysis

### S — Spoofing identity

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| S1 | A consumer tenant's user requests `?detail=full` for a listing they don't own, claiming entitlement | `require_entitlement_or_summary` calls the existing `require_entitlement` from `access_utils.py` for `detail=full`. Failure → `403 ENTITLEMENT_REQUIRED`. Same-tenant short-circuit applies (provider's own users get full without entitlement check). | `test_listing_lineage_view.py::test_full_view_forbidden_without_entitlement` |
| S2 | A user spoofs `consumer_tenant_id` in the request body or query string | Tenant id is server-derived from the authenticated user (`request.user.tenant_id`); never accepted from the request body. Same convention as the L7.2 schema-editor metric receiver. | Code review — no path reads tenant id from `request.data`. |
| S3 | An attacker forges an audit row carrying a fake `consumer_tenant_id` to plant blame on tenant B | Audit emission uses server-derived ids via `create_audit_event(actor_user=request.user, tenant=request.user.tenant)`. Wire-format clients can't influence the persisted row. | The existing `AuditEvent` append-only invariant + the unit test for audit-row composition. |

### T — Tampering with data

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| T1 | A consumer mutates the lineage response (e.g. injects a fake transformation_ref to phish another user) | Response is read-only; no writes accepted on this endpoint. ETag is response-only (client sees, server doesn't trust). | Endpoint definition: `methods=["get"]`. |
| T2 | An attacker tampers with the underlying `LineageEdge` rows to plant a cross-tenant edge (e.g. fake edge tying provider's contract to attacker's contract for IP leakage) | `LineageEdge` is **only writable** by the `lineage_sync` post-save handler + the `backfill_lineage_edges` management command (REQ-LIN-002). Application writers MUST NOT update the table directly. The handler reads from `Contract.hub_contract_json.lineage` (canonical source). The `tenant_id` FK is set from the contract's tenant — there's no path for tenant A's contract to produce an edge in tenant B's row scope. | `test_lineage_sync.py` (Phase 228.0 — REQ-LIN-002 coverage). |
| T3 | Database-level tampering bypasses application checks | Out of scope for application-layer threat model. Mitigated by the audit table's append-only invariant + Phase 234.1 tamper-evidence (hash chain + S3 Object Lock) when shipped. | Phase 234 audit-tamper-evidence work. |

### R — Repudiation

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| R1 | Consumer tenant accesses provider's lineage and later denies having done so | Every cross-tenant access emits a `LINEAGE_VIEWED_CROSS_TENANT` audit row carrying `consumer_tenant_id`, `provider_tenant_id`, `listing_id`, `detail`, `entitlement_id` (REQ-LIN-F1-002). The audit table is append-only (3-year retention). | `test_listing_lineage_view.py::test_audit_row_emitted_on_cross_tenant_view` |
| R2 | Provider tenant denies having allowed access | The `Listing` row + the `Entitlement` row are the authoritative record of "I listed asset X" and "I sold listing Y to tenant B". The audit row complements but doesn't replace these. | Existing marketplace contract; not new in F1. |
| R3 | Audit log flooding from a viral listing makes the trail uninformative ("noise drowns signal") | Per-`(consumer, listing)`-per-hour deduplication via Redis `SETNX` with 1h TTL. 100 views in an hour → 1 audit row. The dedup window does NOT skip the dispatch itself (the response is still served); only the audit row is suppressed. | `test_listing_lineage_view.py::test_repeated_access_within_hour_emits_one_audit_row` |

### I — Information disclosure (the load-bearing boundary)

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| **I1** | Pre-purchase consumer leaks transformation IP via the summary tier | **Explicit serializer field allowlist** in `LineageGraphSummarySerializer`: only `nodes` (id, type, label) and `links` (source, target, edge_type without metadata) are emitted. The fields `transformation_ref`, `job_ref`, `created_by_run`, `source_field`, `target_field` are **explicitly NOT included** in the summary serializer's field list. | `test_listing_lineage_view.py::test_summary_excludes_forbidden_keys` (regression guard with pinned forbidden-key set; a future serializer edit that drops a field FROM the forbidden list still fails) |
| I2 | Information leak via the capability flag's `404` vs `403` distinction | The endpoint returns `404 Not Found` (NOT `403 Forbidden`) when the capability flag is OFF, so an attacker can't distinguish "endpoint exists but is gated for me" vs "endpoint doesn't exist". | `test_listing_lineage_view.py::test_feature_flag_off_returns_404` |
| I3 | Information leak via timing — an entitlement-check failure path is faster than an entitlement-check success path, allowing a probe oracle | Both paths execute the same audit-emission + serialization work after the entitlement check; the timing difference is dominated by serialization, not the check. Documented as accepted residual risk; mitigated by the per-user 60/min rate limit which caps probe volume. | Acknowledged in this threat model; pen-test (F1.25) will validate. |
| I4 | A summary-tier response contains a transformation hint via a node label like "dbt_transform_pii_redact" | Node labels are derived from contract field names + spec metadata, NOT from `transformation_ref`. The summary tier never reads `transformation_ref` so this risk is contained at the serializer level. | `test_listing_lineage_view.py::test_summary_node_labels_dont_carry_transformation_hints` |
| I5 | An attacker crafts a `max_depth=15` request and uses graph-shape inference to derive transformation patterns (e.g. "5 layers deep means there's an aggregation step") | Capped at 15 by the endpoint's parameter validation. The shape itself is signal but the spec accepts that — buyers' legitimate use case is to assess pipeline complexity. Documented as accepted residual risk. | `test_listing_lineage_view.py::test_max_depth_clamped_to_15` |
| I6 | An attacker iterates `listing_id` UUIDs to enumerate listings + their lineage shape | UUIDv4 listing ids are unguessable (122 bits of entropy). Per-user 60/min + per-tenant 600/min rate limits cap probing. | The listing model's `id = UUIDv4` default. |

### D — Denial of service

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| D1 | Cross-tenant probing burns API capacity | Per-user 60/min + per-tenant 600/min rate limits with `429 + Retry-After` (REQ-LIN-F1-003). Two-tier limit prevents a single tenant from exhausting per-user quotas via 100 puppet accounts. | `test_listing_lineage_view.py::test_per_user_rate_limit` + `test_per_tenant_rate_limit` |
| D2 | A `max_depth=15` request on a listing whose backing asset has a dense lineage graph (e.g. 10⁵ edges) — slow-loris style DoS | Service-layer guards: (a) `max_depth` capped at 15 by parameter validation, (b) per-query result-row cap (500 nodes / 1000 edges) returned as the response with a `truncated=true` flag, (c) read-replica routing keeps the primary's writers from being blocked. Documented in `LineageService.get_for_asset` docstring. | `test_lineage_service_for_asset.py::test_dense_graph_truncation_returns_flag` |
| D3 | Cache stampede when `lineage.cross_tenant_marketplace` flips from OFF → ON for a popular listing | `Cache-Control: private, max-age=60` on responses; per-listing ETag enables 304 Not Modified for cache hits. Initial flip absorbed by the rate limits. | `test_listing_lineage_view.py::test_etag_returned_on_response` + `test_cache_control_private_60s` |

### E — Elevation of privilege

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| E1 | A non-platform-admin user obtains another tenant's `full` lineage by abusing entitlement-share-leak | Entitlement is checked per-asset, per-consumer-tenant, per-call. Sharing an entitlement between users within the consumer tenant is intentional (the tenant bought the listing); cross-tenant entitlement sharing is impossible (no UI / API to copy entitlements across tenants). | `test_listing_lineage_view.py::test_entitlement_scoped_to_consumer_tenant` |
| E2 | A consumer with an `EXPIRED` or `REVOKED` entitlement gets `full` access via cache or stale entitlement-check | The check calls `Entitlement.objects.get(...)` at request time; no caching on the entitlement lookup itself. ETag-based response caching (60s) is keyed on `entitlement_id` + `as_of` timestamps; a revocation post-issuance won't return cached `full` data because `entitlement_id` is part of the cache key. | `test_listing_lineage_view.py::test_expired_entitlement_rejected` + `test_revoked_entitlement_rejected` |
| E3 | A platform admin uses their cross-tenant read role to view full lineage on every listing | Platform admins have legitimate cross-tenant read access for support/forensics. Each access is audit-logged regardless of tier; the `LINEAGE_VIEWED_CROSS_TENANT` row carries `actor_user` so platform-admin views are forensically distinguishable. PLATFORM_ADMIN role is itself audited (Phase 235 admin-feature-flag-management when shipped). | The existing audit-row composition. |
| E4 | A consumer-tenant user injects SQL via `max_depth` or `detail` parameters | Parameters are integer / enum-validated by DRF serializer fields; no raw query construction. The service uses Django ORM (`LineageEdge.objects.filter(...)`) which parametrises safely. | `test_listing_lineage_view.py::test_max_depth_rejects_non_integer` + `test_detail_rejects_non_enum_value` |

---

## Residual risks (acknowledged, not mitigated)

| Risk | Severity | Reason for acceptance | Compensating control |
| ---- | -------- | --------------------- | -------------------- |
| **I3 timing-side-channel on entitlement check** | Low | Mitigation cost (constant-time padding) outweighs information value (a confirmed-by-timing entitlement is not a vulnerability — entitlements are issued through the marketplace flow, not through probing) | Per-user rate limit caps probe volume |
| **I5 graph-shape inference** | Low | Buyers' legitimate use case requires showing the pipeline shape; obscuring shape would kill marketplace value | Documented in marketing copy ("graph shape is shared with buyers") |

External pen-test (F1.25) is scheduled to validate all S/T/R/I/D/E findings against a real adversarial model. PIA + DPO sign-off (F1.26) reviews the I-tier findings against GDPR Article 30/35 obligations.

---

## Pre-launch checklist

- [x] STRIDE analysis authored (this document) — F1.1
- [ ] External pen-test conducted, report attached — F1.25
- [ ] PIA + DPO sign-off recorded — F1.26
- [ ] Customer-commitment audit (no contracts mention "private lineage") — F1.27
- [ ] Pricing-tier decision (product/finance) — F1.28

The capability flag `lineage.cross_tenant_marketplace` defaults OFF until ALL five rows above are green. The flag flip is the launch trigger; the threat model is its prerequisite.

---

## Cross-references

- [REQ-LIN-F1-001 .. REQ-LIN-F1-006](../../../openspec/changes/preprod01/specs/lineage-cross-tenant/spec.md) — capability spec
- [hub/apps/marketplace/access_utils.py](../../../hub/apps/marketplace/access_utils.py) — `require_entitlement` reference
- [hub/apps/contracts/models.py](../../../hub/apps/contracts/models.py) `LineageEdge` — Phase 228.0 foundation
- [docs/runbooks/structureless-contracts.md](../../runbooks/structureless-contracts.md) — for the pattern of audit-event + rate-limit + capability-flag rollout used in Phase 227 (precedent for F1.6/F1.7/F1.2)
