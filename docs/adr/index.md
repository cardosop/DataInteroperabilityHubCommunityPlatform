# Architecture Decision Records — Index

**Last updated**: 2026-05-17  
**Total ADRs**: 36 across 11 topic areas  
**280.C.6.3**: Decision summaries added for all ADRs.

## Decision Table

| ID | Title | Decision Summary | Topic | Status | Date | Phase |
|---|---|---|---|---|---|---|
| ADR-API-GQL-001 | GraphQL Consolidation | Strawberry selected as canonical GraphQL implementation; Graphene-Django + graphql_ld deprecated | API | Accepted | 2026-05-13 | 277.B.102 |
| ADR-API-VER-001 | API Versioning Strategy (v2 Plan) | URL-prefix versioning (/api/v1/, /api/v2/); v2 activated by tenant feature flag; v1 deprecated with 12-month sunset | API | Accepted | 2026-05-13 | 277.B.024 |
| ADR-AST-001 | Fail-closed asset persistence | Assets saved to DB on creation failure with status=DRAFT; user can fix and retry; prevents data loss | Asset Creation | Accepted | 2026-05-03 | 250.1.A |
| ADR-AST-002 | Federated import flag | Per-tenant feature flag gates federated asset import; graceful degradation when federation service unavailable | Asset Creation | Accepted | 2026-05-03 | 250.5.A |
| ADR-AST-003 | Asset.status canonical; visibility derived | `status` is the single source of truth; `visibility` is derived from status + compliance; no dual-write | Asset Creation | Accepted | 2026-05-03 | 250.3.B |
| ADR-AST-004 | Optimistic locking on PATCH | Every asset PATCH uses `version` field for optimistic concurrency; 409 Conflict on version mismatch | Asset Creation | Accepted | 2026-05-03 | 250.7.B |
| ADR-AST-005 | Idempotency-Key header format | `Idempotency-Key: <uuid>` header for POST/PATCH; 24h key TTL in Redis; replay returns stored response | Asset Creation | Accepted | 2026-05-03 | 250.1.D |
| ADR-AST-006 | Semantic mapping async + graceful-degrade | Asset→RDF semantic mapping runs async via RQ; failure degrades gracefully (asset published without RDF, retryable) | Asset Creation | Accepted | 2026-05-03 | 250.7.A |
| ADR-BR-001 | Option C (Hybrid) Business Rules | Hybrid rules engine: simple rules in Python, complex chains via registry; rules are versioned and tenant-gated | Business Rules | Accepted | 2026-05-12 | 274 |
| ADR-CLI-SDK-001 | Shared Python Modules | `shared/` at repo root for deduplicated Python modules; `_mvp_detection.py` canonical source; per-consumer re-exports | CLI/SDK | Accepted | 2026-05-14 | 278.AA.15 |
| ADR-CLI-SDK-002 | Error Code Constants | `shared/python/datahub_error_codes.py` as single source of truth for structured API error codes; string constants over Enum | CLI/SDK | Accepted | 2026-05-14 | 279.J.2 |
| ADR-DSF-001 | Dataset versioning correctness | Immutable dataset versions with content-addressing (SHA-256); versions are append-only, never mutated | Datasets/Files | Accepted | 2026-05-12 | 260.0 |
| ADR-DSF-002 | Upload surface & CORS posture | Presigned S3 URLs for direct browser→S3 uploads; API never touches file bytes; CORS allow-list per-environment | Datasets/Files | Accepted | 2026-05-12 | 260.0 |
| ADR-DSF-003 | Purge idempotency + distributed locks | File purge uses Redis Redlock for distributed mutual exclusion; purge is idempotent (repeatable without side effects) | Datasets/Files | Accepted | 2026-05-12 | 260.0 |
| ADR-DSF-004 | Minimum ClamAV engine version | ClamAV engine ≥1.4.0 required; version handshake at startup; older engines reject with clear error | Datasets/Files | Accepted | 2026-05-12 | 260.0 |
| ADR-DSF-005 | FILES/DATASETS error-code layering | Domain-specific error codes (FILE_*, DATASET_*) with consistent HTTP→code mapping; audit events on every error | Datasets/Files | Accepted | 2026-05-12 | 260.0 |
| ADR-DSF-006 | EICAR fixtures + CI antivirus | EICAR test files in test fixtures; CI runs ClamAV in Docker; production scan path identically exercised in CI | Datasets/Files | Accepted | 2026-05-12 | 260.0 |
| ADR-DSF-007 | SHA‑256 uniqueness & tenant isolation | SHA-256 deduplication scoped per-tenant (not global); prevents cross-tenant data leakage via hash collision | Datasets/Files | Accepted | 2026-05-12 | 260.0 |
| ADR-FE-001 | Central useActiveTenantId() Hook | Single React hook for tenant ID; eliminates prop-drilling; reads from JWT claims, not URL; provides loading/error/blocked states | Frontend | Accepted | 2026-05-12 | 276.B.002 |
| ADR-GOV-001 | Multi-Step Approval State Machine | AccessRequest flows through ordered approval chain; each step snapshots policy; PENDING_NEXT_APPROVER intermediate state; delegation support | Governance | Accepted | 2026-05-12 | 272 |
| ADR-LIN-001 | Lineage storage shape | Lineage stored as directed graph in PostgreSQL + RDF (Fuseki); edges carry metadata (transform type, timestamp, contract ref) | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-002 | Lineage snapshot model | Immutable snapshots at points in time; diff between any two snapshots; SCD-2 for upstream changes (close-and-reopen) | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-003 | OpenLineage adapter shape | Adapter translates OpenLineage events → internal lineage model; HMAC-signed ingestion; stateless adapter behind API gateway | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-004 | Change-notification storm prevention | Debounce lineage change notifications; batch events (max 1/sec per asset); consumers poll or subscribe to WebSocket channel | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-005 | Field-level lineage editor | Interactive field-level lineage graph; column-to-column mappings; drag-to-reorder; diff against contract schema | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-006 | Cross-tenant detail granularity | Cross-tenant lineage shows asset-level (not column-level); intra-tenant shows full field-level detail; prevents data leakage | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-007 | Event-bus framework audit | Redis Streams for internal event bus; at-least-once delivery; consumer groups for fan-out; dead-letter queue for unprocessable events | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-008 | Async-worker framework audit | RQ (Redis Queue) for async jobs; separate queues (default, low, critical); circuit breaker integration for downstream dependency failures | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-009 | IaC pattern audit | Terraform for AWS infrastructure; Helm for Kubernetes applications; environment parity enforced via module sharing | Lineage | Accepted | 2026-04-30 | 228 |
| ADR-LIN-F3 | Notification channels for F3 | WebSocket for real-time; webhook for external; email digest for batched; user-configurable per notification type | Lineage | Accepted | 2026-05-01 | 228.F3 |
| UX-Activation | UX & Activation — Phase 278 Index | Persona-driven home pages; onboarding wizard with progress tracking; feature-gated progressive disclosure | UX | Proposed | 2026-05-12 | 278 |
| WH-0004 | WarehouseConnection naming | Connector model named `WarehouseConnection` (not `Connector` or `Integration`); consistent with domain terminology | Warehouse | Accepted | 2026-05-12 | 275.A.14 |
| WH-0005a | API Versioning for Warehouse Connectivity | Warehouse endpoints follow /api/v1/warehouses/ pattern; versioned independently from core API | Warehouse | Accepted | 2026-05-12 | 275.A.22 |
| WH-0005b | Build vs leverage decision | Custom warehouse connector framework (not Airbyte/Fivetran); thin abstraction over JDBC/ODBC with Meshant-specific validation | Warehouse | Accepted | 2026-05-12 | 275.E.3g |
| WH-0005c | Hybrid inbound architecture | Push (webhook) + pull (scheduled) ingestion paths; both feed into same normalization pipeline; tenant chooses per-warehouse | Warehouse | Accepted | 2026-05-12 | 275.E.3g |
| WH-0005d | Wave execution strategy | Warehouse connectivity rolled out in 4 waves: (1) Snowflake, (2) BigQuery, (3) Redshift, (4) Databricks; each wave adds connector + tests | Warehouse | Accepted | 2026-05-12 | 275.E.3g |

