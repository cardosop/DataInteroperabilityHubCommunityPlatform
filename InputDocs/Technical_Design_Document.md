# Technical Design Document (TDD) – Interoperable Data Hub

> Version: MVP v1  
> Status: Draft  
> Scope: Core platform (contracts, assets, DQ, compliance, semantics, marketplace-lite)

This document describes the **technical design** for the Interoperable Data Hub MVP. It translates the system requirements, domain model, and API spec into implementation-level details focused on:

- Database schema (logical data model, keys, indexes).
- Service communication patterns (sync/async, boundaries).
- Error handling standards (cross-service behavior).
- Monitoring & observability (metrics, logs, tracing).

**Technology Stack**: See `Technology_Stack_Decisions.md` for specific technology choices (Django, PostgreSQL, Redis, Strawberry GraphQL, etc.).

---

## 1. Architecture Overview (Recap)

High-level components:

- **API Gateway / Backend Service** (`api-service`)
  - Exposes `/api/v1` REST APIs.
  - **Framework**: Django with Django REST Framework (see `Technology_Stack_Decisions.md`)
  - Implements tenant/user auth & authorization.
  - Owns business logic for assets, contracts, DQ/compliance orchestration, marketplace, and jobs.
  - Talks to the primary relational database and job queue.

- **Job Worker Service** (`worker-service`)
  - Consumes jobs from the queue.
  - Executes long-running or heavy operations:
    - Invokes DataContract CLI.
    - Orchestrates DQ runs (Great Expectations / Soda).
    - Orchestrates compliance scans.
    - Triggers semantic mapping builds.
  - Writes back results (DQRun, ComplianceRun, Job status) to the DB.

- **DataContract CLI Service** (`datacontract-service`)
  - Thin wrapper around `datacontract-cli`.
  - Exposes internal HTTP/gRPC API for:
    - `lint()`, `validate()`, `convert()`.

- **DQ Service** (`dq-service`)
  - Wraps Great Expectations and Soda.
  - Consumes metadata (schema, quality rules) and reads data from object storage or external sources.
  - Returns normalized DQRun result to `worker-service`.

- **Compliance Service** (`compliance-service`)
  - Performs PII/sensitive data detection and rules evaluation.
  - Returns normalized ComplianceRun result to `worker-service`.

- **Semantic Service** (`semantic-service`)
  - Maintains RDF/triple store.
  - **Triple Store**: Apache Jena Fuseki with TDB2 (see `Technology_Stack_Decisions.md`)
  - Provides:
    - URI/IRI resolution.
    - JSON-LD views for assets/contracts.
    - SPARQL endpoint (minimal for MVP).

- **File Storage**
  - Object storage (e.g., S3-compatible).
  - Stores uploaded data files and generated reports.
  - Accessed via pre-signed URLs.

- **Relational Database**
  - **Database**: PostgreSQL 16.x (see `Technology_Stack_Decisions.md`)
  - **ORM**: Django ORM (built-in)
  - Primary persistence for:
    - Tenants, users, roles.
    - Assets, contracts, datasets.
    - Jobs, DQRuns, ComplianceRuns.
    - AuditEvents.
    - Marketplace listings & entitlements.
    - Semantic mapping references.

---

## 2. Database Schema

### 2.1 Technology Choice

- **Relational DB**: PostgreSQL 16.x (see `Technology_Stack_Decisions.md`)
- **ORM**: Django ORM (built-in with Django)
- Use:
  - `UUID` as primary keys for core entities.
  - `JSONB` for flexible structures (HubContract, quality/compliance reports, semantic metadata).
- Multi-tenancy:
  - Row-level multi-tenancy using `tenant_id` on all business tables.
  - No sharing of rows across tenants, except for:
    - Global configs.
    - Public listings (still refer back to provider tenant).

### 2.2 Core Tables

#### 2.2.1 `tenants`

Represents organizations (or individual users acting as their own tenant).

Columns:

- `id` (UUID, PK)
- `name` (text, unique within environment)
- `slug` (text, URL-friendly identifier, unique)
- `status` (enum: `ACTIVE`, `SUSPENDED`, `DELETED`)
- `region` (text, e.g. `eu-central-1`)
- `created_at` (timestamp)
- `updated_at` (timestamp)

Indexes:

- Unique index on `slug`.
- Optional index on `region`.

#### 2.2.2 `users`

Represents user accounts; always associated with exactly one tenant in MVP.

Columns:

- `id` (UUID, PK)
- `tenant_id` (UUID, FK → `tenants.id`)
- `email` (text, unique per tenant)
- `display_name` (text)
- `status` (enum: `ACTIVE`, `INVITED`, `DISABLED`)
- `created_at`, `updated_at` (timestamp)

Indexes:

- `(tenant_id, email)` unique.

#### 2.2.3 `roles` and `user_roles`

Roles are logical permissions within a tenant.

`roles`:

- `id` (UUID, PK)
- `tenant_id` (UUID, FK)
- `name` (text: `TENANT_ADMIN`, `PROVIDER`, `CONSUMER`, `AUDITOR` etc.)
- `description` (text)
- `created_at`, `updated_at`

`user_roles` (many-to-many):

- `user_id` (UUID, FK → `users.id`)
- `role_id` (UUID, FK → `roles.id`)
- composite PK `(user_id, role_id)`

#### 2.2.4 `assets`

Represents a single logical data product (contract + dataset).
For MVP, status = PUBLIC implies visibility = PUBLIC. RETIRED replaces previous DEPRECATED/ARCHIVED states.

Columns:

- `id` (UUID, PK, NOT NULL)
- `tenant_id` (UUID, FK, NOT NULL)
- `key` (text, NOT NULL, unique per tenant; human-friendly identifier)
- `name` (text, NOT NULL)
- `description` (text, NULL)
- `domain` (text, NULL, e.g. `marketing`, `finance`)
- `status` (enum: `DRAFT`, `ACTIVE`, `PUBLIC`, `RETIRED`, NOT NULL, DEFAULT `DRAFT`)
- `visibility` (enum: `INTERNAL`, `PUBLIC`, NOT NULL, DEFAULT `INTERNAL`)
- `latest_contract_id` (UUID, FK → `contracts.id`, nullable)
- `latest_dataset_id` (UUID, FK → `datasets.id`, nullable)
- `dq_status` (enum: `UNKNOWN`, `PASS`, `WARN`, `FAIL`, NOT NULL, DEFAULT `UNKNOWN`)
- `compliance_status` (enum: `UNKNOWN`, `PASS`, `WARN`, `FAIL`, NOT NULL, DEFAULT `UNKNOWN`)
- `created_by` (UUID, FK → `users.id`, NOT NULL)
- `created_at`, `updated_at` (timestamp, NOT NULL, DEFAULT CURRENT_TIMESTAMP)

Indexes:

- `(tenant_id, key)` unique.
- Index on `(tenant_id, visibility)`.
- Index on `(tenant_id, dq_status)` and `(tenant_id, compliance_status)` for filtering.

#### 2.2.5 `contracts`

Represents the canonical internal HubContract + original source contract.

Columns:

- `id` (UUID, PK, NOT NULL)
- `tenant_id` (UUID, FK, NOT NULL)
- `asset_id` (UUID, FK → `assets.id`, NULL - nullable for contract-only assets)
- `version` (integer, NOT NULL, per-asset version counter)
- `source_spec` (text, NOT NULL: e.g. `ODCS`)
- `source_spec_version` (text, NOT NULL: `3.0.2`, etc.)
- `hub_contract_version` (text, NOT NULL: `1.0.0`, etc.)
- `raw_contract` (JSONB or text, NOT NULL; original content)
- `hub_contract` (JSONB, NULL; normalized internal model, set after normalization)
  - **Enhanced HubContract Structure**: The `hub_contract` JSONB field MUST contain complete HubContract v1 with all sections:
    - `info`: name, description, version, owners (array with name/email), tags (array)
    - `schema`: fields (with all properties: semantic_type, format, pattern, enum, default, min/max, metadata), primary_key, unique_constraints, indexes
    - `quality`: default_profile_key, rules (with rule_id, dimension, expression, severity)
    - `privacy_compliance`: contains_personal_data, personal_data_categories, jurisdictions, legal_bases, retention_policy
    - `lifecycle`: data_source, refresh_cadence, slas (availability, latency_ms_p95)
    - `marketplace`: license_summary, intended_use, restricted_use
    - `extensions`: Unmappable fields preserved in extensions.odcs
- `cli_validation_status` (enum: `VALID`, `INVALID`, `WARNING_ONLY`, `ERROR`, NULL, DEFAULT NULL - set after CLI validation)
- `cli_output` (JSONB, NULL; sanitized lint/validation details)
- `status` (enum: `DRAFT`, `VALID`, `INVALID`, `WARNING_ONLY`, NOT NULL, DEFAULT `DRAFT`)
- `is_latest` (boolean, NOT NULL, DEFAULT false)
- `created_by` (UUID, FK → `users.id`, NOT NULL)
- `created_at`, `updated_at` (timestamp, NOT NULL, DEFAULT CURRENT_TIMESTAMP)

Indexes:

- `(tenant_id, asset_id, version)` unique.
- `(tenant_id, asset_id, is_latest)` partial index where `is_latest = true`.

#### 2.2.6 `datasets`

