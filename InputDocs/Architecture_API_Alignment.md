# Architecture–API Alignment (MVP)

This document ensures that the **System Architecture** and the **API Spec v1**
stay aligned as the Interoperable Data Hub evolves.

It provides:

- A mapping between **services** and **API endpoints**.  
- Guidelines for **service boundaries** and responsibilities.  
- A practical **alignment checklist** for new or changed APIs.  
- Conventions for **cross-service dependencies** (e.g. Marketplace → Asset).

---

## 1. Inputs & Scope

This document is derived from:

- `System_Architecture.md` – services and data stores.
- `API_Spec_v1.md` – external HTTP contract (v1).
- `Domain_Model.md` – conceptual entities and relationships.

Scope (MVP):

- Only covers **external HTTP API v1** (`/api/v1/...`) and `/sparql`.  
- Internal-only admin or maintenance endpoints are out of scope unless they
  affect tenant-facing flows.

---

## 2. Service-to-Endpoint Mapping

### 2.1 Summary Table

| Service                     | Primary Responsibility                           | API Paths (v1)                                            |
|----------------------------|--------------------------------------------------|-----------------------------------------------------------|
| Auth & Tenant Service      | Authn, tenant lifecycle, user membership        | `/api/v1/auth/*`, `/api/v1/tenants/*` (future detail)    |
| Asset & Catalog Service    | Assets, datasets, catalog search                 | `/api/v1/assets*`                                        |
| Contract Service           | Contracts & HubContract lifecycle                | `/api/v1/contracts*`                                     |
| Ingestion Service          | File/upload lifecycle, schema inference          | `/api/v1/files*`                                         |
| DataContract Service       | DataContract CLI wrapper                         | **Internal only** (no direct public endpoints)           |
| DQ Service                 | Data Quality runs & results                      | `/api/v1/dq-runs*`                                       |
| Compliance Service         | Compliance runs (PII / regulatory checks)        | `/api/v1/compliance-runs*`                               |
| Marketplace Service        | Listings, orders, entitlements                   | `/api/v1/marketplace/*`                                  |
| Semantic Service           | RDF/graph exposure & semantic search             | `/sparql`, `/api/v1/semantic/*` (MVP or future)          |
| Job Service                | Async job tracking                               | `/api/v1/jobs*`                                          |
| Audit Service              | Audit event ingestion & querying                 | `/api/v1/audit-events*`                                  |
| Billing/Metrics Service    | Metering, usage metrics (future billing)         | `/api/v1/metrics/*` (internal / future)                  |

> **Rule:** each external endpoint must have exactly **one owning service**.
> Shared concerns (auth, audit, jobs) are provided via **cross-cutting services**.

### 2.2 Assets & Catalog vs Marketplace

- **Asset & Catalog Service** owns:
  - asset metadata and lifecycle (`DRAFT → ACTIVE → PUBLIC → RETIRED`),
  - dataset references and primary contracts.
  - Example endpoints:
    - `POST /api/v1/assets`
    - `GET /api/v1/assets/{id}`
    - `GET /api/v1/assets?domain=...`

- **Marketplace Service** owns:
  - listings & pricing for assets,
  - orders and entitlements between **provider** and **consumer** tenants.
  - Example endpoints:
    - `POST /api/v1/marketplace/listings`
    - `GET /api/v1/marketplace/listings`
    - `POST /api/v1/marketplace/orders`
    - `GET /api/v1/marketplace/entitlements`

**Alignment rule:**

- Asset & Catalog Service does **not** manage marketplace pricing or orders.  
- Marketplace Service does **not** change core asset metadata; it references
  assets by `asset_id` and uses Asset APIs to read details.

### 2.3 Contracts vs Ingestion vs DQ/Compliance

- **Contract Service** owns the contract lifecycle and normalization:
  - `POST /api/v1/contracts`
  - `GET /api/v1/contracts/{id}`
  - `POST /api/v1/contracts/{id}/validate`

- **Ingestion Service** owns data onboarding and file lifecycle:
  - `POST /api/v1/files/init`
  - `POST /api/v1/files/{id}/complete`
  - combined flows that orchestrate compliance + DQ (returning job IDs).

- **DQ Service** and **Compliance Service** own their respective runs:
  - `POST /api/v1/dq-runs`
  - `POST /api/v1/compliance-runs`
  - `GET /api/v1/dq-runs/{id}` / `GET /api/v1/compliance-runs/{id}` (directly or via Jobs).

**Alignment rule:**

- Ingestion **triggers** DQ/Compliance via their APIs (or via Job Service), it
  does not implement those checks itself.
- Contract Service may **request** validation via DataContract Service, but
  DataContract Service has no public API.

### 2.4 Jobs, Audit, and Cross-Cutting Concerns

- **Job Service** owns async execution tracking for long-running operations:
  - `POST` to domain-specific APIs (e.g. `/dq-runs`, `/compliance-runs`) return job IDs.
  - `GET /api/v1/jobs/{id}` to poll status.

- **Audit Service** owns centralized audit logging:
  - `POST /api/v1/audit-events` – internal ingestion.
  - `GET /api/v1/audit-events` – tenant-scoped and admin-scoped queries.

- These services are used by many others but are **not** responsible for domain
  logic (e.g. they never decide if a contract is valid or an entitlement exists).

### 2.5 Semantic Service

- Owns the RDF/triple store and semantic queries:
  - `/sparql` for SPARQL queries (read-only in MVP).
  - Future: `/api/v1/semantic/search`, `/api/v1/semantic/assets`, etc.

- Semantic Service consumes **asset/contract** data from Asset & Contract
  services and **never** becomes the source of truth for canonical JSON
  representations.

---

## 3. Boundary Clarification Guidelines

To keep service boundaries clean and avoid coupling:

1. **Single source of truth**
   - Every core entity (`Asset`, `Contract`, `Listing`, `Order`, `DQRun`, `ComplianceRun`)
     has one owning service.
   - Other services always go through the owning service’s API for authoritative
     reads and writes.

2. **No shared write models**
   - No two services write to the same DB table/collection (except shared infra
     like Audit, Jobs, Metrics).

3. **No business logic in the API gateway**
   - The gateway handles:
     - authn/authz,
     - routing,
     - rate limiting,
     - request/response shaping (if needed).
   - It does **not** perform core business decisions (e.g. “is this asset
     eligible for marketplace listing?”).

