# MVP Features

This page lists every feature area for the Meshant MVP (v1) and its
inclusion tier. It is promoted from the internal `InputDocs/MVP_Scope.md`
planning document.

**Tier legend**

- **Fully included** -- fully in scope and shipping at launch.
- **Partial** -- minimal or limited implementation at launch; expanded later.
- **Post-MVP** -- explicitly deferred; tracked on the [Roadmap](roadmap.md).

---

## Core

### Multi-Tenancy and Roles

| Feature | Tier | Notes |
|---------|------|-------|
| Tenant model (isolated orgs, catalogs, configs) | Fully included | Single region initially |
| Basic roles per tenant (Admin, Provider, Consumer, Auditor) | Fully included | Fine-grained RBAC evolves later |
| Platform-level admin / Marketplace Operator | Fully included | Global tenant and marketplace control |

Concept: [Tenants](../concepts/tenants.md) | [Users and Roles](../concepts/users-and-roles.md)
API: `GET /api/v1/tenants/`, `GET /api/v1/users/`

### Authentication and Security

| Feature | Tier | Notes |
|---------|------|-------|
| Token/key-based AuthN (JWT, API keys) | Fully included | Multi-tenant scoping |
| SSO integration (SAML / OIDC) | Fully included | Optional per tenant |
| Role-based AuthZ | Fully included | Coarse-grained, enforced |
| Encryption in transit (TLS) and at rest | Fully included | Cloud-provider encryption |
| Basic rate limiting (per key / tenant) | Partial | 429 responses; plan-based limits later |

API: `POST /api/v1/auth/login/`, `POST /api/v1/auth/register/`, `GET /api/v1/auth/api-keys/`

### Data Residency

| Feature | Tier | Notes |
|---------|------|-------|
| Single-region deployment | Fully included | All tenants co-located |
| Multi-region / per-tenant region assignment | Post-MVP | |

---

## Data Management

### Assets

| Feature | Tier | Notes |
|---------|------|-------|
| Data-first ingestion flow (upload file, infer schema, create contract) | Fully included | Core MVP experience |
| Contract-first flow (upload contract, then data) | Fully included | |
| Contract-only flow (contract without data) | Fully included | Data attached later |
| Ingestion via SDK / API (same three flows) | Fully included | REST + CLI/SDK wrappers |
| Browser upload up to 1-2 GB | Fully included | Configurable |
| CLI/SDK large-file upload | Partial | Simple multipart; no advanced chunking |

Concept: [Assets](../concepts/assets.md)
API: `GET /api/v1/assets/`, `POST /api/v1/assets/`, `POST /api/v1/assets/{id}/activate/`

### Contracts (ODCS and HubContract)

| Feature | Tier | Notes |
|---------|------|-------|
| ODCS v2.2.2-v3.x and DataContract.com support | Fully included | Accept, store, validate |
| Canonical HubContract model | Fully included | Internal normalized representation |
| Original contract preservation | Fully included | Round-trip and audit |
| DataContract CLI integration (`/validate`, `/lint`, `/convert`) | Fully included | Timeouts, basic concurrency |
| Validation statuses (VALID, INVALID, WARNING_ONLY, ERROR) | Fully included | |

Concept: [Contracts](../concepts/contracts.md)
API: `GET /api/v1/contracts/`, `POST /api/v1/contracts/{id}/validate/`, `POST /api/v1/contracts/{id}/lint/`

### Datasets

| Feature | Tier | Notes |
|---------|------|-------|
| Dataset CRUD | Fully included | |
| Dataset versioning and schema evolution | Fully included | |
| Time-travel queries | Fully included | |

Concept: [Datasets](../concepts/datasets.md)
API: `GET /api/v1/datasets/`, `POST /api/v1/datasets/`

### Files

| Feature | Tier | Notes |
|---------|------|-------|
| Multipart upload (init / upload / complete) | Fully included | |
| SHA-256 content hashing | Fully included | Duplicate detection, compute reuse |
| Physical blob deduplication | Post-MVP | Requires `file_blobs` migration |