Represents a dataset attached to an asset (file-based or external reference).

Columns:

- `id` (UUID, PK, NOT NULL)
- `tenant_id` (UUID, FK, NOT NULL)
- `asset_id` (UUID, FK → `assets.id`, NOT NULL)
- `version` (integer, NOT NULL, per-asset dataset version)
- `kind` (enum: `FILE`, `EXTERNAL_REF`, NOT NULL)
- `file_id` (UUID, FK → `files.id`, NULL - required when `kind = 'FILE'`)
- `external_ref` (text, NULL - required when `kind = 'EXTERNAL_REF'`; e.g. table name, connection string identifier)
- `schema_inferred` (JSONB, NULL; schema from data)
- `row_count` (bigint, NULL)
- `sample_reference` (JSONB or text, NULL; pointing to stored sample)
- `created_by` (UUID, NOT NULL)
- `created_at`, `updated_at` (timestamp, NOT NULL, DEFAULT CURRENT_TIMESTAMP)

Indexes:

- `(tenant_id, asset_id, version)` unique.
- `(tenant_id, asset_id)` for latest dataset queries.

#### 2.2.7 `files`

Represents uploaded files (intake or scan-only).

Columns:

- `id` (UUID, PK, NOT NULL)
- `tenant_id` (UUID, FK, NOT NULL)
- `original_filename` (text, NOT NULL)
- `content_type` (text, NULL)
- `size_bytes` (bigint, NULL - set when upload completes)
- `storage_path` (text, NOT NULL; bucket/key)
- `purpose` (enum: `DATASET`, `EXTERNAL_SCAN`, `SAMPLE`, `REPORT`, NOT NULL)
- `status` (enum: `UPLOADING`, `READY`, `FAILED`, `DELETED`, NOT NULL, DEFAULT `UPLOADING`)
- `content_sha256` (text, NULL, DEFAULT NULL - SHA-256 hash, hex-encoded; NULL during upload, computed when status = READY)
- `created_by` (UUID, NULL - nullable for system-created files)
- `created_at`, `updated_at` (timestamp, NOT NULL, DEFAULT CURRENT_TIMESTAMP)

Indexes:

- `(tenant_id, status)`
- `storage_path` unique.

#### 2.2.8 `dq_runs`

Represents one data quality run invocation.

Columns:

- `id` (UUID, PK, NOT NULL)
- `tenant_id` (UUID, FK, NOT NULL)
- `asset_id` (UUID, FK → `assets.id`, NULL - at least one of asset_id, dataset_id, or file_id must be non-NULL)
- `dataset_id` (UUID, FK → `datasets.id`, NULL - at least one of asset_id, dataset_id, or file_id must be non-NULL)
- `file_id` (UUID, FK → `files.id`, NULL - for scan-only; at least one of asset_id, dataset_id, or file_id must be non-NULL)
- `job_id` (UUID, FK → `jobs.id`, NOT NULL)
- `profile` (text, NOT NULL; e.g. `intake_basic`, `custom_profile`)
- `engine` (text, NOT NULL: `GREAT_EXPECTATIONS`, `SODA`)
- `status` (enum: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, NOT NULL, DEFAULT `PENDING`)
- `result_summary` (JSONB, NULL; metrics, scores, counts - populated when status = SUCCEEDED)
- `issues` (JSONB, NULL; list of failed checks, severity - populated when status = FAILED or when warnings exist)
- `created_at`, `updated_at` (timestamp, NOT NULL, DEFAULT CURRENT_TIMESTAMP)

Indexes:

- `(tenant_id, asset_id)`
- `(tenant_id, dataset_id)`
- `(tenant_id, status)`

#### 2.2.9 `compliance_runs`

Represents a compliance check invocation.

Columns:

- `id` (UUID, PK, NOT NULL)
- `tenant_id` (UUID, FK, NOT NULL)
- `asset_id` (UUID, FK, NULL - at least one of asset_id, dataset_id, or file_id must be non-NULL)
- `dataset_id` (UUID, FK, NULL - at least one of asset_id, dataset_id, or file_id must be non-NULL)
- `file_id` (UUID, FK, NULL - scan-only; at least one of asset_id, dataset_id, or file_id must be non-NULL)
- `job_id` (UUID, FK → `jobs.id`, NOT NULL)
- `regulations` (text[], NULL; e.g. `["GDPR","LGPD"]` - populated when status = SUCCEEDED)
- `status` (enum: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, NOT NULL, DEFAULT `PENDING`)
- `allowed_to_store` (boolean, NULL, DEFAULT NULL - set when status = SUCCEEDED; NULL indicates check not completed)
- `pii_summary` (JSONB, NULL; categories and counts - populated when status = SUCCEEDED)
- `risk_score` (numeric, NULL)
- `issues` (JSONB, NULL)
- `created_at`, `updated_at` (timestamp, NOT NULL, DEFAULT CURRENT_TIMESTAMP)

Indexes:

- `(tenant_id, asset_id)`
- `(tenant_id, status)`
- `(tenant_id, allowed_to_store)`

#### 2.2.10 `jobs`

Represents long-running operations (see §14 in System Requirements).

Columns:

- `id` (UUID, PK, NOT NULL)
- `tenant_id` (UUID, FK, NULL - nullable for global/system jobs)
- `user_id` (UUID, FK → `users.id`, NULL)
- `type` (enum: `QUALITY_CHECK`, `COMPLIANCE_CHECK`, `CONTRACT_VALIDATION`, `SEMANTIC_MAPPING`, `CONTRACT_MIGRATION`, etc., NOT NULL)
- `status` (enum: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, NOT NULL, DEFAULT `PENDING`)
- `resource_type` (text, NOT NULL: `CONTRACT`, `DATASET`, `FILE`, `ASSET`)
- `resource_id` (UUID, NOT NULL)
- `created_at` (timestamp, NOT NULL, DEFAULT CURRENT_TIMESTAMP)
- `started_at` (timestamp, NULL - set when status transitions to RUNNING)
- `finished_at` (timestamp, NULL - set when status transitions to terminal state)
- `details_json` (JSONB, NULL, DEFAULT NULL; engine versions, progress, error reasons - may be NULL for jobs that haven't started or don't produce details)
- `percent_complete` (numeric, NULL)
- `estimated_remaining_seconds` (integer, NULL)

Indexes:

- `(tenant_id, status)`
- `(tenant_id, type, status)`
- `(resource_type, resource_id)`

##### 2.2.10.1 Job type enumeration

`jobs.type` is a shared enum used by orchestration, APIs, and UI.

Supported values (MVP):

- `QUALITY_CHECK` – data quality validation jobs (profiling, rules, thresholds).
- `COMPLIANCE_CHECK` – compliance and policy checks (PII, residency, contractual constraints).
- `CONTRACT_VALIDATION` – validates contracts (HubContract/DataContract) against schemas and policies.
- `SEMANTIC_MAPPING` – runs or validates semantic mapping jobs.
- `CONTRACT_MIGRATION` – migrations of contracts between versions or formats.

> **Rule:** All components (DB schema, services, API, UI) must use these exact enum values.  
> Older names like `DQ_CHECK`, `DQ_RUN`, `COMPLIANCE_RUN` are **not allowed** in new code or documentation.


#### 2.2.11 `audit_events`

Append-only log of governance-relevant events.

Columns:

- `id` (UUID, PK)
- `tenant_id` (UUID, FK)
- `user_id` (UUID, FK, nullable)
- `event_type` (text: `DQ_RUN_STARTED`, `DQ_RUN_COMPLETED`, `COMPLIANCE_BLOCKED`, `ASSET_PUBLISHED`, etc.)
- `entity_type` (text: `ASSET`, `CONTRACT`, `DATASET`, `JOB`, `LISTING`, etc.)
- `entity_id` (UUID, nullable)
- `timestamp` (timestamp, UTC)
- `metadata` (JSONB; summarized details, no raw PII)
- `request_id` (text, nullable)

Indexes:

- `(tenant_id, timestamp)`
- `(tenant_id, entity_type, entity_id)`
- `(tenant_id, event_type, timestamp)`