4. **Keep endpoints close to the data they mutate**
   - If an endpoint primarily changes asset data, it belongs to Asset Service.
   - If it primarily changes listings/orders, it belongs to Marketplace Service.

5. **“Can I put this here?” test**
   - When adding an endpoint, ask:
     - Which service owns the data & invariants?
     - Is there an existing API that should be extended instead?
     - Does this create a cycle (Service A calls B which calls A)?

---

## 4. Alignment Checklist for New/Changed Endpoints

When proposing a new endpoint or changing an existing one:

1. **Identify Owner**
   - Which service owns the entity/data being mutated?  
   - Document this in `System_Architecture.md` if new.

2. **Check Existing Paths**
   - Does a similar endpoint already exist under the same service?  
   - Are we duplicating functionality that belongs elsewhere?

3. **Boundary Review**
   - Does this endpoint require cross-service calls?  
   - If yes, are they **read-only** or **write/side-effecting**?  
   - Should some of those calls be async (via Jobs)?

4. **Security & Multi-Tenancy**
   - Is tenant scoping clear from the URL and auth model?  
   - Are we exposing any cross-tenant data unintentionally?

5. **Semantic & Domain Model Consistency**
   - Does the endpoint use the same IDs and vocabulary as the Domain Model?  
   - Are we adding new concepts that must be reflected in the domain / semantic
     layer?

6. **Versioning & Compatibility**
   - If this is a breaking change, has it been handled via the v1/v2 strategy
     described in `API_Contract_First_Workflow.md`?  
   - Have SDKs and documentation impacts been considered?

7. **Cross-Service Dependency Review**
   - Have we considered Marketplace ↔ Asset, Asset ↔ Contract, etc. in the
     design? (See section 5.)

> **Output:** Every significant API change should link to this checklist in the
> design/PR description and explicitly call out any non-trivial decisions.

---

## 5. Cross-Service Dependencies & Interaction Patterns

Many user flows span multiple services (e.g. Marketplace → Asset Service →
Compliance / DQ). This section defines guidelines for **safe, maintainable**
cross-service dependencies.

### 5.1 Circuit breaker configuration

All internal calls between microservices MUST use the standard circuit breaker policy defined in Technical_Design_Document.md §4.5 (50% failure rate over 60s, min 20 requests, 30s reset timeout, half-open with limited test calls). Any deviation MUST be explicitly documented for that service.


The platform uses circuit breakers on **synchronous calls between services** (HTTP/gRPC) and to **external dependencies** (e.g., object storage, email, external DQ/compliance providers) to prevent cascading failures.

Circuit breaking is implemented at the **client layer** (e.g., API service → downstream service) via a shared resilience library / middleware. This section defines the default configuration and how it can be overridden per service.

#### 5.1.1 Scope: where circuit breakers apply

Circuit breakers are enabled for:

- API service → internal HTTP services (if split out):
  - `auth-service` (if externalized)
  - `dq-service`
  - `compliance-service`
  - `semantic-mapping-service`
- API service / worker-service → external services:
  - Object storage control plane (non-upload control calls: listing, metadata, compose).
  - Email / notification provider.
  - Any external data quality / compliance APIs (if used).

Circuit breakers are **not** applied to:

- Direct DB connections (handled via connection pools, timeouts, and retries).
- Asynchronous message publishing to the job queue (which have their own retry policies).

#### 5.1.2 Failure threshold

We use a **rolling window** with a failure rate threshold and minimum volume:

- **Rolling window:** 60 seconds (config: `CB_WINDOW_SECONDS`)
- **Minimum request count:** 20 calls in the window (config: `CB_MIN_CALLS`)
- **Failure rate threshold:** 50% failures (config: `CB_FAILURE_RATE_THRESHOLD`)

Definition of “failure”:

- HTTP 5xx responses from the downstream.
- Network errors (connection refused, timeouts).
- Explicit timeouts from the client (e.g., request > configured timeout).

**Open condition (per circuit):**

> If, in the last `CB_WINDOW_SECONDS`,  
> `total_calls >= CB_MIN_CALLS` **and**  
> `failures / total_calls >= CB_FAILURE_RATE_THRESHOLD`,  
> then the circuit transitions from **CLOSED → OPEN**.

Default values:

- `CB_WINDOW_SECONDS = 60`
- `CB_MIN_CALLS = 20`
- `CB_FAILURE_RATE_THRESHOLD = 0.5`  (50%)

#### 5.1.3 States and half-open behavior

Each circuit operates in three states:

1. **CLOSED**
   - All requests pass through to the downstream.
   - Failures are recorded in the rolling window.
   - If the failure threshold is exceeded, the circuit moves to **OPEN**.

2. **OPEN**
   - Requests **fail fast** without calling the downstream.
   - Client immediately returns:
     - For internal calls: a synthetic 503 (or translated to the public error format at the API boundary).
     - For user-facing APIs: a standardized error code, e.g. `DOWNSTREAM_UNAVAILABLE`.
   - After the **reset timeout**, the circuit transitions to **HALF_OPEN**.

3. **HALF_OPEN**
   - Only a **limited number of trial requests** are allowed through to the downstream.
   - Config:
     - `CB_HALF_OPEN_MAX_CALLS = 5`
     - `CB_HALF_OPEN_SUCCESS_THRESHOLD = 4` (number of successful calls required to close)
   - Behavior:
     - For each trial request:
       - On success: increment a success counter.
       - On failure: immediately transition back to **OPEN**, reset the reset timer.
     - If `CB_HALF_OPEN_SUCCESS_THRESHOLD` successes are observed **before** any failure:
       - Circuit transitions to **CLOSED** and all counters are reset.

#### 5.1.4 Reset timeout (open → half-open)

When a circuit transitions to **OPEN**, it stays open for a **reset timeout** before moving to **HALF_OPEN**.

- Base reset timeout: `CB_RESET_TIMEOUT_SECONDS = 30`
- Optional exponential backoff per subsequent open cycles:
  - 1st open: 30 seconds
  - 2nd consecutive open: 60 seconds
  - 3rd consecutive open: 120 seconds
  - Capped at `CB_MAX_RESET_TIMEOUT_SECONDS = 300` (5 minutes)

The backoff counters are reset when the circuit successfully transitions to **CLOSED** and remains stable for one full `CB_WINDOW_SECONDS` period.

#### 5.1.5 Per-service configuration

Circuit breakers are configured per **logical downstream service**, not per individual endpoint.

Each internal/external dependency has its own named circuit, e.g.:

- `cb.auth_service`
- `cb.dq_service`
- `cb.compliance_service`
- `cb.semantic_mapping_service`
- `cb.object_storage_control`
- `cb.notification_service`

Each circuit can override the global defaults via configuration (env, config file, or service discovery):

| Circuit                          | Window | Min calls | Failure threshold | Reset timeout | Notes                                  |
|----------------------------------|--------|-----------|-------------------|---------------|----------------------------------------|
| `cb.auth_service`                | 30 s   | 10        | 30%               | 15 s          | Needs quicker feedback, low latency.   |
| `cb.dq_service`                  | 60 s   | 20        | 50%               | 30 s          | Standard settings.                     |
| `cb.compliance_service`          | 60 s   | 20        | 50%               | 30 s          | Standard settings.                     |
| `cb.semantic_mapping_service`    | 120 s  | 50        | 40%               | 60 s          | Heavier calls; tolerate a few failures.|
| `cb.object_storage_control`      | 60 s   | 20        | 50%               | 30 s          | Non-upload control calls only.         |
| `cb.notification_service`        | 60 s   | 10        | 50%               | 30 s          | Email/SMS provider.                    |

Defaults (if no override):

- `CB_WINDOW_SECONDS = 60`
- `CB_MIN_CALLS = 20`
- `CB_FAILURE_RATE_THRESHOLD = 0.5`
- `CB_RESET_TIMEOUT_SECONDS = 30`
- `CB_MAX_RESET_TIMEOUT_SECONDS = 300`
- `CB_HALF_OPEN_MAX_CALLS = 5`
- `CB_HALF_OPEN_SUCCESS_THRESHOLD = 4`

#### 5.1.6 Observability & alerts

Each circuit emits metrics:

- `circuit_state{circuit_name=...}` – current state (`CLOSED`, `OPEN`, `HALF_OPEN`).
- `circuit_open_total{circuit_name=...}` – count of open events.
- `circuit_half_open_total{circuit_name=...}` – count of half-open transitions.
- `circuit_forced_open_total{circuit_name=...}` – manual/admin opens (if supported).

Alerting:

- Ops should be alerted if:
  - A critical circuit (e.g., `cb.auth_service`, `cb.object_storage_control`) remains in **OPEN** state for more than **5 minutes**.
  - The rate of `circuit_open_total` exceeds a threshold per minute.

This configuration ensures consistent, predictable behavior across services, while allowing **per-service tuning** as we learn more about latency/error profiles in production.


### 5.2 Sync vs Async Calls

- Use **synchronous** calls when:
  - The user needs up-to-date data in the same interaction
    (e.g. show asset details on a listing page).
  - The operation is fast and bounded (read or simple write).

- Use **asynchronous** flows (via Job Service / events) when:
  - The operation is long-running (ingestion, compliance/DQ runs).
  - Multiple services must coordinate work (e.g. ingest → compliance → DQ).

**Guideline:**

- Cross-service writes that trigger heavy work SHOULD enqueue a **Job** rather
  than directly chaining multiple synchronous calls.

### 5.3 Failure Handling, Timeouts & Retries

- All cross-service calls MUST:
  - Have sensible **timeouts** (e.g. 1–3s for read calls).
  - Use **idempotent** operations where retries are possible.
  - Translate errors into consistent API error shapes at the gateway layer.

- For **Marketplace → Asset** and similar calls:
  - If the Asset Service is down, prefer **graceful degradation**:
    - show partial listing data with “asset details temporarily unavailable”,
    - prevent new orders if critical checks cannot be performed.
  - Avoid tight retry loops; use limited retries + backoff.

- For high-volume or critical dependencies:
  - Consider **circuit breakers** to avoid cascading failures.
  - Emit metrics for:
    - success/error rates,
    - latency,
    - timeouts.

### 5.4 Caching & Read Models

- Services MAY maintain local **read models** or caches of foreign data
  (e.g. Marketplace caching asset name/description):
  - Cached fields are treated as **non-authoritative**.
  - Changes in the owning service are eventually propagated via:
    - polling, or
    - events (future enhancement).

- Do not rely on cached data for:
  - authorization decisions,
  - critical compliance checks,
  - financial calculations.

#### 5.4.1 Cache Invalidation Strategy

**Cache Types**

The platform uses two types of caches:

1. **In-memory caches** (per-service, local to each service instance):
   - Stored in service memory (e.g., Redis, local hash map).
   - TTL-based expiration (time-to-live).
   - No cross-instance invalidation (each instance manages its own cache).

2. **Shared caches** (cross-service, shared across instances):
   - Stored in shared cache store (e.g., Redis cluster).
   - TTL-based expiration + explicit invalidation.
   - Cross-instance invalidation via cache invalidation events.

**Invalidation Triggers**

Caches are invalidated in the following scenarios:

1. **TTL-based expiration** (automatic):
   - Default TTL: **5 minutes** for most cached data.
   - Configurable per cache key pattern (e.g., `asset:{id}` has 5-minute TTL, `tenant_config:{id}` has 15-minute TTL).
   - TTL starts from cache entry creation time.

2. **Explicit invalidation** (on data change):
   - When a resource is **updated** or **deleted**, the owning service:
     - Invalidates cache entries for that resource (e.g., `asset:{asset_id}`, `contract:{contract_id}`).
     - Publishes cache invalidation event (if using shared cache).
   - Cache keys follow pattern: `<resource_type>:<resource_id>` (e.g., `asset:uuid-123`, `contract:uuid-456`).

3. **Bulk invalidation** (on tenant-level changes):
   - When tenant configuration changes (e.g., `PATCH /tenants/{id}/config`):
     - Invalidates all cache entries for that tenant (pattern: `*:tenant:{tenant_id}:*`).
   - When tenant is suspended or deleted:
     - Invalidates all tenant-related cache entries.

**Cache Key Patterns**

Standard cache key patterns:

- **Asset data**: `asset:{asset_id}` (TTL: 5 minutes)
- **Contract data**: `contract:{contract_id}` (TTL: 5 minutes)
- **Tenant configuration**: `tenant_config:{tenant_id}` (TTL: 15 minutes)
- **User data**: `user:{user_id}` (TTL: 10 minutes)
- **Entitlement checks**: `entitlement:{tenant_id}:{asset_id}` (TTL: 1 minute)
- **Marketplace listings**: `listing:{listing_id}` (TTL: 5 minutes)

**Invalidation Implementation**

