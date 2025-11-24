# Testing Strategy

This document describes how we will **prove that the Interoperable Data Hub MVP works as intended**, across:

- Functional behavior (contracts, DQ, compliance, marketplace)
- Non-functional aspects (security, privacy, performance at MVP scale)
- Multi-tenant isolation
- Semantic / ontology behavior

It also defines the **sample datasets** we will use during testing.

This strategy aligns with:

- `SystemRequirements.md`
- `Personas.md`
- `MVP_Scope.md`
- `Domain_Model.md`
- `API_Spec_v1.md`
- `Security_Design_and_Threat_Model.md`
- `UX_MVP_Flows.md`

---

## 1. Goals & Scope

### 1.1 Testing Goals

1. Verify that the **three onboarding flows** (data-first, contract-first, contract-only) behave exactly as specified:
   - Correct validation of contracts (via DataContract CLI).
   - Correct enforcement of DQ & compliance rules.
   - Correct lifecycle of Asset, Contract, Dataset, DQRun, ComplianceRun, Job, AuditEvent.

2. Prove that the platform **never stores non-compliant data** according to configured rules:
   - If compliance marks `allowed_to_store = false`, no Dataset is created and raw file is removed.

3. Demonstrate **multi-tenant isolation**:
   - A user in tenant A cannot access or infer data from tenant B, except for explicitly public marketplace metadata and semantic info.

4. Demonstrate **auditability**:
   - Every critical action (onboarding, validation, DQ, compliance, marketplace order/entitlement) produces an appropriate AuditEvent that can be queried.

5. Demonstrate that the **semantic layer** is consistent with the core data model:
   - URIs for assets/contracts/datasets are stable and resolvable.
   - JSON-LD outputs reflect the underlying entities.

6. Provide **repeatable automated tests** suitable for CI/CD.

### 1.2 Scope (MVP)

In scope:

- All `/api/v1` APIs.
- Web UI flows described in `UX_MVP_Flows.md`.
- Integration with:
  - DataContract CLI.
  - Great Expectations / Soda for DQ.
  - Compliance service (internal component).
- Semantic endpoints (`/id/...`, `/sparql`).
- Audit logging and retrieval for 3-year retention (logical tests; we cannot time-travel but can assert retention configuration).

Out of scope for MVP testing:

- Full penetration testing (only basic security tests).
- Large-scale performance & chaos testing (we will do limited load tests at MVP scale).
- KYC & full payment flows (future).

---

## 2. Test Levels

### 2.1 Unit Tests

**Purpose:** Validate behavior of individual functions/classes with no external dependencies.

Examples:

- **Contract Normalization & Mapping**
  - Map normalized HubContract to internal models (schema fields, quality rules, compliance metadata).
  - Validate required fields presence and defaulting logic.

- **Access Control Helpers**
  - Given a token (tenant_id, roles[]), check:
    - CanCreateAsset, CanReadAsset, CanListAuditEvents, etc.
  - Ensure “least privilege” rules are encoded and tested.

- **Result Mappers**
  - Mapping Great Expectations / Soda results → DQRun JSON.
  - Mapping Compliance engine output → ComplianceRun JSON, including:
    - `overall_status`
    - `risk_level`
    - `allowed_to_store`
    - `detected_categories`

- **Audit Event Builders**
  - Ensure every critical action generates consistent, structured AuditEvent payloads (no raw PII).

Unit tests are run in:

- Local dev environment.
- CI on every push / PR.

### 2.2 Service & Integration Tests

**Purpose:** Ensure services work correctly together: API + DB + external tools.

Examples:

- **Contracts Service + DataContract CLI**
  - `POST /contracts` with ODCS and DataContract.com examples.
  - CLI is invoked, validation results are stored.
  - Errors and warnings are exposed via API accordingly.

- **DQ Service**
  - `POST /dq-runs` using sample datasets.
  - Great Expectations / Soda executed.
  - DQRun record is created and contains expected metrics and statuses.

- **Compliance Service**
  - `POST /compliance-runs` using sample datasets with:
    - No PII.
    - Synthetic PII that should be allowed (depending on policy).
    - Synthetic PII that should trigger `allowed_to_store = false`.
  - Assertions:
    - Raw files for blocked runs are deleted.
    - Datasets are not created.

- **File Intake Pipeline**
  - `/files/init` → upload file → `/files/{id}/complete` with `run_dq=true`, `run_compliance=true`.
  - Verify:
    - Jobs created (DQ & compliance).
    - DQRun & ComplianceRun records.
    - Asset/Dataset created only when all checks pass and compliance allows storage.

- **Semantic Mapping**
  - When an Asset is created/updated:
    - RDF graph is updated.
  - `/id/asset/{id}` returns JSON-LD with correct DCAT mapping.

These tests run against a **docker-compose** or similar environment (API + DB + CLI + DQ/Compliance containers).

### 2.3 End-to-End (E2E) / UI Tests

**Purpose:** Validate full user journeys from UI perspective, using headless browser or automated client (e.g., Playwright, Cypress, or similar).

Core scenarios:

1. **Data-First Happy Path**
   - Data Product Owner logs in.
   - Creates new asset, uploads “clean” dataset.
   - Sees schema inference, DQ pass, compliance pass.
   - Edits contract, runs validation, activates asset.
   - Result: Asset is `ACTIVE`, dataset present, DQ & compliance badges `PASS`.

2. **Data-First Compliance Block**
   - Uses “blocked_PII” dataset.
   - Upload triggers compliance run with `allowed_to_store = false`.
   - UI displays blocking banner.
   - No dataset appears under asset.
   - Audit log shows compliance check and failure.

3. **Contract-First Happy Path**
   - Upload valid contract (ODCS example).
   - Validate with CLI.
   - Upload matching dataset.
   - See schema comparison, no critical mismatches.
   - Edit contract if needed, validate, activate.

4. **Contract-Only**
   - Upload contract.
   - Validate and create asset without data.
   - Later attach dataset and go through DQ/compliance.

5. **Marketplace Flow**
   - Provider publishes `ACTIVE` asset as listing.
   - Consumer from another tenant browses marketplace, sees listing.
   - Consumer requests access and is auto-entitled (for MVP).
   - Consumer sees asset in “My Data” and can call read/download endpoints.

6. **Audit & Compliance Officer View**
   - Auditor filters audit logs by asset, sees:
     - Contract validation events.
     - DQ run events.
     - Compliance run events.
     - Listing publication event.
   - Compliance Officer opens compliance run detail and sees expected categories and risk levels.

These E2E tests can run nightly or before major releases.

### 2.4 Non-Functional Tests

- **Performance (MVP target)**
  - Run DQ & compliance on medium-sized files (e.g., 50–200 MB).
  - Measure:
    - Time to complete intake pipeline.
    - Memory usage & CPU of services.
  - Ensure operations finish within acceptable bounds for MVP (e.g., a few minutes).

- **Security (basic)**
  - Automated tests that:
    - Try cross-tenant resource access (should get 404/403).
    - Ensure that sample PII values do not appear in logs (spot checks with log scraping in CI).
    - Fuzz input for contract upload, SPARQL endpoint with read-only restrictions.

---

## 3. Test Environments