- `event_type` (text: `DQ_RUN_STARTED`, `DQ_RUN_COMPLETED`, `COMPLIANCE_BLOCKED`, `ASSET_PUBLISHED`, etc.)
```

with:

```md
- `event_type` (text: `QUALITY_CHECK_STARTED`, `QUALITY_CHECK_COMPLETED`, `COMPLIANCE_CHECK_FAILED`, `COMPLIANCE_BLOCKED`, `ASSET_PUBLISHED`, etc.)
```

(If you don’t want to introduce `COMPLIANCE_CHECK_FAILED`, you can just keep `COMPLIANCE_BLOCKED` and drop that part.)

This removes `DQ_RUN_*` and aligns the audit event names with the canonical `QUALITY_CHECK`/`COMPLIANCE_CHECK` job types.

For any Job.type = X, the corresponding audit events MUST follow:
- `X_STARTED` when the job transitions to `RUNNING`
- `X_COMPLETED` when the job transitions to `SUCCEEDED`
- `X_FAILED` when the job transitions to `FAILED`

#### 2.2.12 Marketplace: `listings`, `orders`, `entitlements`

**`listings`** (public or internal offers):

- `id` (UUID, PK)
- `tenant_id` (UUID; provider)
- `asset_id` (UUID, FK → `assets.id`)
- `status` (enum: `DRAFT`, `PUBLISHED`, `UNPUBLISHED`)
- `pricing_model` (text: e.g. `FREE`, `FREE_AUTO_APPROVE`, `REQUEST_APPROVAL`)
- `metadata` (JSONB; description, legal terms)
- `created_at`, `updated_at`

Indexes:

- `(tenant_id, asset_id)`
- `(status)`

**`orders`** (for `REQUEST_APPROVAL` flows):

- `id` (UUID, PK)
- `tenant_id` (UUID; consumer)
- `listing_id` (UUID, FK → `listings.id`)
- `status` (enum: `REQUESTED`, `APPROVED`, `REJECTED`)
- `created_by` (UUID, FK → `users.id`)
- `created_at`, `updated_at`

Indexes:

- `(tenant_id, listing_id)`
- `(status)`

**`entitlements`** (who can access which asset):

- `id` (UUID, PK)
- `tenant_id` (UUID; consumer)
- `listing_id` (UUID, FK)
- `asset_id` (UUID, FK → `assets.id`)
- `status` (enum: `ACTIVE`, `REVOKED`, `EXPIRED`)
- `granted_at`, `revoked_at` (timestamp, nullable)
- `metadata` (JSONB; license details, expiry)

Indexes:

- `(tenant_id, asset_id, status)`
- `(listing_id, status)`

#### 2.2.13 Semantic Mapping: `semantic_resources`

Semantic store itself lives in a triple store; the relational DB just references it.

`semantic_resources`:

- `id` (UUID, PK)
- `tenant_id` (UUID, FK, nullable for global classes)
- `resource_type` (text: `ASSET`, `CONTRACT`, `DATASET`, `FIELD`, `LISTING`, etc.)
- `resource_id` (UUID)
- `uri` (text, unique)
- `status` (enum: `ACTIVE`, `DEGRADED`, `STALE`)
- `last_mapped_at` (timestamp)
- `mapping_version` (text; semantic mapping version)
- `metadata` (JSONB; additional links)

Indexes:

- `uri` unique.
- `(tenant_id, resource_type, resource_id)` unique.

**Enhanced Semantic Mapping Requirements**:

- **Complete RDF Mapping**: The semantic service MUST map ALL HubContract sections to RDF:
  - Contract metadata (spec type, version, format, title, description, identifier)
  - Owners (FOAF agents, linked via `hub:hasOwner`)
  - Tags (hub:Tag resources, linked via `hub:hasTag`, also `dcat:keyword`)
  - Schema fields (all properties, constraints, validation rules with SHACL)
  - Quality rules (hub:QualityRule with DQV vocabulary links)
  - Compliance policy (hub:CompliancePolicy with DPV vocabulary links)
  - Lifecycle policy (hub:LifecyclePolicy with PROV-O vocabulary links)
  - Marketplace policy (hub:MarketplacePolicy with ODRL vocabulary links)

- **Standard Vocabulary Integration**: The semantic service MUST integrate and use:
  - DQV (Data Quality Vocabulary) for quality dimensions
  - DPV (Data Privacy Vocabulary) for compliance, jurisdictions, legal bases
  - PROV-O (Provenance Ontology) for data source relationships
  - ODRL (Open Digital Rights Language) for marketplace permissions/prohibitions
  - SHACL (Shapes Constraint Language) for field validation rules
  - Schema.org for field semantic types
  - FOAF (Friend of a Friend) for contract owners

- **Enhanced Ontology**: The semantic service MUST define additional ontology classes and properties:
  - Classes: `hub:QualityRule`, `hub:CompliancePolicy`, `hub:LifecyclePolicy`, `hub:MarketplacePolicy`, `hub:Owner`, `hub:Tag`
  - Properties: Field validation (format, pattern, enum, min/max), schema constraints (isPrimaryKey, isUnique, isIndexed), quality/compliance/lifecycle/marketplace policy properties

---


### 2.3 Object storage path structure

The `files.storage_path` column stores the location of each uploaded file (intake or scan-only) in object storage. This section defines:

- The canonical **bucket + key** pattern.
- How multi-tenancy is expressed in prefixes.
- Lifecycle policies for different `files.purpose` values.
- How S3 bucket-level versioning (if enabled) relates to application-level versioning.

#### 2.3.1 Buckets and multi-tenant strategy

For simplicity and operational control, the platform uses **one primary bucket per environment**:

- `idh-dev-files`
- `idh-stg-files`
- `idh-prod-files`

(Names are configurable via `FILES_BUCKET`.)

Multi-tenancy is handled via **key prefixes**, not per-tenant buckets:

- A **single bucket per environment** avoids explosion of buckets and simplifies IAM and lifecycle policies.
- **Tenant isolation** is enforced by:
  - Application-level authorization checks (each `files` row is scoped by `tenant_id`).
  - Pre-signed URLs that are specific to a single `storage_path`.
  - IAM policies that only allow backend services to access the `FILES_BUCKET`.

**Pre-signed URL Generation**

- **Generation**: Pre-signed URLs are generated by the backend service (e.g., `api-service`) using the storage provider's SDK (e.g., AWS S3 `generate_presigned_url`).
- **Expiration**: Default TTL is **15 minutes** (900 seconds), configurable via `PRESIGNED_URL_TTL_SECONDS` environment variable.
- **HTTP Method**: `PUT` for direct uploads (SIMPLE mode).
- **Permissions**:
  - Pre-signed URLs grant temporary `PutObject` permission for the specific object key.
  - Object key is derived from `storage_path` pattern: `{tenant_id}/{purpose}/{file_id}`.
  - URLs are scoped to a single file upload; cannot be reused for other files.
- **Headers**:
  - `Content-Type`: Set from request `content_type` or defaults to `application/octet-stream`.
  - Storage provider-specific headers (e.g., `x-amz-server-side-encryption`) are included as required.
- **Security**:
  - URLs are signed with backend service credentials (stored in secrets manager).
  - Signature includes expiration timestamp, HTTP method, object key, and required headers.
  - Expired URLs are rejected by the storage provider; clients must request a new URL if expiration occurs.

#### 2.3.1.1 Pre-signed URL Security Requirements

**Signature Algorithm**

- **Algorithm**: Uses storage provider's native signing algorithm (e.g., AWS Signature Version 4 for S3)
- **Signing key**: Backend service uses IAM role credentials or access keys stored in secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault)
- **Signature components**:
  - Expiration timestamp (Unix epoch seconds)
  - HTTP method (`PUT` for uploads, `GET` for downloads)
  - Object key (full path: `{tenant_id}/{purpose}/{file_id}`)
  - Required headers (`Content-Type`, `Content-Length` if specified)
  - Query parameters (if any)

**Access Control**

- **IP restrictions**: Pre-signed URLs **do not include IP restrictions** by default (allows uploads from any IP)
  - **Future enhancement**: IP whitelisting may be added for enterprise tenants
  - **Rationale**: Browser-based uploads may come from dynamic IPs; IP restrictions would break uploads
- **Referrer checks**: Pre-signed URLs **do not include referrer restrictions** (not supported by most storage providers)
- **User-agent checks**: Pre-signed URLs **do not include user-agent restrictions** (not supported by most storage providers)

**URL Scope and Reusability**

- **Single-use intent**: Pre-signed URLs are intended for single-use, but storage providers typically allow multiple requests until expiration
- **Object key binding**: URLs are bound to a specific object key; cannot be used to upload to different keys
- **Method binding**: URLs are bound to a specific HTTP method (`PUT` for uploads, `GET` for downloads)
- **Reuse detection**: Backend does not track URL reuse; storage provider handles this at the protocol level

**Expiration and Revocation**

- **Expiration**: URLs expire after TTL (default: 15 minutes for uploads, 5 minutes for downloads)
- **Revocation**: Pre-signed URLs **cannot be revoked** before expiration (storage provider limitation)
  - **Workaround**: If a URL is compromised, the backend can:
    - Delete the file record (prevents completion via `POST /files/{id}/complete`)
    - Mark file as `FAILED` or `DELETED`
    - Generate a new pre-signed URL for a new file upload
- **Expired URL handling**: Storage provider rejects expired URLs with `403 Forbidden` or `401 Unauthorized`
  - Clients should request a new URL if expiration occurs during upload

**Content Validation**

- **Content-Type validation**: Pre-signed URLs include `Content-Type` header in signature
  - Clients **must** use the exact `Content-Type` specified in the URL
  - Storage provider validates `Content-Type` matches signature
  - Mismatch results in `403 Forbidden` from storage provider
- **Content-Length validation** (if specified):
  - If `Content-Length` is included in signature, client must upload exactly that many bytes
  - Mismatch results in `403 Forbidden` from storage provider

**Security Best Practices**

- **Short TTL**: Use short expiration times (15 minutes for uploads, 5 minutes for downloads) to minimize exposure window
- **HTTPS only**: Pre-signed URLs are only generated for HTTPS endpoints (never HTTP)
- **Secrets rotation**: Backend service credentials are rotated regularly (e.g., every 90 days)
- **Audit logging**: All pre-signed URL generation is logged in audit events:
  - Event type: `PRESIGNED_URL_GENERATED`
  - Includes: `file_id`, `purpose`, `expiration_timestamp`, `object_key` (redacted)
- **Monitoring**: Monitor for unusual patterns:
  - Multiple URL generations for the same file (potential abuse)
  - URLs generated but not used (potential reconnaissance)
  - Failed uploads after URL generation (potential security issues)

#### 2.3.2 storage_path format and key pattern

`files.storage_path` is a text field storing the concatenation of bucket and key:

```text
{bucket}/{key}
```

- `bucket` – environment-specific files bucket (`idh-*-files`).
- `key` – S3 object key with a stable, tenant-scoped pattern.

**MVP key pattern**

We do **not** embed a version segment in the key. Each `files.id` is treated as immutable and maps to exactly one physical object.

```text
key = "{tenant_id}/{purpose}/{file_id}"
```

Where:

- `tenant_id` – UUID from `tenants.id` (string form).
- `purpose` – lower-case string derived from `files.purpose` enum:
  - `dataset`        (for `DATASET`)
  - `external-scan`  (for `EXTERNAL_SCAN`)
  - `sample`         (for `SAMPLE`)
  - `report`         (for `REPORT`)
- `file_id` – UUID from `files.id`.

**Examples**

- Dataset file (attached to an asset):

  ```text
  storage_path = "idh-prod-files/9f2b0e8e-...-tenant/dataset/7c1eaa0f-...-file"
  ```

- External scan-only file:

  ```text
  storage_path = "idh-prod-files/9f2b0e8e-...-tenant/external-scan/ab3e612c-...-file"
  ```

This pattern gives:

- A **unique, stable mapping** from `files.id` to object.
- Easy grouping by `tenant_id` (for diagnostics, data export).
- A top-level `purpose` segment that can be used with **lifecycle policies** and/or object tags.

> Note: if future flows need multiple objects per file (e.g. preview, sample), they can be stored under a sub-prefix:
> `"{tenant_id}/{purpose}/{file_id}/preview"` etc. The `files.storage_path` for the “primary” object remains the base key above.

#### 2.3.3 Lifecycle policies (TTL by purpose)

Lifecycle rules are configured per environment on the `FILES_BUCKET` to align with `files.purpose`:

- **DATASET (`purpose = dataset`)**
  - **No automatic deletion** by lifecycle.
  - Objects are retained as long as corresponding datasets/assets exist.
  - When a dataset is deleted:
    - Application marks `files.status = DELETED`.
    - A background cleanup job deletes the object from storage (hard delete).

- **EXTERNAL_SCAN (`purpose = external-scan`)**
  - Ephemeral, “scan-only” uploads (no asset/dataset created).
  - Lifecycle policy:
    - Tag objects with `purpose=EXTERNAL_SCAN` at upload.
    - S3 lifecycle rule: **expire objects after 7 days** (configurable; MVP default).
  - Application behavior:
    - Once DQ/Compliance jobs finish, the file is **eligible for immediate deletion**:
      - Worker or a cleanup job deletes it early.
      - The 7-day TTL acts as a **safety net** if cleanup jobs fail.

- **SAMPLE (`purpose = sample`)**
  - Small, derived samples used for UI previews.
  - Lifecycle policy:
    - Tag with `purpose=SAMPLE`.
    - S3 rule: **expire after 30 days** (configurable).
  - Application may re-generate samples if needed.

- **REPORT (`purpose = report`)**
  - Generated reports (DQ/Compliance summaries, etc.).
  - Lifecycle policy:
    - Default: **no automatic deletion** (or long-lived, e.g. 365 days), depending on compliance needs.
    - Deletion is driven by application semantics (e.g., asset archival) rather than fixed TTL.

These rules satisfy:

- Security: scan-only data is short-lived.
- Cost control: samples and transient artifacts don’t accumulate indefinitely.
- Governance: dataset files and reports stick around until explicitly deleted or archived.

#### 2.3.4 Versioning strategy (with S3 versioning)

**Application-level versioning**

- Dataset versions are modeled in the DB (`datasets.version` per asset).
- A dataset version points to a specific `files.id` via `datasets.file_id`.
- Each `files.id` is **immutable**: new dataset versions create new `files` rows and new `storage_path` values.
- The **key itself does not encode dataset version** (no `/v1`, `/v2` etc. in the path), because:
  - The file can be created **before** the dataset/asset exists.
  - Version semantics live at the dataset/asset layer, not storage.

**Bucket-level S3 versioning (optional)**

If S3 **bucket versioning** is enabled on `FILES_BUCKET`:

- It is treated as a **safety and DR feature**, not part of business semantics.
- The application always uses the **latest object version** for a given key.
- We still map `files.id → storage_path (bucket/key)` and do **not** rely on S3 `version_id` to find the correct file.
- Optionally, implementation may store `storage_version_id` in `files` as an internal/debugging field, but this is **not** part of the public domain model.

**Deletion with S3 versioning enabled**

- When `files.status = DELETED`, the cleanup process:
  - Issues a DELETE on the object key.
  - Lets S3 retain older versions according to retention/compliance settings, or adds a lifecycle rule to permanently remove non-current versions after a longer retention window.
- For `EXTERNAL_SCAN` and `SAMPLE` prefixes, lifecycle rules should:
  - Remove current and non-current versions after the configured TTL.

This strategy keeps:

- A **simple, deterministic** mapping from DB → object storage.
- Clear multi-tenant separation via prefixes.
- Explicit lifecycle controls for different purposes.
- Compatibility with S3 bucket-level versioning, without coupling business logic to S3 `version_id`s.


## 3. Service Communication Patterns

### 3.1 Sync vs Async

- **Sync (HTTP/REST + JSON)**:
  - External clients ↔ `api-service` (`/api/v1`).
  - `api-service` ↔ `datacontract-service` (for small/fast CLI operations).
  - `api-service` ↔ triple store/semantic-service (for quick lookups).
- **Async (Job queue + object storage)**:
  - `api-service` enqueues jobs into `job_queue`.
  - `worker-service` consumes `job_queue`.
  - `worker-service` makes outbound calls to:
      - `datacontract-service`
      - `dq-service`
      - `compliance-service`
      - `semantic-service`
  - Large data moves via:
    - Object storage (files), referenced by IDs.

### 3.2 Sequence Examples

#### 3.2.1 Data-First Intake

1. Client uploads file via `files` API:
   - `api-service` → object storage (pre-signed URLs).
   - `files` record created with `status=READY`.
2. Client calls `POST /intake/data-first` (or `POST /assets` with `file_id`).
3. `api-service`:
   - Creates initial `asset` (status `DRAFT`).
   - Enqueues jobs:
     - `schema_inference` (can be part of DQ job).
     - `QUALITY_CHECK` job (DQ).
     - `COMPLIANCE_CHECK` job.
4. `worker-service` consumes:
   - For DQ:
     - Calls `dq-service` with file reference and inferred schema.
   - For compliance:
     - Calls `compliance-service` with file reference and contract/data metadata.
5. Results written back to DB (`dq_runs`, `compliance_runs`, update `assets` status fields).
6. `api-service` exposes job and run status via `/jobs/{id}`, `/dq-runs/{id}`, `/compliance-runs/{id}`.

#### 3.2.2 Contract Validation (via CLI)

1. Client uploads contract or edits in UI.
2. `api-service` calls `cli-service`:
   - `POST /validate` with raw contract content, spec/version.
3. `cli-service` runs `datacontract-cli` locally.
4. Result:
   - Returns structured validation output (errors/warnings).
5. `api-service`:
   - Stores result in `contracts.cli_output`.
   - Sets `cli_validation_status`.
   - Returns normalized error list to client.

If contract validation may be slow or heavy, it can also be done via `Job` + `worker-service`, but MVP can run some validations synchronously.

#### 3.2.3 DQ/Compliance External Scan-Only

1. Client:
   - Uploads file via `files` API with purpose `EXTERNAL_SCAN`.
2. Calls `POST /scan-only/checks` or similar.
3. `api-service`:
   - Creates `jobs` (`QUALITY_CHECK`, `COMPLIANCE_CHECK`) with `file_id`.
   - Does **not** create assets/datasets.
4. `worker-service`:
   - Calls `dq-service` and `compliance-service`.
   - Writes `dq_runs` and `compliance_runs` with `file_id`, no `asset_id`.
5. Client polls `/jobs/{job_id}` or uses SDK helper.
6. Once complete:
   - `api-service` can delete the file after a short TTL or flag it for cleanup.

#### 3.3 File storage model & deduplication

File storage follows a two-phase deduplication design:

- **MVP (logical deduplication):**
  - Every file record includes `content_sha256` computed from the full binary payload.
  - `content_sha256` is used to:
    - Detect re-uploads of identical content (same tenant or cross-tenant).
    - Avoid redundant compute operations (e.g. re-validation, semantic extraction).
    - Optionally enable future storage-level deduplication.
  - Each file is stored independently in object storage; no shared blob or reference counting is performed.

- **Post-MVP (physical deduplication):**
  - Introduce a `file_blobs` table with schema similar to:
    ```sql
    file_blobs (
      id UUID PRIMARY KEY,
      content_sha256 CHAR(64) UNIQUE NOT NULL,
      size_bytes BIGINT NOT NULL,
      storage_uri TEXT NOT NULL,
      ref_count INT DEFAULT 1
    )
    ```
  - Each logical file in `files` references one blob via `blob_id`.
  - Enables physical storage reuse across tenants and files with identical checksums.

In all phases:
- The API continues to expose the logical `File` resource.
- `content_sha256` remains the canonical content identifier.
- Object storage paths remain tenant-scoped until physical deduplication is introduced.

#### 3.3.1 Content-based identity (hash-based)

Each uploaded file is assigned a **content hash** once upload completes:

- Algorithm: **SHA-256** over the full file content.
- Stored in DB as `files.content_sha256` (hex-encoded, indexed).
- **Initial state**: `content_sha256 = NULL` when file record is created (`status = UPLOADING`).

**Hash Computation Timing**

**For SIMPLE uploads:**
1. Client uploads file directly to pre-signed URL (object storage).
2. Client calls `POST /files/{id}/complete`.
3. **During `POST /files/{id}/complete` processing**:
   - Server verifies upload completed successfully at object storage.
   - Server computes `content_sha256` by:
     - **Method**: Streaming the file from object storage in chunks (e.g., 8 MB chunks).
     - **Algorithm**: Incremental SHA-256 hashing:
       ```python
       import hashlib
       sha256 = hashlib.sha256()
       with storage_client.get_object_stream(file_key) as stream:
           for chunk in stream.iter_chunks(chunk_size=8*1024*1024):
               sha256.update(chunk)
       content_sha256 = sha256.hexdigest()
       ```
     - **Alternative**: If object storage provides ETag that matches SHA-256 (e.g., S3 single-part upload ETag), use ETag directly (must verify it's SHA-256, not MD5).
   - Server sets `files.content_sha256 = <computed_hash>`, `files.status = READY`.
   - **Deduplication check occurs synchronously** at this point (see below).

**For CHUNKED uploads:**
1. Client uploads chunks via `PUT /files/{id}/chunks/{chunk_number}`.
   - Each chunk includes `X-Chunk-Checksum-Sha256` header (client-computed).
   - Server validates per-chunk checksum and stores chunk metadata.
2. Client calls `POST /files/{id}/complete` when all chunks are uploaded.
3. **During `POST /files/{id}/complete` processing**:
   - Server validates all chunks are present and verified.
   - Server composes/merges chunks into final object in object storage.
   - **After composition completes**:
     - **Method**: Compute full-file SHA-256 using **concatenation approach**:
       ```python
       import hashlib
       sha256 = hashlib.sha256()
       # Option A: Stream composed object and hash
       with storage_client.get_object_stream(composed_key) as stream:
           for chunk in stream.iter_chunks(chunk_size=8*1024*1024):
               sha256.update(chunk)
       content_sha256 = sha256.hexdigest()
       
       # Option B: Combine per-chunk hashes (if stored)
       # NOTE: This requires careful implementation to match streaming hash
       # For MVP, prefer Option A (streaming) for consistency
       ```
     - **Important**: The hash MUST match what would be computed if the file were uploaded as a single object (deterministic).
     - Server sets `files.content_sha256 = <computed_hash>`, `files.status = READY`.
   - **Deduplication check occurs synchronously** after hash computation (see below).

**Implementation Notes**

- **Streaming preferred**: Always stream and hash in chunks (8 MB default) to avoid loading entire file into memory.
- **Deterministic**: Hash computation MUST be deterministic (same file content always produces same hash).
- **Error handling**: If hash computation fails, file is marked `status = FAILED` with error code `FILE_CHECKSUM_COMPUTATION_FAILED`.
- **Performance**: Hash computation is done synchronously during `POST /files/{id}/complete` but should complete within reasonable time (< 30 seconds for typical files).

**Hash Computation Timing**

**For SIMPLE uploads:**
1. Client uploads file directly to pre-signed URL (object storage).
2. Client calls `POST /files/{id}/complete`.
3. **During `POST /files/{id}/complete` processing**:
   - Server verifies upload completed successfully at object storage.
   - Server computes `content_sha256` by:
     - Streaming the file from object storage, OR
     - Using object storage metadata if available (e.g., S3 ETag for single-part uploads).
   - Server sets `files.content_sha256 = <computed_hash>`, `files.status = READY`.
   - **Deduplication check occurs synchronously** at this point (see below).

**For CHUNKED uploads:**
1. Client uploads chunks via `PUT /files/{id}/chunks/{chunk_number}`.
   - Each chunk includes `X-Chunk-Checksum-Sha256` header (client-computed).
   - Server validates per-chunk checksum and stores chunk metadata.
2. Client calls `POST /files/{id}/complete` when all chunks are uploaded.
3. **During `POST /files/{id}/complete` processing**:
   - Server validates all chunks are present and verified.
   - Server composes/merges chunks into final object in object storage.
   - **After composition completes**:
     - Server computes full-file `content_sha256` by:
       - Option A: Streaming the composed object from object storage and hashing it, OR
       - Option B: Combining per-chunk SHA-256 digests using a Merkle tree or concatenation (implementation detail; must produce same result as Option A).
     - Server sets `files.content_sha256 = <computed_hash>`, `files.status = READY`.
   - **Deduplication check occurs synchronously** after hash computation (see below).

**Deduplication Check Process**

**When deduplication occurs:**
- **Timing**: Synchronously during `POST /files/{id}/complete` processing, **after** `content_sha256` is computed.
- **Scope**: Within the same tenant (`tenant_id`).
- **Check query**:
  ```sql
  SELECT id, status, content_sha256, size_bytes
  FROM files
  WHERE tenant_id = :tenant_id
    AND content_sha256 = :computed_hash
    AND size_bytes = :computed_size
    AND status = 'READY'
  ORDER BY created_at DESC
  LIMIT 1;
  ```

**Behavior when duplicate detected:**

1. **If duplicate found** (same `tenant_id`, `content_sha256`, `size_bytes`, `status = READY`):
   - The new file record is **still created** with its own `id` and `storage_path`.
   - The new file's `storage_path` points to the **newly uploaded object** (not the duplicate's object).
   - **Logical deduplication metadata** is stored:
     - `files.details_json.duplicate_of_file_id = <existing_file_id>` (optional, for diagnostics).
   - **Compute reuse** (if enabled):
     - If the duplicate file has existing schema inference, DQ, or compliance results:
       - These results **MAY be copied** to the new file record (subject to configuration and policy).
       - The new file's `dq_runs` and `compliance_runs` records reference the new `file_id` but may include `details_json.reused_from_file_id = <existing_file_id>`.
   - **No physical deduplication**: The new object is stored independently; no shared blob or reference counting.

2. **If no duplicate found**:
   - File proceeds normally with schema inference, DQ, and compliance checks.

**What happens if duplicate detected mid-upload:**

- **During chunked upload** (before `POST /files/{id}/complete`):
  - **No deduplication check occurs** (hash not yet computed).
  - Client continues uploading chunks normally.
  - Deduplication only happens at finalization.

- **If duplicate detected at finalization**:
  - Upload is **not rejected**; the file is stored normally.
  - Deduplication benefits (compute reuse) are applied as described above.
  - Client receives normal success response; deduplication is transparent.

**Deduplication Check: Synchronous vs Async**

- **MVP**: Deduplication check is **synchronous** during `POST /files/{id}/complete`.
  - Reason: Simple implementation, immediate compute reuse benefits.
  - Impact: Adds minimal latency (single DB query, typically < 10ms).
- **Post-MVP**: May be moved to async background job if:
  - Deduplication check becomes a bottleneck.
  - Cross-tenant deduplication is introduced (requires more complex checks).

To minimize collision risk and accidental aliasing:

- We always consider both:
  - `content_sha256`
  - `size_bytes` (stored on the `files` row and/or blob row)
- Two files are considered **byte-identical candidates** if:

```text
content_sha256_A == content_sha256_B
AND size_bytes_A == size_bytes_B
```

Cross-tenant deduplication is not performed for MVP due to isolation and side-channel concerns; deduplication is scoped within a tenant.

#### 3.3.3 Cross-Tenant Deduplication Considerations

**MVP Scope: Tenant-Scoped Only**

For MVP, file deduplication is **strictly scoped to a single tenant**:

- **Deduplication check**: Only compares files within the same `tenant_id`
- **Rationale**: Maintains tenant isolation and prevents information leakage
- **Security**: Prevents side-channel attacks where one tenant could infer information about another tenant's data

**Post-MVP: Cross-Tenant Deduplication (Future Enhancement)**

If cross-tenant deduplication is introduced in the future, the following considerations apply:

**Security and Privacy Implications**

- **Information leakage risk**: Cross-tenant deduplication could leak information:
  - Tenant A uploads file → Tenant B uploads same file → System deduplicates
  - Tenant B could infer that Tenant A has the same data (if deduplication is visible)
  - **Mitigation**: Deduplication metadata must be hidden from tenants
- **Data sovereignty**: Cross-tenant deduplication may violate data residency requirements:
  - Tenant A's data in region X, Tenant B's data in region Y
  - Deduplication would require cross-region data sharing
  - **Mitigation**: Only deduplicate within same region/data residency zone
- **Compliance concerns**: Cross-tenant deduplication may violate regulatory requirements:
  - GDPR: Data must be isolated per data controller
  - HIPAA: Patient data must be isolated per covered entity
  - **Mitigation**: Opt-in only, with explicit consent and compliance review

**Implementation Considerations**

- **Opt-in model**: Cross-tenant deduplication should be:
  - **Opt-in per tenant**: Tenants explicitly enable cross-tenant deduplication
  - **Configurable per asset**: Some assets may opt out even if tenant opts in
  - **Audit trail**: All cross-tenant deduplication events are logged
- **Blind deduplication**: Deduplication should be "blind" to tenants:
  - Tenants cannot see which other tenants have the same file
  - Deduplication metadata is not exposed via API
  - Only system admins can see cross-tenant deduplication statistics
- **Reference counting**: Physical deduplication with cross-tenant sharing requires:
  - Shared blob table with reference counts per tenant
  - Careful deletion logic (don't delete blob until all tenant references removed)
  - Complex cascade deletion rules

**Performance Benefits**

- **Storage savings**: Cross-tenant deduplication could save significant storage:
  - Common datasets (e.g., public reference data) shared across tenants
  - Estimated savings: 10-30% for typical multi-tenant deployments
- **Compute savings**: Reuse of DQ/compliance results across tenants:
  - If Tenant A runs DQ on a file, Tenant B could reuse results (with consent)
  - Estimated savings: 20-40% reduction in DQ/compliance compute costs

**Migration Path**

If cross-tenant deduplication is introduced:

1. **Phase 1: Opt-in pilot**:
   - Enable for select tenants (with explicit consent)
   - Monitor security and compliance implications
   - Gather performance metrics
2. **Phase 2: Gradual rollout**:
   - Expand to more tenants (opt-in)
   - Refine implementation based on feedback
   - Document best practices
3. **Phase 3: Default opt-in** (if successful):
   - Make cross-tenant deduplication default (with opt-out)
   - Maintain strict security and compliance controls

**Current Recommendation**

- **MVP**: Do not implement cross-tenant deduplication
- **Post-MVP**: Consider only if:
  - Strong business case (significant storage/compute savings)
  - Security and compliance concerns are addressed
  - Explicit tenant consent and opt-in model
  - Comprehensive audit trail and monitoring

#### 3.3.2 Logical vs physical deduplication
We distinguish between:

Logical deduplication (MVP)

Physical deduplication (optional, feature-flagged)

(a) Logical deduplication (MVP)

In MVP, we:

Compute and store files.content_sha256.

Use it to:

Detect when a newly uploaded file is identical to an existing one for the same tenant.

Optionally reuse previous computation:

If there is a prior files row with the same (tenant_id, content_sha256, size_bytes) and completed:

Schema inference results can be copied.

DQ and compliance results can be re-used (subject to config and policy).

But we do not:

Rewrite the new file’s storage_path to point to the old object.

Avoid storing the newly uploaded object in S3.

This mode is:

Low complexity: no shared physical blobs, no reference counting.

Zero risk to tenant isolation and deletion semantics.

Still gives CPU savings by avoiding redundant compute.

(b) Physical deduplication (post-MVP option)

When enabled (per environment / tenant-plan), we introduce a shared blob abstraction.

New table (conceptual):

text
Copy code
file_blobs
---------
id                  UUID (PK)
tenant_id           UUID (scope dedup per tenant)
storage_path        text (bucket/key of canonical object)
content_sha256      text
size_bytes          bigint
ref_count           integer
created_at          timestamptz
deleted_at          timestamptz (nullable)
Changes in files:

Add files.blob_id (FK → file_blobs.id).

files.storage_path may either:

Continue to hold the canonical storage_path, or

Be derived from the blob (files.storage_path becomes effectively redundant and could later be dropped).

Upload flow with physical dedup enabled

User uploads file (SIMPLE or CHUNKED) to a temporary object key (as today).

At POST /files/{id}/complete:

Compute content_sha256 and size_bytes.

Look up an existing blob:

sql
Copy code
SELECT id, storage_path
FROM file_blobs
WHERE tenant_id = :tenant_id
  AND content_sha256 = :hash
  AND size_bytes = :size
  AND deleted_at IS NULL;
If no existing blob:

Create new file_blobs row with:

storage_path pointing to the just-uploaded object (or move/rename as needed).

ref_count = 1.

Set files.blob_id to the new blob.

files.storage_path = blob’s storage_path.

If existing blob found:

Option 1 (simpler): delete the just-uploaded temp object, and re-point:

files.blob_id = existing blob ID.

files.storage_path = existing blob.storage_path.

Increment file_blobs.ref_count by 1.

Reuse existing canonical object.

This gives true storage deduplication for identical content within a tenant.

#### 3.3.3 Reference counting semantics
When physical dedup is enabled, file_blobs.ref_count tracks how many files rows share the same physical object.

Increment

On creation of a files row that points to a blob:

Within a transaction, UPDATE file_blobs SET ref_count = ref_count + 1 WHERE id = :blob_id.

A unique constraint on (tenant_id, content_sha256, size_bytes) on file_blobs prevents concurrent duplicate blobs; ON CONFLICT is used to pick a single canonical blob.

Decrement

When a files row is logically deleted (e.g., dataset or asset is deleted):

Within a transaction:

Mark files.status = 'DELETED'.

UPDATE file_blobs SET ref_count = ref_count - 1 WHERE id = :blob_id RETURNING ref_count.

If ref_count becomes 0:

Mark blob deleted_at = now().

Enqueue a storage cleanup job to delete the physical object at storage_path.

GC & safety

A background “blob reaper” periodically:

Scans file_blobs where ref_count = 0 and deleted_at older than a grace period (e.g., 24h).

Ensures physical deletion was successful; retries on transient errors.

This design is robust to:

Process crashes between ref_count update and storage delete.

Temporary failures in object storage.

If physical dedup is disabled, file_blobs is not used; each files row has its own storage_path and direct delete semantics (as described in the object storage section).

3.3.4 Storage savings vs. complexity trade-offs
Benefits of full physical dedup

Storage savings in scenarios with:

Repeated uploads of the same file (e.g., same dataset re-ingested many times).

Multiple datasets sharing identical raw files (e.g., different contracts referencing the same underlying data).

Compute reuse becomes easier when the same blob is referenced from multiple files.

Costs / complexity

Extra tables (file_blobs) and reference counting logic.

More complex deletion semantics and background cleanup.

Need careful handling of:

Races between concurrent uploads of the same content.

Races between upload completion and deletion.

Dedup across tenants is intentionally avoided:

To prevent information leakage via timing or existence of duplicates.

To keep data isolation simple and auditable.

MVP decision

MVP implements logical dedup only:

files.content_sha256 is computed and used for compute reuse and diagnostics (e.g., “you’ve uploaded this file before”).

No shared physical file_blobs, no reference counting.

Physical dedup (file_blobs + ref_count) is designed as a forward-compatible extension, to be enabled per environment or per-tenant plan once:

Storage usage patterns justify the added complexity.

Operational tooling for monitoring and debugging reference counts is in place.

---

### 4. Error Handling Standards

Error handling is standardized across services to match the external API behavior (§13 in System Requirements).

#### 4.1 Cross-Service Error Envelope

- Internal services (`cli-service`, `dq-service`, `compliance-service`, `semantic-service`) SHOULD:
  - Return JSON error envelopes similar to the public API:
    - `code`, `message`, `details`, `http_status`, `request_id`.
- `api-service`:
  - When calling internal services:
    - Propagates `request_id` (tracing context).
    - On error, maps internal errors to external error codes (see §13.2).

#### 4.2 Mapping Internal Failures

Examples:

- `cli-service` timeout:
  - Internal error: `CONTRACT_CLI_ERROR` with `http_status=502 or 504`.
  - Exposed as same `CONTRACT_CLI_ERROR` to client.
- DQ engine crash:
  - Internal error: `DQ_ENGINE_ERROR`.
  - External: `DQ_ENGINE_ERROR` (500 or 502).
- Compliance engine indicates dataset is not allowed to store:
  - Internal: success with `allowed_to_store=false`.
  - `api-service`:
    - Sets `COMPLIANCE_BLOCKED` state.
    - Blocks asset creation or marks dataset as unusable.
    - Returns `409 Conflict` with `error.code = "COMPLIANCE_BLOCKED"`.

#### 4.3 Retry & Idempotency

- `api-service` MUST treat calls to internal services as:
  - **Safe to retry** on transient failures (`5xx`, `SYSTEM_UNAVAILABLE`, timeouts).
- `worker-service`:
  - Uses job-level retry policy:
    - Eg., up to N retries with exponential backoff for `DQ_ENGINE_ERROR`, `COMPLIANCE_ENGINE_ERROR`, `SYSTEM_UNAVAILABLE`.
- Idempotency:
  - Job processing:
    - Jobs MUST be idempotent based on `job.id` (re-running the same job should not create duplicates).
  - Asset creation:
    - Once asset is created, errors in DQ/compliance do not re-create the same asset.

#### 4.4 Logging & Correlation

- All services MUST:
  - Include `request_id` and `job_id` in logs when available.
  - Use common error codes as per §13.2.

#### 4.5 Circuit breakers & timeouts

   All service-to-service calls MUST be wrapped in a circuit breaker with the following default configuration:

   - Failure conditions: HTTP 5xx, network errors, timeouts.
   - Sliding window: 60s with minimum 20 requests.
   - Failure threshold: 50% failures -> breaker opens.
   - Reset timeout: 30s; after this, breaker transitions to half-open.
   - Half-open: up to 5 test calls; if 3 consecutive succeed -> closed; on any failure -> open.

   **Default Configuration (All Services)**

   Unless otherwise specified, all services use the default configuration above.

   **Per-Service Overrides**

   The following services have documented overrides due to different failure characteristics:

   | Service | Override | Rationale |
   |---------|----------|-----------|
   | `datacontract-service` | Sliding window: **30s** (instead of 60s)<br>Minimum requests: **10** (instead of 20) | CLI operations are typically fast; failures surface quickly. Shorter window allows faster recovery. |
   | `dq-service` | Reset timeout: **60s** (instead of 30s)<br>Half-open test calls: **3** (instead of 5) | DQ jobs are long-running; longer reset timeout prevents premature re-opening during normal job execution. |
   | `compliance-service` | Reset timeout: **60s** (instead of 30s)<br>Half-open test calls: **3** (instead of 5) | Similar to DQ service; compliance checks can be long-running. |
   | `semantic-service` | No overrides | Uses default configuration. |
   | `api-service` → `datacontract-service` | Uses `datacontract-service` overrides | Inherits from downstream service. |
   | `worker-service` → `dq-service` | Uses `dq-service` overrides | Inherits from downstream service. |
   | `worker-service` → `compliance-service` | Uses `compliance-service` overrides | Inherits from downstream service. |

   **Configuration Method**

   Circuit breaker configuration is specified via environment variables or configuration files:

   - Environment variables (per service):
     - `CIRCUIT_BREAKER_SLIDING_WINDOW_SECONDS` (default: 60)
     - `CIRCUIT_BREAKER_MIN_REQUESTS` (default: 20)
     - `CIRCUIT_BREAKER_FAILURE_THRESHOLD_PERCENT` (default: 50)
     - `CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS` (default: 30)
     - `CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` (default: 5)
     - `CIRCUIT_BREAKER_HALF_OPEN_SUCCESS_THRESHOLD` (default: 3)
   - Configuration files (YAML/JSON):
     - Service-specific config files may override defaults.
     - Example: `config/datacontract-service.yaml`:
       ```yaml
       circuit_breaker:
         sliding_window_seconds: 30
         min_requests: 10
       ```

   **State Model**

   The state model (closed, open, half-open) and failure conditions are shared across all services:
   - **Closed**: Normal operation; requests pass through.
   - **Open**: Circuit is open; requests fail fast without calling downstream.
   - **Half-open**: Testing state; limited requests allowed to test if downstream recovered.

   All services MUST log circuit breaker state transitions for observability.

---

## 5. Monitoring & Observability Design

This section translates the monitoring requirements (§17 in System Requirements) into implementation-level choices.

### 5.1 Tooling (Example Stack)

The exact tools can vary, but a typical stack:

- **Metrics**: Prometheus-compatible metrics exposed by services.
- **Dashboards & Alerts**: Grafana (or equivalent).
- **Logs**: Structured JSON logs shipped to a centralized log store (e.g. ELK/Loki).
- **Tracing**: OpenTelemetry instrumentation + backend (e.g. Jaeger/Tempo).

The TDD is tool-agnostic, but assumes:

- Each service exposes `/metrics` endpoint for scraping.
- Each service is instrumented with OpenTelemetry for traces.

### 5.2 Metrics Implementation

Each service must expose metrics covering:

- Request metrics:
  - `http_requests_total{service,route,method,status_class}`
  - `http_request_duration_seconds{service,route,method}`
- Job metrics:
  - `jobs_started_total{type}`
  - `jobs_completed_total{type,status}`
  - `job_duration_seconds{type,status}`
- Dependency metrics:
  - DB connection pool usage:
    - `db_pool_active_connections{service}` (gauge)
    - `db_pool_idle_connections{service}` (gauge)
    - `db_pool_wait_time_ms{service}` (histogram)
    - `db_pool_connection_errors_total{service}` (counter)
  - CLI/DQ/Compliance errors:
    - `dependency_errors_total{service,dependency}`.

Implementation specifics:

- Use per-service middleware to:
  - Increment counters on every HTTP request.
  - Observe latency histograms.
- Worker instrumentation:
  - Time job execution segments.
  - Count job failures by type and error code.

### 5.3 Logging Implementation

- All services log in structured JSON format:
  - Fields:
    - `timestamp`, `level`, `service`, `message`,
    - `request_id`, `job_id`, `tenant_id`, `user_id`, `route`, `status_code`, `error_code`.
- Logging libraries:
  - **Python services**: `structlog` with `django-structlog` for Django integration
  - Output format: JSON (required)
  - See `Technology_Stack_Decisions.md` for version and configuration details
- Sensitive data:
  - Logging filters remove or mask any PII if accidentally passed.
  - No raw dataset values in logs by design.

### 5.4 Tracing Implementation

- Services use OpenTelemetry SDK:
  - For incoming HTTP requests:
    - Start a new trace if none is present.
    - Extract trace context if present in headers.
  - For outgoing calls:
    - Inject trace context into headers for:
      - `cli-service`, `dq-service`, `compliance-service`, `semantic-service`.
- Each Job execution:
  - New span for the job:
    - Sub-spans for CLI, DQ, Compliance calls.
- Correlation:
  - **`request_id` and `trace_id` relationship**:
    - `request_id` is a **unique identifier** for each HTTP request, generated at the API gateway/edge.
    - `trace_id` is the **OpenTelemetry trace ID** (16-byte identifier, typically hex-encoded as 32 characters).
    - **Relationship**: `request_id` MAY be derived from `trace_id` (e.g., first 16 characters of `trace_id`), OR they may be independent.
    - **Recommendation for MVP**: Use independent generation:
      - `request_id`: UUID v4 or similar (e.g., `req-abc123def456`).
      - `trace_id`: OpenTelemetry trace ID (32-character hex string).
    - **Correlation**: Both `request_id` and `trace_id` are included in:
      - HTTP response headers (`X-Request-ID`, `X-Trace-ID`).
      - Log entries (both fields present).
      - Error responses (`error.request_id`).
    - **Querying**: Logs and traces can be correlated by:
      - Searching logs for `request_id = <value>`.
      - Searching traces for `trace_id = <value>` or `request_id = <value>` (if trace includes request_id as an attribute).

**Sampling strategy (MVP)**

- **Head-based sampling (SDK level)**
  - Default sampling rate: **10%** of successful requests per service.
  - Implemented via OpenTelemetry SDK samplers in each service.
- **Error-centric sampling**
  - Requests that result in:
    - HTTP `5xx`, or
    - HTTP `429` (rate limited), or
    - Job failures (where a job ends in `FAILED`)
  - MUST be sampled at **100%**, regardless of the default rate.
- **Per-endpoint higher sampling**
  - The following operations SHOULD be sampled at **≥ 50%**:
    - Job creation: `POST /jobs`, `POST /dq-runs`, `POST /compliance-runs`
    - File upload completion: `POST /files/{id}/chunks/complete`
    - Contract upload & validation: `POST /contracts` and its validation pipeline
- **Background jobs**
  - Workers MUST propagate trace context from the triggering request.
  - If the parent request trace is sampled, all spans for that job MUST also be sampled.
- **Post-MVP**
  - Tail-based sampling in the collector MAY be introduced later to favor:
    - High-latency traces
    - Error traces
  - Any tail-based policy MUST still effectively sample error traces at ~100%.


### 5.5 Dashboards & Alerts

The platform MUST provide the following monitoring dashboards for operations teams:

#### 5.5.1 Dashboard Specifications

**1. API Health Dashboard**

**Purpose**: Monitor API availability, latency, and error rates across all services.

**Panels**:

| Panel | Metrics | Query (PromQL example) | Threshold |
|-------|---------|------------------------|-----------|
| Request Rate | Total requests per second | `sum(rate(http_requests_total[5m])) by (service)` | - |
| Error Rate | 5xx error rate by service | `sum(rate(http_requests_total{status=~"5.."}[5m])) by (service) / sum(rate(http_requests_total[5m])) by (service)` | Warning: > 1%, Critical: > 5% |
| Latency P50 | Median response time | `histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (service, route, le))` | - |
| Latency P95 | 95th percentile response time | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (service, route, le))` | Warning: > 1s (read), > 2s (write) |
| Latency P99 | 99th percentile response time | `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (service, route, le))` | Critical: > 3s (read), > 5s (write) |
| Top Error Endpoints | Error count by endpoint | `topk(10, sum(rate(http_requests_total{status=~"5.."}[5m])) by (service, route))` | - |
| Rate Limit Hits | Rate limit violations | `sum(rate(http_requests_total{status="429"}[5m])) by (service, route)` | - |

