# Deployment Architecture (MVP)

This document describes how the Interoperable Data Hub MVP is deployed across
environments, with a focus on:

- Local development using **Docker Compose**.
- Service-to-service **communication patterns**.
- **Environment configuration** (dev / staging / prod).
- **Secrets management** and configuration hygiene.

It complements `System_Architecture.md`, `Technical_Design_Document.md`,
`SystemRequrements.md`, and `Technology_Stack_Decisions.md`.

---

## 1. Overview

At a high level, deployments follow this model:

- **Web UI** + **API Gateway / API Service** at the edge.
- A set of **domain services** (Auth/Tenant, Asset/Catalog, Contract,
  Ingestion, DQ, Compliance, Marketplace, Semantic, Jobs, Audit, Billing/Metrics).
- Shared **infrastructure services**:
  - Relational DB (PostgreSQL-compatible).
  - Object storage (S3-compatible).
  - Message queue for Jobs.
  - Triple store / graph DB for the semantic layer.
  - Central logging/monitoring stack.

Local development uses **Docker Compose** to approximate the production topology
with a single-node deployment. Staging/production use managed equivalents of
these components (e.g. managed DB, object storage, queue) with similar wiring.

---

## 2. Local Development Topology (Docker Compose)

### 2.1 Core Services (containers)

A typical dev `docker-compose.yml` includes the following containers:

- `api-service` – API gateway / edge service exposing `/api/v1` and proxying to
  back-end services.
- `web-ui` – Front-end web app (optional; can also run via `npm start` locally).
- `auth-service` – Auth & Tenant management.
- `asset-service` – Asset & Catalog.
- `contract-service` – Contracts & HubContract + DataContract CLI integration.
- `ingestion-service` – File ingest, schema inference, orchestration.
- `dq-service` – Data Quality engine wrapper (GX/Soda).
- `compliance-service` – Compliance / PII detection engine.
- `datacontract-service` – DataContract CLI wrapper.
- `semantic-service` – Semantic layer API (wraps triple store).
- `marketplace-service` – Listings, orders, entitlements.
- `worker-service` – Job worker(s) that process jobs from the queue.
- `audit-service` – Audit log query API (append-only writes to DB).
- `metrics-service` – Billing/Metrics (MVP: usage metrics).

Infrastructure containers:

- `postgres` – Relational DB (metadata).
- `minio` – S3-compatible object storage for files.
- `triplestore` – Semantic triple store (e.g. Blazegraph/Fuseki/Neptune local equivalent).
- `job-queue` – Message queue (Redis-backed queue using `django-rq` or `celery` with Redis broker).
- `otel-collector` / `jaeger` / `prometheus` (optional) – Observability stack.

All containers share a common Docker network (e.g. `hub-net`) so they can
address each other by **service name**.

### 2.2 Example `docker-compose.yml` (abridged)

> **Note:** This is illustrative; names and images should be adjusted to match
> the actual repo structure.

```yaml
version: "3.9"

services:
  api-service:
    image: hub-api:local
    build: ./services/api
    ports:
      - "8080:8080"
    env_file:
      - .env.dev
    depends_on:
      - auth-service
      - asset-service
      - contract-service
      - ingestion-service
      - dq-service
      - compliance-service
      - marketplace-service
      - redis
      - postgres
    networks:
      - hub-net

  asset-service:
    image: hub-asset:local
    build: ./services/asset
    env_file:
      - .env.dev
    depends_on:
      - postgres
    networks:
      - hub-net

  # ... other domain services omitted for brevity ...

  worker-service:
    image: hub-worker:local
    build: ./services/worker
    env_file:
      - .env.dev
    depends_on:
      - redis
      - postgres
    networks:
      - hub-net

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: hub
      POSTGRES_PASSWORD: hub
      POSTGRES_DB: hub
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - hub-net

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - hub-net

  minio:
    image: minio/minio:latest
    command: server /data
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio123
    ports:
      - "9000:9000"
      - "9001:9001"  # MinIO console
    volumes:
      - minio-data:/data
    networks:
      - hub-net

  triplestore:
    image: apache/jena-fuseki:latest
    ports:
      - "3030:3030"
    volumes:
      - fuseki-data:/fuseki
    networks:
      - hub-net

networks:
  hub-net:

volumes:
  pgdata:
  redis-data:
  minio-data:
  fuseki-data:
```

---

