# Phase 250.0.24 — Capacity-planning addendum for asset-creation

**Phase**: 250.0.24
**Status**: Authoritative; reviewed at every Phase 250 milestone + quarterly thereafter.
**Owners**: SRE, Phase 250 Driver

## Scope

Capacity guidance for the new tables, audit-event volume, and runtime resource usage introduced by Phase 250 sub-phases. Companion to:
- [docs/capacity/lineage-storage.md](lineage-storage.md) (existing pattern)
- Phase 240's capacity sizing (data-quality runbook)

## New tables (Phase 250)

| Table | Phase | Schema growth | Storage projection (12 months) | Notes |
|---|---|---|---|---|
| `WorkflowDefinition` | (existing; extended) | ~10 versions per workflow × 5 workflows = ~50 rows total | ~250 KB | Modest; one row per `(workflow_name, version)`; `dsl_json` field is the largest column (~5 KB / row average). |
| `WorkflowInstance` (extended) | (existing; extended) | ~100 RPS × 86 400 s × 365 days × 1 KB = ~3 TB / year if all retained | ~3 TB / year unbounded | Phase 240's retention pattern applies: 90 d default for terminal runs (per D240.7); 14 d for in-flight. Daily purge job mandatory. |
| `WorkflowVersion` (alias to `WorkflowDefinition`) | 250.0.12 | Same as `WorkflowDefinition` | (no extra) | Per D250.7, this is a logical alias; physical model is `WorkflowDefinition`. |
| `WorkflowState` (existing) | (existing) | Per-step state per run; ~10 steps × 100 RPS × 86 400 s × 365 = ~30 TB / year if retained | ~30 TB / year unbounded | Aggressive retention: 14 d for terminal-run state; 90 d for in-flight. |
| `WarehouseConnectionACL` | 275.A.21 (D250.24-equivalent in Phase 275) | One row per (connection, user_or_group) grant; expected 10× connection count | ~50 KB total | Negligible. |
| `Idempotency-Key cache` | 250.1.D (Redis) | 100 RPS × 24 h × 1 KB = ~8.6 GB max at full saturation | ~8.6 GB at peak; TTL-evicted | Redis instance MUST size for this; current `BAAS_REDIS_URL` instance has 16 GB; sufficient with headroom. Phase 240's Redis pattern documented in `docs/capacity/lineage-storage.md` extends here. |

## Audit-event volume

Phase 250 introduces ~12 new audit codes (per [docs/api/error-codes.md](../api/error-codes.md) cross-ref):

| Audit code | Per-day at 100 RPS | Daily storage (1 KB / event) | Retention (D240.7 + D250) |
|---|---|---|---|
| `ASSET_FAIL_CLOSED_REJECTED` | ~50 (5% rejection rate) | ~50 KB | 90 d |
| `ASSET_WORKFLOW_ROLLED_BACK` | ~10 (1% rollback) | ~10 KB | 90 d |
| `ASSET_VERSION_MISMATCH` | ~100 (1% PATCH conflict rate) | ~100 KB | 90 d |
| `ASSET_PATCH_MISSING_IF_MATCH` (soak) | ~1 000 (until enforcement flip) | ~1 MB | 90 d |
| `ASSET_VISIBILITY_WRITE_DEPRECATED` | ~1 000 (during deprecation window) | ~1 MB | 90 d |
| `ASSET_SEMANTIC_DEGRADED` | ~100 (semantic-service noise) | ~100 KB | 90 d |
| `ASSET_ORPHAN_DRAFT_CLEANED` | ~10 (cleanup-job runs) | ~10 KB | 365 d (compliance-relevant) |
| `WORKFLOW_RUN_MIGRATED` | ~5 (rare) | ~5 KB | 365 d |
| `WORKFLOW_SOAK_EXTENDED` | ~1 (very rare) | ~1 KB | 365 d |
| `TENANT_FEATURE_FLAG_FLIPPED` | ~10 (admin actions) | ~10 KB | 365 d |
| `CROSS_SERVICE_VERSION_MISMATCH` | 0 (only on deploy failures; should never fire in steady-state) | n/a | 365 d |
| **Total** | ~2 300 events / day | ~2.5 MB / day | mixed retention |