API: `POST /api/v1/files/init/`, `POST /api/v1/files/complete/`

---

## Quality and Compliance

### Data Quality

| Feature | Tier | Notes |
|---------|------|-------|
| DQ gate at intake (`intake_basic` profile) | Fully included | Types, nulls, uniqueness, ranges |
| Structured DQ results (`quality_score`, `checks[]`) | Fully included | Linked to asset |
| Full vs sampled DQ | Fully included | Sampling for large datasets |
| Manual DQ runs (UI / API) | Partial | Minimal trigger; scheduling later |
| Scheduled DQ runs | Post-MVP | |
| Billable DQ metering | Fully included | Operation tracking |

Concept: [DQ Runs](../concepts/dq-runs.md)
API: `GET /api/v1/dq/runs/`, `POST /api/v1/dq/runs/`

### Compliance

| Feature | Tier | Notes |
|---------|------|-------|
| Compliance gate at intake (fail-closed) | Fully included | No override |
| PII detection (direct identifiers, payment, health, free-text) | Partial | Heuristic v1; improved over time |
| Threshold policy (e.g. >=1% direct PII blocks storage) | Fully included | Global default; per-tenant later |
| Scan-only mode (external files, ephemeral storage) | Fully included | Only reports and hashes retained |
| Structured compliance reports | Fully included | `risk_level`, `detected_categories`, `regulation_mapping` |
| Audit entries per compliance run | Fully included | Linked to job and asset |

Concept: [Compliance Runs](../concepts/compliance-runs.md)
API: `POST /api/v1/compliance/runs/`

---

## Marketplace

| Feature | Tier | Notes |
|---------|------|-------|
| Internal catalog per tenant | Fully included | |
| Public marketplace flag | Fully included | Requires KYC-verified tenant |
| Marketplace listings with basic filters | Fully included | Advanced semantic search later |
| Data preview (sample data, schema, quality metrics) | Fully included | |
| Trust signals (quality badges, SLA labels) | Fully included | Configurable per tenant |
| Basic purchase / access-request flow | Fully included | |
| Entitlement model | Fully included | Checked on data/API access |
| Operation metering | Fully included | |
| KYC status flag and verified-tenant restriction | Fully included | Actual KYC process external |
| Complex pricing, promotions, revenue sharing | Post-MVP | |
| Rich semantic faceting | Post-MVP | |

Concept: [Marketplace Listings](../concepts/marketplace-listings.md)
API: `GET /api/v1/marketplace/listings/`, `POST /api/v1/marketplace/orders/`

---

## Governance

| Feature | Tier | Notes |
|---------|------|-------|
| Access requests and approval workflow | Fully included | |
| Role-based and attribute-based access control | Fully included | |
| Data classifications | Fully included | |
| Compliance reporting | Fully included | |
| Retention policies | Fully included | |
| Consent management | Fully included | |
| GDPR data-subject rights | Fully included | Export, erasure, portability |

Concept: [Governance](../concepts/governance.md)
API: `GET /api/v1/governance/access-requests/`, `POST /api/v1/governance/access-requests/{id}/approve/`

---

## Developer Experience

| Feature | Tier | Notes |
|---------|------|-------|
| Versioned REST API (`/api/v1`) with OpenAPI docs | Fully included | |
| Python SDK | Fully included | Contracts, assets, DQ, compliance, jobs |
| CLI tool | Partial | Minimal surface; grows over time |
| SPARQL and JSON-LD documentation | Fully included | URI patterns and query examples |
| Webhooks (event subscriptions) | Fully included | |
| GraphQL schema docs | Post-MVP | v1 external API is REST + SPARQL only |
| JavaScript SDK | Post-MVP | Planned in roadmap |

Concept: [Webhooks](../concepts/webhooks.md)
API: `GET /api/v1/webhooks/`

---

## Platform

### Search