**For in-memory caches**:
- Services check TTL on cache read.
- Services invalidate local cache entries when they receive update/delete operations for resources they own.
- No cross-instance invalidation (stale data may exist briefly until TTL expires).

**For shared caches (Redis)**:
- Services use Redis `SET` with `EX` (expiration) for cache writes.
- Services use Redis `DEL` for explicit invalidation.
- Services publish cache invalidation events to Redis pub/sub channel `cache:invalidate`:
  - Event format: `{"resource_type": "asset", "resource_id": "uuid-123", "action": "update"}`
  - All service instances subscribe to this channel and invalidate their local caches on receipt.

**Cache Invalidation Flow Example**

When `PATCH /assets/{id}` is called:

1. **API service** receives request and updates asset in database.
2. **API service** publishes cache invalidation event:
   ```json
   {
     "resource_type": "asset",
     "resource_id": "uuid-123",
     "action": "update",
     "tenant_id": "uuid-tenant"
   }
   ```
3. **All service instances** (including API service, Marketplace service, etc.) receive the event.
4. **Each instance** invalidates its local cache entry for `asset:uuid-123`.
5. **Shared cache (Redis)** entry is deleted (if using shared cache).
6. **Next read** of `GET /assets/{id}` will fetch fresh data from database and repopulate cache.

**Cache Consistency Guarantees**

- **Eventual consistency**: Cache updates are eventually consistent (may be stale for up to TTL duration).
- **Strong consistency for critical data**: Authorization and compliance checks **never** use cached data (always query authoritative source).
- **Stale data tolerance**: UI and read-only operations can tolerate slightly stale data (e.g., asset name/description cached for 5 minutes is acceptable).

**Configuration**

Cache TTLs and invalidation behavior are configurable via environment variables:

- `CACHE_TTL_ASSET_SECONDS` (default: 300 = 5 minutes)
- `CACHE_TTL_CONTRACT_SECONDS` (default: 300 = 5 minutes)
- `CACHE_TTL_TENANT_CONFIG_SECONDS` (default: 900 = 15 minutes)
- `CACHE_TTL_ENTITLEMENT_SECONDS` (default: 60 = 1 minute)
- `CACHE_ENABLE_SHARED` (default: `true` for production, `false` for local dev)

### 5.5 Versioning Across Services

- A service that **consumes** another service’s API:
  - Pins to a specific major version (`/api/v1/...`).  
  - Must be updated deliberately to consume `/api/v2/...` when introduced.

- The owning service:
  - Maintains both `v1` and `v2` during the deprecation window.
  - Communicates deprecation timelines in advance.

### 5.6 Cross-Service Dependency Rules

- Avoid **cyclic dependencies**:
  - e.g. Marketplace depends on Asset & Contract;
    Asset must not depend back on Marketplace.
- Prefer **one-way dependencies** or **hub-and-spoke** patterns
  (e.g. Job Service, Audit Service as shared infra).
- Any new cross-service dependency SHOULD:
  - Be documented in this file (service → service, API surface).
  - Be reviewed for:
    - ownership boundaries,
    - security (authz between services),
    - failure and latency impact.

### 5.7 Partial failure handling (DQ vs Compliance)

DQ and compliance checks run as **separate jobs** during intake (both for new assets and new dataset versions). They can succeed or fail independently. This section defines:

- The intake state machine for partial successes/failures.
- How we avoid exposing “half-validated” data.
- How users are notified.
- How partial failures are captured in the audit trail.

#### 5.7.1 Intake state machine (DQ vs. Compliance)

Conceptually, each **dataset version** has an intake status:

- `INTAKE_PENDING` – file uploaded, dataset row created, jobs enqueued.
- `INTAKE_RUNNING` – at least one of DQ or compliance is running.
- `INTAKE_PARTIAL` – one dimension complete (DQ or compliance), the other pending or failed.
- `INTAKE_READY` – all required checks completed, no blocking failures.
- `INTAKE_BLOCKED` – a **policy violation** (e.g., compliance FAIL with blocking severity).
- `INTAKE_FAILED_SYSTEM` – a **technical failure** (timeouts, infra errors) that prevents checks from completing.
  
We also track **dimension-level** statuses on the dataset (and roll up to the asset):

- `dq_status`: `UNKNOWN | PASS | WARN | FAIL`
- `compliance_status`: `UNKNOWN | PASS | WARN | FAIL`

**Transitions (simplified):**

1. **File upload / dataset created**
   - `INTAKE_PENDING`
   - `dq_status = UNKNOWN`
   - `compliance_status = UNKNOWN`
   - DQ job + compliance job enqueued.

2. **Jobs start**
   - When either job goes `RUNNING` → `INTAKE_RUNNING`.

3. **DQ succeeds, compliance still pending**
   - DQ job: `SUCCEEDED` → `dq_status = PASS/WARN` (based on rules).
   - Compliance job: `PENDING` or `RUNNING`.
   - Intake: `INTAKE_PARTIAL` (this is the “DQ ok, compliance not done yet” case).

4. **DQ succeeds, compliance fails**
   - If compliance fails with **policy violation**:
     - `compliance_status = FAIL`
     - Intake: `INTAKE_BLOCKED`
   - If compliance fails with **system error**:
     - `compliance_status = UNKNOWN` (or `FAIL` + `failure_mode = SYSTEM`)
     - Intake: `INTAKE_FAILED_SYSTEM` (partial success but technically incomplete).

5. **Both complete successfully (no blocking failures)**
   - `dq_status = PASS/WARN`
   - `compliance_status = PASS/WARN`
   - Intake: `INTAKE_READY`
   - Asset may now transition (or remain) in `ACTIVE`/`PUBLIC` depending on other rules.

6. **All checks finished, at least one blocking failure**
   - Policy violation in compliance or catastrophic DQ failure:
   - Intake: `INTAKE_BLOCKED`
   - Dataset is not eligible for exposure (no pointer from asset’s “current dataset” to this version).

**Key principle:**  
The asset’s `latest_dataset_id` used for **consumer-visible reads** is only updated when the new dataset reaches `INTAKE_READY`. If a new version ends in `INTAKE_BLOCKED` or `INTAKE_FAILED_SYSTEM`, consumers continue to see the previous dataset version (if any).

---

#### 5.7.2 Rollback & data exposure rules

We avoid complicated multi-resource rollback by using **gating** rather than “commit then roll back”:

- On **new dataset version**:
  - We create the dataset + file rows and kick off DQ/compliance as usual.
  - We **do not** switch the asset’s `latest_dataset_id` to this version until intake reaches `INTAKE_READY`.