## 3. Service Communication Patterns

### 3.1 Intra-Cluster Networking

- All services communicate over the Docker network (`hub-net`):
  - `http://asset-service:8080/...`
  - `http://contract-service:8080/...`
  - `http://dq-service:8080/...`, etc.
- The **API Service** is the only container exposed publicly in dev (mapped to
  host port 8080). Web UI can either:
  - run as a separate container hitting `api-service`, or
  - run on the host and call `http://localhost:8080/api/v1/...`.

### 3.2 Synchronous Calls

- `web-ui` → `api-service` → domain services via REST:
  - Asset CRUD, contract CRUD, DQ/compliance report reads, marketplace flows.
- `api-service` → `auth-service` for authn/authz (or uses library/middleware).
- Domain services → `datacontract-service` for **small, fast** CLI-based contract validation.
- Domain services → `semantic-service` for semantic lookups (e.g. URI → JSON-LD).

Synchronous calls are kept **short-lived** and **idempotent** where possible.

### 3.3 Asynchronous Jobs & Queue

- `api-service` and domain services (Ingestion, DQ, Compliance, Contract, Semantic):
  - create a `job` row in the database,
  - publish a message to Redis queue with `job_id` and `job_type`.
- `worker-service` instances:
  - consume from Redis queue,
  - look up job details in DB,
  - call `dq-service`, `compliance-service`, `datacontract-service`,
    `semantic-service` and update job status.

**Implementation**: Redis-backed queue using `django-rq` or `celery` with Redis broker. See `Technology_Stack_Decisions.md` for version and configuration details.

Queue and DLQ behavior are described in `System_Architecture.md` §5.3.

### 3.4 External Integrations

- **Object Storage**:
  - Domain services issue **pre-signed URLs** (via `minio`/S3) for browser/SDK uploads.
  - Ingestion and DQ/Compliance services read files from object storage.
- **Triple Store**:
  - `semantic-service` communicates with `triplestore` via HTTP/SPARQL.
- **Identity Provider (IdP)** (if used in MVP):
  - `api-service` integrates with external IdP (OIDC/OAuth2) for login; details
    vary per environment.

---

## 4. Environment Configuration

### 4.1 Configuration Sources

Each service reads configuration from:

- **Environment variables** (primary mechanism).
- Optional: configuration files (e.g. `config.yaml`) mounted as volumes for
  non-secret settings.

For local dev, a `.env.dev` file is used and referenced via `env_file` in
`docker-compose.yml`.

For staging/prod, environment variables are injected by the orchestration
platform (e.g. Kubernetes, ECS) and secrets are sourced from a secrets manager
(see §5).

### 4.2 Common Environment Variables