## By Topic

| Topic | Count | Most Recent |
|---|---|---|
| [API](api-surface/) | 2 | 2026-05-13 |
| [API Versioning](api-versioning/) | 1 | 2026-05-13 |
| [Asset Creation](asset-creation/) | 6 | 2026-05-03 |
| [Business Rules](business-rules/) | 1 | 2026-05-12 |
| [CLI/SDK](cli-sdk/) | 2 | 2026-05-14 |
| [Datasets/Files](datasets-files/) | 7 | 2026-05-12 |
| [Frontend](frontend-audit/) | 1 | 2026-05-12 |
| [Governance](governance/) | 1 | 2026-05-12 |
| [Lineage](lineage/) | 10 | 2026-05-01 |
| [UX & Activation](ux-activation/) | 1 | 2026-05-12 |
| [Warehouse Connectivity](warehouse-connectivity/) | 5 | 2026-05-12 |

## By Status

| Status | Count |
|---|---|
| Accepted | 34 |
| Proposed | 1 (UX-Activation) |
| Superseded | 0 |

## ADR Format

Each ADR follows a lightweight template:

```markdown
# ADR-XXX-NNN — Title

**Status**: {Proposed, Accepted, Superseded}
**Date**: YYYY-MM-DD
**Phase**: {Phase name + number}

## Context
## Decision
## Consequences
```

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-15 (280.C.6.3 — decision summaries added)
- **Next review**: 2026-08-15

New ADRs must be added to this index with the decision table entry. Superseded ADRs must be marked as such in both the ADR file and this index.