| Feature | Tier | Notes |
|---------|------|-------|
| Full-text search across contracts, assets, datasets | Fully included | |
| Resource-specific search | Fully included | |

Concept: [Search](../concepts/search.md)
API: `GET /api/v1/search/`

### Audit

| Feature | Tier | Notes |
|---------|------|-------|
| Audit event logging (uploads, checks, purchases, access) | Fully included | |
| Audit API with filters (time, asset, event type) | Fully included | CSV/JSON export |
| No-PII-in-logs enforcement | Fully included | |

Concept: [Audit Events](../concepts/audit-events.md)
API: `GET /api/v1/audit/`

### Jobs

| Feature | Tier | Notes |
|---------|------|-------|
| Job entity (DQ, compliance, validation, semantic mapping) | Fully included | |
| Job API (`GET /jobs/{id}`, list per asset/tenant) | Fully included | |
| Job-to-audit linkage | Fully included | |

Concept: [Jobs](../concepts/jobs.md)
API: `GET /api/v1/jobs/`, `GET /api/v1/jobs/{id}/`

### Semantic Layer

| Feature | Tier | Notes |
|---------|------|-------|
| Stable URIs for assets and contracts | Fully included | `/id/contract/{uuid}` pattern |
| JSON-LD representations | Fully included | |
| RDF persistence (DCAT + custom ontology) | Fully included | |
| SPARQL endpoint | Fully included | No UI; endpoint + docs |
| Ontology scope (DCAT + PII/quality/compliance) | Partial | MVP subset |
| Contract-to-RDF on save | Fully included | |
| Asset semantic status (OK / DEGRADED) | Fully included | Basic retry |

Concept: [Semantic Resources](../concepts/semantic-resources.md)
API: `GET /api/v1/semantic/`

### Observability

| Feature | Tier | Notes |
|---------|------|-------|
| Data observability metrics | Fully included | |
| Freshness monitoring | Fully included | |
| Contract-level lineage | Fully included | |
| SLA monitoring | Fully included | |

Concept: [Lineage](../concepts/lineage.md)
API: `GET /api/v1/observability/metrics/`, `GET /api/v1/observability/lineage/`

### Billing

| Feature | Tier | Notes |
|---------|------|-------|
| Plan tiers (Free, Professional, Enterprise) | Fully included | |
| Plan-based quota enforcement | Fully included | |
| Usage metering | Fully included | |
| Full billing engine and invoicing | Post-MVP | External initially |

Concept: [Billing](../concepts/billing.md)
API: `GET /api/v1/billing/`

### Versioning and Orchestration

| Feature | Tier | Notes |
|---------|------|-------|
| Resource versioning | Fully included | Contracts, datasets |
| Workflow orchestration | Fully included | ODPS, ingestion |

Concept: [Versioning](../concepts/versioning.md) | [Orchestration](../concepts/orchestration.md)

---

## Post-MVP (Explicitly Deferred)

The following feature areas are **not** included in the MVP and are tracked
on the [Roadmap](roadmap.md).

| Feature Area | Notes |
|--------------|-------|
| BaaS (Backend as a Service) | Dedicated instances, SDK downloads |
| Virtualization (ODBC/JDBC virtual datasets) | Virtual query layer |
| Data Mesh (domains, topology, federation) | Domain-scoped governance |
| ML / AI (model serving, training, inference) | Anomaly detection, recommendations |
| Transformation pipelines | ETL/ELT within the platform |
| Social (ratings, reviews, communities) | Marketplace social features |
| Scheduled Ingestion | Periodic automated data pulls |
| Scheduled Export | Periodic automated data pushes |
| Streaming ingestion | Real-time contracts for event data |
| Advanced RBAC | Per-field / per-API fine-grained permissions |
| Advanced marketplace | Complex pricing, promotions, revenue sharing |
| Advanced semantic UI | Ontology browser, SPARQL query builder |
| GraphQL API | Post-MVP; REST + SPARQL only in v1 |
| JavaScript SDK | Planned post-MVP |