Common variables (used across services):

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `S3_ENDPOINT`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`
- `JOB_QUEUE_URL` or `JOB_QUEUE_HOST` / `JOB_QUEUE_PORT`
- `TRIPLESTORE_ENDPOINT`
- `AUTH_PUBLIC_KEY` / `JWKS_URL` (for JWT verification)
- `LOG_LEVEL`, `OTEL_EXPORTER_OTLP_ENDPOINT` (if using OTEL)
- `ENVIRONMENT` (`local`, `dev`, `staging`, `prod`)

#### 4.2.0 Environment Variable Naming Convention

All environment variables MUST follow a standardized naming convention to ensure consistency and discoverability.

**Naming Pattern**

Format: `[SERVICE_][CATEGORY_]SETTING[_UNIT]`

- **`SERVICE_`** (optional): Service-specific prefix (e.g., `API_`, `WORKER_`, `DQ_`)
  - Omit for common/shared variables
  - Use service name in UPPER_SNAKE_CASE
- **`CATEGORY_`** (optional): Logical grouping (e.g., `DB_`, `S3_`, `AUTH_`, `LOG_`)
- **`SETTING`**: Descriptive setting name in UPPER_SNAKE_CASE
- **`_UNIT`** (optional): Unit suffix for numeric values (e.g., `_MS`, `_SECONDS`, `_BYTES`, `_COUNT`)

**Examples**

| Category | Pattern | Examples |
|----------|---------|----------|
| **Common/Shared** | `CATEGORY_SETTING[_UNIT]` | `DB_HOST`, `S3_BUCKET`, `LOG_LEVEL` |
| **Service-Specific** | `SERVICE_CATEGORY_SETTING[_UNIT]` | `API_RATE_LIMIT_REQUESTS_PER_MINUTE`, `WORKER_MAX_CONCURRENT_JOBS` |
| **Time Values** | `..._MS` or `..._SECONDS` | `DB_POOL_CONNECTION_TIMEOUT_MS`, `JWT_EXPIRES_IN_SECONDS` |
| **Size Values** | `..._BYTES` or `..._MB` | `MAX_FILE_SIZE_BYTES`, `CHUNK_SIZE_BYTES` |
| **Count Values** | `..._COUNT` or no suffix | `DB_POOL_MAX`, `MAX_RETRY_COUNT` |
| **Boolean** | `..._ENABLED` or `ENABLE_...` | `AUTO_REFRESH_ENABLED`, `ENABLE_DEBUG_LOGGING` |
| **URLs/Endpoints** | `..._URL` or `..._ENDPOINT` | `S3_ENDPOINT`, `TRIPLESTORE_URL` |
| **Keys/Secrets** | `..._KEY` or `..._SECRET` | `S3_ACCESS_KEY_ID`, `JWT_SIGNING_KEY` |

**Rules**

1. **Uppercase Only**: All environment variable names MUST be UPPERCASE
2. **Snake Case**: Use underscores to separate words (e.g., `MAX_FILE_SIZE_BYTES`, not `MAXFILESIZEBYTES`)
3. **Units Required for Numeric Values**: 
   - Time: Use `_MS` (milliseconds) or `_SECONDS` (seconds)
   - Size: Use `_BYTES`, `_KB`, `_MB`, `_GB`
   - Count: Use `_COUNT` or no suffix (if obvious from context)
4. **Service Prefix for Service-Specific Settings**: 
   - If a setting applies to only one service, prefix with service name
   - Example: `API_RATE_LIMIT_REQUESTS_PER_MINUTE` (not `RATE_LIMIT_REQUESTS_PER_MINUTE`)
5. **Category Prefix for Shared Settings**:
   - If a setting applies to multiple services, use category prefix
   - Example: `DB_POOL_MAX` (shared by all services that connect to DB)
6. **Consistency**: 
   - Use consistent naming for similar settings across services
   - Example: All pool settings use `DB_POOL_*` prefix

**Common Patterns Reference**

| Setting Type | Pattern | Example |
|--------------|---------|---------|
| Database connection | `DB_[HOST\|PORT\|USER\|PASSWORD\|NAME]` | `DB_HOST`, `DB_PORT` |
| Database pool | `DB_POOL_[MIN\|MAX\|TIMEOUT_MS\|IDLE_TIMEOUT_MS]` | `DB_POOL_MAX`, `DB_POOL_CONNECTION_TIMEOUT_MS` |
| Object storage | `S3_[ENDPOINT\|ACCESS_KEY_ID\|SECRET_ACCESS_KEY\|BUCKET]` | `S3_ENDPOINT`, `S3_BUCKET` |
| Authentication | `AUTH_[PUBLIC_KEY\|JWKS_URL\|TOKEN_TTL_SECONDS]` | `AUTH_PUBLIC_KEY`, `JWT_EXPIRES_IN_SECONDS` |
| Logging | `LOG_[LEVEL\|FORMAT\|OUTPUT]` | `LOG_LEVEL`, `LOG_FORMAT` |
| Rate limiting | `[SERVICE_]RATE_LIMIT_[REQUESTS_PER_MINUTE\|BURST]` | `API_RATE_LIMIT_REQUESTS_PER_MINUTE` |
| Timeouts | `[SERVICE_]TIMEOUT_[MS\|SECONDS]` | `API_REQUEST_TIMEOUT_MS` |
| File size limits | `MAX_[BROWSER\|SDK]_UPLOAD_SIZE_BYTES` | `MAX_BROWSER_UPLOAD_SIZE_BYTES` |
| Job configuration | `WORKER_MAX_CONCURRENT_JOBS`, `JOB_TIMEOUT_SECONDS` | `WORKER_MAX_CONCURRENT_JOBS` |

**Migration Notes**

- Existing environment variables that do not follow this convention SHOULD be migrated gradually
- New environment variables MUST follow this convention
- Documentation MUST be updated when variables are renamed

#### 4.2.1 Database Connection Pool Configuration

All services that connect to the primary relational database MUST use connection pooling with the following configuration:

**Default Connection Pool Settings (All Services)**

| Setting | Environment Variable | Default Value | Description |
|---------|---------------------|---------------|-------------|
| Minimum pool size | `DB_POOL_MIN` | `2` | Minimum number of connections to maintain |
| Maximum pool size | `DB_POOL_MAX` | `10` | Maximum number of connections per service instance |
| Connection timeout | `DB_POOL_CONNECTION_TIMEOUT_MS` | `5000` (5 seconds) | Time to wait when acquiring a connection from pool |
| Idle timeout | `DB_POOL_IDLE_TIMEOUT_MS` | `600000` (10 minutes) | Time before idle connections are closed |
| Max lifetime | `DB_POOL_MAX_LIFETIME_MS` | `3600000` (1 hour) | Maximum lifetime of a connection before it's recycled |
| Validation query | `DB_POOL_VALIDATION_QUERY` | `SELECT 1` | Query to validate connections before use |

**Per-Service Overrides**

Some services require different pool sizes based on their workload:

| Service | `DB_POOL_MIN` | `DB_POOL_MAX` | Rationale |
|---------|---------------|---------------|-----------|
| `api-service` | `5` | `20` | High concurrency, many short-lived queries |
| `worker-service` | `3` | `15` | Long-running jobs, but fewer concurrent jobs per instance |
| `auth-service` | `2` | `10` | Standard workload |
| `asset-service` | `2` | `10` | Standard workload |
| `contract-service` | `2` | `10` | Standard workload |
| `ingestion-service` | `3` | `12` | Moderate workload during file processing |
| `marketplace-service` | `2` | `10` | Standard workload |
| `audit-service` | `2` | `8` | Write-heavy but predictable workload |

**Connection Pool Implementation**

- Services MUST use a connection pool library (e.g., HikariCP for Java, `pg.Pool` for Node.js, SQLAlchemy pool for Python).
- Pool configuration MUST be validated at service startup:
  - If `DB_POOL_MAX` exceeds database `max_connections`, log a warning.
  - If pool cannot acquire a connection within `DB_POOL_CONNECTION_TIMEOUT_MS`, return `503 Service Unavailable`.
- Connection health checks:
  - Before using a connection from the pool, validate it with `DB_POOL_VALIDATION_QUERY`.
  - If validation fails, discard the connection and acquire a new one.
- Monitoring:
  - Services MUST expose metrics:
    - `db_pool_active_connections` (gauge)
    - `db_pool_idle_connections` (gauge)
    - `db_pool_wait_time_ms` (histogram)
    - `db_pool_connection_errors_total` (counter)

**Database-Level Connection Limits**

The database server MUST be configured with:
- `max_connections` ≥ (sum of all `DB_POOL_MAX` across all service instances) + buffer (e.g., 20% overhead for admin connections, migrations, monitoring).
- Example: If 10 service instances each use `DB_POOL_MAX=10`, database should have `max_connections ≥ 120`.

**Example Configuration**

```env
# Database connection
DB_HOST=postgres
DB_PORT=5432
DB_USER=hub
DB_PASSWORD=hub
DB_NAME=hub