- If **DQ succeeds but compliance fails**:
  - DQ results are **kept** (they’re useful diagnostics).
  - Compliance job result is stored as `FAIL` with a `failure_mode` (`POLICY` or `SYSTEM`).
  - Dataset is marked:
    - `INTAKE_BLOCKED` (policy) **or**
    - `INTAKE_FAILED_SYSTEM` (technical failure).
  - Asset **continues to point** to the previous dataset version (or has no readable dataset if this is the first upload).

This means:

- No consumer will ever see a dataset that hasn't passed whatever compliance rules are configured as **blocking**.
- We **never roll back** successful jobs; we simply do not advance the dataset to "current" if blocking checks failed.
- If this was the **first** dataset for an asset:
  - The asset remains in `DRAFT` (or equivalent "not ready" status).
  - Consumers will not see it in catalog / marketplace until issues are resolved and a successful intake occurs.

#### 5.7.2.1 Transaction Boundaries for Multi-Step Operations

To ensure data consistency and avoid partial states, the platform uses explicit transaction boundaries for multi-step operations:

**Principle: Single-Resource Transactions**

- Each database write operation (INSERT, UPDATE, DELETE) is executed within a **single database transaction**.
- Transactions are **short-lived** (typically < 1 second) and do not span multiple service calls.
- Long-running operations (DQ, compliance, semantic mapping) are **asynchronous** and executed outside of database transactions.

**Transaction Boundaries by Operation Type**

**1. Asset Creation with File Upload**

- **Transaction 1**: Create `files` record (`status = UPLOADING`).
  - Scope: Single INSERT into `files` table.
  - Commit: Immediately after file record creation.
- **Transaction 2**: Create `datasets` record and link to `files`.
  - Scope: INSERT into `datasets` table, UPDATE `files.status = READY`.
  - Commit: After dataset record creation.
- **Transaction 3**: Create `assets` record and link to `datasets`.
  - Scope: INSERT into `assets` table, UPDATE `datasets.asset_id`.
  - Commit: After asset record creation.
- **Asynchronous**: DQ and compliance jobs are enqueued **after** all database transactions complete.

**2. Dataset Version Creation with DQ/Compliance**

- **Transaction 1**: Create new `datasets` record (`version = N+1`, `status = INTAKE_PENDING`).
  - Scope: INSERT into `datasets` table.
  - Commit: Immediately after dataset record creation.
- **Transaction 2**: Create `jobs` records for DQ and compliance.
  - Scope: INSERT into `jobs` table (two records: one for DQ, one for compliance).
  - Commit: After job records creation.
- **Asynchronous**: DQ and compliance jobs execute in background workers.
- **Transaction 3** (on job completion): Update `datasets.status` and `assets.latest_dataset_id`.
  - Scope: UPDATE `datasets.status = INTAKE_READY` (if both DQ and compliance pass), UPDATE `assets.latest_dataset_id = <new_dataset_id>`.
  - Commit: Only if both DQ and compliance pass; otherwise, dataset remains `INTAKE_BLOCKED` or `INTAKE_FAILED_SYSTEM`.

**3. Contract Creation and Validation**

- **Transaction 1**: Create `contracts` record (`status = DRAFT`, `validation_status = PENDING`).
  - Scope: INSERT into `contracts` table.
  - Commit: Immediately after contract record creation.
- **Asynchronous**: Contract validation job executes in background.
- **Transaction 2** (on validation completion): Update `contracts.validation_status`.
  - Scope: UPDATE `contracts.validation_status = VALID | INVALID | WARNING_ONLY`.
  - Commit: After validation status update.

**4. Marketplace Order Approval**

- **Transaction 1**: Create `orders` record (`status = REQUESTED`).
  - Scope: INSERT into `orders` table.
  - Commit: Immediately after order record creation.
- **Transaction 2** (on approval): Update `orders.status = APPROVED` and create `entitlements` record.
  - Scope: UPDATE `orders.status`, INSERT into `entitlements` table.
  - Commit: Both operations in a single transaction (atomic).

**5. Tenant Creation with Initial Admin**

- **Transaction 1**: Create `tenants` record (`status = ACTIVE`, `kyc_status = UNVERIFIED` unless specified).
  - Scope: INSERT into `tenants` table.
  - Commit: Immediately after tenant record creation.
- **Transaction 2**: Create default roles for the tenant (`TENANT_ADMIN`, `DATA_PROVIDER`, `DATA_CONSUMER`, `AUDITOR`).
  - Scope: INSERT into `roles` table (4 records, one per role). Uses `INSERT ... ON CONFLICT DO NOTHING` for idempotency.
  - Commit: After all role records are created (or skipped if they already exist).
- **Transaction 3**: Create initial admin user and assign `TENANT_ADMIN` role.
  - Scope: INSERT into `users` table, INSERT into `user_roles` join table (linking user to `TENANT_ADMIN` role).
  - Commit: Both operations in a single transaction (atomic).
  - User status: `INVITED` if `send_invitation = true`, `ACTIVE` if `send_invitation = false`.
- **Asynchronous**: If `send_invitation = true`, sends invitation email to `initial_admin_email` (within 1 minute). Email failures are logged but do not affect tenant creation.

**Consistency Guarantees**

- **No distributed transactions**: The platform does not use distributed transactions (2PC, Saga) across services.
- **Eventual consistency**: Long-running operations (DQ, compliance) achieve eventual consistency:
  - Initial state: Resources created with `PENDING` status.
  - Final state: Resources updated to terminal status (`SUCCEEDED`, `FAILED`, `BLOCKED`) after async jobs complete.
- **Idempotency**: All operations are idempotent:
  - Re-running the same operation (e.g., re-validating a contract) does not create duplicates.
  - Idempotency is enforced via `idempotency_key` or natural keys (e.g., `(tenant_id, asset_id, version)`).

**Error Handling**

- **Transaction failures**: If a database transaction fails:
  - All changes within that transaction are rolled back.
  - No partial state is persisted.
  - Client receives error response with appropriate error code.
- **Async job failures**: If an async job fails:
  - Job status is updated to `FAILED` (in a separate transaction).
  - Related resources remain in `PENDING` or `BLOCKED` state.
  - Client can retry by creating a new job.

#### 5.7.2.2 Service Crash Recovery During Multi-Step Operations

When a service crashes or becomes unavailable during a multi-step operation, the platform uses the following recovery mechanisms:

**Recovery Principles**

1. **Idempotent Operations**: All operations are designed to be idempotent, allowing safe retries.
2. **State Tracking**: Each operation's state is persisted in the database before execution.
3. **Background Cleanup**: Orphaned resources are cleaned up by background jobs.
4. **Timeout-Based Recovery**: Operations that exceed their timeout are automatically marked as failed.

**Recovery Scenarios**

**Scenario 1: Service Crash During File Upload**

- **State**: File record created (`status = UPLOADING`), but upload not completed.
- **Recovery**:
  - Background job (`Upload Session Cleanup`, see `System_Architecture.md` §2.6) runs every hour.
  - Identifies files with `status = UPLOADING` and `created_at < NOW() - INTERVAL '24 hours'`.
  - Marks file as `status = EXPIRED` and deletes partial chunks from object storage.
  - Client receives `410 Gone` with `UPLOAD_SESSION_EXPIRED` on subsequent requests.
  - Client must start a new upload.

**Scenario 2: Service Crash During Dataset Creation**

- **State**: File uploaded (`status = READY`), but dataset record not created.
- **Recovery**:
  - Client can retry `POST /assets/{id}/datasets` with the same `data_file_id`.
  - Server checks if dataset already exists for this file (idempotency check).
  - If dataset exists, returns existing dataset (no duplicate created).
  - If dataset doesn't exist, creates new dataset.

**Scenario 3: Service Crash During DQ/Compliance Job Execution**

- **State**: Job record created (`status = PENDING` or `RUNNING`), but job not completed.
- **Recovery**:
  - Worker service monitors job queue for stuck jobs.
  - Jobs with `status = RUNNING` and `updated_at < NOW() - INTERVAL '<job_timeout>'` are marked as `FAILED`.
  - Error code: `JOB_TIMEOUT` or `JOB_WORKER_CRASHED`.
  - Client can retry by creating a new job (idempotent operation).

**Scenario 4: Service Crash During Asset Update**

- **State**: Asset update transaction in progress.
- **Recovery**:
  - Database transaction is rolled back automatically (no partial state).
  - Client receives error response (if connection was still open) or timeout.
  - Client can retry with same `version` value (optimistic locking prevents conflicts).
  - If `version` mismatch, client fetches fresh data and retries.

**Scenario 5: Service Crash During Marketplace Order Approval**

- **State**: Order approval transaction in progress.
- **Recovery**:
  - Database transaction is rolled back automatically.
  - Order remains in `status = REQUESTED`.
  - Admin can retry approval (idempotent operation).

**Background Cleanup Jobs**

The following background jobs handle orphaned resources (see `System_Architecture.md` §2.6):

1. **Upload Session Cleanup** (runs every hour):
   - Identifies expired upload sessions (`files.status = UPLOADING`, `created_at < NOW() - INTERVAL '24 hours'`).
   - Deletes partial chunks from object storage.
   - Marks files as `status = EXPIRED`.

2. **Stuck Job Recovery** (runs every 5 minutes):
   - Identifies stuck jobs (`jobs.status = RUNNING`, `updated_at < NOW() - INTERVAL '<job_timeout>'`).
   - Marks jobs as `FAILED` with error code `JOB_TIMEOUT`.
   - Emits audit event for monitoring.

3. **Orphaned Resource Cleanup** (runs daily):
   - Identifies orphaned resources (e.g., datasets without assets, files without datasets).
   - Marks resources for deletion or alerts operators.

**Monitoring and Alerting**

- Services MUST emit metrics for crash recovery:
  - `service_crashes_total{service}` (counter)
  - `orphaned_resources_total{resource_type}` (gauge)
  - `stuck_jobs_total{job_type}` (gauge)
- Alerts fire when:
  - Service crash rate exceeds threshold (e.g., > 3 crashes in 10 minutes).
  - Orphaned resources exceed threshold (e.g., > 100 orphaned files).
  - Stuck jobs exceed threshold (e.g., > 50 stuck jobs).

**Manual Recovery Procedures**

If automatic recovery fails, operators can use the following procedures (see `Runbooks_and_Operational_Procedures.md`):

1. **Identify orphaned resources**: Query database for resources in intermediate states.
2. **Assess impact**: Determine if resources can be safely cleaned up or need manual intervention.
3. **Cleanup or repair**: Execute cleanup scripts or manual database updates.
4. **Verify**: Run consistency checks to ensure system is in valid state.

---

#### 5.7.3 User notification strategy

There are three primary notification surfaces:

1. **Synchronous API response**
   - Creation endpoints (e.g. `POST /files/complete` or `POST /assets`) immediately return:
     - IDs of created resources, and
     - IDs of DQ and compliance jobs.
   - They do **not** block on long-running checks; clients are expected to:
     - Poll `/jobs/{id}` or
     - Use the asset/dataset read APIs to see rolled-up statuses.

2. **UI / Dashboard**
   - Asset and dataset pages display DQ and compliance chips separately, e.g.:
     - `DQ: PASS`, `Compliance: FAIL (policy violation – sensitive column X)`
   - Dedicated **intake status banner**:
     - `Intake partially succeeded: Data quality checks passed, but compliance checks failed. Asset is not yet available to consumers.`
   - For system errors (`INTAKE_FAILED_SYSTEM`):
     - Banner suggests retry and/or contacting support.
     - UI offers a “Re-run compliance” button that queues a new job reusing the same file.

3. **Asynchronous notifications (optional)**
   - For tenants that enable them:
     - **Email** to asset owners when intake ends in `INTAKE_BLOCKED` or `INTAKE_FAILED_SYSTEM`.
     - **Webhooks** with events like:
       - `intake.completed`
       - `intake.partial_failure`
       - `intake.blocked`
     - Payload includes:
       - `asset_id`, `dataset_id`, `dq_job_id`, `compliance_job_id`
       - summary status and error codes.

---

#### 5.7.4 Audit trail for partial failures

All key transitions and outcomes are recorded in the **audit log** (e.g. `audit_events` table).

Events include at least:

- `INTAKE_STARTED`
  - `target_type = "dataset"`, `target_id = dataset_id`
  - `details`: `asset_id`, `file_id`, `dq_job_id`, `compliance_job_id`, `triggered_by`.

- `DQ_RUN_COMPLETED`
  - `target_type = "dq_run"`, `target_id = dq_job_id`
  - `details`: summary metrics, `status`, `severity`, `rules_failed`.