12-month projection: ~900 MB on the `AuditEvent` table from Phase 250 codes alone. Comfortably within the 3-year retention envelope (per D240.7) on the existing audit infrastructure.

**Coupling to Phase 234**: high-volume codes (`ASSET_VERSION_MISMATCH`, `ASSET_PATCH_MISSING_IF_MATCH`) benefit from Phase 234.5's per-event-type retention registry — flagged as 90 d in this table; can be tightened to 30 d if Phase 234 lands compaction.

## Runtime resource sizing

### Hub api pod

- Per pod: 2 vCPU + 4 GiB RAM baseline.
- Phase 250 additions:
  - In-memory compliance + DQ scan increase peak memory by ~50 MB / concurrent scan (CSV buffer).
  - At 50 concurrent scans / pod: +2.5 GB peak. Total pod memory: 6.5 GiB.
  - Recommendation: bump pod memory to 8 GiB; 2 vCPU unchanged; HPA target CPU 60%.

### Hub worker pod (django-rq)

- Per pod: 2 vCPU + 4 GiB RAM baseline.
- Phase 250 additions:
  - Workflow re-sequence runs gates synchronously; same memory profile as api pod (~50 MB / scan).
  - At 50 concurrent workflows / pod: +2.5 GB peak.
  - Recommendation: bump worker memory to 8 GiB; 4 vCPU (compute-heavier than api); HPA target CPU 70%.

### Redis (BAAS instance)

- Existing 16 GiB instance.
- Phase 250 additions:
  - Idempotency-Key cache: ~8.6 GB peak (24h × 100 RPS × 1 KB).
  - Workflow state cache: ~1 GB.
  - Total Phase 250 use: ~10 GB.
  - Recommendation: NO upgrade needed; existing 16 GiB has headroom. Monitor `redis_memory_used_bytes` at p95 < 12 GB; alert at > 14 GB.

### PostgreSQL

- Existing 4 vCPU + 32 GiB RAM RDS instance.
- Phase 250 additions:
  - `WorkflowInstance` + `WorkflowState` table growth at ~3-4 GB / month with retention enforced.
  - Index growth: ~10% of table size per index; 5 new indexes × ~3 GB = ~1.5 GB.
  - Total Phase 250 storage growth: ~5 GB / month.
  - Recommendation: NO upgrade needed; existing 100 GB SSD has 4-year horizon at this rate.

## Per-tenant limits

Phase 250 introduces per-tenant concurrency semaphores (per ADR-AST-004 + Phase 250.A.18 equivalent):

- Per-tenant concurrent workflow runs: 50 (default; configurable per tenant).
- Per-tenant `Idempotency-Key` cache size: 100 keys (24h × ~5 keys/sec; cardinality-bounded).
- Per-tenant audit-event rate: ~150 events/day per tenant on average; accounted in the per-event-type retention registry.

## Capacity-review cadence

- **Monthly**: SRE review of the Phase 250 panels in Grafana — workflow duration, RQ queue depth, Redis memory, PostgreSQL storage growth.
- **Quarterly**: Tech-debt review evaluates retention policy effectiveness; tighten if >2× projection.
- **Phase 250 closeout**: full audit of the projections in this document vs reality; revise if drift > 25%.
- **Annually thereafter**: until Phase 250 capabilities transition to BAU (per RACI maintenance cadence).

## Soft / hard limits

| Limit | Soft (alert) | Hard (block) | Mechanism |
|---|---|---|---|
| Per-tenant concurrent workflows | 40 | 50 | Phase 250.A.18 semaphore returns 429 |
| RQ queue depth (global) | 500 | 1000 | Prometheus alert; auto-scale workers |
| Redis memory | 12 GB | 14 GB | Prometheus alert; cardinality-cap kicks in |
| PostgreSQL storage | 80 GB | 90 GB | Prometheus alert; retention-purge cadence increased |
| Per-tenant `Idempotency-Key` count | 100 | 200 | Phase 250.1.D cardinality cap |

## Related

- [docs/capacity/lineage-storage.md](lineage-storage.md) — existing capacity pattern.
- [docs/runbooks/asset-creation.md](../runbooks/asset-creation.md) — operational runbook (cross-references this doc).
- D240.7 + D250.x retention decisions.
