MVP_Scope.md

# MVP Scope

This document defines the **MVP (v1)** scope for the **Interoperable Data Hub**, based on:

- **System Requirements**
- **Personas** (Data Product Owner, Data Engineer, Compliance Officer, Data Consumer, Platform Admin, External Developer)

It focuses on *what will be delivered in v1* vs *what is explicitly out of scope for v1*.

---

## 1. Legend

- **In MVP v1**
  - ✅ = Fully in scope for v1
  - 🟡 = Partial / minimal implementation in v1
  - ⏳ = Explicitly out of scope for v1 (future)

- **Personas**
  - **DPO** = Data Product Owner
  - **DE** = Data Engineer / Contract Author
  - **CPO** = Compliance & Privacy Officer
  - **DC** = Data Consumer / Buyer
  - **MPA** = Marketplace Operator / Platform Admin
  - **DEV** = External Developer / Integrator

---

## 2. MVP Objectives (High-Level)

For **MVP v1**, the platform should:

- Allow **multi-tenant** onboarding of data assets via three flows (data-first, contract-first, contract-only).
- Enforce **DataContract standards** via DataContract CLI.
- Enforce **Data Quality** and **Compliance** gates at data intake, with:
  - Clear reports
  - Fail-closed behavior for compliance
- Expose basic **semantic representations** (URIs + JSON-LD + minimal SPARQL).
- Provide a basic **marketplace** with:
  - Internal catalog per tenant
  - Ability to make assets public
  - Simple purchase/access flow
- Provide **SDKs/CLI** for JS and Python to integrate contracts, DQ, and compliance programmatically.
- Log key actions in **audit trails** and expose a minimal **job model** for long-running operations.

---

## 3. Core Tenant, Users & Security

### 3.1 Multi-Tenancy & Roles

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Tenant model | Tenants as isolated orgs with their own users, catalogs, configs | ✅ | MPA, DPO, DE, CPO, DC, DEV | Single region/cluster initially; data residency support evolves later |
| Basic roles per tenant | Roles: Tenant Admin, Data Provider, Data Consumer; Auditor (read-only) | ✅ | DPO, DE, CPO, DC, MPA | Permissions based on System Requirements §9.6; fine-grained RBAC can evolve later |
| Platform-level admin | Global Platform Admin / Marketplace Operator | ✅ | MPA | Needed for tenant management & global marketplace control |

### 3.2 Security & Auth

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| AuthN for APIs & UI | Token-/key-based authentication for REST/GraphQL/UI | ✅ | All | Exact auth mechanism (OAuth2/JWT/API keys) to be chosen in design, but must support multi-tenant scoping |
| Role-based authZ | Enforce role & tenant-based access to resources | ✅ | All | Coarse-grained but enforced for v1 |
| Encryption in transit | HTTPS/TLS for all external & inter-service traffic | ✅ | All | |
| Encryption at rest | Storage-level encryption for DB, files, triple store | ✅ | All | Use cloud provider features in MVP |
| Basic rate limiting | Per-API key/tenant rate limits on sensitive endpoints (DQ, compliance) | 🟡 | DE, DEV, MPA | Basic caps & 429 responses; plan-based limits later |

### 3.3 Data Residency

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Single-region deployment | All tenants in a single primary region | ✅ | All | Data residency config per-tenant ⏳ (future) |
| Multi-region support | Assigning tenants to specific regions, cross-region policies | ⏳ | MPA | Explicitly out of MVP |

---

## 4. Data Contracts & Ingestion

### 4.1 Contract Standards & HubContract

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Support ODCS & DataContract.com versions | Accept, store, validate supported ODCS / DataContract.com versions | ✅ | DPO, DE, DEV | Exact subset: ODCS v2.2.2–v3.x + main DataContract.com versions per System Requirements |
| Canonical HubContract model | Internal normalized representation + `hub_contract_version` | ✅ | DE, DEV, DPO, MPA | Basic v1 model; migration to v2+ later |
| Store original contract | Preserve original spec, version, and raw JSON/YAML | ✅ | DPO, DE, DEV | Needed for round-trip & audits |

### 4.2 DataContract CLI Integration

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| CLI service wrapper | `datacontract-service` with `/validate`, `/lint`, `/convert` | ✅ | DE, DEV, DPO | With timeouts & basic concurrency |
| Validation status | Interpret CLI results → `VALID`, `INVALID`, `WARNING_ONLY`, `ERROR` | ✅ | DPO, DE | Only `VALID` active; `WARNING_ONLY` allowed with warnings |
| Spec/version selection in UI | Choose spec + version for new contracts (default to latest ODCS) | ✅ | DPO | Conversion via CLI, not custom code |