- `COMPLIANCE_RUN_COMPLETED`
  - `target_type = "compliance_run"`, `target_id = compliance_job_id`
  - `details`: `status`, `policy_ids`, `violation_count`, etc.

- `INTAKE_PARTIAL_FAILURE`
  - Emitted when one dimension succeeds and the other fails.
  - `details` includes:
    - `dq_status`, `compliance_status`
    - `failure_mode` (`POLICY` or `SYSTEM`)
    - whether asset’s `latest_dataset_id` was advanced (it should be `false` here).

- `INTAKE_READY` / `INTAKE_BLOCKED` / `INTAKE_FAILED_SYSTEM`
  - Final state of the intake pipeline for that dataset version.
  - `details`: final statuses and any resulting asset status change.

**Audit guarantees:**

- Every dataset intake has a **start** and **final** audit event.
- Partial failures (e.g., DQ succeeded, compliance failed) are **explicitly labeled** via `INTAKE_PARTIAL_FAILURE`.
- Audit entries are linked by:
  - `asset_id`, `dataset_id`, and job IDs, so investigators can reconstruct exactly what happened.

This design:

- Makes partial failures first-class, inspectable states.
- Avoids exposing partially-validated data by **gating promotion** of new dataset versions.
- Preserves successful computation (DQ) for troubleshooting.
- Gives clear signals to users and auditors about what went wrong and what is safe to use.

### 5.8 Retry strategy details

This section refines the high-level “timeouts & retries” guidance in §5.3 with concrete parameters:

- Exponential backoff behavior.
- Max retry counts per operation type.
- Idempotency key usage.
- Per-tenant retry budgets.

#### 5.8.1 Scope & principles

Retries are only applied when:

- The operation is **idempotent** (or explicitly designed to be retriable), and
- The failure is **transient-looking**:
  - timeouts,
  - 5xx responses,
  - connection issues,
  - circuit **half-open** probe failures.

We do **not** retry on:

- 4xx errors (validation, auth, business rule violations).
- Idempotency conflicts (e.g. duplicate request with conflicting payload).
- Anything documented as “non-retriable” for a given endpoint.

Retries are always **bounded** (count + time) and use **jittered exponential backoff** to avoid thundering herds.

---

#### 5.8.2 Exponential backoff parameters

We use a standard exponential backoff with jitter:

- Base delay: `BASE_DELAY_MS` (varies by call type).
- Exponent: `2^attempt_index` (attempt index starting at 0).
- Max delay cap: `MAX_DELAY_MS`.
- Jitter: randomization in `[delay * 0.5, delay * 1.5]`.

Formula (before jitter):

```text
delay_ms = min(BASE_DELAY_MS * 2^attempt_index, MAX_DELAY_MS)
```

Then apply jitter:

```text
delay_ms = random_between(delay_ms * 0.5, delay_ms * 1.5)
```

**Default parameters (per call type)**

| Call type                               | BASE_DELAY_MS | MAX_DELAY_MS | Notes                                 |
|-----------------------------------------|---------------|--------------|---------------------------------------|
| Internal read (service → service)       | 100 ms        | 1,000 ms     | Low latency, few retries.             |
| Internal idempotent write               | 200 ms        | 2,000 ms     | e.g. posting a job, updating status.  |
| External provider (email, 3rd-party)    | 500 ms        | 5,000 ms     | External dependencies.                |
| Job queue publish / metadata operations | 200 ms        | 2,000 ms     | Not for bulk data upload.             |

**Exact Backoff Calculation Example**

For an internal read call with `BASE_DELAY_MS = 100` and `MAX_DELAY_MS = 1000`:

- **Attempt 0** (first retry):
  - Base delay: `min(100 * 2^0, 1000) = min(100, 1000) = 100 ms`
  - With jitter: `random(50, 150) ms` (e.g., 87 ms)
- **Attempt 1** (second retry):
  - Base delay: `min(100 * 2^1, 1000) = min(200, 1000) = 200 ms`
  - With jitter: `random(100, 300) ms` (e.g., 234 ms)
- **Attempt 2** (third retry):
  - Base delay: `min(100 * 2^2, 1000) = min(400, 1000) = 400 ms`
  - With jitter: `random(200, 600) ms` (e.g., 387 ms)
- **Attempt 3** (fourth retry, if allowed):
  - Base delay: `min(100 * 2^3, 1000) = min(800, 1000) = 800 ms`
  - With jitter: `random(400, 1200) ms` (capped at 1000 ms, e.g., 923 ms)
- **Attempt 4+** (further retries):
  - Base delay: `min(100 * 2^4, 1000) = min(1600, 1000) = 1000 ms` (capped)
  - With jitter: `random(500, 1500) ms` (capped at 1000 ms, e.g., 1000 ms)

**Jitter Implementation**

- Jitter uses a **uniform random distribution** between `delay * 0.5` and `delay * 1.5`.
- For capped delays (at `MAX_DELAY_MS`), jitter is also capped:
  - If `delay = MAX_DELAY_MS`, jitter range is `[MAX_DELAY_MS * 0.5, MAX_DELAY_MS]`.
- Jitter prevents synchronized retries (thundering herd problem) when multiple clients retry simultaneously.

These are **client-side** defaults used by the shared resilience library; individual services may override them with config (per environment).

---

#### 5.8.3 Max retry count per operation type

We cap retries per **call type** to balance resilience and load:

| Call type                               | Max retries (`N`) | Total attempts (1 + N) | Rationale                               |
|-----------------------------------------|-------------------|------------------------|-----------------------------------------|
| Internal read (GET-like)                | 2                 | 3                      | Reads are cheap; quick second/third try.|
| Internal idempotent write (POST/PUT)    | 1                 | 2                      | Avoid duplicate work, still resilient.  |
| External provider (email/SaaS)          | 2                 | 3                      | External flakiness is common.           |
| Job queue publish / control metadata    | 3                 | 4                      | Critical for async flows.               |
| Non-idempotent write                    | 0                 | 1                      | **No automatic retries.**               |

Notes:

- “Max retries = 2” means **original attempt + 2 retries**.
- Each retry still obeys:
  - per-service **circuit breakers** (§5.1),
  - overall **timeout** per call (e.g. 1–3s),
  - and **tenant retry budget** (below).

---

#### 5.8.4 Idempotency key generation & use

For external-facing APIs where a client may **safely retry** a create-like operation (e.g., “create DQ run”, “create compliance run”), we support **idempotency keys**.

**Request contract**