# Connection pool (api-service example)
DB_POOL_MIN=5
DB_POOL_MAX=20
DB_POOL_CONNECTION_TIMEOUT_MS=5000
DB_POOL_IDLE_TIMEOUT_MS=600000
DB_POOL_MAX_LIFETIME_MS=3600000
```

Example `.env.dev` snippet:

```env
ENVIRONMENT=local

DB_HOST=postgres
DB_PORT=5432
DB_USER=hub
DB_PASSWORD=hub
DB_NAME=hub

S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY_ID=minio
S3_SECRET_ACCESS_KEY=minio123
S3_BUCKET=hub-samples

REDIS_HOST=redis
REDIS_PORT=6379

TRIPLESTORE_ENDPOINT=http://triplestore:7200

LOG_LEVEL=debug
```

### 4.3 Per-Service Configuration

Each service has additional specific configuration, for example:

- `dq-service`:
  - `DQ_ENGINE_DEFAULT` (`GREAT_EXPECTATIONS` or `SODA`).
  - Paths to expectations/configs (mounted via volume or S3 prefix).
- `compliance-service`:
  - Enabled detectors (regex/dictionary/ML), thresholds.
  - Max file size, sampling strategy.
- `datacontract-service`:
  - `DATACONTRACT_CLI_PATH`
  - `DATACONTRACT_CLI_VERSION`
  - Timeouts and concurrency limits.
- `semantic-service`:
  - Default ontology/context URIs.
  - SPARQL endpoint for triple store.

These are defined in the TDD and System Requirements and should be reflected in
per-service `.env` templates (e.g. `.env.dq.example`).

### 4.4 Environment-Specific Overrides

- **Local** (`ENVIRONMENT=local`):
  - All infra runs via Docker Compose (Postgres, Minio, queue, triplestore).
  - Debug logging enabled.
- **Dev/Staging**:
  - Use managed DB, object storage, queue, and logging.
  - More realistic data volumes and sample datasets.
  - Feature flags and experimental detectors can be enabled.
- **Production**:
  - Strictly controlled secret injection
  - Reduced log verbosity (no PII).
  - Higher resource limits and autoscaling thresholds.

Configuration differences per environment MUST be documented and kept in sync
with infra-as-code definitions.

---

## 5. Secrets Management

### 5.1 Principles

- **No secrets in source control.**
- Use environment variables + secrets manager for production.
- Secrets should be **rotatable** without redeploying code (e.g. updated via
  secret store + rolling restart).
- Logging MUST NEVER include secret values.

### 5.2 Local Development

- Local secrets MAY be stored in `.env.dev` / `.env.local` files, which:
  - are excluded from version control (`.gitignore`),
  - contain only non-production credentials (local Postgres, Minio, etc.).
- For slightly stronger isolation, Docker Compose can use **Docker secrets**
  or local secret stores, but this is optional for MVP.

### 5.3 Staging & Production

- All secrets (DB passwords, S3 keys, JWT signing keys, third-party API keys)
  MUST be stored in a **managed secrets service** (e.g. AWS Secrets Manager,
  GCP Secret Manager, HashiCorp Vault, etc.).
- Application containers receive secrets at runtime via:
  - environment variables injected from the secrets store, or
  - mounted secret volumes (Kubernetes `Secret` objects, etc.).
- Secrets are **never baked into Docker images**.

Recommended secret categories:

- Database: `DB_USER`, `DB_PASSWORD`, `DB_URL`.
- Object storage: `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`.
- Queue credentials: user/pass or access keys if required.
- IdP / auth: signing keys or JWKS endpoint credentials if needed.
- Compliance/DQ: credentials for any external classification services (if used).

### 5.4 Rotation & Audit

- Secret rotation MUST be possible without code changes.
- Rotation events SHOULD be:
  - Logged as security events (e.g. in `audit_events` or infra logs).
  - Performed first in non-prod, then in production.
- Access to secrets and rotation operations MUST be restricted to a small set of
  operators and tracked via IAM/audit logs.

---

## 6. Summary

- Docker Compose provides a realistic **single-node** deployment for local
  development, mirroring production components.
- Services communicate over a shared Docker network; `api-service` is the single
  public entry point in dev.
- Asynchronous work is handled via a **job queue + worker** model, with details
  in `System_Architecture.md` and the TDD.
- Environment configuration is driven by environment variables with per-service
  `.env` templates and environment-specific overrides.
- Secrets are handled via `.env` files locally and a **managed secrets service**
  in staging/production, with no secrets committed to source control.

## 7. Semantic layer

### 7.1 Triple store technology choice

The semantic layer uses an RDF triple store to power:

- SPARQL queries over the semantic model and semantic mappings.
- JSON-LD `/id/...` dereferencing.
- Semantic search / discovery enrichment for assets and datasets.

This section defines:

- The **MVP triple store selection**.
- SPARQL endpoint security model.
- Backup and restore strategy.
- Performance targets and basic capacity guidelines.

- **Semantic store (MVP)**: Apache Jena Fuseki
     - Deployed as a containerized service in the same VPC/cluster as core services.
     - Uses a persistent TDB2-backed dataset for RDF storage.
     - Exposes an internal SPARQL endpoint consumed by the `semantic-mapper` service.
     - No direct public access; external clients go through the hub API.

#### 7.1.1 Technology selection

For MVP, the platform standardizes on:

- **Apache Jena Fuseki** running on top of **TDB2** as the embedded storage engine.
- **Docker image**: `apache/jena-fuseki:latest` (see `Technology_Stack_Decisions.md`)

Rationale:

- Open source, widely used in the RDF/SPARQL ecosystem.
- Easy to containerize and run in-cluster (Kubernetes / Docker).
- Good support for:
  - SPARQL 1.1 query and update.
  - Named graphs (for per-tenant / per-environment segregation).
  - Reasonable performance for medium-sized graphs (10–100M triples) on commodity hardware.

**Future option (non-MVP):**

- **Amazon Neptune** as a managed alternative for AWS-only deployments:
  - Offers managed backups, scaling, and higher availability.
  - Would be integrated behind the same semantic service interface so that:
    - API surface (`/sparql`, `/id/...`) remains unchanged.
    - Only the semantic service’s storage adapter changes.

For the purposes of this document, “triple store” refers to **Fuseki/TDB2** in the default deployment, with an abstraction layer that allows swapping in Neptune or other compatible stores later.

#### 7.1.2 Deployment & topology

MVP topology:

- A dedicated **Semantic Service** that:
  - Embeds or connects to a **single Fuseki instance** per environment.
  - Provides:
    - `/sparql` endpoint.
    - `/id/{resource}` JSON-LD dereferencing endpoint.
- Storage:
  - Persistent volume per environment (e.g., Kubernetes PVC):
    - `semantic-data-dev`
    - `semantic-data-stg`
    - `semantic-data-prod`
  - Backed by SSD-class storage for low-latency random reads.

Multi-tenancy:

- Multi-tenant data is stored in a **single dataset** with **named graphs** or graph partitioning:
  - One named graph per tenant:
    - `urn:tenant:{tenant_id}`
  - Shared reference vocabularies (e.g., common ontologies) in:
    - `urn:system:ontology`
- The Semantic Service enforces tenant scoping at query time by:
  - Rewriting or constraining SPARQL queries to only touch the caller’s graphs, unless the caller has platform-admin rights.

High availability (MVP):

- Initially: **single primary instance** with:
  - Vertical scaling.
  - Regular backups and fast restore procedures.
- Future: add **read replicas** (Fuseki cluster or Neptune read replicas) if query load grows.

#### 7.1.3 SPARQL endpoint security

Endpoints:

- `POST /sparql` (and optionally `GET /sparql` for simple queries).
- Internal URL (e.g. `https://semantic.internal/...`), fronted by API gateway or service mesh.