### 3.1 Local Development

- Each developer can run:
  - API server.
  - DB (e.g. PostgreSQL).
  - Local DataContract CLI container.
  - Local DQ (GX/Soda) and Compliance containers.
- Use a `docker-compose` to spin up all dependencies.
- Synthetic test data and sample datasets only.

### 3.2 CI Environment

- Automation runs on every PR:
  - Unit tests.
  - Integration tests (API + CLI + DB).
- Nightly or scheduled runs:
  - E2E tests (headless browser).
  - Basic performance tests with sample datasets.

### 3.3 Staging Environment

- Mirror production configuration (minus scale).
- Used for manual exploratory testing:
  - UI flows.
  - Semantics and marketplace integration.

### 3.4 Integration Test Setup (Local & CI)

**Goal:** make it easy to spin up a realistic environment and run integration
tests consistently on developer machines and in CI.

#### 3.4.1 Local Integration Tests

- Use `docker-compose` to start dependencies:
  - Postgres (metadata DB),
  - object storage (e.g. MinIO),
  - job queue,
  - triplestore (semantic RDF),
  - DataContract CLI / wrapper,
  - DQ & Compliance services (or their mocks, if needed).
- Run DB migrations for the local schema.
- Seed **only synthetic** data:
  - create 1–2 test tenants and users,
  - register sample assets and contracts,
  - upload sample files from `sample_datasets/`.
- Run integration/API tests from the host (or a dedicated `test-runner` container)
  against `api-service` and domain services.

#### 3.4.2 CI Integration Tests

- CI stage \"Integration Tests\" performs the same steps as local, but in a
  clean environment:

  1. Build service images (or use pre-built ones).
  2. Start `docker-compose` stack for tests (DB, queue, object storage,
     triplestore, core services).
  3. Wait for health checks to pass.
  4. Run integration/API test suite:
     - contract endpoints,
     - DQ/Compliance orchestration,
     - job polling and status transitions.
  5. Tear down containers and volumes after the run.

- Tests MUST assume **no shared state** between runs:
  - each run uses a fresh database/schema and fresh object storage prefix.

---

## 4. Test Data Strategy & Sample Datasets

All sample datasets are **synthetic** and must **never contain real customer data**.

We store them under a dedicated directory (e.g., `sample_datasets/`) with clear documentation.

### 4.1 Dataset Overview

We define the following sample datasets:

1. **orders_clean.csv**  
   - For “happy path” DQ & compliance passes.
   - Contains typical ecommerce order data with minimal PII and compliant structure.

2. **orders_pii_blocked.csv**  
   - Purposefully contains synthetic direct identifiers (e.g., national IDs, credit cards).
   - Intended to trigger `allowed_to_store = false` in compliance engine.

3. **orders_low_quality.csv**  
   - Contains missing values, duplicates, and some invalid types.
   - Expected to cause DQ `WARN` or `FAIL` depending on thresholds.

4. **orders_semantic_edge.csv** (optional)  
   - Includes columns mapped to ontology entities for semantic testing.
   - Used to verify URIs and RDF mapping.