- Header:

  ```http
  Idempotency-Key: <opaque-string>
  ```

- Requirements:
  - Globally unique per client **for each logical operation**.
  - Must be treated as an **opaque token** by the server.
  - Recommended client format:
    - UUID v4, or
    - `<client-system-id>/<operation-type>/<client-local-id>` hashed to a fixed-length string.

**Idempotency Key Validation Rules**

The server validates idempotency keys according to the following rules:

- **Format validation**:
  - **Length**: Minimum 8 characters, maximum 256 characters.
  - **Character set**: Alphanumeric characters, hyphens (`-`), underscores (`_`), and forward slashes (`/`).
  - **Pattern**: Must match regex: `^[a-zA-Z0-9\-_/]{8,256}$`.
  - **Rejection**: Keys that do not match the pattern are rejected with `400 Bad Request` and error code `VALIDATION_ERROR` (message: "Invalid idempotency key format").

- **Uniqueness scope**:
  - Idempotency keys are scoped to:
    - `tenant_id` (from authentication token)
    - `method + path` (e.g., `POST /api/v1/dq-runs`)
  - The same key can be reused for different endpoints or different tenants.
  - The same key cannot be reused for the same `(tenant_id, method, path)` combination within the expiry window.

- **Expiry**:
  - Idempotency records expire after **24 hours** from creation.
  - After expiry, the same key can be reused for a new operation.
  - Expired records are cleaned up by a background job (runs every 6 hours).

- **Request fingerprint matching**:
  - The server computes a request fingerprint from:
    - HTTP method (e.g., `POST`)
    - Request path (e.g., `/api/v1/dq-runs`)
    - Request body hash (SHA-256 of the JSON body, hex-encoded)
  - If a request with the same `idempotency_key` has a **matching fingerprint**:
    - Returns the cached response (status code and body) from the original request.
  - If the fingerprint **differs**:
    - Returns `409 Conflict` with error code `IDEMPOTENCY_CONFLICT`.
    - Error message: "Idempotency key already used with different request parameters".

**Server behavior**

- We persist idempotency records in a dedicated table (`idempotency_keys`) keyed by:
  - `tenant_id` (UUID, FK to `tenants.id`)
  - `idempotency_key` (text, indexed)
  - `method` (text, e.g., `POST`)
  - `path` (text, e.g., `/api/v1/dq-runs`)
  - Unique constraint: `(tenant_id, idempotency_key, method, path)`
- Additional columns:
  - `request_fingerprint` (text, SHA-256 hash of method + path + body)
  - `response_status` (integer, HTTP status code)
  - `response_body` (JSONB, cached response body)
  - `created_at` (timestamp)
  - `expires_at` (timestamp, `created_at + 24 hours`)

- First request:
  - Validate idempotency key format.
  - Compute request fingerprint.
  - Check for existing record with same `(tenant_id, idempotency_key, method, path)`.
  - If not found:
    - Execute operation as normal.
    - Persist idempotency record with fingerprint, response, and expiry.
  - If found and fingerprint matches:
    - Return cached response (do not re-execute operation).
  - If found and fingerprint differs:
    - Return `409 Conflict` with `IDEMPOTENCY_CONFLICT` error.

- Subsequent identical requests:
  - If request fingerprint matches:
    - Return cached response immediately (no operation execution).
  - If fingerprint differs:
    - Return `409 Conflict` with a standardized error:
      - `code = "IDEMPOTENCY_CONFLICT"`
      - `message = "Idempotency key already used with different request parameters"`

**Implementation Notes**

- **Database index**: Create composite index on `(tenant_id, idempotency_key, method, path)` for fast lookups.
- **Cleanup job**: Background job runs every 6 hours to delete expired idempotency records (`expires_at < NOW()`).
- **Performance**: Idempotency checks should complete in < 10ms (single database lookup).

**Idempotency rules**

- Idempotency is **required** for:
  - `POST /dq-runs`
  - `POST /compliance-runs`
  - Any “create job / create run” endpoint where clients might retry on network failure.
- Optional / recommended for:
  - Asset and dataset creation endpoints, depending on client usage patterns.

Internal service-to-service calls:

- Prefer **natural idempotency** via “upsert” patterns, or
- Use an internal idempotency token where necessary (e.g. job enqueue to avoid duplicates).

---

#### 5.8.5 Retry budget per tenant

To prevent a single tenant from causing excess load through retries (especially under widespread failure), we enforce a **retry budget per tenant**.

**Concept**

- Over a sliding time window, retries for a tenant are capped relative to their **original call volume**.
- A retry is every attempt **after the first** for the same logical operation.

**Implementation sketch**

For each tenant and operation category (e.g., “internal calls”, “external calls”):

- Track:
  - `original_calls` – first attempts.
  - `retry_calls` – subsequent attempts.
  - Window: 60 seconds (sliding).
- Define a budget ratio:

  ```text
  retry_calls <= RETRY_BUDGET_RATIO * original_calls + RETRY_BUDGET_FLOOR
  ```

  where (defaults):

  - `RETRY_BUDGET_RATIO = 0.5` (retries up to 50% of original calls)
  - `RETRY_BUDGET_FLOOR = 50` (allow some retries even at low volume)

**Behavior when budget exceeded**

- The resilience library stops issuing further retries for that tenant and operation category in the current window:
  - The **next failure** will be surfaced directly to the caller **without retry**.
- The caller receives the underlying error as if **no retry** had been attempted.
- Optionally, we may return (or log) additional metadata indicating that the retry budget was exhausted.

This budget works together with:

- **API rate limits** (per tenant & per user, see API Spec).
- **Circuit breakers** (§5.1) to limit pressure on failing dependencies.

**Tuning**

- Retry budget parameters are configurable per environment.
- Critical internal operations (e.g. job publishing) may be assigned:
  - a higher `RETRY_BUDGET_RATIO` or
  - a dedicated bucket, separate from user-triggered calls.

---

Overall, this retry strategy ensures:

- Explicit, bounded, and jittered retries.
- Clear **idempotency** semantics for client-facing creates.
- Protection against runaway retries via **per-tenant budgets**.
- Alignment with the circuit breaker behavior already defined in §5.1.


---

## 6. Maintenance & Governance

- This document should be updated whenever:
  - a new service is introduced,
  - a service boundary changes,
  - new major API paths are added.
- Architecture and API owners share responsibility to keep the mapping accurate
  and to review changes against this alignment document during design and PR
  reviews.