Security model:

1. **Internal-only by default**

   - `/sparql` is **not** exposed to the public internet in MVP.
   - Only trusted services (API gateway, internal batch tools) can call `/sparql`.
   - External consumers use:
     - High-level REST/GraphQL endpoints, or
     - JSON-LD `/id/...` dereferencing for public resources.

2. **Optional read-only public SPARQL (future)**

   - If exposed publicly, `/sparql` would:
     - Be **read-only** (SPARQL `SELECT`/`CONSTRUCT`, no `UPDATE`).
     - Only access a **public** named graph (or a union of explicitly public graphs).
     - Be heavily rate-limited and monitored.
   - Authentication options:
     - Public, anonymous read (for strictly non-sensitive public data).
     - API-key or OAuth-based for partner access.

3. **Authentication and authorization**

   - For internal callers:
     - All requests go through the gateway with JWT-based auth (see JWT section).
     - The Semantic Service extracts `tenant_id`, `roles`, and `scopes` from the token.
   - Authorization rules:
     - Tenant-scoped queries:
       - Only allowed against the tenant’s named graph(s).
       - No cross-tenant queries unless `roles` contains platform-level admin roles.
     - Write/management operations:
       - Only allowed for service accounts and specific admin workflows.
       - Not exposed directly to general API clients.