### 4.3 Ingestion Flows (UI & API)

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Data-first flow (UI) | Upload file, run compliance & DQ, infer schema, then edit contract & validate | ✅ | DPO, DE | Core MVP experience |
| Contract-first flow (UI) | Upload contract, validate, then upload data, run gates, reconcile schema | ✅ | DPO, DE | |
| Contract-only flow (UI) | Upload and validate contract, store contract-only asset | ✅ | DPO, DE | Attach data later with gates |
| Ingestion via SDK/API | Programmatic support for same 3 flows | ✅ | DE, DEV | At least REST-based, CLI/SDK wrappers |
| File size limits – UI | Browser upload up to ~1–2GB | ✅ | DPO, DE, DC | Configurable, but must be implemented |
| File size – CLI/SDK | Larger files supported (up to infra constraints) | 🟡 | DE, DEV | Simple multi-part or direct upload; no advanced chunking logic yet |

### 4.4 File Storage & Deduplication

| Capability             | Description                                                                 | In MVP v1 | Personas      | Notes |
|------------------------|-----------------------------------------------------------------------------|-----------|---------------|-------|
| File content hashing   | Compute and store SHA-256 hash (`content_sha256`) for each uploaded file   | ✅        | DE, DPO, DEV  | Used for compute reuse (e.g. skipping repeated validation) and duplicate detection. No changes to physical storage layout in MVP. |
| Physical blob dedupe   | Single stored blob referenced by multiple logical files via `file_blobs`   | ⏳        | MPA, DE, DEV  | Post-MVP. Requires `file_blobs` model and migration; not required for v1. |

---

## 5. Data Quality as a Service (DQ)

### 5.1 Core DQ Capabilities

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| DQ at intake (mandatory gate) | Run DQ before storing any new/updated data file | ✅ | DPO, DE, CPO, MPA | Using `intake_basic` profile |
| `intake_basic` profile | Types, null ratios, uniqueness, basic ranges, row count | ✅ | DPO, DE, CPO | Per System Requirements §2.8 |
| Structured DQ results | `overall_status`, `quality_score`, `checks[]`, `details_json` | ✅ | DPO, DE, CPO, MPA, DEV | Stored & linked to asset |

### 5.2 DQ Execution

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Full vs sampled DQ | Full scan for small/medium; sampling for large datasets | ✅ | DE, DPO | Sampling logic & metadata recorded |
| Manual DQ runs | Trigger DQ on existing assets manually via UI or API | 🟡 | DPO, DE | Minimal UI/API trigger; advanced scheduling later |
| Scheduled DQ runs | Periodic automatic checks | ⏳ | MPA, CPO | Explicitly post-MVP |

### 5.3 DQ as Billable Service

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Billable DQ runs | Track each DQ run as billable operation with metrics | ✅ | MPA | Basic metering + aggregation sufficient; pricing UI can be simple |

---

## 6. Data Compliance as a Service

### 6.1 Core Compliance Gate (Intake)

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Compliance gate at intake | Mandatory compliance check before storing data files | ✅ | DPO, DE, CPO, MPA | Fail-closed if engine fails; no override |
| Detection scope | Detect direct identifiers, payment data, health data, special categories, free-text PII | 🟡 | CPO, MPA, DPO | v1 heuristic; rules improved over time |
| Threshold policy | Default threshold (e.g. ≥1% with direct PII → `allowed_to_store = false`) | ✅ | MPA, CPO | Configurable per tenant later; global default in MVP |

### 6.2 Scan-Only Compliance

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| External scan-only mode | Run compliance checks on external files without storing data | ✅ | DE, DEV, CPO, MPA | Raw data ephemeral; only reports + hashes stored |
| Ephemeral storage & deletion | Delete raw scan-only data quickly after check | ✅ | MPA, CPO | Implementation detail but required behavior |

### 6.3 Compliance Reporting & Audit

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Structured compliance reports | `overall_status`, `risk_level`, `detected_categories`, `column_findings`, `regulation_mapping` | ✅ | CPO, DPO, MPA | Core report shape implemented in MVP |
| Audit entries per check | Audit log entry for each compliance run, including `allowed_to_store` decision | ✅ | CPO, MPA | Linked to job & asset |

---

## 7. Semantic Layer & Ontologies

### 7.1 URIs & JSON-LD

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Stable URIs for assets | Public URIs for contracts, datasets, versions | ✅ | DE, DEV, DPO, DC, CPO | Pattern like `/id/contract/{uuid}` |
| JSON-LD representations | `GET` on URIs returns JSON-LD with basic metadata | ✅ | DEV, DE | Minimal mapping; extended later |

### 7.2 RDF/Triple Store & SPARQL

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| RDF persistence | Store contract + asset metadata as RDF triples | ✅ | DEV, DE, MPA | Focus on DCAT + core custom ontology parts |
| SPARQL endpoint | Minimal SPARQL endpoint for queries | ✅ | DEV, DE, CPO | No advanced UI; just endpoint & docs |
| Ontology scope | Basic custom ontology extending DCAT + some PII/quality/compliance concepts | 🟡 | DEV, DE, CPO | MVP subset of full design |