**Filters**: Service, Route, Time Range (1h, 6h, 24h, 7d)

**2. Jobs & DQ/Compliance Dashboard**

**Purpose**: Monitor background job execution, success rates, and DQ/compliance operations.

**Panels**:

| Panel | Metrics | Query (PromQL example) | Threshold |
|-------|---------|------------------------|-----------|
| Job Start Rate | Jobs started per minute | `sum(rate(jobs_started_total[5m])) by (job_type)` | - |
| Job Success Rate | Success rate by type | `sum(rate(jobs_completed_total{status="SUCCEEDED"}[5m])) by (job_type) / sum(rate(jobs_completed_total[5m])) by (job_type)` | Warning: < 95%, Critical: < 90% |
| Job Failure Rate | Failure rate by type | `sum(rate(jobs_completed_total{status="FAILED"}[5m])) by (job_type) / sum(rate(jobs_completed_total[5m])) by (job_type)` | Warning: > 5%, Critical: > 10% |
| Average Job Duration | Mean duration by type | `sum(rate(job_duration_seconds_sum[5m])) by (job_type) / sum(rate(job_duration_seconds_count[5m])) by (job_type)` | - |
| Queue Depth | Pending jobs in queue | `sum(job_queue_depth) by (job_type)` | Warning: > 200, Critical: > 500 |
| DQ Run Status | DQ runs by status | `sum(dq_runs_total) by (status)` | - |
| Compliance Run Status | Compliance runs by status | `sum(compliance_runs_total) by (status)` | - |
| Compliance Blocked Count | Assets blocked by compliance | `sum(compliance_blocked_total)` | - |
| Worker Utilization | Active jobs per worker | `sum(worker_active_jobs) by (instance)` | - |