4. **Hardening**

   - Limit query timeout and result size:
     - Max execution time: e.g. 5 seconds.
     - Max result rows: e.g. 10,000 rows per query.
   - Reject obviously dangerous queries (e.g. `SELECT * WHERE { ?s ?p ?o }` with no filters) from external callers.
   - Enforce strict content types and CORS policies at the gateway.

#### 7.1.4 Backup & restore strategy

Backing store: Fuseki/TDB2 database files on a persistent volume.

Backup approach:

- **Daily full backups** of the semantic store volume (e.g., filesystem snapshot → object storage).
- **Hourly incremental backups** or WAL-based backups if supported by the deployment stack.
- Backups are encrypted at rest in object storage (e.g. S3, GCS, Azure Blob).

Backup contents:

- All TDB2 data files.
- Semantic Service configuration (namespaces, dataset configs).
- Versioned by date/time and environment.

Restore procedure:

1. Provision a new semantic store instance with an empty volume.
2. Restore the latest full backup plus any incremental/WAL segments if applicable.
3. Start Fuseki and run a **consistency check**:
   - Validate that required graphs exist.
   - Sample a set of SPARQL queries against known resources.
4. Re-point the Semantic Service to the restored instance.
5. Rotate traffic via gateway (blue/green or canary-style).