5. **contract_examples/**  
   - A folder of ODCS and DataContract.com example contracts:
     - Valid and invalid cases.
   - Used in contract API tests and CLI integration tests.

### 4.2 Sample Dataset Schemas

#### 4.2.1 orders_clean.csv

Columns:

- `order_id` (string, non-null, unique)
- `order_date` (ISO date)
- `customer_id` (string)
- `customer_email` (string with synthetic emails)
- `country_code` (ISO country)
- `total_amount` (decimal)
- `currency` (string, e.g., "USD")

Intended behavior:

- DQ:
  - Null ratio for key fields is near 0%.
  - Unique constraint (e.g., `order_id`) passes.
  - Type checks pass.
- Compliance:
  - Detect `PII_EMAIL` in `customer_email`, but configuration allows storage (e.g., because it’s expected and covered by default policy).
  - `allowed_to_store = true`.

#### 4.2.2 orders_pii_blocked.csv

Columns:

- Same base schema as `orders_clean.csv`, plus:
  - `credit_card_number` (synthetic but realistic format).
  - `national_id` (synthetic).
- Contains rows where these columns are populated.

Intended behavior:

- Compliance:
  - Detect sensitive categories such as `PII_FINANCIAL_CARD`, `PII_GOV_ID`.
  - Policy is configured so that:
    - If any such category exists above threshold (e.g., >= 1% of rows), then `allowed_to_store = false`.
- Platform behavior:
  - Intake pipeline:
    - Compliance run → `FAIL`, `allowed_to_store = false`.
    - No Dataset is created.
    - File is deleted from temporary storage.
  - UI:
    - Shows blocking message.
  - Audit:
    - AuditEvent records compliance run and blocked decision.

#### 4.2.3 orders_low_quality.csv

Columns:

- Same base as `orders_clean.csv`.

Characteristics:

- Some `order_id` values are duplicated.
- Some `order_date` values are invalid or missing.
- Some `total_amount` are negative or null.

Intended behavior:

- DQ:
  - Check fails for:
    - Uniqueness of `order_id`.
    - Validity/range checks on `total_amount`.
  - Overall status: `WARN` or `FAIL` depending on thresholds.
- Compliance:
  - Same as `orders_clean.csv` (under expected PII categories).
  - `allowed_to_store = true`.

#### 4.2.4 contract_examples

- A set of JSON/YAML files covering:
  - Valid ODCS v3.0.x contract.
  - Valid ODCS v2.2.x contract.
  - Valid DataContract.com contract.
  - Contracts with missing required fields (expected CLI `INVALID`).
  - Contracts with deprecated fields (expected CLI warnings).

These examples are used in tests for:

- `/contracts` creation and validation.
- `/contracts/{id}/validate` behavior.
- HubContract normalization across versions.

### 4.3 Test Data Management Strategy

**Principles**

- All automated tests MUST use **synthetic data only**.
- Test data MUST be:
  - repeatable (same inputs → same expected outputs),
  - versioned with the code,
  - isolated per environment and per test run (no hidden coupling).

**Static vs generated data**

- **Static sample datasets** live under `sample_datasets/`:
  - used for integration, E2E, and manual testing,
  - updated deliberately via code review (changes may affect many tests).
- **Generated data**:
  - small, focused fixtures generated inline or via factories for unit tests,
  - used when only structure matters (e.g. “any valid HubContract”),
  - avoid over-reliance on large static fixtures in unit tests.

**Seeding & cleanup**

- Each test environment (local, CI, staging) MUST provide a **seed script** that:
  - creates test tenants, users, roles,
  - registers sample assets, datasets, and contracts,
  - uploads or references sample files (e.g. `orders_clean.csv`).
- Seeds MUST be:
  - **idempotent** (safe to run multiple times),
  - **environment-aware** (e.g. separate prefixes/buckets per environment).
- Integration tests and CI runs MUST:
  - either use a **fresh schema/database** per run, or
  - truncate/reset core tables between test suites.

**Isolation between environments**

- Local dev, CI, and staging MUST NOT share the same buckets/prefixes or DBs.
- Naming convention example:
  - `hub_local_*` for local DB/schema,
  - `hub_ci_*` for CI,
  - `hub_staging_*` for staging.
- Object storage prefixes should follow similar patterns:
  - `s3://hub-local-samples/...`,
  - `s3://hub-ci-samples/...`.

**Golden test cases**

- For critical flows (e.g. intake with blocking PII, cross-tenant access denial),
  we SHOULD maintain a small set of **golden test cases**:
  - stable inputs (contracts + datasets + config),
  - stable expected outputs (DQ/compliance results, job states, audit events),
  - used as regression checks whenever rules or engines change.

---

## 5. Test Cases by Feature Area

### 5.1 Data Contract Handling

Key test cases:

- Upload valid ODCS contract → `VALID` status.
- Upload invalid contract (missing fields) → `VALIDATION_FAILED`.
- Edit HubContract JSON → status resets to `DRAFT`, validate again.
- Contract-only asset:
  - Asset can be created and activated without data.
  - Later when data is attached, contract reconciliation works.

### 5.2 DQ as a Service

Key test cases:

- Run DQ on `orders_clean.csv`:
  - DQRun `overall_status = PASS`, score > 90.
- Run DQ on `orders_low_quality.csv`:
  - DQRun `overall_status = WARN` or `FAIL`, detailed checks for duplicates/nulls.
- Verify that DQRun is:
  - Linked to Dataset.
  - Exposed on Asset Detail page.
  - Logged in AuditEvents.

### 5.3 Compliance as a Service

Key test cases:

- Internal intake of `orders_clean.csv`:
  - ComplianceRun `overall_status = PASS` or `WARN`, `allowed_to_store = true`.
  - Dataset and Asset are created/updated.
- Internal intake of `orders_pii_blocked.csv`:
  - ComplianceRun `overall_status = FAIL`, `allowed_to_store = false`.
  - No Dataset created; file removed; appropriate UI error.
- External (scan-only) compliance on `orders_pii_blocked.csv`:
  - ComplianceRun stored with `mode = EXTERNAL`.
  - No Asset/Dataset created.
  - Only ComplianceRun + AuditEvents persist.

### 5.4 Audit Trails

Key test cases:

- Ensure AuditEvents created for:
  - Asset creation/update.
  - Contract creation/validation.
  - DQ run creation/completion.
  - Compliance run creation/completion.
  - Marketplace listing publish/unpublish.
  - Order/entitlement creation.

- Verify:
  - AuditEvents are tenant-scoped.
  - No raw PII appears in `details_json`.
  - Filters on `/audit-events` return expected subsets.

### 5.5 Semantic Layer

Key test cases:

- For a given Asset:
  - `/id/asset/{id}` returns JSON-LD with correct DCAT terms and URIs.
  - Editing asset metadata (name, description) updates JSON-LD representation.

- For SPARQL:
  - Queries for `dcat:Dataset` return expected assets.
  - Queries for specific domain tags (e.g., “sales”) return matching assets.
  - No raw sample data or PII is present in the semantic graph.

### 5.6 Marketplace

Key test cases:

- Publish asset to marketplace:
  - Listing created with correct metadata.
  - Listing visible in `/marketplace/listings` for other tenants.

- Access control:
  - Without entitlement:
    - Consumer cannot download or access data.
  - With entitlement:
    - Consumer can see the asset in “My Data” and call read/download APIs.

- Audit:
  - Listing publish/unpublish events logged.
  - Orders and entitlements logged.

---

## 6. Automation & Tooling

### 6.1 CI Pipeline

Typical CI stages:

1. **Lint & Unit Tests**
   - Run backend and frontend linters, unit tests.
2. **Integration Tests**
   - Bring up DB + CLI + DQ + Compliance containers.
   - Run REST/API tests against a local instance.
3. **E2E Smoke Tests**
   - Run a minimal subset of E2E tests (e.g., data-first happy path).
4. **Artifact Build**
   - Build Docker images or deployment artifacts only if tests pass.

Nightly builds:

- Full E2E test suite.
- Basic performance runs with `orders_clean.csv` and `orders_low_quality.csv`.

### 6.2 Local Developer Workflow

- Developers can:
  - Run unit tests freely.
  - Use `docker-compose` to run integration tests locally.
  - Use sample datasets in `sample_datasets/` for manual testing via UI and API.

### 6.3 Recommended Frameworks & Libraries

The exact choice of frameworks depends on the implementation language for each
service, but we recommend the following baselines.

**Backend services (APIs, workers)**

- If implemented in **Python**:
  - **Unit & integration tests:** `pytest`
    - Use `pytest` fixtures for DB/session setup and teardown.
  - **HTTP/API tests:** `httpx` or `requests` for calling local endpoints.
  - **Schema/contract tests:** JSON Schema validators or Pydantic models, where applicable.

- If implemented in **Node.js/TypeScript**:
  - **Unit & integration tests:** `jest` (with `ts-jest` for TypeScript).
  - **HTTP/API tests:** `supertest` (or similar) against the running API service.

**Front-end / UI**

- **Component tests & unit tests:** `jest` + `testing-library` (React Testing Library, etc.).
- **E2E/UI tests:** `Playwright` or `Cypress` running against:
  - a locally started UI + API,
  - or a deployed staging environment (for smoke/regression suites).

**Data Contract / CLI / DQ / Compliance**

- **DataContract CLI wrapper:**
  - tests that call the wrapper API + mocked CLI process,
  - verify error handling and mapping to internal models.
- **Great Expectations (GX):**
  - use GX’s native test utilities where appropriate,
  - assert expectation suite results match normalized `DQRun` records.
- **Soda:**
  - use Soda’s CLI/API to run checks in integration tests,
  - capture and normalize results for comparison in assertions.

**General utilities**

- **Factories/fixtures:**
  - lightweight factory helpers to build valid `HubContract`, `DQRun`,
    `ComplianceRun`, `Asset` objects for unit tests.
- **Contract tests (optional future enhancement):**
  - Provider/consumer tests using tools like Pact to ensure API contracts remain
    compatible as services evolve.

The Testing Strategy document should be kept in sync with actual framework
choices as the implementation stack is finalized.

---

## 7. Summary

This testing strategy ensures that:

- Core flows (onboarding, DQ, compliance, marketplace) are covered by unit, integration, and E2E tests.
- Compliance and privacy requirements are verifiable (no non-compliant data stored, no PII in logs).
- Semantic and marketplace features behave consistently with the domain model and API spec.
- Tests are **repeatable, automated**, and support continuous delivery.

As the platform evolves, we will extend this strategy to:

- Larger-scale performance and reliability testing.
- Regression suites for new contract/spec versions.
- More advanced privacy and security testing.

## 8. Performance & Load Testing

### 8.1 Load testing specifications

This section defines **MVP performance targets** and how load tests will validate them. These are not hard SLOs for all future versions, but concrete goals the MVP must meet under realistic multi-tenant load.

#### 8.1.1 Scope & assumptions

- Environment: dedicated **performance / pre-prod** environment, sized similarly to production.
- Traffic mix:
  - ~70% read operations (catalog, asset/listing views, job status polling).
  - ~20% write operations (asset/dataset updates, job creation).
  - ~10% file uploads / downloads.
- Datasets: representative sample datasets as defined elsewhere in this doc (including at least one “large but realistic” dataset for DQ/compliance runs).
- Tenants: tests assume **5–10 active tenants** sharing the environment.

All tests must be **repeatable**, automated (e.g. Gatling, k6, JMeter, Locust), and produce time-series metrics (latency, RPS, error rates, resource utilization).

---

#### 8.1.2 Concurrent user targets

We model “concurrent users” as **simultaneous active sessions** issuing requests (both UI-driven and API-driven).

**Targets**

- **Baseline concurrency**:
  - **50 concurrent active users** across all tenants.
  - Each user performs a realistic mix of:
    - Asset search/browse.
    - Viewing asset and listing details.
    - Creating and monitoring DQ/compliance jobs.
- **Stress concurrency (stretch)**:
  - **200 concurrent active users**.
  - Used to validate headroom and degradation behavior (latency/error rate, but not necessarily all other targets).

**Acceptance**

Under **baseline concurrency**:

- Overall **error rate** (`5xx` and timeouts) ≤ **0.5%**.
- P95 end-to-end **API response time** for typical CRUD and listing endpoints:
  - ≤ **300 ms**.

---

#### 8.1.3 API throughput targets (requests/second)

We define throughput targets for the **public API layer** (`/api/v1` + `/graphql`).

**Baseline throughput**

- Sustained:
  - **30–50 requests/second (RPS)** overall (across all endpoints).
  - Mix as per §8.1.1 (reads/writes/jobs).
- Bursts:
  - Short spikes up to **100 RPS** for 1–5 minutes, without:
    - P95 latency exceeding **500 ms** on core read endpoints.
    - Error rate exceeding **1%**.

**Endpoint-level expectations (baseline concurrency)**

- Core read endpoints (`GET /assets`, `GET /assets/{id}`, `GET /listings`, `GET /jobs/{id}`):
  - P50 latency ≤ **100 ms**.
  - P95 latency ≤ **300 ms**.
- Core write endpoints (`POST /dq-runs`, `POST /compliance-runs`, `POST /assets`, `POST /datasets`):
  - P50 latency ≤ **200 ms**.
  - P95 latency ≤ **500 ms**.
- No endpoint under test should consistently exceed its P95 target for more than **5%** of the test duration.

---

#### 8.1.4 File upload throughput

File uploads (including chunked uploads) are a critical path for onboarding and scan-only flows.

**Targets**

- Support at least:
  - **20 concurrent file uploads** (across tenants).
  - Each upload up to **5 GB** (chunked) or **1 GB** (single-stream) depending on endpoint.
- Throughput:
  - Sustained **ingress** throughput of at least **50 MB/s** aggregate across all uploads.
  - No single upload should drop below **2 MB/s** sustained throughput under baseline load (network permitting).

**Latency**

- For a **1 GB** file on a normal network link:
  - End-to-end upload time (client → `/files` → object storage) should be **I/O bound** and not significantly inflated by backend processing.
- API behavior:
  - `POST /files` (init) and `POST /files/{id}/complete`:
    - P95 latency ≤ **500 ms** under concurrent upload load.

Load tests will simulate a mix of:

- Small files (10–100 MB).
- Medium (100–500 MB).
- Large (0.5–5 GB, chunked).

---

#### 8.1.5 Job processing throughput (DQ / compliance / semantic)

Job throughput defines how quickly tenants get results for DQ/compliance and semantic mapping.

**Targets (per environment)**

- **DQ + Compliance jobs**:
  - Sustained throughput: **≥ 100 jobs/hour** for “medium” datasets (e.g. tens of millions of rows or a few GB), distributed across tenants.
  - Ability to handle bursts:
    - Up to **50 new jobs** submitted within a 5-minute window without:
      - Job queue latency (time from `PENDING` → `RUNNING`) exceeding **5 minutes** for more than 5% of jobs.
- **Semantic mapping jobs**:
  - At least **50 semantic mapping jobs/hour** for typical assets (tens–hundreds of fields).
  - Mapping jobs must not significantly degrade DQ/compliance throughput (monitored during mixed-load tests).

**Latency**

For a “standard” dataset size (per Testing Strategy samples):

- DQ and compliance jobs:
  - P50 end-to-end duration (from job creation to `SUCCEEDED`):
    - ≤ **15 minutes**.
  - P95:
    - ≤ **30 minutes**.
- Semantic mapping:
  - P50 duration ≤ **2 minutes**.
  - P95 duration ≤ **5 minutes**.

Load tests will:

- Measure **queue latency** (time spent in `PENDING`).
- Measure **processing time** (time in `RUNNING`).
- Verify that worker scaling and concurrency settings (see worker design) can sustain these rates without saturating CPU/IO.

---

#### 8.1.6 Database query performance targets

The primary relational database (OLTP cluster) backs most APIs. Load tests will inspect DB-level metrics to ensure healthy query behavior.

**Targets under baseline load (50 concurrent users, 30–50 RPS)**

- Transactional queries (single-row lookups, small joins):
  - P50 query time ≤ **20 ms**.
  - P95 query time ≤ **100 ms**.
- Medium complexity queries (asset/listing searches, filtered job lists):
  - P50 query time ≤ **50 ms**.
  - P95 query time ≤ **200 ms**.
- No individual query pattern under test should:
  - Regularly exceed **500 ms**.
  - Cause connection pool exhaustion or significant lock contention.

**Throughput**

- Support ≥ **200–300 queries/second** at the DB layer during peak API load (since each API call may issue multiple queries), with:
  - CPU utilization typically ≤ **70%**.
  - I/O wait within acceptable thresholds (no chronic saturation).

**Indexes & plan stability**

- Load tests must validate:
  - Key queries use expected indexes (verified via query plan sampling).
  - No sudden plan regressions under realistic data volumes (by running tests on datasets similar in size to target MVP tenants).

---

#### 8.1.7 Test reporting & pass criteria

For each category above, performance/load test runs must produce:

- Time-series charts for:
  - RPS, latency (P50/P90/P95/P99), error rates.
  - CPU, memory, disk I/O, network, DB connections.
- A summary table for each scenario:
  - Measured vs. target for:
    - concurrent users,
    - API throughput,
    - upload throughput,
    - job throughput,
    - DB query latencies.

**Pass criteria (MVP)**

- All baseline targets in §§8.1.2–8.1.6 are met in at least one stable, repeatable test run.
- Under stress scenarios:
  - System may violate targets, but:
    - It degrades **gracefully**,
    - Does not crash or corrupt data,
    - Recovers automatically once load returns to normal.

These specifications turn “we will do performance tests” into **concrete, measurable performance goals** for the MVP.

content = """### 8.2 Chaos engineering

This section defines the MVP strategy for **chaos testing** (controlled failure injection) to validate:

- Resilience of services and infrastructure.
- Adherence to recovery time targets.
- Preservation of data consistency and integrity under failure.

Chaos experiments are executed only in:

- **Non-production** environments by default (dev / staging / perf).
- Production-like environments with strict change control and opt-in, if/when adopted.

#### 8.2.1 Scope & objectives

Primary objectives:

- Validate that **expected failures** (service outage, DB slowness, queue pressure) lead to:
  - Graceful degradation (clear errors, no crashes).
  - Respect of timeouts and retries.
  - Circuit breakers behaving as designed.
- Confirm that after recovery:
  - Services return to normal operation within the configured RTO.
  - There is **no data corruption** and only acceptable, documented side-effects (e.g., some jobs retried).

Out of scope for MVP:

- Rare infrastructure disasters (entire region failure).
- Deep network partition testing across data centers.

These may be covered in disaster recovery planning.

---

#### 8.2.2 Failure injection scenarios

Chaos scenarios are grouped by dependency type. Each scenario includes:

- Injection method (how we simulate the failure).
- Expected behavior (what “correct” looks like).
- Metrics to monitor.

**(a) Service down / unreachable**

Examples:

- Asset service unavailable (if separate microservice).
- DQ/compliance worker pool temporarily down.
- Semantic service (triple store API) not responding.

Injection methods:

- Kill or stop a service pod / container.
- Blackhole network traffic to a service (e.g., iptables rules or service mesh fault injection).
- Force health checks to fail, so the gateway marks the service as down.

Expected behavior:

- Circuit breakers trip after configured failure thresholds.
- API layer returns appropriate errors (e.g., 503 with clear message) instead of hanging.
- No tight retry loops; backoff and retry budgets apply.
- Critical operations switch to **graceful degradation** where documented (e.g., asset listings load with partial data).

**(b) Database slow / partially unavailable**

Target: primary relational database; optionally triple store.

Injection methods:

- Introduce artificial latency at the DB layer (e.g., proxy with delay).
- Throttle I/O or CPU for DB via container limits or chaos tools.
- Temporarily reduce connection pool limits.

Expected behavior:

- Service-side timeouts fire before requests hang indefinitely.
- Retry logic applies only where **idempotent** and within retry budgets.
- Circuit breakers treat persistent latency/timeouts as failures and open.
- API-level response:
  - Fewer “hung requests”, more explicit 5xx/timeout errors.
  - Latency SLOs will be violated, but **no data corruption**.

**(c) Queue full / message delays**

Target: job queue (e.g., SQS, RabbitMQ, Kafka).

Injection methods:

- Pause consumer workers.
- Artificially throttle queue throughput (e.g., via configuration or injected delay in consumer).
- Simulate “queue full” / throttling responses from the broker.

Expected behavior:

- Job queue latency grows, but:
  - Producers respect throttling / error responses and do not spin uncontrollably.
  - Job creation endpoints enforce rate limits and quotas, returning 429/QUOTA errors where appropriate.
- Worker processes:
  - Do not crash when encountering temporary broker errors.
  - Respect backoff and retry strategies.

**(d) Partial dependency failures**

Combinations, such as:

- DQ service available, compliance service down.
- Triple store down while core asset APIs are healthy.

Expected behavior:

- Mixed results as defined in partial failure handling:
  - Assets may be partially degraded (e.g., semantic_status = DEGRADED, compliance pending).
  - Core catalog and asset read APIs still operate.
- UI / API clearly reflect degraded state, not silent failures.

---

#### 8.2.3 Recovery time targets (RTO under chaos)

For each scenario, we define a **Recovery Time Objective (RTO)** in non-production tests:

- **Service down (single internal service)**:
  - After resolving the cause (service restarted, network restored), the system should:
    - Resume normal traffic within **5 minutes**.
    - Clear error rates to baseline (< 1%) within **10 minutes**.
- **DB slow / throttled**:
  - After removing induced latency:
    - Average DB query latency should return to normal levels within **5 minutes**.
    - P95 application latency back under performance targets within **10 minutes**.
- **Queue paused / backlogged**:
  - After resuming consumers:
    - Backlog should be cleared within **2× the normal processing time** for the queued volume.
    - Job queue latency metrics (`PENDING` → `RUNNING`) should return to baseline within **30 minutes**.

In all cases, the platform must demonstrate **automatic recovery**:

- No manual restarts of unrelated services (beyond fixing the injected fault).
- No manual data fixes for consistency (beyond cleaning up intentionally injected anomalies, if any).

---

#### 8.2.4 Data consistency verification after failures

Chaos tests must verify that failures do **not** result in:

- Partial, invalid writes (e.g., assets without required related rows).
- Corrupted state in jobs, datasets, mappings.
- Divergence between relational DB and triple store that is not captured as DEGRADED state.

Verification strategies:

1. **Invariant checks**

   After chaos experiments, run automated checks on:

   - Relational DB invariants:
     - Every `asset` with `status = ACTIVE` must have:
       - A valid `latest_dataset_id` (if required by design).
       - No dangling references (e.g., datasets pointing to deleted files).
     - Jobs:
       - No job stuck indefinitely in `RUNNING` past a maximum allowed duration.
   - Semantic invariants:
     - For non-DEGRADED assets, a minimal set of triples must exist in the triple store.
   - Security invariants:
     - No jobs or assets created with missing or null `tenant_id` or `owner` fields.

2. **Idempotency & exactly-once semantics where expected**

   For endpoints with idempotency keys:

   - Verify that retry storms triggered during chaos:
     - Do not create duplicate jobs or runs.
     - Return consistent responses for the same idempotency key.

3. **Reconciliation runs**

   In some scenarios (especially queue backlogs and DB slowdowns):

   - Run reconciliation jobs post-experiment:
     - Ensure `audit_events`, `jobs`, and asset states align.
     - Confirm that any transient inconsistencies (e.g., job created but not enqueued) are resolved or marked for manual intervention.

4. **Golden path regression**

   After recovery, execute core **golden path** journeys:

   - Onboard dataset → run DQ/compliance → publish asset.
   - Run semantic mapping → semantic discovery.
   - Place/approve marketplace listing.

   All must complete successfully without manual repairs, confirming the system is consistent enough for normal use.

---

#### 8.2.5 Tooling & automation

Chaos experiments should be:

- Defined as **code** (e.g., using a chaos framework or custom scripts).
- Version-controlled and documented alongside test scenarios.

Tooling may include:

- Service-mesh fault injection (latency, aborts).
- Kubernetes tools (e.g., Pod deletion, CPU/memory stress).
- DB proxies or configuration toggles to introduce latency.
- Queue-level tooling (pausing consumers, throttling producers).

Each chaos scenario should have:

- A **clear description** (what, why).
- Preconditions and rollback steps.
- Metrics and logs to monitor during and after the experiment.

---

#### 8.2.6 Reporting & pass criteria

For each chaos scenario:

- Capture:

  - Timeline of events (start, failure injection, recovery).
  - Key metrics:
    - Application error rates.
    - Latencies (API, DB, queue).
    - Circuit breaker states (open/half-open/closed).
  - Data consistency check results.

**Pass criteria (MVP):**

- No data corruption or unresolvable inconsistencies.
- System recovers **within RTO** for the scenario.
- Golden path scenarios succeed after recovery without manual data repairs.
- Any deviations from expectations are documented along with:
  - Observed behavior,
  - Root cause analysis,
  - Planned fixes or configuration changes.

This chaos engineering approach ensures that resilience features (retries, timeouts, circuit breakers, rate limits) are not just configured, but **proven** under realistic failure conditions before going to production.

## 9. Migration & Backward-Compatibility Testing

### 9.1 HubContract migration testing

SystemRequirements.md §19 defines **HubContract migration** between versions (e.g., `v1 → v2`, `v2 → v3`). This section describes how we test those migrations to ensure:

- No data loss or semantic corruption.
- Backward compatibility for existing assets/datasets.
- Performance characteristics that are acceptable at MVP scale.

#### 9.1.1 Objectives

1. **Functional correctness**
   - Every supported HubContract migration path (e.g. v1→v2, v2→v3, v1→v3 via chained migrations) produces:
     - A valid HubContract in the target version schema.
     - Semantically equivalent constraints wherever possible (types, required fields, DQ/compliance rules).
   - Unsupported or invalid migrations fail **explicitly and safely**, with clear error messages.

2. **Golden behavior**
   - For each version pair, there is a **golden set of contracts** with known expected outputs.
   - Any change to migration logic is tested against these golden fixtures to detect regressions.

3. **Regression safety**
   - A dedicated regression test suite runs:
     - On every change to the contract schema or migration functions.
     - At least once per release in CI.

4. **Performance**
   - Migration functions must be fast enough to handle:
     - Large contracts (many fields, rules, and lineage metadata).
     - Bulk migrations (e.g., all contracts for a tenant) within acceptable time bounds.

---

#### 9.1.2 Test suite for migration functions

The migration logic (e.g., `migrate_v1_to_v2(contract)`) is covered by:

1. **Unit tests (per function)**
   - For each migration function (e.g. `v1→v2`, `v2→v3`), unit tests cover:
     - Required field additions / removals.
     - Type changes (e.g., string → enum).
     - Defaulting behavior (when new fields are introduced).
     - Edge cases (empty optional sections, nested structures, arrays).
   - Tests assert:
     - Output validates against the **target version schema** (JSON Schema or equivalent).
     - No unexpected fields are dropped unless explicitly specified in the migration spec.

2. **Property-based tests (optional, where helpful)**
   - Generate random valid contracts for a given version, migrate them, and assert:
     - Round-trip behaviors for fields that are intended to be preserved.
     - Invariants such as:
       - IDs remain stable (unless explicitly re-keyed).
       - Core identifiers (`asset_id`, `dataset_id`, `contract_id`) remain unchanged.

3. **Cross-version tests**
   - Test the supported migration chains:
     - `v1 → v2 → v3` vs. `v1 → v3` (if direct migration exists).
   - Assert:
     - Equivalent end result for overlapping fields and semantics.
     - No duplicate or conflicting rules introduced by sequential migrations.

4. **Failure-path tests**
   - Verify that:
     - Invalid inputs (malformed contracts, unsupported versions) produce predictable errors.
     - Migration refuses to proceed when critical information is missing (e.g., required v2 fields cannot be derived from v1).

All tests live under a dedicated `hubcontract_migration` test suite (e.g., `tests/hubcontract_migration/`).

---

#### 9.1.3 Golden test cases per HubContract version

We maintain a set of **golden fixtures** for each version pair, stored under source control:

- Directory structure (example):

  ```text
  tests/hubcontract_migration/golden/
    v1_to_v2/
      simple_contract.in.json
      simple_contract.out.json
      complex_schema.in.json
      complex_schema.out.json
      dq_rules_heavy.in.json
      dq_rules_heavy.out.json
    v2_to_v3/
      ...
  ```

Each golden pair (`*.in.json` → `*.out.json`) captures a specific scenario:

- **Simple baseline**
  - Minimal, valid contract (small schema, no optional sections).
- **Complex schema**
  - Many fields, nested structures, arrays, and multiple data types.
- **DQ/Compliance-heavy**
  - Multiple rules, thresholds, and rule groups.
- **Deprecated fields**
  - Contracts that use fields removed or transformed in the newer version.
- **Edge cases**
  - Contracts using all optional sections.
  - Contracts relying on defaulting behavior (missing fields that migration populates).

Tests:

- Load the `*.in.json` contract.
- Run the appropriate migration function.
- Compare the result to `*.out.json` (ignoring expected ordering differences).
- Optionally validate the result against the **target version schema** as part of the test.

Golden test updates:

- Any change to the migration spec that requires updating goldens must:
  - Be clearly documented in a migration CHANGELOG.
  - Have review from both:
    - Contract/domain owner, and
    - Platform/implementation owner.

---

#### 9.1.4 Regression testing strategy

Regression tests ensure that changes to:

- HubContract schema definitions.
- Migration functions.
- Related validation logic.

do not inadvertently break existing flows.

**CI integration**

- The **full HubContract migration test suite** (unit + golden tests) runs on:
  - Every PR that touches:
    - `HubContract` schemas,
    - Migration code,
    - Contract validation logic.
  - Nightly, as part of a broader regression job.

- CI must fail if:
  - Any golden migration test fails.
  - Any migrated contract no longer validates against the target schema.

**Release gates**

- Before cutting a release that includes **new HubContract versions**:
  - Run a dedicated regression job that:
    - Migrates a representative set of real or synthetic contracts for:
      - Internal test tenants.
      - (Where permitted) anonymized samples from early adopters.
    - Verifies all migrations succeed or fail according to the migration spec.

**Backward-compatibility checks**

- For each new contract version, we define:
  - Which older versions can be migrated forward.
  - Whether there is any support for **reading** older versions without migration (if applicable).
- Tests should confirm:
  - Old clients sending old-version contracts receive:
    - Either a clear error instructing them to upgrade/migrate, or
    - A successful migration path via the API (if implemented).

---

#### 9.1.5 Migration performance targets

Migration is typically run:

- On-demand for a single contract (e.g., when a user upgrades a contract).
- In bulk (e.g., when a tenant upgrades many assets after a platform release).

**Per-contract performance**

- Target:
  - **P95** migration time for a single, large contract:
    - ≤ **200 ms** in the application layer (excluding I/O and network latency).
- For typical contracts:
  - P95 ≤ **50 ms**.

Tests:

- Performance tests in CI/perf environment:
  - Run migration on a set of sample contracts of varying size.
  - Measure migration function time only (pure CPU + memory).

**Bulk migration performance**

- For bulk migration jobs (e.g., “migrate all contracts for Tenant X from v2 → v3”):

  - Target:
    - Ability to migrate **1,000 contracts** within **5 minutes** of dedicated processing time.
  - Limits:
    - Bulk jobs should be chunked to avoid long transactions and memory spikes.
    - Progress must be observable (job metrics, logs, per-asset status).

**Resource usage**

- Migration functions should:
  - Avoid loading excessively large in-memory structures beyond the contract itself.
  - Not allocate unbounded data structures (no O(N²) blowups for large schemas).

Performance testing approach:

- Integrate a small migration benchmark suite:
  - Runs regularly in the performance environment.
  - Stores historical results to detect regressions (e.g., > 50% increase in median migration time).

---

With this testing plan, HubContract migrations are:

- Functionally validated via unit and property-based tests.
- Locked down by golden fixtures per version pair.
- Continuously guarded by regression tests in CI/CD.
- Checked for performance regressions both for single-contract and bulk migration scenarios.

### 9.2 Data migration rollback testing

SystemRequirements.md §19 mentions **rollback** for HubContract and related data migrations, but does not specify how rollback is tested. This section defines:

- Rollback test procedures for schema and data migrations.
- Data integrity verification after rollback.
- Rollback performance targets for MVP.

This applies primarily to **relational database** migrations (DDL + DML) and any associated semantic/triple-store adjustments that have explicit rollback paths.

---

#### 9.2.1 Scope & assumptions

- Migrations are managed using a standard migration tool (e.g., Flyway, Liquibase, Django/Alembic migrations).
- Each migration has:
  - An **"up"** script (forward migration).
  - A **"down"** script (rollback), wherever safe and feasible.
- Some **destructive migrations** (e.g., permanent data drops, irreversible transformations) may:
  - Have **no down-script**.
  - Be guarded by strong review and separate backup/restore procedures.
- Rollback testing focuses on:
  - Reversible schema changes (adding/removing columns, indexes, constraints).
  - Data migrations that transform data in-place but can be reversed or reconstructed.

---

#### 9.2.2 Rollback test procedures

Rollback tests are implemented as part of the automated test suite and CI pipeline.

**A. Per-migration “up/down” tests (unit/integration)**

For each migration `N` with both `up` and `down` scripts:

1. **Setup baseline**
   - Start from a known baseline schema (e.g., previous release schema or `N-1`).
   - Seed representative test data:
     - Cover typical and edge-case rows for affected tables.
     - Include foreign-key relationships and optional fields.

2. **Apply `up` migration**
   - Run migration `N` in **forward** direction.
   - Verify:
     - Schema is as expected (columns, indexes, constraints).
     - Test data is transformed as defined in the migration spec.

3. **Apply `down` migration**
   - Run migration `N` in **rollback** direction.
   - Verify:
     - Schema returns to the baseline version (no unexpected tables/columns).
     - Test data is either:
       - Restored to its baseline form, or
       - In a documented, acceptable state for that migration.

4. **Assertions**
   - Run migration-specific assertions (see §9.2.3).
   - Ensure that `up` + `down` is **idempotent** on the test dataset (can be repeated without degradation).

These tests live alongside other migration tests, e.g.:

```text
tests/migrations/
  test_migration_019_up_down.py
  test_migration_020_up_down.py
```

**B. End-to-end rollback scenario tests (release level)**

For each release that includes **multiple migrations**, we add a higher-level scenario:

1. Start from `schema_version = current_release`.
2. Seed a **realistic dataset snapshot** (anonymized/synthetic but reflecting production scale/shape).
3. Apply all new migrations `N+1 … M` (forward).
4. Run smoke tests (basic API and job flows) to ensure forward migration is healthy.
5. Roll back selected migrations:
   - Either step-by-step (M→N+1)
   - Or to a known safe point (e.g., “rollback 2 releases” scenario).
6. Re-run data integrity and smoke tests.

This scenario ensures rollback works not just per migration, but also in **chained** contexts.

**C. Triple-store / semantic migrations**

Where semantic graphs are updated as part of a migration:

- The rollback test must verify that:
  - Named graphs and RDF structures return to a consistent state with respect to the relational schema.
  - `semantic_status` for assets/datasets is updated appropriately (e.g., marked DEGRADED if graphs cannot be fully restored).

#### 9.2.2.1 CI/CD Integration for Rollback Tests

Rollback tests are integrated into the CI/CD pipeline to ensure migrations can be safely rolled back before deployment.

**Pipeline Stages**

**Stage 1: Pre-Merge (Pull Request)**

- **Trigger**: On every pull request that includes migration files
- **Execution**:
  1. Run per-migration "up/down" tests (Section A) for all new migrations in the PR
  2. Run end-to-end rollback scenario tests (Section B) if PR includes multiple migrations
  3. Run data integrity verification (Section 9.2.3) after each rollback
- **Failure Handling**:
  - If any rollback test fails, block PR merge
  - Require developer to fix migration or add `[skip-rollback-test]` tag (requires approval)
- **Duration**: ~5-10 minutes per migration

**Stage 2: Pre-Release (Main Branch)**

- **Trigger**: On merge to main branch (before release)
- **Execution**:
  1. Run all rollback tests for all migrations in the release
  2. Run end-to-end rollback scenario for the entire release
  3. Generate rollback test report (JSON/HTML)
- **Failure Handling**:
  - If rollback tests fail, block release creation
  - Alert release manager and development team
- **Duration**: ~15-30 minutes (depends on number of migrations)

**Stage 3: Pre-Deployment (Staging)**

- **Trigger**: Before deploying to staging environment
- **Execution**:
  1. Apply all migrations to staging database
  2. Run smoke tests to verify forward migration
  3. **Dry-run rollback** (test rollback without actually rolling back):
     - Verify rollback scripts are valid
     - Check for blocking dependencies
  4. If dry-run succeeds, proceed with deployment
- **Failure Handling**:
  - If dry-run rollback fails, block deployment
  - Require manual intervention or rollback script fixes
- **Duration**: ~10-15 minutes

**Stage 4: Post-Deployment (Production)**

- **Trigger**: After successful production deployment
- **Execution**:
  1. Monitor migration status and application health
  2. **No automatic rollback tests in production** (too risky)
  3. If issues detected, manual rollback procedure (see `Runbooks_and_Operational_Procedures.md` RB-DB-002)
- **Note**: Rollback tests are NOT run in production; they are validated in staging

**CI/CD Configuration Example**

**GitHub Actions**:
```yaml
name: Migration Rollback Tests

on:
  pull_request:
    paths:
      - 'migrations/**'
  push:
    branches: [main]

jobs:
  rollback-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-postgresql
      
      - name: Run per-migration rollback tests
        run: |
          pytest tests/migrations/ -v --tb=short
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/testdb
      
      - name: Run end-to-end rollback scenario
        run: |
          pytest tests/migrations/test_e2e_rollback.py -v
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/testdb
      
      - name: Generate rollback test report
        run: |
          pytest tests/migrations/ --json-report --json-report-file=rollback-report.json
      
      - name: Upload rollback test report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: rollback-test-report
          path: rollback-report.json
```

**Jenkins Pipeline**:
```groovy
pipeline {
    agent any
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Rollback Tests') {
            steps {
                sh '''
                    docker-compose -f docker-compose.test.yml up -d postgres
                    sleep 10
                    pytest tests/migrations/ -v
                    docker-compose -f docker-compose.test.yml down
                '''
            }
        }
        
        stage('E2E Rollback Scenario') {
            steps {
                sh '''
                    docker-compose -f docker-compose.test.yml up -d postgres
                    pytest tests/migrations/test_e2e_rollback.py -v
                    docker-compose -f docker-compose.test.yml down
                '''
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'rollback-report.json', fingerprint: true
        }
        failure {
            emailext subject: "Migration Rollback Tests Failed",
                     body: "Rollback tests failed for ${env.BUILD_URL}",
                     to: "${env.DEV_TEAM_EMAIL}"
        }
    }
}
```

**Test Execution Strategy**

- **Parallel Execution**: Per-migration tests can run in parallel (one test per migration)
- **Sequential Execution**: End-to-end rollback scenario tests run sequentially (they depend on previous migrations)
- **Test Isolation**: Each test uses a fresh database instance or transaction rollback
- **Test Data**: Use synthetic/anonymized data that mirrors production structure

**Failure Reporting**

- **Console Output**: Detailed error messages with migration name and failure reason
- **JSON Report**: Machine-readable report with:
  - Migration name and version
  - Test status (PASS/FAIL)
  - Failure reason
  - Rollback duration
  - Data integrity check results
- **Notifications**: 
  - PR comments (for pre-merge failures)
  - Slack/email alerts (for pre-release failures)
  - Dashboard updates (for test metrics)

**Metrics and Monitoring**

- Track rollback test execution time (P50, P95, P99)
- Track rollback test pass rate (should be 100%)
- Alert if rollback test duration exceeds threshold (e.g., > 30 minutes)
- Alert if rollback test pass rate drops below threshold (e.g., < 95%)

---

#### 9.2.3 Data integrity verification after rollback

After rollback, we must confirm **data integrity** and consistency:

**Schema integrity checks**

- Confirm DB schema version:
  - `schema_version` table/metadata must show the baseline version.
- Validate schema structure:
  - All tables, columns, indexes that existed before migration are present.
  - No unexpected tables/columns remain from the rolled-back migration.
- Run schema validation scripts:
  - E.g., compare actual schema to a checked-in schema definition (DDL snapshot).

**Data integrity checks**

The test suite runs automated checks, including:

1. **Row counts & basic aggregates**
   - For affected tables:
     - Compare row counts pre-migration vs post-rollback.
     - Compare basic aggregates (e.g., sum of numeric fields, min/max timestamps) where meaningful.

2. **Referential integrity**
   - Ensure all foreign-key constraints remain valid.
   - For critical relationships:
     - Explicitly query for orphaned rows.
       - E.g., `datasets` without matching `assets`, `jobs` without matching `tenants`.

3. **Checksums / hash-based comparisons**
   - For rollback-safe migrations, keep **pre-migration snapshots** of:
     - Selected rows (identified by primary key).
     - With row-level hashes (e.g., hash of JSON representation).
   - After rollback:
     - Recompute hashes and compare to pre-migration.
     - Any mismatch must be explained and documented.

4. **Business invariants**
   - Run application-level invariants, such as:
     - “Every ACTIVE asset has an existing latest dataset.”
     - “No job is stuck in RUNNING past max allowed duration.”
   - These are the same invariants used in regular health checks (§Testing Strategy).

**Rollback-unsafe migrations**

- For migrations where data cannot be perfectly restored:
  - The migration spec must document:
    - Expected state after rollback.
    - Which fields may be lossy or reset.
  - Tests validate that:
    - The resulting state is **safe** (consistent, no corrupt relationships).
    - Any loss is limited to optional/non-critical data.

---

#### 9.2.4 Rollback performance targets

Rollback operations must be:

- Fast enough to be usable in **emergency scenarios**.
- Predictable under typical data volumes for MVP tenants.

**Per-migration rollback performance**

- For single migration `N` rollback on a production-like dataset:

  - Target:
    - **P95 rollback time ≤ 5 minutes** for a migration affecting:
      - Up to tens of millions of rows across a few tables.
    - **P50 rollback time ≤ 2 minutes** for typical migrations.

- Performance tests:
  - Run rollback on representative datasets in a perf environment.
  - Capture:
    - Total rollback time.
    - Locks held and impact on concurrent traffic.

**Bulk rollback performance (multi-migration)**

In rare cases, we may need to roll back multiple migrations (e.g., revert a release):

- Target:
  - Rolling back a **release worth of migrations** (e.g., 5–10 migrations) should complete within:
    - **≤ 30 minutes** for MVP-scale data.
  - Application may be in **maintenance mode** during this time, but:
    - No data corruption.
    - No long-running inconsistent state.

**Operational considerations**

- Rollbacks should be:
  - Scripted and automated (no manual SQL editing).
  - Logged in detail (start/end times, affected tables, row counts).
- Before using rollback in production:
  - A rehearsal must be run in a staging/perf environment using:
    - A recent snapshot of production-like data.
    - The exact same tooling and config.

---

With these procedures and targets in place, data migrations and their rollbacks are:

- Routinely tested and validated in CI.
- Verified for data integrity with both schema-level and business-level checks.
- Bound by performance expectations that make rollbacks feasible as part of an emergency response plan.

## 10. Load testing targets not quantified

**Issue**

`Testing_Strategy.md` §2.4 mentions performance tests but does not define concrete non-functional targets:

- No quantified concurrent users.
- No target API throughput.
- No file upload throughput.
- No job processing throughput.

This makes it hard to know whether performance tests have “passed” for MVP.

**Decision**

For MVP, define **baseline load targets** (not customer SLAs) that performance tests MUST exercise:

- **Concurrent users**: 100 active users performing typical UI/API flows.
- **API throughput**: 1,000 requests/second sustained for read-heavy endpoints, with no critical errors and acceptable latency.
- **File upload throughput**: 100 MB/s aggregate across all uploads (e.g., multiple concurrent 50–200 MB files).
- **Job processing throughput**: 50 jobs/minute across DQ and compliance jobs combined, on medium datasets.

These numbers are **test targets**, not contractual SLAs, but provide clear success criteria for the MVP load tests.

**Action**

Update `Testing_Strategy.md` §2.4 `Non-Functional Tests` to include these targets.

---

### Patch for `Testing_Strategy.md` §2.4

Replace the existing **2.4 Non-Functional Tests** block with this expanded version:

```md
2.4 Non-Functional Tests

- **Performance & Load (MVP targets)**
  - Run DQ & compliance on medium-sized files (e.g., 50–200 MB).
  - Measure:
    - Time to complete intake pipeline.
    - Memory usage & CPU of services.
  - Ensure operations finish within acceptable bounds for MVP (e.g., a few minutes).

  - **Load test targets (baseline, not SLA)**
    - **Concurrent users**: target at least **100** concurrent active users exercising:
      - Asset catalog browsing.
      - Contract upload & validation.
      - Triggering DQ/compliance runs.
      - Viewing run results.
    - **API throughput**: target sustained **1,000 requests/second** across key read-heavy REST endpoints (`GET /assets`, `GET /assets/{id}`, `GET /jobs/{id}`, etc.), with:
      - No more than a low single-digit error rate from transient failures.
      - p95 latency within acceptable bounds for MVP (e.g., < 1s for these endpoints).
    - **File upload throughput**: target at least **100 MB/s aggregate** upload throughput:
      - Multiple concurrent chunked uploads of 50–200 MB files.
      - Validate that chunked upload session handling remains correct under load (no increased 4xx/5xx beyond expected).
    - **Job processing throughput**: target at least **50 jobs/minute** processed across DQ and compliance jobs:
      - Mix of small and medium datasets.
      - Ensure queueing behavior, retries, and status transitions (`PENDING` → `RUNNING` → `SUCCEEDED`/`FAILED`) remain correct at this rate.

- **Security (basic)**
  - Automated tests that:
    - Try cross-tenant resource access (should get 404/403).
    - Ensure that sample PII values do not appear in logs (spot checks with log scraping in CI).
    - Fuzz input for contract upload, SPARQL endpoint with read-only restrictions.