**Filters**: Job Type, Status, Time Range (1h, 6h, 24h, 7d)

**3. Database & Storage Dashboard**

**Purpose**: Monitor database performance, connection pools, and object storage health.

**Panels**:

| Panel | Metrics | Query (PromQL example) | Threshold |
|-------|---------|------------------------|-----------|
| DB Connection Pool Usage | Active connections | `sum(db_pool_active_connections) by (service)` | Warning: > 80% of max, Critical: > 90% |
| DB Query Latency P95 | 95th percentile query time | `histogram_quantile(0.95, sum(rate(db_query_duration_seconds_bucket[5m])) by (service, query_type, le))` | Warning: > 200ms, Critical: > 500ms |
| DB Query Error Rate | Query failures | `sum(rate(db_query_errors_total[5m])) by (service, error_code)` | Warning: > 1%, Critical: > 5% |
| DB CPU Usage | Database CPU utilization | `db_cpu_usage_percent` | Warning: > 80%, Critical: > 90% |
| DB I/O Wait | Database I/O wait time | `db_io_wait_seconds` | Warning: > 100ms, Critical: > 500ms |
| Object Storage Error Rate | S3/object storage errors | `sum(rate(s3_operations_total{status=~"5.."}[5m])) by (operation) / sum(rate(s3_operations_total[5m])) by (operation)` | Warning: > 2%, Critical: > 5% |
| Object Storage Latency | S3 operation latency | `histogram_quantile(0.95, sum(rate(s3_operation_duration_seconds_bucket[5m])) by (operation, le))` | Warning: > 1s, Critical: > 3s |
| Storage Usage | Object storage size | `s3_bucket_size_bytes` | - |