### 7.3 Semantic Mapping Triggers

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Contract → RDF on save | Generate/update triples when contracts are saved | ✅ | DE, DPO, DEV | |
| Asset semantic status | Mark assets as `OK` or `DEGRADED` if mapping fails, with retries | ✅ | DPO, DE, MPA | MVP includes basic retry mechanism |

---

## 8. Marketplace & Billing

### 8.1 Asset Publishing & Visibility

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Internal catalog | Each tenant sees their own assets & internal-only assets | ✅ | DPO, DC, CPO, DE | |
| Public marketplace flag | Assets can be marked as public/marketplace-visible | ✅ | DPO, MPA | Requires tenant to be in good standing (KYC status) |
| Simple marketplace listing | List public assets with basic filters (domain, tags, owner, etc.) | ✅ | DC, DPO, MPA | Advanced filtering & semantic search later |

### 8.2 Purchase & Entitlements

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Basic purchase flow | Simple purchase / access request flow for public assets | ✅ | DC, DPO, MPA | Could be “request access” if payments handled outside for MVP |
| Entitlement model | After purchase/approval, consumer tenant has access to asset | ✅ | DC, DPO, MPA | Entitlements stored, checked for data/API access |

### 8.3 Billing & Cost Tracking

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Operation metering | Collect metrics per DQ/compliance run & key operations | ✅ | MPA | Future billing formulas can be applied later |
| Full billing engine & invoicing | Automated invoices, complex pricing, promotions | ⏳ | MPA | Out of MVP; might be partly external initially |

### 8.4 KYC / Tenant Vetting

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Store KYC status flag | Simple `verified`/`unverified` per tenant | ✅ | MPA | Actual KYC process & integrations defined outside MVP |
| Restrict selling to verified tenants | Only verified tenants allowed to publish public assets | ✅ | MPA | Business-level rule in MVP |

---

## 9. Developer Experience (DX)

### 9.1 SDKs & CLI

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| JS SDK | Basic JS SDK for core API calls (contracts, assets, DQ/compliance, jobs) | ✅ | DE, DEV | Polished but minimal surface |
| Python SDK | Basic Python SDK with similar coverage | ✅ | DE, DEV | |
| CLI tool | CLI wrapping APIs for common tasks (onboarding, checks) | 🟡 | DE, DEV | MVP can be minimal; grows over time |

### 9.2 API Documentation & Sandbox

| Capability           | Description                          | In MVP v1 | Personas | Notes                                    |
|----------------------|--------------------------------------|-----------|----------|------------------------------------------|
| Versioned REST API docs | `/api/v1` documented with schemas & examples | ✅ | DE, DEV | |
| GraphQL schema docs  | Document GraphQL schema for main types | ⏳       | DE, DEV | Post-MVP. v1 external API is REST + SPARQL only. |
| SPARQL & JSON-LD docs | Examples of URI patterns & queries | ✅ | DEV, DE | |


---

## 10. Jobs & Audit

### 10.1 Job Model

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Job entity | Standard `Job` structure (`job_id`, `type`, `status`, `resource_id`, timestamps) | ✅ | DE, DEV, DPO, MPA | For DQ, compliance, contract validation, semantic mapping |
| Job API | `GET /jobs/{job_id}`, list jobs per asset/tenant | ✅ | DE, DEV, DPO | UI uses this to show progress |
| Job → Audit linkage | Each job generates/links to an audit log entry | ✅ | CPO, MPA, DE | |

### 10.2 Audit Trail

| Capability | Description | In MVP v1 | Personas | Notes |
|-----------|-------------|-----------|----------|-------|
| Audit event logging | Key events (uploads, checks, validations, purchases, access) logged | ✅ | CPO, MPA, DE, DPO | At least minimal set from System Requirements §4.3 |
| Audit API & UI | Tenant-scoped audit browsing, export to CSV/JSON | ✅ | CPO, MPA, DPO | Initially simple filters (time range, asset, event type) |
| “No PII in logs” enforcement | Ensure no raw PII in logs; only metrics & hashes | ✅ | CPO, MPA | Design & code review discipline |

---

## 11. Out-of-Scope (Post-MVP) Summary

The following are explicitly **not required** for MVP v1, but are part of the future roadmap:

- **Advanced marketplace**
  - Complex pricing (tiers, promotions, revenue sharing UI).
  - Rich marketplace search & semantic faceting beyond basics.
- **Scheduled DQ/compliance**
  - Periodic, automated checks with scheduling UI.
- **Streaming ingestion**
  - Real-time contracts for streams and event data.
- **Advanced semantic UI**
  - Full visual ontology browser, SPARQL query builder in UI.
- **Advanced data residency**
  - Per-tenant region assignment, cross-region replication policies.
- **Full KYC integration**
  - Automated identity verification flows, third-party KYC providers.
- **Full billing system**
  - Automated invoicing, payments integration (Stripe, etc.), detailed billing dashboards.
- **Highly granular RBAC**
  - Fine-grained per-field/per-API-permission beyond the base roles in MVP.

These items should be tracked as separate roadmap epics and **must not block** the delivery of MVP v1.

---

_End of MVP Scope._