RPO/RTO targets (MVP):

- **RPO (Recovery Point Objective):** ≤ 24 hours (driven by daily full backup + business criticality; can be tightened later).
- **RTO (Recovery Time Objective):** ≤ 2 hours for a full environment-wide restore.

Semantic reconstruction:

- In case of complete data loss, semantic graphs can be **partially rebuilt** from:
  - Recorded semantic mappings in the relational database.
  - Asset and dataset metadata.
- However, the triple store is treated as a **Tier-1** data store and backed up accordingly.

#### 7.1.5 Performance targets & capacity planning

Initial sizing assumptions (MVP):

- Triple count:
  - 1–10 million triples for early tenants.
  - Up to 50–100 million triples at moderate scale.
- Hardware:
  - 2–4 vCPU, 8–16 GB RAM, fast SSD backing.

Performance targets:

- **Query latency (internal callers)**:
  - P50: < 100 ms for typical asset/dataset discovery queries.
  - P95: < 300 ms.
  - P99: < 1,000 ms for complex joins over medium graphs.

- **Throughput**:
  - 50–100 queries per second sustained for read-only workloads in a single Fuseki instance at moderate scale.
  - Can be scaled:
    - Vertically by increasing memory/CPU.
    - Horizontally by adding read replicas or moving to a managed store (e.g. Neptune).

- **Update/ingest**:
  - Semantic graph updates are primarily driven by:
    - New assets/datasets.
    - New or updated semantic mappings.
  - Ingest pipeline batches updates into small transactions to avoid long write locks.

Monitoring:

- Metrics to track:
  - `sparql_query_latency_ms` (histogram).
  - `sparql_query_throughput` (QPS).
  - `sparql_query_failures_total` (by error type).
  - Triple store resource metrics: JVM heap, GC pauses, I/O wait.

Alerting:

- Alerts when:
  - P95 latency exceeds 500 ms for sustained periods (e.g., 5 min).
  - Error rates > 1% for SPARQL queries.
  - Disk utilization for the semantic volume > 80%.

These choices and targets give the platform:

- A concrete, open-source triple store for MVP (Fuseki/TDB2).
- A clear security posture for `/sparql` (internal-first, read-only public optional later).
- Practical backup/restore procedures.
- Realistic performance goals for early and moderate scale deployments.

## 8. Core Services Deployment

This section describes how logical services map to concrete Kubernetes deployments and services.

### 8.1 Service naming conventions

We use the following pattern for Kubernetes service and deployment names:

- Logical name: **Asset & Catalog Service**
- Deployment/Service name: `asset-service` (lowercase, `kebab-case`, `-service` suffix)

This applies consistently across core services.

### 8.2 Core domain services

| Logical Service           | Deployment Name   | Namespace   | Notes                                               |
|---------------------------|-------------------|-------------|-----------------------------------------------------|
| Auth & Tenant Service     | `auth-service`    | `core`      | Handles auth, tokens, and tenant/user management.   |
| Asset & Catalog Service   | `asset-service`   | `core`      | Manages assets, metadata, and catalog search APIs.  |
| Contract Service          | `contract-service`| `core`      | Manages contracts and integration with HubContract. |
| Ingestion Service         | `ingestion-service` | `core`    | Orchestrates file ingestion and schema inference.   |
| Marketplace Service       | `marketplace-service` | `core` | Exposes listings, orders, and entitlement flows.    |

### 3.3 Example Kubernetes resources (Asset & Catalog Service)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: asset-service
  labels:
    app: asset-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: asset-service
  template:
    metadata:
      labels:
        app: asset-service
    spec:
      containers:
        - name: asset-service
          image: ghcr.io/your-org/asset-service:{{ .Values.image.tag }}
          env:
            - name: SERVICE_NAME
              value: asset-service
---
apiVersion: v1
kind: Service
metadata:
  name: asset-service
  labels:
    app: asset-service
spec:
  selector:
    app: asset-service
  ports:
    - name: http
      port: 80
      targetPort: 8080