**Filters**: Service, Database, Time Range (1h, 6h, 24h, 7d)

**4. Infrastructure & Dependencies Dashboard**

**Purpose**: Monitor infrastructure health and external dependencies.

**Panels**:

| Panel | Metrics | Query (PromQL example) | Threshold |
|-------|---------|------------------------|-----------|
| Service Health | Health check status | `up{job="service-health"}` | Critical: 0 (service down) |
| Circuit Breaker State | Circuit breaker status | `circuit_breaker_state` (0=closed, 1=open, 2=half-open) | Critical: open for > 5 minutes |
| Dependency Error Rate | External service errors | `sum(rate(dependency_errors_total[5m])) by (service, dependency)` | Warning: > 1%, Critical: > 5% |
| Triple Store Latency | SPARQL query latency | `histogram_quantile(0.95, sum(rate(sparql_query_latency_ms_bucket[5m])) by (le))` | Warning: > 500ms, Critical: > 1000ms |
| CLI Service Health | DataContract CLI errors | `sum(rate(cli_errors_total[5m])) by (error_type)` | Warning: > 1%, Critical: > 5% |
| Message Queue Depth | Job queue depth | `sum(job_queue_depth) by (queue_name)` | Warning: > 200, Critical: > 500 |

**Filters**: Service, Dependency, Time Range (1h, 6h, 24h, 7d)

**5. Tenant & Usage Dashboard**

**Purpose**: Monitor tenant activity, resource usage, and quota consumption.

**Panels**:

| Panel | Metrics | Query (PromQL example) | Threshold |
|-------|---------|------------------------|-----------|
| Active Tenants | Number of active tenants | `count(tenants_total{status="ACTIVE"})` | - |
| API Requests by Tenant | Request rate per tenant | `sum(rate(http_requests_total[5m])) by (tenant_id)` | - |
| Job Creation by Tenant | Jobs created per tenant | `sum(rate(jobs_started_total[5m])) by (tenant_id)` | - |
| Storage Usage by Tenant | Object storage per tenant | `sum(s3_tenant_storage_bytes) by (tenant_id)` | - |
| Rate Limit Violations | Rate limit hits per tenant | `sum(rate(http_requests_total{status="429"}[5m])) by (tenant_id)` | - |

**Filters**: Tenant ID, Time Range (1h, 6h, 24h, 7d, 30d)

**Dashboard Implementation**

- Dashboards MUST be implemented using Grafana or equivalent visualization tool.
- All dashboards MUST support:
  - Time range selection (1h, 6h, 24h, 7d, 30d, custom).
  - Service/tenant filtering.
  - Export to PDF/PNG.
  - Refresh intervals (auto-refresh every 30s, 1m, 5m).
- Dashboards MUST be accessible to:
  - Operations/on-call engineers (read-only).
  - Platform administrators (read-only).
  - Development teams (read-only, for debugging).

Alerts:

- API availability:
  - 5xx rate threshold on core routes over rolling window.
- Job failure spikes:
  - `jobs_failed_total` for `QUALITY_CHECK` and `COMPLIANCE_CHECK` exceeding threshold.
- Dependency issues:
  - CLI/DQ/Compliance error rates above normal.
- Queue backlog:
  - Jobs waiting too long in queue.

#### 5.5.1 Alerting thresholds (MVP)

Alerting MUST be driven by a small, opinionated set of thresholds to avoid both alert fatigue and silent failures. Thresholds below apply to **production**; non-prod may use relaxed settings.

- **API error rate alerts**
  - Metric: HTTP 5xx rate per service for key REST endpoints.
  - Thresholds:
    - **Critical**: 5xx error rate **> 5%** over **5 consecutive minutes** on:
      - `GET /assets`, `GET /assets/{id}`
      - `POST /contracts`, `POST /files`, `POST /jobs`, `POST /dq-runs`, `POST /compliance-runs`
    - Alert: page on-call for the affected service.
  - Optional **Warning**: 5xx error rate **> 1%** over **15 minutes** → non-paging alert (Slack/email).

- **Latency (p95 / p99) alerts**
  - Metrics:
    - p95 and p99 latency per endpoint.
  - Read-heavy endpoints (e.g., `GET /assets`, `GET /jobs/{id}`):
    - **Warning**: p95 latency **> 1s** for **5 minutes**.
    - **Critical**: p99 latency **> 3s** for **10 minutes**.
  - Write / job-triggering endpoints (`POST /contracts`, `POST /files/{id}/chunks/complete`, `POST /dq-runs`, `POST /compliance-runs`):
    - **Warning**: p95 latency **> 2s** for **5 minutes**.
    - **Critical**: p99 latency **> 5s** for **10 minutes**.
  - Alerts should be grouped by service to avoid one noisy endpoint paging everyone separately.

- **Queue depth & job delay alerts**
  - Metrics:
    - Job queue depth (pending jobs).
    - Time in queue (age of oldest PENDING job).
  - Thresholds:
    - **Warning**:
      - Queue depth **> 200 jobs** for **10 minutes**, or
      - p95 time-in-queue **> 5 minutes**.
    - **Critical**:
      - Queue depth **> 500 jobs** for **10 minutes**, or
      - p95 time-in-queue **> 15 minutes**.
  - Scope:
    - At least for DQ/compliance job queues; other job types may share thresholds or define their own if needed.

- **Data-plane / storage alerts (lightweight for MVP)**
  - Object storage:
    - Alert if error rate for upload/GET operations from the hub **> 2%** for **5 minutes**.
  - Semantic / DB:
    - Alert on connection failure or repeated retries to the metadata DB or semantic store.

- **Noise control**
  - All thresholds MUST be implemented with:
    - Short evaluation window (as above) **and**
    - A minimum time-in-alert before paging (e.g., 5 minutes) to avoid flapping.
  - Repeated alerts for the same condition MUST be grouped (single incident / ticket per service).


---

## 6. Summary

This Technical Design Document defines:

- A **relational schema** centered on `tenants`, `users`, `assets`, `contracts`, `datasets`, `files`, `jobs`, `dq_runs`, `compliance_runs`, `audit_events`, `listings`, `orders`, `entitlements`, and `semantic_resources`.
- Clear **service boundaries** and communication patterns:
  - `api-service` orchestrating business flows.
  - `worker-service` executing async jobs via job queue.
  - Supporting services for CLI, DQ, compliance, and semantics.
- A unified **error handling model** aligned with the external `/api/v1` envelope and codes.
- A concrete **monitoring & observability** strategy:
  - Metrics, logging, tracing, dashboards, and alerts.

This TDD serves as the main reference for implementation and should evolve in lockstep with the code and infrastructure as the platform matures.
