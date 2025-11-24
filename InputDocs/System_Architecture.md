# System Architecture (MVP)

This document describes the **system architecture for MVP v1** of the Interoperable Data Hub, based on:

- Personas
- System Requirements
- MVP Scope

It focuses on:

- Core services & data stores
- How they interact
- Which interactions are **synchronous** vs **asynchronous**
- How this supports the MVP user journeys

---

## 1. Architectural Goals & Constraints

### 1.1 Goals

- Support **multi-tenant** data onboarding and cataloging via:
  - Data-first, Contract-first, Contract-only flows.
- Enforce:
  - **Data contract standards** (ODCS/DataContract.com) via DataContract CLI.
  - **Data Quality** and **Compliance** checks at **intake** (fail-closed for compliance).
- Treat data contracts as **semantic assets**:
  - Provide URIs, JSON-LD, RDF, and a SPARQL endpoint.
- Provide a basic **marketplace**:
  - Internal catalog per tenant.
  - Ability to flag assets as public and enable simple purchase/access.
- Provide **SDKs/CLI** for JS and Python.
- Maintain robust **audit trails** and a generic **Job** model.

### 1.2 Non-Functional Constraints (MVP)

- Multi-tenant isolation of assets, logs, runs.
- Security:
  - AuthN/AuthZ, encryption in transit & at rest.
  - No raw PII/sensitive data in logs.
- Availability targets:
  - Core APIs ≈ 99.5% (target).
  - DQ/Compliance ≈ 99% (target).
- Batch-first: ingestion via files (UI/CLI/SDK); streaming out of scope for MVP.

---

## 2. High-Level Context

### 2.1 External Actors

- **Data Product Owner (DPO)** – UI + SDK.
- **Data Engineer / Contract Author (DE)** – SDK + APIs + CLI.
- **Compliance / Privacy Officer (CPO)** – UI (dashboards & logs).
- **Data Consumer / Buyer (DC)** – UI (catalog & marketplace).
- **Tenant Admin** – UI (user/role management, config).
- **Marketplace Operator / Platform Admin (MPA)** – Admin UI (cross-tenant).
- **External Developer / Integrator (DEV)** – SDK/API + semantic endpoints.
- Future external systems:
  - Payments provider.
  - KYC/KYB provider.
  - Internal data platforms / catalogs.

### 2.2 High-Level System View

At a high level, the platform is organized into:

1. **Edge Layer**
   - Web UI (front-end web app).
   - Public API Gateway (REST APIs for MVP; GraphQL reserved for future versions).
2. **Core Domain Services**
   - Auth & Tenant Service (`auth-service`).
   - Asset & Catalog Service (`asset-service`).
   - Contract Service (`contract-service`, HubContract + DataContract CLI integration).
   - Ingestion Service (`ingestion-service`, files, schema inference, orchestration).
   - Marketplace Service (`marketplace-service`, listings, orders, entitlements).
3. **Supporting Services**
   - DQ Service (Great Expectations / Soda integration).
   - Compliance Service (PII/sensitive detection & regulatory mapping).
   - DataContract Service (CLI wrapper).
   - Semantic Service (RDF/triple store & URIs).
   - Job Service (generic job model).
   - Audit Service (append-only audit log).
   - Billing/Metrics Service (for operation metering).
4. **Data Stores**
   - Primary Relational DB (metadata).
   - Object Storage (data files).
   - Triple Store / Graph DB (semantic layer).
   - Log/Audit Storage (append-only, possibly in separate DB or log store).
  
### 2.3 Worker concurrency and scaling

`worker-service` is a stateless service that consumes `Job` records from `job_queue` and orchestrates long-running operations (DQ, compliance, contract validation, semantic mapping). It scales horizontally and enforces per-instance and per-tenant limits to prevent noisy-neighbor behavior and accidental or malicious overload.

#### 2.3.1 Max concurrent jobs per worker instance

- Each worker pod/container is sized at **2 vCPU / 4 GiB** in the default environment (tunable per deployment).
- Concurrency is controlled via `WORKER_MAX_CONCURRENCY` (env/config).
- **MVP default**
  - `WORKER_MAX_CONCURRENCY = 4` jobs per worker instance.
- Behavior:
  - Worker maintains an internal async/concurrency pool.
  - When `active_jobs >= WORKER_MAX_CONCURRENCY`, the worker **stops pulling** from `job_queue` until a slot frees up.
  - MVP treats all job types uniformly; later we can add per-job-type tuning if DQ/compliance workloads prove significantly heavier.

Effective cluster-wide processing capacity at any time:

> `max_running_jobs_cluster = worker_replicas * WORKER_MAX_CONCURRENCY`

#### 2.3.2 Worker pool sizing strategy

Workers run as a horizontally scalable deployment on the container orchestration platform (e.g. Kubernetes, ECS).

- **Baseline sizing**
  - `minReplicas = 2` (avoid single point of failure).
  - `maxReplicas = 20` (initial soft cap; configurable).
- **Autoscaling inputs**
  - HPA (or equivalent) driven by:
    - Average CPU utilization per worker.
    - Job queue depth (pending jobs), exposed as a custom metric.
- **Example autoscaling policy (initial)**
  - Scale **out** when:
    - `CPU > 70%` for 5 minutes, **or**
    - `pending_jobs / replicas > 20`.
  - Scale **in** (down to `minReplicas`) when:
    - `CPU < 40%` for 10 minutes **and**
    - `job_queue_depth == 0`.

This keeps ingestion/DQ/compliance latency reasonable while avoiding over-provisioning.

#### 2.3.3 Per-tenant job rate limits

Per-tenant limits are enforced at **two layers** to prevent a single tenant from monopolizing worker capacity:

1. **API-level rate limiting (job creation)**
2. **Cluster-level per-tenant concurrency limits**

**Enforcement Points**

- **API Gateway**: Enforces API-level rate limits (burst, sustained, daily caps) before requests reach services.
- **API Service**: Enforces cluster-level concurrency limits before enqueuing jobs.

**(a) API-level rate limiting**

Applied at the **API Gateway** (or API service edge) for endpoints that create jobs (e.g. DQ/compliance job creation such as `POST /api/v1/dq-runs`, `POST /api/v1/compliance-runs`, and any other job-creating endpoints).

- **Enforcement point**: API Gateway middleware or API service request handler.
- **Storage**: Rate limit counters stored in Redis or shared cache (sliding window algorithm).
- Rate-limit keys:
  - Primary: `tenant_id`
  - Optional: `user_id` or API key for finer-grained controls.
- **MVP default limits per tenant (configurable / plan-based):**
  - Burst: up to **20** job-creating requests in any **10-second** window.
  - Sustained: up to **60** new jobs **per minute** on average.
  - Daily quota: **10,000** jobs **per day**.
- On violation:
  - API returns **HTTP 429** with standard error envelope:
    - `code = "RATE_LIMIT_EXCEEDED"` or `code = "JOB_QUOTA_EXCEEDED"` (for daily cap).
    - `message`, `details`, `http_status`, `request_id`.
  - **Request is rejected** (not queued, not processed).

**(b) Cluster-level per-tenant concurrency**

Before enqueuing a job, `api-service` checks per-tenant counters (`running_jobs`, `queued_jobs`) stored in the primary DB or a shared cache (e.g. Redis) with atomic increments/decrements.

- **Enforcement point**: API service (before publishing to job queue).
- **Storage**: Counters in database (`jobs` table aggregates) or Redis cache.
- **MVP defaults:**
  - `MAX_TENANT_RUNNING_JOBS = 5` (across all workers).
  - `MAX_TENANT_QUEUED_JOBS = 50`.
- Behavior:
  - If `running_jobs >= MAX_TENANT_RUNNING_JOBS` **or**
    `queued_jobs >= MAX_TENANT_QUEUED_JOBS`, the job is **rejected** (not queued).
  - API returns **HTTP 429** with:
    - `code = "JOB_RATE_LIMITED"`
    - `details` including current counters and configured limits.
  - **Request is rejected** (not queued, not processed).

**Enforcement Order**

1. API Gateway checks API-level rate limits (burst, sustained, daily).
2. If passed, request reaches API service.
3. API service checks cluster-level concurrency limits.
4. If passed, job is enqueued.

**What Happens When Quota Exceeded**

- **Reject immediately**: Requests are rejected with HTTP 429 (not queued for later processing).
- **No queuing**: Quota violations do not queue requests; clients must retry later.
- **Clear error messages**: Error responses include `Retry-After` header and current quota status.

This provides clear backpressure and avoids a single tenant saturating the queue.

#### 2.3.4 Priority queues

To keep ingestion and UI-triggered flows responsive under heavy background load, jobs are assigned to priority tiers.

- **Priority levels**
  - **High priority** (`critical` queue/topic):
    - Compliance and DQ jobs triggered as part of intake (asset gating).
    - Contract validation jobs invoked from interactive flows (UI/SDK).
  - **Normal priority** (`default` queue/topic):
    - Manual DQ re-runs.
    - External / scan-only compliance checks.
    - Semantic mapping/indexing jobs and other background tasks.
- **Concurrency reservation**
  - A fixed fraction of each worker’s concurrency is reserved for high-priority jobs.
  - With `WORKER_MAX_CONCURRENCY = 4`:
    - **2 slots** reserved for high-priority jobs.
    - **2 slots** shared by any priority.
- **Scheduling behavior**
  - Worker always attempts to fill reserved high-priority slots first.
  - Normal-priority jobs **cannot** consume reserved slots while any high-priority job is waiting.
- **Implementation options**
  - Separate physical queues/topics: `job_critical`, `job_default`, with workers polling `job_critical` first.
  - Or a single priority-aware queue where dequeue operations respect job priority.

#### 2.3.4.1 Job Prioritization Algorithm

**Job Selection Algorithm**

When a worker has available concurrency slots, it selects the next job using the following algorithm:

1. **Check reserved high-priority slots**:
   - If any reserved slots are available (e.g., 2 slots reserved for high-priority):
     - Poll `job_critical` queue (or priority-aware queue with `priority = HIGH`)
     - If a high-priority job is available, select it immediately
     - Fill all reserved slots with high-priority jobs before considering normal-priority jobs
2. **Check shared slots**:
   - If reserved slots are full or no high-priority jobs are available:
     - Check shared slots (e.g., 2 slots shared by any priority)
     - Poll both `job_critical` and `job_default` queues
     - **Selection order**: High-priority jobs are selected before normal-priority jobs, even in shared slots
3. **Within same priority level**:
   - Jobs are selected in **FIFO order** (first-in, first-out) based on `jobs.created_at`
   - No additional prioritization within the same priority level
   - **Exception**: Jobs with `cancellation_requested = true` are deprioritized (processed last within their priority level)

**Priority Assignment Rules**

Jobs are assigned priorities based on their type and context:

| Job Type | Priority | Rationale |
|----------|----------|-----------|
| `COMPLIANCE_CHECK` (intake flow) | `HIGH` | Blocks asset activation, user waiting |
| `QUALITY_CHECK` (intake flow) | `HIGH` | Blocks asset activation, user waiting |
| `CONTRACT_VALIDATION` (interactive) | `HIGH` | User-initiated, interactive flow |
| `COMPLIANCE_CHECK` (manual re-run) | `NORMAL` | Background operation, not blocking |
| `QUALITY_CHECK` (manual re-run) | `NORMAL` | Background operation, not blocking |
| `SEMANTIC_MAPPING` | `NORMAL` | Background indexing, eventual consistency |
| `CONTRACT_MIGRATION` | `NORMAL` | Background migration, not time-sensitive |
| `UPLOAD_CLEANUP` | `LOW` | Maintenance job, lowest priority |
| `AUDIT_RETENTION_CLEANUP` | `LOW` | Maintenance job, lowest priority |

**Priority Override**

- **Explicit priority**: Jobs can specify `priority` in their creation request (if supported by the API)
- **Default priority**: If not specified, priority is determined by job type (see table above)
- **Tenant-level overrides**: Tenants can configure priority overrides via `tenant_config.job_priorities` (future enhancement)

**Queue Depth Monitoring**

- **High-priority queue depth**: Monitored via `job_queue_depth{priority="HIGH"}` metric
  - **Warning threshold**: > 10 pending high-priority jobs
  - **Critical threshold**: > 50 pending high-priority jobs
- **Normal-priority queue depth**: Monitored via `job_queue_depth{priority="NORMAL"}` metric
  - **Warning threshold**: > 100 pending normal-priority jobs
  - **Critical threshold**: > 500 pending normal-priority jobs

**Starvation Prevention**

- **Fairness guarantee**: To prevent normal-priority jobs from starving:
  - After processing N high-priority jobs in a row (e.g., N=10), worker must check normal-priority queue
  - If normal-priority jobs have been waiting > 5 minutes, they are temporarily elevated to high priority
  - **Starvation detection**: Monitored via `job_wait_time_seconds{priority="NORMAL"}` metric
    - **Warning**: Average wait time > 5 minutes
    - **Critical**: Average wait time > 15 minutes

**Concurrency Slot Allocation Example**

With `WORKER_MAX_CONCURRENCY = 4` and 2 reserved slots:

- **Scenario 1**: 3 high-priority jobs, 10 normal-priority jobs
  - Slots 1-2: Reserved for high-priority → filled with 2 high-priority jobs
  - Slots 3-4: Shared → filled with 1 high-priority job, 1 normal-priority job
  - Remaining: 0 high-priority, 9 normal-priority jobs waiting

- **Scenario 2**: 0 high-priority jobs, 10 normal-priority jobs
  - Slots 1-2: Reserved → remain empty (cannot be used by normal-priority)
  - Slots 3-4: Shared → filled with 2 normal-priority jobs
  - Remaining: 8 normal-priority jobs waiting

**Implementation Details**

- **Queue implementation**: Uses separate physical queues (`job_critical`, `job_default`) or priority field in single queue
- **Worker polling**: Workers poll `job_critical` queue first, then `job_default` queue
- **Polling interval**: Workers poll queues every 1 second (configurable via `WORKER_POLL_INTERVAL_SECONDS`)
- **Batch processing**: Workers can process multiple jobs concurrently up to `WORKER_MAX_CONCURRENCY`

### 2.4 Health Check Standardization

All services MUST implement standardized health check endpoints for Kubernetes liveness and readiness probes.

#### 2.4.1 Standard Health Check Endpoints

**All Services MUST Implement:**

- `GET /healthz` (liveness probe):
  - **Purpose**: Indicates if the service process is alive and should not be restarted.
  - **Response**: `200 OK` if service is running, `503 Service Unavailable` if process is unhealthy.
  - **Checks**: Minimal checks only (process is running, no deadlocks).
  - **Timeout**: Should respond within 1 second.
  - **Response format**:
    ```json
    {
      "status": "ok",
      "service": "asset-service",
      "timestamp": "2025-01-15T10:00:00Z"
    }
    ```

- `GET /ready` (readiness probe):
  - **Purpose**: Indicates if the service is ready to accept traffic.
  - **Response**: `200 OK` if ready, `503 Service Unavailable` if not ready.
  - **Checks**: All critical dependencies (database, message queue, external services).
  - **Timeout**: Should respond within 2 seconds.
  - **Response format**:
    ```json
    {
      "status": "ready",
      "service": "asset-service",
      "checks": {
        "database": "ok",
        "cache": "ok",
        "message_queue": "ok"
      },
      "timestamp": "2025-01-15T10:00:00Z"
    }
    ```

#### 2.4.2 Per-Service Health Check Requirements

**API Service (`api-service`)**
- Liveness: Process running, no deadlocks.
- Readiness: Database connection pool healthy, downstream services reachable (circuit breakers not all open).

**Auth Service (`auth-service`)**
- Liveness: Process running.
- Readiness: Database connection pool healthy, JWT key store accessible.

**Asset Service (`asset-service`)**
- Liveness: Process running.
- Readiness: Database connection pool healthy, cache connection healthy (if using shared cache).

**Contract Service (`contract-service`)**
- Liveness: Process running.
- Readiness: Database connection pool healthy, DataContract CLI service reachable (circuit breaker not open).

**Ingestion Service (`ingestion-service`)**
- Liveness: Process running.
- Readiness: Database connection pool healthy, object storage accessible, message queue healthy.

**DQ Service (`dq-service`)**
- Liveness: Process running, DQ engine (GX/Soda) initialized.
- Readiness: Database connection pool healthy, DQ engine ready to accept requests.

**Compliance Service (`compliance-service`)**
- Liveness: Process running, compliance engine initialized.
- Readiness: Database connection pool healthy, compliance engine ready to accept requests.

**Marketplace Service (`marketplace-service`)**
- Liveness: Process running.
- Readiness: Database connection pool healthy, cache connection healthy.

**Semantic Service (`semantic-service`)**
- Liveness: Process running.
- Readiness: Database connection pool healthy, triple store (SPARQL endpoint) reachable.

**Worker Service (`worker-service`)**
- Liveness: Worker loop is running and a minimal self-check passes.
- Readiness: Config is loaded, connections to DB and `job_queue` are healthy, worker is **not** in draining/shutdown mode.

**Audit Service (`audit-service`)**
- Liveness: Process running.
- Readiness: Database connection pool healthy, audit log storage accessible.

**DataContract Service (`datacontract-service`)**
- Liveness: Process running, CLI binary accessible.
- Readiness: CLI binary executable and ready to accept requests.

#### 2.4.3 Health Check Implementation Logic

**Database Connection Pool Health Check**

All services that connect to the database MUST implement the following logic for database health checks:

```python
def check_database_health(pool):
    """
    Checks if database connection pool is healthy.
    Returns: (healthy: bool, error: str | None)
    """
    try:
        # 1. Check pool is not exhausted
        if pool.get_active_connections() >= pool.get_max_connections() * 0.95:
            return False, "Connection pool nearly exhausted"
        
        # 2. Acquire connection with timeout (5 seconds)
        conn = pool.get_connection(timeout=5.0)
        if not conn:
            return False, "Failed to acquire connection within timeout"
        
        try:
            # 3. Execute validation query
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            # 4. Verify result
            if result and result[0] == 1:
                return True, None
            else:
                return False, "Validation query returned unexpected result"
        finally:
            # 5. Return connection to pool
            pool.return_connection(conn)
            
    except Exception as e:
        return False, f"Database health check failed: {str(e)}"
```

**Implementation Details**:
- **Timeout**: Connection acquisition timeout is **5 seconds** (configurable via `DB_HEALTH_CHECK_TIMEOUT_MS`)
- **Validation query**: `SELECT 1` (lightweight, no table access required)
- **Pool exhaustion threshold**: Pool is considered unhealthy if active connections ≥ 95% of max connections
- **Error handling**: Any exception during health check results in unhealthy status

**Message Queue Health Check**

Services that use message queues (e.g., `worker-service`, `ingestion-service`) MUST implement:

```python
def check_message_queue_health(queue_client):
    """
    Checks if message queue is healthy.
    Returns: (healthy: bool, error: str | None)
    """
    try:
        # 1. Check queue connectivity
        if not queue_client.is_connected():
            return False, "Queue client not connected"
        
        # 2. Verify queue exists and is accessible
        queue_info = queue_client.get_queue_info(timeout=3.0)
        if not queue_info:
            return False, "Failed to retrieve queue info"
        
        # 3. Check queue depth (optional, for monitoring)
        if queue_info.depth > 100000:  # Configurable threshold
            return False, f"Queue depth too high: {queue_info.depth}"
        
        return True, None
        
    except Exception as e:
        return False, f"Message queue health check failed: {str(e)}"
```

**Implementation Details**:
- **Timeout**: Queue operations timeout is **3 seconds** (configurable via `QUEUE_HEALTH_CHECK_TIMEOUT_MS`)
- **Queue depth threshold**: Queue is considered unhealthy if depth > 100,000 messages (configurable)
- **Connectivity check**: Verifies queue client can establish connection

**Object Storage Health Check**

Services that use object storage (e.g., `ingestion-service`) MUST implement:

```python
def check_object_storage_health(storage_client):
    """
    Checks if object storage is healthy.
    Returns: (healthy: bool, error: str | None)
    """
    try:
        # 1. Check connectivity
        if not storage_client.is_connected():
            return False, "Storage client not connected"
        
        # 2. Perform lightweight operation (head bucket or list)
        bucket_info = storage_client.head_bucket(timeout=3.0)
        if not bucket_info:
            return False, "Failed to access storage bucket"
        
        return True, None
        
    except Exception as e:
        return False, f"Object storage health check failed: {str(e)}"
```

**Implementation Details**:
- **Timeout**: Storage operations timeout is **3 seconds** (configurable via `STORAGE_HEALTH_CHECK_TIMEOUT_MS`)
- **Operation**: Uses lightweight operation (`HEAD` bucket or `LIST` with limit=1) to avoid heavy I/O
- **Circuit breaker integration**: If circuit breaker is open, health check returns unhealthy

**Cache Health Check**

Services that use shared cache (e.g., `asset-service`, `marketplace-service`) MUST implement:

```python
def check_cache_health(cache_client):
    """
    Checks if cache is healthy.
    Returns: (healthy: bool, error: str | None)
    """
    try:
        # 1. Check connectivity
        if not cache_client.is_connected():
            return False, "Cache client not connected"
        
        # 2. Perform ping operation
        ping_result = cache_client.ping(timeout=1.0)
        if not ping_result:
            return False, "Cache ping failed"
        
        return True, None
        
    except Exception as e:
        return False, f"Cache health check failed: {str(e)}"
```

**Implementation Details**:
- **Timeout**: Cache operations timeout is **1 second** (configurable via `CACHE_HEALTH_CHECK_TIMEOUT_MS`)
- **Operation**: Uses `PING` command (Redis) or equivalent lightweight operation
- **Graceful degradation**: If cache is unhealthy, service may continue operating with degraded performance (cache misses)

**Circuit Breaker Integration**

For services that depend on external services (e.g., `contract-service` → `datacontract-service`):

```python
def check_downstream_service_health(circuit_breaker):
    """
    Checks if downstream service is healthy based on circuit breaker state.
    Returns: (healthy: bool, error: str | None)
    """
    state = circuit_breaker.get_state()
    
    if state == "OPEN":
        return False, "Circuit breaker is open (downstream service unavailable)"
    elif state == "HALF_OPEN":
        # Service is attempting recovery; consider healthy but monitor closely
        return True, None
    else:  # CLOSED
        return True, None
```

**Implementation Details**:
- **Circuit breaker states**:
  - **CLOSED**: Healthy (normal operation)
  - **HALF_OPEN**: Recovering (test requests allowed)
  - **OPEN**: Unhealthy (requests fail fast)
- **Readiness behavior**: Service is considered **not ready** if circuit breaker is **OPEN** for critical dependencies

**Composite Health Check Logic**

Each service combines individual health checks:

```python
def check_readiness():
    """
    Composite readiness check for a service.
    Returns: (ready: bool, checks: dict, error: str | None)
    """
    checks = {}
    all_healthy = True
    
    # Database check (required for all services)
    db_healthy, db_error = check_database_health(db_pool)
    checks["database"] = "ok" if db_healthy else f"unhealthy: {db_error}"
    if not db_healthy:
        all_healthy = False
    
    # Service-specific checks
    if has_message_queue:
        mq_healthy, mq_error = check_message_queue_health(mq_client)
        checks["message_queue"] = "ok" if mq_healthy else f"unhealthy: {mq_error}"
        if not mq_healthy:
            all_healthy = False
    
    if has_object_storage:
        storage_healthy, storage_error = check_object_storage_health(storage_client)
        checks["object_storage"] = "ok" if storage_healthy else f"unhealthy: {storage_error}"
        if not storage_healthy:
            all_healthy = False
    
    # ... additional checks ...
    
    if all_healthy:
        return True, checks, None
    else:
        error_msg = "; ".join([f"{k}: {v}" for k, v in checks.items() if "unhealthy" in v])
        return False, checks, error_msg
```

**Response Format**

Health check endpoints MUST return:

**Liveness (`GET /healthz`)**:
```json
{
  "status": "ok",
  "service": "api-service",
  "timestamp": "2025-01-15T10:00:00Z"
}
```

**Readiness (`GET /ready`)**:
```json
{
  "status": "ready",
  "service": "api-service",
  "checks": {
    "database": "ok",
    "message_queue": "ok",
    "object_storage": "ok"
  },
  "timestamp": "2025-01-15T10:00:00Z"
}
```

**Unhealthy Response** (HTTP 503):
```json
{
  "status": "not_ready",
  "service": "api-service",
  "checks": {
    "database": "ok",
    "message_queue": "unhealthy: Failed to acquire connection within timeout",
    "object_storage": "ok"
  },
  "error": "message_queue: Failed to acquire connection within timeout",
  "timestamp": "2025-01-15T10:00:00Z"
}
```

**Timeout Configuration**

All health checks MUST complete within their respective timeouts:

| Check Type | Default Timeout | Configurable Via |
|------------|----------------|------------------|
| Database | 5 seconds | `DB_HEALTH_CHECK_TIMEOUT_MS` |
| Message Queue | 3 seconds | `QUEUE_HEALTH_CHECK_TIMEOUT_MS` |
| Object Storage | 3 seconds | `STORAGE_HEALTH_CHECK_TIMEOUT_MS` |
| Cache | 1 second | `CACHE_HEALTH_CHECK_TIMEOUT_MS` |
| Downstream Service | 2 seconds | `DOWNSTREAM_HEALTH_CHECK_TIMEOUT_MS` |

**Total Readiness Check Timeout**: Should not exceed **10 seconds** (sum of all individual checks).

#### 2.3.5 Worker health checks and graceful shutdown

Workers integrate with the platform's health, deployment, and observability model.

**Health checks**

- HTTP endpoints:
  - `GET /healthz` (liveness):
    - OK if the worker loop is running and a minimal self-check passes.
    - Failure indicates the process should be restarted.
  - `GET /ready` (readiness):
    - OK only if:
      - Config is loaded.
      - Connections to DB and `job_queue` are healthy.
      - Worker is **not** in draining/shutdown mode.
    - Failure removes the pod from service discovery / load balancing and stops it from consuming new jobs.

**Graceful shutdown**

- Pods are configured with `terminationGracePeriodSeconds = 300` (5 minutes) by default.
- On `SIGTERM` (e.g. deploy rollout):
  1. Worker sets `/ready` to **unready**, so no new jobs are assigned.
  2. Stops pulling from `job_queue` (enters drain mode).
  3. Continues processing in-flight jobs up to `GRACEFUL_SHUTDOWN_SECONDS` (default 300s).
  4. For jobs still running at the end of the grace period:
     - For idempotent job types (DQ/compliance/validation):
       - Mark the attempt as transient failure (e.g. `TERMINATED_DURING_DEPLOYMENT`).
       - Requeue or schedule retry according to the job’s retry policy.
     - For non-idempotent jobs (if any are introduced later):
       - Mark as `FAILED` with a specific reason and **do not** auto-retry.

**Metrics & alerts**

Each worker exports metrics such as:

- `worker_active_jobs`
- `worker_completed_jobs`
- `worker_failed_jobs`
- `job_queue_depth{priority=…}`
- Rate-limit related counts:
  - `RATE_LIMIT_EXCEEDED`
  - `JOB_RATE_LIMITED`

These metrics are used to:

- Tune `WORKER_MAX_CONCURRENCY`.
- Adjust per-tenant limits and quotas.
- Refine autoscaling thresholds (HPA) as real-world usage patterns emerge.


**Description**  
Requests cancellation of a running or queued job.  

**Request parameters**  

| Field | Type | Required | Description |
|-------|------|-----------|-------------|
| `reason` | string | no | Optional human-readable reason, stored in `cancel_reason`. |
| `requested_by` | string | no | Populated automatically from auth context. |

**Responses**

| Code | Meaning |
|------|----------|
| `202 Accepted` | Cancellation accepted; job state transitions to `RUNNING (cancellation_requested = true)`. |
| `404 Not Found` | No job with that ID visible to the tenant. |
| `409 Conflict` | Job already completed, failed, or cancelled. |
| `403 Forbidden` | Tenant or user not authorized to cancel this job. |

**Behavior**

1. API validates that the job belongs to the authenticated tenant and is in `QUEUED` or `RUNNING`.
2. Job record is updated:  
   - `status = 'RUNNING (cancellation_requested = true)'`  
   - `cancel_requested_at` timestamp and `cancel_reason`.
3. A `cancel` event is published to the `job_queue`’s control topic for the responsible worker.

#### 2.4.3 Worker cancellation handling

Workers must support both *user-requested* and *timeout-triggered* cancellations.

**Complete State Transition Diagram**

| From Status | Event | To Status | Notes |
|-------------|-------|-----------|-------|
| `PENDING` | `cancel()` API call | `CANCELLED` | No worker started; job removed from queue immediately |
| `PENDING` | worker picks up job | `RUNNING` | Normal execution begins |
| `RUNNING` | `cancel()` API call | `RUNNING` (with `cancellation_requested = true`) | Worker continues but observes cancellation flag |
| `RUNNING` (cancellation_requested = true) | worker observes flag and stops | `CANCELLED` | Worker exits cleanly after cleanup |
| `RUNNING` (cancellation_requested = true) | worker completes before observing flag | `SUCCEEDED` | **Edge case:** Worker finished before cancellation processed; result is valid |
| `RUNNING` (cancellation_requested = false) | worker completes normally | `SUCCEEDED` | Normal success path |
| `RUNNING` | fatal error / exception | `FAILED` | Normal failure path |
| `CANCELLED` | any operation | `CANCELLED` | Terminal state; no further transitions allowed |

**Database Structure for Cancellation**

The `jobs` table includes the following fields to support cancellation:

- `status` enum: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED` (NOT NULL, DEFAULT `PENDING`)
- `cancellation_requested` boolean (NOT NULL, DEFAULT false) - Set to `true` when cancellation is requested
- `cancel_requested_at` timestamp (NULL) - Timestamp when cancellation was requested
- `cancel_reason` text (NULL) - Human-readable reason for cancellation
- `cancel_requested_by` UUID (NULL, FK → `users.id`) - User who requested cancellation
- `details_json` JSONB (NULL) - May contain partial results and cancellation metadata

**Cancellation Flow (Detailed)**

1. **API receives cancellation request** (`POST /jobs/{id}/cancel`):
   - Validates job belongs to tenant and is in `PENDING` or `RUNNING` state.
   - If job is `PENDING`:
     - Immediately sets `status = CANCELLED`, `cancellation_requested = true`, `cancel_requested_at = NOW()`, `cancel_reason = <provided reason>`.
     - Removes job from queue (if not yet picked up).
     - Returns `202 Accepted`.
   - If job is `RUNNING`:
     - Sets `cancellation_requested = true`, `cancel_requested_at = NOW()`, `cancel_reason = <provided reason>`.
     - **Does NOT change `status`** (remains `RUNNING`).
     - Publishes cancellation event to job queue control topic.
     - Returns `202 Accepted`.

2. **Worker receives cancellation signal**:
   - Worker subscribes to cancellation messages for job IDs it owns.
   - If job is **PENDING** (not yet started):
     - Worker removes job from internal pool.
     - Marks job `status = CANCELLED` (if not already done by API).
   - If job is **RUNNING**:
     - Worker observes `cancellation_requested = true` flag (polled periodically or via event).
     - Worker invokes component-specific `on_cancel()` hook:
       - Close DB cursors/connections.
       - Terminate subprocesses (CLI, DQ engines, etc.).
       - Abort external API calls.
       - Release locks/leases.
     - Worker performs cleanup (see §2.4.5).
     - Worker sets `status = CANCELLED`.
     - Worker updates `details_json` with cancellation metadata.

**Edge Cases & Partial Results**

**Case 1: Worker writes partial results before cancellation**

- If a worker has already written partial results (e.g., partial DQ metrics, compliance findings) to `dq_runs` or `compliance_runs` tables:
  - **Partial results are preserved** with a flag indicating incompleteness.
  - For `dq_runs`: Set `status = FAILED` (or a new `PARTIAL` status if supported), include `partial = true` in `details_json`.
  - For `compliance_runs`: Set `status = FAILED`, include `partial = true` in `details_json`.
  - The `jobs.details_json` includes:
    ```json
    {
      "cancelled": true,
      "cancel_reason": "User requested cancellation",
      "partial_results": {
        "dq_run_id": "uuid-or-null",
        "compliance_run_id": "uuid-or-null"
      }
    }
    ```
  - These partial results remain queryable for diagnostics but are **not considered valid** for asset activation or compliance decisions.

**Case 2: Worker completes after cancellation requested**

- If a worker finishes processing **after** `cancellation_requested = true` is set but **before** it observes the flag:
  - Worker completes normally and sets `status = SUCCEEDED`.
  - The cancellation request is **ignored** (job already completed).
  - Results are valid and can be used normally.
  - This is an acceptable race condition; the cancellation is considered "too late."

**Case 3: Re-running cancelled jobs**

- **A `CANCELLED` job cannot be re-run directly.**
- To re-run a cancelled job:
  - Client must create a **new job** with the same parameters.
  - The new job gets a new `job_id` and starts fresh.
  - The old cancelled job remains in the database for audit/history.
  - Clients can reference the cancelled job's `job_id` in the new job's `details_json` for traceability.

**Case 4: Timeout during cancellation**

- If a job times out **while** `cancellation_requested = true`:
  - The timeout handler (see §2.4.4) sets `status = FAILED` (or `FAILED_TIMEOUT` if supported).
  - The `details_json` includes both cancellation and timeout information.
  - Error code: `JOB_TIMEOUT` (not `JOB_CANCELLED`).

**Partial Results Handling**

If the job type produces intermediate artifacts (e.g., partial DQ metrics, compliance findings), the worker:

1. **Persists partial results** (if any exist):
   - For DQ jobs: Writes to `dq_runs` with `status = FAILED` and `details_json.partial = true`.
   - For Compliance jobs: Writes to `compliance_runs` with `status = FAILED` and `details_json.partial = true`.
   - Links are stored in `jobs.details_json.partial_results`.

2. **Includes cancellation metadata**:
   - `jobs.details_json.cancelled = true`
   - `jobs.details_json.cancel_reason = <reason>`
   - `jobs.details_json.partial_results = { ... }`

3. **Marks job as CANCELLED**:
   - `status = CANCELLED`
   - `cancellation_requested = true` (already set)
   - `finished_at = NOW()`

4. **These records remain queryable** for diagnostics but are **not used** for:
   - Asset activation decisions.
   - Compliance gate decisions.
   - Marketplace publication decisions.

**Detailed Partial Results Behavior**

- **DQ Jobs**:
  - If cancellation occurs mid-execution:
    - Partial metrics (e.g., completeness for first N columns) are saved to `dq_runs.result_summary`.
    - `dq_runs.status = FAILED` (not `PASS` or `WARN`).
    - `dq_runs.details_json.partial = true` indicates incomplete results.
    - Asset `dq_status` remains `UNKNOWN` (not updated from partial results).
  - Partial results are **not** used for asset activation; user must re-run DQ job.

- **Compliance Jobs**:
  - If cancellation occurs mid-execution:
    - Partial findings (e.g., PII detected in first N columns) are saved to `compliance_runs.details_json`.
    - `compliance_runs.status = FAILED` (not `PASS` or `WARN`).
    - `compliance_runs.details_json.partial = true` indicates incomplete scan.
    - `compliance_runs.allowed_to_store = false` (fail-closed: incomplete scan blocks storage).
    - Asset `compliance_status` remains `UNKNOWN` (not updated from partial results).
  - Partial results are **not** used for compliance gate; user must re-run compliance job.

- **Semantic Mapping Jobs**:
  - If cancellation occurs mid-execution:
    - Partial triples (e.g., asset mapped but fields not mapped) may be written to triple store.
    - `asset.semantic_status = DEGRADED` (not `OK`).
    - Partial results are **acceptable** for semantic mapping (non-blocking feature).
    - User can manually trigger remap via `POST /assets/{id}/remap`.

- **Re-running Cancelled Jobs**:
  - Cancelled jobs cannot be re-run directly (must create new job).
  - New job starts fresh; partial results from cancelled job are not merged.
  - User can reference cancelled job's `job_id` in new job's `details_json.parent_job_id` for traceability.

#### 2.4.4 Timeout escalation and failover

When the orchestrator or monitoring service detects a job past its `timeout_seconds`:

1. Sets job status to `RUNNING (cancellation_requested = true)` and emits a `timeout_cancellation` event.
2. Waits `GRACE_PERIOD` (default = 5 min) for the owning worker to acknowledge and clean up.
3. If no acknowledgment:
   - Marks job `FAILED_TIMEOUT`.
   - Triggers automated cleanup (temporary files, external task IDs, DB locks, cloud resources).
4. Worker metrics increment `worker_timeout_failures_total`.

This policy ensures deterministic outcomes even if a worker becomes unresponsive.

#### 2.4.5 Resource cleanup on cancellation

All job types must define a cleanup contract:

| Resource Type | Cleanup Action | Responsibility |
|----------------|----------------|----------------|
| Temporary files (local / object storage) | Delete path prefix under `/tmp/jobs/{job_id}` or `s3://bucket/tmp/{job_id}/` | Worker |
| External connections / sessions | Close sockets, terminate subprocesses, release API tokens | Worker |
| Queue leases / locks | Release or delete visibility lock in `job_queue` | Worker |
| DB artifacts (partial tables, temp rows) | Roll back transaction or delete partial entries | Worker or orchestrator |
| Cloud / external resources (if any) | Cancel external job ID, de-allocate compute | Worker |

Workers must guarantee that cleanup runs once and is idempotent; orchestrator periodically runs a **reaper** to handle orphaned jobs older than `timeout_seconds + GRACE_PERIOD`.

#### 2.4.6 Metrics and audit logging

- `job_cancel_requested_total`
- `job_cancel_completed_total`
- `job_timeout_failures_total`
- `job_partial_result_count`
- Audit log entries:
  - `action = "job_cancel" | "job_timeout"`
  - `job_id`, `tenant_id`, `requested_by`, `reason`, and timestamps.

---

**Summary**

This design ensures deterministic, auditable job lifecycle management:
- Explicit user cancellation via API.
- Automatic timeouts with clear escalation.
- Worker-side cleanup and partial-result preservation.
- Idempotent resource reclamation.

### 2.5 Service naming conventions

To avoid confusion between logical components and their deployed services, we use:

- **Logical service name** in prose and architecture diagrams.
- **Deployment identifier** (Kubernetes service/deployment name) in code/config examples, in `kebab-case` with a `-service` suffix.

**Canonical Service Name Registry (MVP)**

The following service names are **canonical** and MUST be used consistently across all documentation, code, configuration, and deployment manifests:

| Logical Service Name | Deployment Identifier | Description |
|---------------------|----------------------|-------------|
| API Gateway / Backend Service | `api-service` | Main API gateway exposing `/api/v1` and `/graphql` endpoints |
| Job Worker Service | `worker-service` | Processes async jobs from the job queue (DQ, compliance, semantic mapping, etc.) |
| DataContract CLI Service | `datacontract-service` | Wraps DataContract CLI for validation, linting, and conversion |
| Data Quality Service | `dq-service` | Executes DQ checks using Great Expectations or Soda |
| Compliance Service | `compliance-service` | Executes compliance checks (PII detection, regulatory mapping) |
| Semantic Service | `semantic-service` | Manages RDF/triple store and provides SPARQL/JSON-LD endpoints |
| Auth & Tenant Service | `auth-service` | Handles authentication, authorization, and tenant management |

**Naming Rules**

- All deployment identifiers use `kebab-case` with `-service` suffix.
- No variations are allowed (e.g., `hub-api-service`, `cli-service`, `job-worker-service` are **not** canonical).
- In documentation, use the logical service name in prose, and the deployment identifier in code/config examples.
- In Kubernetes manifests, Docker Compose files, and environment variables, use the deployment identifier.

**Examples of Correct Usage**

- ✅ "The `api-service` handles incoming HTTP requests."
- ✅ "`worker-service` consumes jobs from the queue."
- ✅ "`datacontract-service` wraps the DataContract CLI."
- ❌ "The `hub-api-service`..." (incorrect; use `api-service`)
- ❌ "The `cli-service`..." (incorrect; use `datacontract-service`)
- ❌ "The `job-worker-service`..." (incorrect; use `worker-service`)

For the MVP, the core mappings are:

- Asset & Catalog Service → `api-service` (handled by API service)
- Auth & Tenant Service   → `auth-service`
- Contract Service        → `contract-service`
- Ingestion Service       → `ingestion-service`
- Marketplace Service     → `marketplace-service`

**Rules:**

- In architecture docs, write **"Asset & Catalog Service (`asset-service` on first mention)"**, then just the logical name afterwards.
- In deployment/config examples, use only the deployment identifier (e.g., `asset-service`).

---

### 2.6 Background Job Scheduling

The platform requires several **scheduled background jobs** that run periodically to maintain system health, enforce policies, and perform cleanup operations.

#### 2.6.1 Scheduler Architecture

- **Scheduler**: Kubernetes CronJob or dedicated scheduler service (e.g., Celery Beat, Temporal).
- **Job Types**: All scheduled jobs are implemented as standard `Job` records with `type` indicating the scheduled operation.
- **Idempotency**: All scheduled jobs MUST be idempotent (safe to run multiple times).

**Timezone Configuration**

- **Default Timezone**: All cron schedules use **UTC (Coordinated Universal Time)**.
- **Configuration**:
  - Timezone is configured via environment variable: `SCHEDULER_TIMEZONE` (default: `UTC`).
  - For Kubernetes CronJobs, timezone is specified in the CronJob manifest:
    ```yaml
    apiVersion: batch/v1
    kind: CronJob
    metadata:
      name: entitlement-expiration-check
    spec:
      schedule: "*/15 * * * *"
      timeZone: "UTC"  # Explicitly set to UTC
      jobTemplate:
        # ...
    ```
- **Daylight Saving Time (DST)**:
  - UTC does not observe DST, so schedules remain consistent year-round.
  - If a different timezone is used (not recommended for MVP), DST transitions are handled automatically by the scheduler.
- **Schedule Format**:
  - All cron expressions in this document use standard cron format: `minute hour day month weekday`.
  - All times are interpreted in UTC unless explicitly stated otherwise.

#### 2.6.2 Scheduled Job Definitions

**A. Entitlement Expiration Check**

- **Schedule**: Every 15 minutes (`*/15 * * * *` UTC).
- **Job Type**: `ENTITLEMENT_EXPIRATION_CHECK` (internal, not exposed via API).
- **Behavior**:
  - Queries `entitlements` where `status = ACTIVE` AND `expires_at IS NOT NULL` AND `expires_at <= NOW()`.
  - Updates `status = EXPIRED` for expired entitlements.
  - Emits audit events: `ENTITLEMENT_EXPIRED`.
  - Processes in batches (1000 entitlements per batch) to avoid long transactions.

**B. Upload Session Cleanup**

- **Schedule**: Every hour (`0 * * * *` UTC).
- **Job Type**: `UPLOAD_CLEANUP` (internal).
- **Behavior**:
  - Identifies expired upload sessions (created > 24 hours ago, status = `UPLOADING` or `PENDING_FINALIZE`).
  - Deletes partial chunks from object storage.
  - Updates `files.status = FAILED` for expired sessions.
  - Emits audit events: `UPLOAD_SESSION_CLEANED_UP`.

**C. File Physical Deletion**

- **Schedule**: Every 6 hours (`0 */6 * * *` UTC).
- **Job Type**: `FILE_DELETION` (internal).
- **Behavior**:
  - Identifies files marked for deletion (`files.status = DELETED`, `updated_at < NOW() - INTERVAL '1 hour'`).
  - Deletes physical objects from object storage.
  - Updates `files.status = DELETED` (already set, no change needed).
  - Emits audit events: `FILE_PHYSICALLY_DELETED`.

**D. Audit Log Retention Cleanup**

- **Schedule**: Daily at 2 AM UTC (`0 2 * * *`).
- **Job Type**: `AUDIT_RETENTION_CLEANUP` (internal).
- **Behavior**:
  - Identifies audit events older than retention period (default: 3 years, configurable per tenant).
  - Archives or deletes old audit events (per retention policy).
  - Emits audit events: `AUDIT_RETENTION_CLEANUP_COMPLETED`.

**E. Tenant Suspension Check**

- **Schedule**: Daily at 3 AM UTC (`0 3 * * *`).
- **Job Type**: `TENANT_SUSPENSION_CHECK` (internal).
- **Behavior**:
  - Identifies tenants suspended for > 90 days (configurable via `SUSPENSION_TO_DELETION_DAYS`).
  - Notifies Platform Admin (via email or alert).
  - Does NOT automatically delete (requires manual Platform Admin action).

**F. Contract Migration (Background)**

- **Schedule**: On-demand or triggered by `POST /contracts/{id}/migrate` with `migration_strategy = BACKGROUND`.
- **Job Type**: `CONTRACT_MIGRATION`.
- **Behavior**:
  - Processes contracts in batches (100 contracts per batch).
  - Applies migration transformation rules (see `SystemRequrements.md` §19).
  - Updates `hub_contract_version` and `hub_contract_json`.
  - Emits audit events: `CONTRACT_MIGRATION_COMPLETED` or `CONTRACT_MIGRATION_FAILED`.

#### 2.6.3 Job Queue Initialization

- **On service startup**: Scheduler service initializes and registers all scheduled jobs.
- **Job persistence**: Scheduled job definitions are stored in database or configuration (not in code).
- **Failure handling**: If a scheduled job fails, it is retried with exponential backoff (max 3 retries).
- **Monitoring**: All scheduled jobs emit metrics (`scheduled_job_runs_total`, `scheduled_job_duration_seconds`, `scheduled_job_failures_total`).

#### 2.6.4 Scheduled Job Failure Handling and Notifications

**Failure Handling**

- **Retry Policy**:
  - **Max retries**: 3 attempts per scheduled job execution
  - **Backoff**: Exponential backoff (1 minute, 5 minutes, 15 minutes)
  - **Retry window**: If job fails after all retries, next scheduled run will attempt again (jobs are idempotent)

- **Failure Notification**:
  - **On first failure**: Log warning to application logs
  - **After 3 retries fail**: 
    - Emit alert to monitoring system (severity: WARNING)
    - Send notification to operations team (Slack/email)
    - Create incident ticket (low priority)
  - **Consecutive failures** (same job fails 3+ times in a row):
    - Escalate to CRITICAL alert
    - Page on-call engineer
    - Create high-priority incident ticket

- **Failure Metrics**:
  - `scheduled_job_failures_total{job_type}` (counter)
  - `scheduled_job_consecutive_failures{job_type}` (gauge)
  - `scheduled_job_last_success_timestamp{job_type}` (gauge)

- **Manual Intervention**:
  - Operations team can manually trigger scheduled jobs via admin API (future enhancement)

#### 2.6.5 Scheduler Failure Recovery

**Scheduler Service Failure Scenarios**

The scheduler service itself may fail or become unavailable. The following recovery mechanisms ensure scheduled jobs continue to run:

**Scenario 1: Scheduler Service Crash**

- **Detection**:
  - Kubernetes liveness probe detects service crash
  - Service is automatically restarted by Kubernetes
  - **Recovery time**: Typically < 30 seconds (Kubernetes restart)
- **Recovery**:
  - Scheduler service restarts and re-registers all scheduled jobs
  - **Missed executions**: Scheduler checks for missed scheduled jobs on startup
  - **Catch-up logic**: For jobs with high frequency (e.g., every 15 minutes), scheduler may execute missed jobs if they are within a grace period (e.g., 1 hour)
  - **Idempotency**: All scheduled jobs are idempotent, so executing a missed job is safe
- **Monitoring**:
  - Alert fires if scheduler service is down > 5 minutes
  - Metrics: `scheduler_service_restarts_total` (counter)

**Scenario 2: Scheduler Service Unavailable (Network/Infrastructure)**

- **Detection**:
  - Health checks fail (readiness probe)
  - Service is marked as not ready
  - Kubernetes stops routing traffic to the service
- **Recovery**:
  - **Manual intervention**: Operations team must investigate and restore service
  - **Backup scheduler**: If primary scheduler is unavailable for > 15 minutes, a backup scheduler instance may be activated (future enhancement)
  - **Missed jobs**: Jobs missed during downtime are **not automatically executed** after recovery (to prevent system overload)
  - **Next scheduled run**: Jobs resume on their next scheduled time
- **Monitoring**:
  - Alert fires if scheduler service is unavailable > 15 minutes
  - Metrics: `scheduler_service_availability` (gauge, 0 = down, 1 = up)

**Scenario 3: Database Unavailable During Scheduled Job Execution**

- **Detection**:
  - Database connection fails during job execution
  - Job execution fails with database error
- **Recovery**:
  - **Job retry**: Job is retried with exponential backoff (up to 3 retries)
  - **Database recovery**: Once database is available, retries succeed
  - **No data loss**: Job state is persisted in database (if available) or in-memory (if database is down)
  - **Idempotency**: Jobs are idempotent, so retries are safe
- **Monitoring**:
  - Alert fires if database is unavailable > 5 minutes
  - Metrics: `scheduled_job_database_errors_total{job_type}` (counter)

**Scenario 4: Message Queue Unavailable During Scheduled Job Execution**

- **Detection**:
  - Message queue connection fails when enqueuing job results
  - Job execution completes but result cannot be published
- **Recovery**:
  - **Result buffering**: Job results are buffered in-memory or database
  - **Queue recovery**: Once queue is available, buffered results are published
  - **Retry logic**: If buffering fails, job is retried (up to 3 retries)
- **Monitoring**:
  - Alert fires if message queue is unavailable > 5 minutes
  - Metrics: `scheduled_job_queue_errors_total{job_type}` (counter)

**Missed Job Detection and Recovery**

- **Detection algorithm**:
  - On scheduler startup, scheduler queries database for scheduled job definitions
  - For each scheduled job, scheduler calculates expected execution times since last successful run
  - **Grace period**: Jobs that should have run within the last 1 hour are considered "missed"
  - **Catch-up execution**: Missed jobs are executed immediately (if within grace period)
- **Grace period rules**:
  - **High-frequency jobs** (every 15 minutes or less): Grace period = 1 hour
  - **Medium-frequency jobs** (every hour or less): Grace period = 4 hours
  - **Low-frequency jobs** (daily or less): Grace period = 24 hours
- **Catch-up limits**:
  - **Max catch-up executions**: Maximum 10 missed executions per job (prevents system overload)
  - **Catch-up delay**: Missed jobs are executed with 1-minute delay between executions
  - **Skip if too many**: If > 10 missed executions, scheduler skips catch-up and waits for next scheduled time

**Scheduler State Persistence**

- **Job execution history**: Scheduler persists job execution history in database:
  - Table: `scheduled_job_executions`
  - Columns: `job_type`, `scheduled_time`, `execution_time`, `status`, `duration_seconds`, `error_message`
  - **Retention**: 30 days (for monitoring and debugging)
- **Last execution tracking**: Scheduler tracks last successful execution time per job:
  - Stored in database: `scheduled_jobs.last_success_at`
  - Used for missed job detection
  - Updated after each successful execution

**Scheduler Health Monitoring**

- **Health check endpoint**: Scheduler service exposes `/healthz` and `/ready` endpoints
- **Health metrics**:
  - `scheduler_healthy` (gauge, 0 = unhealthy, 1 = healthy)
  - `scheduler_jobs_registered` (gauge, number of registered scheduled jobs)
  - `scheduler_missed_jobs_total{job_type}` (counter, number of missed job executions)
  - `scheduler_catchup_executions_total{job_type}` (counter, number of catch-up executions)
- **Alerts**:
  - **Warning**: Scheduler service down > 5 minutes
  - **Critical**: Scheduler service down > 15 minutes
  - **Warning**: > 5 missed job executions in last hour
  - **Critical**: > 20 missed job executions in last hour

**Manual Recovery Procedures**

If automatic recovery fails, operators can use the following procedures:

1. **Restart scheduler service**:
   - `kubectl rollout restart deployment/scheduler-service`
   - Verify service comes back up: `kubectl get pods -l app=scheduler-service`
2. **Manually trigger missed jobs**:
   - Use admin API (future enhancement) to trigger specific scheduled jobs
   - Or directly execute job logic via database/CLI
3. **Verify job execution**:
   - Check `scheduled_job_executions` table for recent executions
   - Verify job results (e.g., entitlements expired, files deleted)
4. **Investigate root cause**:
   - Check scheduler service logs
   - Check database connectivity
   - Check message queue connectivity
  - Failed jobs can be retried manually via runbook procedures

---

## 3. Logical Components

### 3.1 Edge Layer

#### 3.1.1 Web UI

- Single-page app (SPA) or standard web app.
- Functions:
  - Supports all persona UIs:
    - Asset onboarding (three flows).
    - Contract editor and validation.
    - DQ & compliance report views.
    - Catalog & marketplace.
    - Jobs status and basic logs.
    - Admin & tenant configuration.
- Communicates with API Gateway via HTTPS/JSON.

#### 3.1.2 API Gateway

- Single entry-point for:
  - REST APIs (`/api/v1/...`) – **only supported external API for MVP v1**.
  - (Optional / future) GraphQL endpoint (`/graphql`) – reserved for post-MVP; MAY be used internally but is not part of the public v1 contract.
- Responsibilities:
  - AuthN/AuthZ (token validation, tenant scoping).
  - Routing to backend services.
  - Rate limiting and basic logging.

---

### 3.2 Core Domain Services

#### 3.2.1 Auth & Tenant Service

- Manages:
  - Tenants (organizations).
  - Users within tenants.
  - Roles (Tenant Admin, Data Provider, Data Consumer, Auditor).
  - KYC status flags (verified/unverified).
- Issues or validates auth tokens that encode:
  - `tenant_id`
  - `user_id`
  - `roles[]`
- Provides APIs:
  - Create/update tenant (platform admin only).
  - Invite/manage users in tenant.
  - Assign roles.

> **Sync:** Called synchronously by API Gateway to validate tokens & authorize access.

---

#### 3.2.2 Asset & Catalog Service (`asset-service`)

- Deployment identifier: `asset-service`.
- Manages the **logical Asset** entity:
  - Asset metadata (name, description, domain, tags).
  - Manages the **logical Asset** entity:
  - Asset metadata (name, description, domain, tags).
  - Links to:
    - Contract(s).
    - Dataset(s)/DataFiles.
    - DQ runs / Compliance runs.
    - Marketplace listing(s).
  - Asset states: `DRAFT`, `ACTIVE`, `PUBLIC`, `RETIRED`.
- Functions:
  - Tenant-internal catalog (list/filter assets).
  - Marketplace view (public assets, with cross-tenant filters).
- APIs:
  - `POST /assets` – create draft asset.
  - `GET /assets` – search/list.
  - `GET /assets/{id}` – details.
  - `PATCH /assets/{id}` – update metadata, state changes.
- Responsible for:
  - Ensuring that only assets with valid contracts and passed gates are `active`.

These map directly to the Asset.status enum (DRAFT | ACTIVE | PUBLIC | RETIRED). public corresponds to status = PUBLIC and visibility = PUBLIC.

---

#### 3.2.3 Contract Service

- Manages **contracts** and the canonical **HubContract** model.
- Responsible for:
  - Storing:
    - Original contract (`original_spec_type`, `original_spec_version`, `original_raw`).
    - Normalized HubContract JSON.
  - Enforcing:
    - Spec/version compliance using **DataContract CLI**.
    - Contract status: `DRAFT`, `VALID`, `INVALID`, `WARNING_ONLY`.
- Functions:
  - CRUD for contracts via UI and APIs.
  - Triggering CLI validation (via DataContract Service).
  - Versioning HubContract (`hub_contract_version`) and handling upgrades (later).
- APIs:
  - `POST /contracts` – create from file or JSON.
  - `GET /contracts/{id}` – retrieve.
  - `PATCH /contracts/{id}` – edit.
  - `POST /contracts/{id}/validate` – run validation (creates Job).

> **Sync:** CRUD operations.  
> **Async:** Validation via Job & DataContract Service (validate, lint, convert).

---

#### 3.2.4 Ingestion Service

- Orchestrates **data onboarding** for all three flows:
  - Data-first.
  - Contract-first (data attachment).
  - Contract-only (contract creation only).
- Responsibilities:
  - File upload lifecycle:
    - `POST /files/init` → returns upload URL or upload ID.
    - `PUT /files/...` actual upload (via gateway / object storage direct).
    - `POST /files/{id}/complete`.
  - File format validation.
  - Schema inference (column names, types).
  - Triggering:
    - Compliance Job (mandatory gate).
    - DQ Job (`intake_basic`).
  - Creating/attaching datasets and linking to assets & contracts.

> **Sync:** File metadata registration, schema inference for small samples.  
> **Async:** DQ & compliance checks are Jobs; ingestion service creates Jobs and later consumes results to finalize asset.

---

#### 3.2.5 Marketplace Service

- Manages:
  - Public **Listings/Products** associated with Assets.
  - Orders/Access Requests.
  - Entitlements (who can access what).
- Responsibilities:
  - Ensure only **KYC-verified tenants** can publish public listings.
  - Track which tenants have entitlements to which assets.
- APIs:
  - `POST /marketplace/listings` – create listing (from asset).
  - `GET /marketplace/listings` – public search.
  - `POST /marketplace/orders` – create purchase/access request.
  - `GET /entitlements` – list assets the tenant can access.
- Billing integration:
  - For MVP, primarily metering and simple access; full billing engine later.

> **Sync:** Creating/updating listings, orders, entitlements.  
> **Async:** Integration with external payment systems (future), and with billing/metering.

---

### 3.3 Supporting Services

#### 3.3.1 DQ Service

- Wraps **Great Expectations** / **Soda** for **Data Quality checks**.
- Responsibilities:
  - Run `intake_basic` profile on uploaded datasets.
  - Optionally support other profiles (future).
  - Return standardized DQ result object.
- APIs (internal):
  - `POST /dq-runs` – request DQ check for a dataset reference.
  - `GET /dq-runs/{id}` – get result.
- DQRun entity:
  - Linked to dataset & asset.
  - Contains `overall_status`, `quality_score`, `checks[]`, and `details_json`.

> **Async:** DQ runs are Jobs; Ingestion/Asset services create Jobs and poll or subscribe for updates.

---

#### 3.3.2 Compliance Service

- Performs **Data Compliance checks**:
  - PII/sensitive detection.
  - Regulatory mapping (GDPR, LGPD, CCPA, HIPAA, SOX).
- Responsibilities:
  - Mandatory gate at intake:
    - Decide `allowed_to_store` based on findings and thresholds.
    - Fail-closed on internal errors.
  - External **scan-only** mode:
    - No data storage; ephemeral data; only report and hash retained.
- APIs (internal & external via gateway):
  - `POST /compliance-runs`:
    - Params: dataset reference or file upload, `scan_mode` (`internal`/`external`), `applicable_regimes`.
  - `GET /compliance-runs/{id}` – report.

> **Async:** Compliance checks are Jobs; ingestion/DE/DEV call to create, then poll Jobs.  
> **Side effect:** If `scan_mode=internal` and `allowed_to_store=false`, ingestion MUST NOT persist the dataset.

---

#### 3.3.3 DataContract Service (CLI Wrapper)

- Wraps `datacontract-cli` in a microservice.
- Responsibilities:
  - Provide HTTP endpoints for:
    - `validate`, `lint`, `convert`.
  - Manage CLI process execution, timeouts, and concurrency.
- APIs (internal):
  - `POST /validate` – run CLI validate.
  - `POST /lint`
  - `POST /convert`
- Returns:
  - Structured result with:
    - `validation_status` (`VALID`, `INVALID`, `WARNING_ONLY`, `ERROR`).
    - Errors/warnings (mapped for UI display).
    - CLI version used.

> **Sync or Async:**  
> - For small contracts: direct sync calls from Contract Service.  
> - For heavy operations: Contract Service can create a `CONTRACT_VALIDATION` job that uses DataContract Service asynchronously.

---

#### 3.3.4 Semantic Service

- Manages the **semantic layer**:
  - RDF graphs.
  - Ontology.
  - URIs and JSON-LD representations.
- Responsibilities:
  - Map HubContract + Asset metadata → RDF using custom ontology (extending DCAT).
  - Manage triple store / graph DB.
  - Serve:
    - URIs (`/id/contract/{uuid}`, `/id/dataset/{uuid}`) returning JSON-LD.
    - SPARQL endpoint for semantic queries.
- APIs:
  - `POST /semantic/contract/{id}` – update RDF mapping for contract.
  - `POST /semantic/asset/{id}` – update mapping for asset.
  - `GET /id/contract/{id}` – JSON-LD.
  - `GET /id/dataset/{id}` – JSON-LD.
  - `/sparql` – SPARQL endpoint.

The semantic store is implemented using Apache Jena Fuseki (MVP), exposing a SPARQL endpoint to the semantic-mapper service and the API.



---

#### 3.3.5 Job Service

- Generic **Job/Run** abstraction for:
  - DQ runs.
  - Compliance runs.
  - Contract validation.
  - Semantic mappings.
- Responsibilities:
  - Create jobs with:
    - `job_id`, `type`, `status`, `tenant_id`, `user_id`, `resource_type`, `resource_id`, timestamps, `details_json`.
  - Update job status as workers complete tasks.
  - Provide APIs for UI/SDK to poll and list jobs.

- APIs:
  - `POST /jobs` – (optional, internal) schedule jobs.
  - `GET /jobs/{job_id}` – get job details.
  - `GET /jobs` – list jobs with filters (by tenant, resource, type).

> **Async:** Jobs are inherently asynchronous; services either poll Job Service or get notified via events.

---

#### 3.3.6 Audit Service

- Central place to store **audit events**:
  - Append-only model.
- Responsibilities:
  - Accept audit records from all services.
  - Enforce “no PII in logs” / only metrics & hashes.
  - Provide tenant-scoped and admin-scoped views.
- APIs:
  - `POST /audit-events` – internal event ingestion.
  - `GET /audit-events` – query by tenant, asset, event type, date.
- Storage:
  - Could be:
    - Separate relational DB.
    - Log store (e.g. append-only table).
    - Or a combination with external log system.

> **Sync:** Event ingestion is sync (fire-and-forget semantics).  
> **Async:** Analysis and export features may run asynchronously.

---

#### 3.3.7 Billing / Metrics Service

- Aggregates **usage metrics** for billing and observability:
  - Count of DQ runs, compliance runs.
  - Scan volumes, durations.
  - Asset access counts.
- MVP:
  - Simple aggregation tables or time-series store.
  - No full billing engine; just metrics per tenant & per operation type.

> **Async:** Metrics ingestion may be buffered or event-driven.  
> **Sync:** Basic usage queries (e.g., per tenant for dashboards).

---

## 4. Data Stores

### 4.1 Primary Relational Database

Stores:

- Tenants, Users, Roles.
- Assets, Contracts, HubContracts, Datasets, DataFiles.
- DQRun, ComplianceRun, Job, Entitlement, Listing/Order.
- Basic audit metadata (or at least references).

Properties:

- Multi-tenant aware (`tenant_id` in all relevant tables).
- Encrypted at rest.

---

### 4.2 Object Storage

Stores:

- Raw data files (datasets) for **internal** ingestion.
- Temporary/ephemeral data for scan-only mode (must be auto-deleted).

Properties:

- Encrypted at rest.
- Multi-tenant isolation via bucket/folder strategy or metadata tags.

---

### 4.3 Triple Store / Graph Database

Stores:

- RDF triples for:
  - Contracts (HubContract).
  - Assets/datasets (DCAT).
  - Quality & compliance metadata (where mapped).
  - Marketplace-related ontology concepts.

Used by:

- Semantic Service.
- SPARQL endpoint.
- JSON-LD URI resolution.

---

### 4.4 Audit/Log Storage

- Audit events in append-only store.
- Must support 3-year retention and immutable or soft-append-only semantics.
- May be:
  - A dedicated table or DB.
  - Connected to external log platforms.

---

## 5. Communication & Interaction Patterns

### 5.1 Synchronous vs Asynchronous

**Synchronous (request/response)**

- Frontend → API Gateway → Core services:
  - CRUD on contracts, assets, datasets metadata.
  - Listing assets, marketplace listings.
  - Reading DQ/compliance reports.
  - Reading jobs (status).
  - Reading audit logs.
  - Resolving URIs to JSON-LD.
- Core services → DataContract Service:
  - CLI validation for small contracts (with timeout).
- Core services → Semantic Service:
  - JSON-LD retrieval, SPARQL queries.

**Asynchronous (job-based)**

- DQ runs:
  - `POST /dq-runs` creates Job; worker runs GE/Soda; Job completes.
- Compliance runs:
  - `POST /compliance-runs` creates Job; worker runs detection; Job completes.
- Contract validation (heavy cases):
  - Contract Service creates Job; Job worker calls DataContract Service.
- Semantic mapping:
  - Job per contract/asset update; worker updates RDF triples.

> The **Job Service** is the consistent way to track these operations and tie them to Audit and Billing.

---

### 5.2 Example Interactions

#### 5.2.1 Data-First Ingestion (Happy Path)

1. UI → API Gateway:
   - `POST /files/init` → get upload URL.
2. Browser uploads file to object storage.
3. UI → API Gateway → Ingestion Service:
   - `POST /assets` with initial metadata.
4. Ingestion Service:
   - Registers DataFile.
   - Runs schema inference (sync).
   - Creates **Compliance Job** and **DQ Job**:
     - `POST /compliance-runs`
     - `POST /dq-runs`
   - Stores Job IDs.
5. UI polls `GET /jobs/{job_id}` until both Jobs `SUCCEEDED`.
6. Ingestion Service:
   - If compliance `allowed_to_store=true` and DQ acceptable:
     - Confirms dataset.
     - Creates/updates Asset & Dataset.
     - Calls Contract Service to create draft HubContract.
     - Triggers optional Semantic Job for contract/asset.
7. UI:
   - Opens Contract Editor.
   - User edits and triggers `POST /contracts/{id}/validate`.
8. Contract Service:
   - Calls DataContract Service (sync or async).
   - On success, marks contract `VALID`.
9. Asset Service:
   - Marks asset `active`.

All these steps generate Audit events and metrics; long steps are Jobs.

---

#### 5.2.2 External Compliance Scan-Only

1. DE/DEV → API Gateway:
   - `POST /compliance-runs` with `scan_mode="external"` and file/source info.
2. Compliance Service:
   - Stores file temporarily.
   - Creates Job (`COMPLIANCE_CHECK`).
3. Worker:
   - Executes scan.
   - Deletes raw data promptly.
   - Writes ComplianceRun + report.
   - Updates Job to `SUCCEEDED`.
   - Writes Audit event.
4. Client polls `GET /jobs/{id}` and then `GET /compliance-runs/{id}` to get report.

No Asset or Dataset is created.

---

#### 5.2.3 Publishing Asset to Marketplace

1. DPO → UI → API Gateway → Asset Service:
   - `GET /assets/{id}` (must be `active`).
2. DPO fills marketplace fields → UI → API Gateway → Marketplace Service:
   - `POST /marketplace/listings` with asset ID and pricing.
3. Marketplace Service:
   - Validates:
     - Tenant KYC = `verified`.
   - Creates Listing.
   - Updates Asset with `public` flag.
4. Marketplace search:
   - DC → UI → API Gateway → Marketplace Service:
     - `GET /marketplace/listings` to discover assets.

---


### 5.3 Asynchronous Jobs & Queue Message Format

Asynchronous work (DQ checks, compliance checks, contract validation, semantic
mapping) is modeled as **Jobs** plus messages on a **job queue**.

#### 5.3.1 Message Payload Schema

All job queue messages use a common envelope + payload structure. For MVP, the
body is serialized as **JSON**.

Canonical message shape:

```json
{
  "schema_version": 1,
  "message_id": "b3e0f0c4-0c4d-4b8c-9d8d-6d7e8f9a0b1c",
  "type": "job.dispatch",
  "idempotency_key": "job:8a1c3f4e-1234-5678-9abc-def012345678",
  "created_at": "2025-01-01T12:34:56Z",
  "payload": {
    "job_id": "8a1c3f4e-1234-5678-9abc-def012345678",
    "job_type": "COMPLIANCE_CHECK",
    "tenant_id": "c0ffee00-0000-0000-0000-000000000000",
    "resource_type": "DATASET",
    "resource_id": "f00dbabe-0000-0000-0000-000000000000",
    "priority": "NORMAL",
    "attempt": 1,
    "metadata": {
      "regulations": ["GDPR", "LGPD"]
    }
  }
}
```

Field semantics:

- `schema_version` (int)
  - Version of the **message schema**, not the DB schema.
  - Allows introducing new, incompatible message shapes (see §5.2.3).

- `message_id` (UUID)
  - Unique per message in the queue.
  - Useful for tracing and debugging.

- `type` (string)
  - Message kind, e.g. `job.dispatch`, `job.retry`, `job.cancel`.
  - MVP primarily uses `job.dispatch`.

- `idempotency_key` (string)
  - Global idempotency key for the logical operation.
  - For `job.dispatch` messages, this is typically `job:{job_id}`.
  - Workers use this and `job_id` to avoid double-processing.

- `created_at` (ISO-8601 UTC)
  - Time at which the message was enqueued.

- `payload.job_id` (UUID)
  - Primary key into the `jobs` table.

- `payload.job_type` (enum)
  - Logical job type, e.g. `QUALITY_CHECK`, `COMPLIANCE_CHECK`,
    `CONTRACT_VALIDATION`, `SEMANTIC_MAPPING`, etc.

- `payload.tenant_id` (UUID)
  - Tenant that owns the job (for metrics, sharding, and scoping).

- `payload.resource_type` / `payload.resource_id`
  - Reference to the entity the job is acting on (`ASSET`, `DATASET`, `FILE`,
    `CONTRACT`, etc.).

- `payload.priority` (enum)
  - MVP: `LOW`, `NORMAL`, `HIGH` (configurable mapping to queue priority or
    separate queues where supported).

- `payload.attempt` (int)
  - Attempt number for this job (starts at 1). Workers update this when
    re-enqueuing jobs after transient failures.

- `payload.metadata` (object)
  - Free-form JSON for job-specific parameters (e.g. target regulation list,
    DQ profile name, engine version).

Infrastructure-specific metadata (e.g. SQS attributes, RabbitMQ headers) MAY
duplicate some of these fields, but the **canonical message definition** is the
JSON body shown above.

#### 5.3.2 Serialization Format (MVP)

- MVP uses **JSON** as the serialization format for job messages:
  - Simple to inspect and debug.
  - Works with all common queue providers.
- In a future iteration, we MAY add support for Avro or Protobuf, but only if:
  - there is a demonstrable performance or schema-evolution benefit, and
  - the Job Service abstraction fully hides the wire format from domain
    services.

Domain services never construct queue messages directly. They:

1. Create a `job` record in the database.
2. Call the Job Service, which:
   - builds the canonical message envelope,
   - serializes it to JSON,
   - publishes it to the queue.

Workers reverse this process: consume → deserialize → look up `job_id` → execute.

#### 5.3.3 Message Versioning Strategy

- New message versions are introduced by **incrementing `schema_version`**.
- `schema_version = 1`:
  - MVP baseline, containing all fields shown in the schema above.
- Changes should be **backward compatible** where possible:
  - Adding optional fields is preferred over changing meanings or types.
- For **breaking changes**:
  - Bump `schema_version` (e.g. to `2`).
  - Workers MUST support both `schema_version = 1` and `2` during the
    transition period.
  - Producers MUST only emit the new version after all workers understand it.

If fundamentally different message shapes are required (e.g. non-job messages),
a new `type` (e.g. `event.audit_log.v1`) SHOULD be introduced rather than
overloading the job schema.

#### 5.3.4 Idempotency & Deduplication

Given at-least-once delivery semantics, workers MUST treat messages as
potentially **duplicated** and use idempotent logic:

- The combination of:
  - `idempotency_key` and
  - `payload.job_id`
  uniquely identifies the logical job execution.

Worker behavior:

1. On message receipt, look up the job in the `jobs` table by `job_id`.
2. If the job is already in a terminal state (`SUCCEEDED`, `FAILED`, `CANCELLED`):
   - Acknowledge the message and **do nothing** else.
3. If the job is `PENDING` or `RUNNING`:
   - Proceed with execution (subject to concurrency controls).
4. When retrying a job, the worker:
   - increments `payload.attempt`,
   - preserves the same `idempotency_key`,
   - republishes a new message.

Queue-level deduplication features (if supported by the provider) MAY be used as
an extra safety net, but the **source of truth** for idempotency remains the
`jobs` table and `idempotency_key` logic described above.


---

## 6. Deployment & Operational View (MVP)

### 6.1 Deployment Topology (Simplified)

- Single cloud region for MVP:
  - One or more **API nodes** (Gateway + Backend).
  - Separate pods/services for:
    - Auth/Tenant
    - Asset/Catalog
    - Contract
    - Ingestion
    - DQ
    - Compliance
    - DataContract service
    - Semantic service
    - Marketplace
    - Job service
    - Audit service
    - Billing/Metrics service
  - Shared infrastructure:
    - Relational DB cluster.
    - Object storage bucket(s).
    - Triple store cluster.
    - Queue system for Jobs (if used).
    - Central logging/monitoring.

### 6.2 Runtime Concerns

- **Scaling**
  - API layer: horizontally scalable.
  - DQ and Compliance services: scale via worker pools (more replicas).
  - Semantic service: scale triple store per vendor guidelines.

- **Resilience**
  - If DQ service is down:
    - Ingestion cannot complete for new data; show UI error, allow retry.
  - If Compliance service is down:
    - Fail-closed; ingestion blocked to avoid storing unchecked data.
  - If Semantic service is down:
    - Mark `semantic_status = DEGRADED`; core non-semantic features still work.

- **Observability**
  - All services emit metrics and logs:
    - Latency, error rates, job queues.
  - DQ/compliance runs and Jobs are central to SLO/SLA monitoring.

---

## 7. Future Extensions (Beyond MVP)

These are not required for MVP but are considered in the architecture:

- Multi-region deployments with tenant-level data residency.
- Streaming ingestion and streaming contracts.
- Advanced marketplace features (dynamic pricing, promotions, rev-share).
- Full billing engine with invoices and payment integration.
- Rich semantic UI (graph visualizations, SPARQL query builder).
- More fine-grained RBAC and per-field permissions.

The current architecture is designed so that these can be added without breaking core MVP services and APIs.

---

_End of System Architecture (MVP)._

## 8. Observability & Monitoring

### 8.1 Metrics aggregation and retention

This section defines how metrics are:

- Collected and aggregated over time.
- Retained at different resolutions.
- Constrained to avoid excessive cardinality and cost.

It applies to:

- Infrastructure metrics (CPU, memory, disk, network, container).
- Application metrics (latency, error rates, queue depth, job durations).
- Business-level metrics (asset counts, job volumes) when emitted via the same metrics pipeline.

#### 8.1.1 Metrics storage & tiers

The platform uses a standard metrics stack (e.g., Prometheus + remote storage) with multiple **resolution tiers**.

**Raw (high-resolution) metrics**

- Resolution: **10–30 seconds** scrape interval (per target).
- Retention: **30 days** (config: `METRICS_RAW_RETENTION_DAYS`).
  - **Note**: This aligns with `SystemRequrements.md` §17.2.5. The previous value of 14 days was incorrect and has been updated.
- Scope:
  - Infrastructure metrics (CPU, memory, disk, network).
  - Application-level latency, error rate, QPS.
  - Queue and worker metrics.

**Aggregated metrics**

- Aggregations are computed over fixed windows:
  - **1-minute** aggregates.
  - **5-minute** aggregates.
  - **1-hour** aggregates.
- Retention:
  - 1-minute: **7 days** (config: `METRICS_1M_RETENTION_DAYS`).
  - 5-minute: **30 days** (config: `METRICS_5M_RETENTION_DAYS`).
  - 1-hour: **13 months** (config: `METRICS_1H_RETENTION_DAYS`, default 395 days).
  - **Note**: These values align with `SystemRequrements.md` §17.2.5. Previous values (90/180/365 days) were incorrect and have been updated.
- Aggregations include:
  - `sum`, `avg`, `min`, `max`, `p50`, `p95`, `p99` where applicable.
  - Pre-computed SLI-style metrics (e.g., success rate, latency buckets).

Raw metrics are used primarily for:

- Short-term operational debugging.
- Incident analysis within the last 1–2 weeks.

Aggregated metrics are used for:

- Trend analysis.
- Capacity planning.
- SLO reporting.

#### 8.1.2 Aggregation intervals & queries

Aggregation windows are defined as:

- **1 minute**:
  - Default for dashboards focused on the last few hours/days.
  - X-axis granularity for most real-time operational views.
- **5 minute**:
  - Used for:
    - 24h–30d views in dashboards.
    - Alerting where small spikes are not critical.
- **1 hour**:
  - Used for:
    - Monthly/quarterly trend views.
    - High-level business/usage reporting.

Guidance for dashboard authors:

- Use **1-minute** resolution for:
  - Latency, error rates, queue depth, worker saturation.
- Use **5-minute or 1-hour** for:
  - Long-range views of traffic volume, CPU usage, storage trends.
- Avoid querying high-cardinality metrics with fine-grained resolution over long periods (e.g., 1-minute per-pod metrics over 30 days).

#### 8.1.3 Metrics cardinality limits

To control cost and protect the metrics system, we enforce **cardinality budgets**:

**Per metric family**

- Hard limit on label combinations (time series) per metric name:
  - Target: **≤ 10,000 time series** per metric in normal operation.
  - Soft warning at **5,000**; dashboards/alerts should be reviewed.
- Metrics that risk exceeding this limit must:
  - Be redesigned to use fewer or coarser labels, or
  - Be sampled or aggregated before export.

**Label design rules**

- Allowed labels:
  - `service`, `instance`, `pod`, `namespace`
  - `tenant_id` (only where necessary and with strong justification)
  - `endpoint_category` (e.g., `assets_read`, `jobs_write`, not full URL)
  - `job_type` (`DQ_RUN`, `COMPLIANCE_RUN`, `SEMANTIC_MAPPING`)
  - `status` / `result` (e.g., `success`, `error`)

- **Forbidden labels** (high-cardinality, unbounded):
  - `user_id`, `email`, `request_id`, `session_id`
  - Raw URLs with query strings.
  - `file_id`, `dataset_id`, `asset_id` (except in very limited, short-lived debug metrics not enabled by default).
  - Arbitrary free-form text (error messages, stack traces, etc.).

**Per-tenant cardinality**

- For metrics labeled by `tenant_id`:
  - Total number of tenant-labeled series per metric is capped (e.g., **≤ 2,000**).
  - For very large multi-tenant deployments, consider:
    - Dropping tenant labels on infrastructure-level metrics (they are cluster-wide).
    - Using sampling or per-plan metrics (only for enterprise tenants requiring per-tenant dashboards).

Metrics that violate cardinality budgets:

- May be automatically dropped (via metrics relabeling rules) at the collection or remote-write layer.
- Trigger alerts to the platform team to adjust instrumentation.

#### 8.1.4 Retention configuration & cost trade-offs

Metrics retention has direct cost and performance implications:

- **Storage cost**:
  - Roughly proportional to:
    - Number of time series (cardinality), and
    - Retention duration and resolution.
- **Query cost**:
  - Higher cardinality and finer resolution → heavier queries → slower dashboards and higher CPU.

MVP retention defaults (aligned with `SystemRequrements.md` §17.2.5):

| Tier          | Resolution   | Retention | Intended use                           |
|---------------|--------------|-----------|----------------------------------------|
| Raw           | 10–30s       | 30 days   | Incident debugging, short-term ops.    |
| Aggregated 1m | 1 minute     | 7 days    | SLOs, recent performance trends.       |
| Aggregated 5m | 5 minutes    | 30 days   | Monthly usage/performance trends.      |
| Aggregated 1h | 1 hour       | 13 months | Long-term capacity & business trends.  |

Changes to retention must consider:

- Budget for the metrics backend.
- Regulatory/compliance requirements for operational data.
- Impact on dashboard and alert reliability.

#### 8.1.5 Cost implications of high-cardinality metrics

High-cardinality metrics (e.g., per-user, per-file, per-dataset series) can:

- **Explode storage**:
  - Each new label combination creates a new time series.
  - Large tenants or frequent ID churn can generate millions of series.
- **Degrade performance**:
  - Query times increase significantly.
  - Memory usage on the metrics store grows, causing evictions or OOMs.
- **Increase complexity**:
  - Dashboards become unwieldy.
  - Harder to reason about and debug.

Therefore:

- High-cardinality metrics are allowed only when:

  - They are scoped to:
    - Non-production envs (debug only), or
    - Specific, temporary experiments.
  - They are **gated by feature flags** and disabled by default in production.

- Instead of per-ID labels:

  - Use aggregated metrics (e.g., per-tenant, per-service, per-endpoint category).
  - Use logs and traces for **per-request** analysis instead of metrics.
  - For rare “forensics” needs, rely on:
    - Sampling (e.g., 1% of requests),
    - Ephemeral debug metrics with strict TTLs.

Operational guidelines:

- New metrics must be reviewed for cardinality before deployment.
- Any metric that causes:
  - A sudden jump in series count, or
  - Metrics storage/CPU usage alerts,
  must be either:
  - Adjusted to reduce cardinality, or
  - Disabled in production.

By constraining retention, aggregation, and cardinality, the platform ensures metrics remain:

- Useful for debugging and capacity planning.
- Affordable to store and query.
- Stable and reliable for alerting at scale.

### 8.2 Distributed tracing implementation

This section defines how the platform implements **distributed tracing** across services:

- Tracing library and backend choice.
- Sampling strategy.
- Trace context propagation between services and async jobs.
- Trace retention and storage.

#### 8.2.1 Tracing stack & library choice

**Instrumentation**

- The platform standardizes on **OpenTelemetry** for:
  - Language-specific SDKs in services (API, workers, semantic service, etc.).
  - **Python services**: `opentelemetry-instrumentation-django` for Django auto-instrumentation
  - Auto-instrumentation for:
    - HTTP servers and clients.
    - gRPC (if used).
    - Database clients (SQL).
    - Message queues (job enqueue/dequeue).
  - See `Technology_Stack_Decisions.md` for version and configuration details.

**Export**

- OpenTelemetry SDKs export traces using **OTLP** (`otlphttp` or `otlpgrpc`) to a central collector.

**Backend (MVP)**

- The default tracing backend for MVP is:

  - **Jaeger** (self-hosted) or a compatible OTLP-capable trace backend (e.g., Tempo) deployed per environment.

- The OpenTelemetry Collector:
  - Receives traces from services.
  - Performs sampling (if configured centrally).
  - Forwards accepted traces to Jaeger / backend storage.

**Future options (non-MVP)**

- Swap-in managed vendor backends (e.g., AWS X-Ray, Azure Monitor, commercial APM) by:
  - Reconfiguring the collector exports.
  - Keeping service instrumentation unchanged (still OpenTelemetry).

#### 8.2.2 Instrumentation scope

All first-party services are instrumented:

- **API / Gateway service**
  - Incoming HTTP requests to `/api/v1/...` and `/graphql`.
  - Outgoing HTTP/gRPC calls to downstream services.
- **Worker / job processing service**
  - Job lifecycle spans:
    - Fetch from queue.
    - DQ/compliance run.
    - Semantic mapping.
  - DB and object storage interactions.
- **Semantic service**
  - SPARQL queries and RDF updates.
- **Background services**
  - Reconciliation jobs, scheduled tasks, cleanup jobs.

Each incoming request creates a **root span** and attaches:

- `service.name`
- `http.method`, `http.route`, `http.status_code`
- `tenant_id`, `user_id` (as attributes, NOT as labels in metrics)
- `job_type`, `asset_id`, `dataset_id` where applicable (for specific spans only, not every span).

Structured logs include `trace_id` and `span_id` fields so logs can be correlated with traces.

#### 8.2.3 Trace context propagation

The platform uses **W3C Trace Context** for cross-service propagation:

- Primary headers:
  - `traceparent`
  - `tracestate`
- Optional baggage:
  - `baggage` header for non-sensitive cross-cutting metadata (e.g., `tenant_id`).

**HTTP**

- On inbound requests:
  - API gateway / service extracts `traceparent`/`tracestate` if present.
  - If missing, a new trace is started and headers are added for downstream calls.
- On outbound calls:
  - Services inject current span context into `traceparent`/`tracestate` headers.

**gRPC (if used)**

- W3C trace context is propagated via gRPC metadata, using language-specific OpenTelemetry interceptors.

**Message queues / async jobs**

- When enqueuing a job:
  - The current trace context is encoded into message attributes/headers (e.g., `traceparent`, `tracestate`).
- When consuming a job:
  - Worker extracts the trace context and:
    - Continues the existing trace (if context is present), or
    - Starts a new trace if not present.
- For long-running jobs:
  - Workers may create child traces per major phase (DQ → COMPLIANCE → SEMANTIC), but tie them to a common `job_id` attribute.

**Security**

- Only non-sensitive identifiers (tenant_id, job_id, asset_id) may be placed into trace/baggage attributes.
- No raw PII (names, emails, etc.) may be placed into trace baggage or attributes.

#### 8.2.4 Sampling strategy

To balance observability and cost, we use **head-based sampling** (at trace start), with error- and SLO-conscious adjustments.

**Defaults (per environment)**

- **Development / staging**
  - Sampling: **100%** of requests (full tracing).
  - Useful for debugging and integration testing.

- **Production**
  - Baseline sample rate:
    - **5–10%** of incoming traces at the edge (API/gateway).
  - Always-sample rules:
    - Traces containing:
      - HTTP 5xx responses.
      - Job failures (`status = FAILED`).
      - Security-/auth-related errors (401/403).
  - Optional dynamic sampling:
    - Increase sampling temporarily during incidents or for specific endpoints/tenants.

**Implementation**

- Sampling is configured centrally in the OpenTelemetry Collector:
  - Head-based sampling on the **root span**.
  - Simple rules-based sampler:
    - Sample if:
      - `http.status_code >= 500`, OR
      - `job.status == "FAILED"` (where known).
    - Else, random sampling at configured rate (e.g., 5–10%).

- Services:
  - Use the collector’s sampling decisions; they do not implement their own independent samplers.

#### 8.2.5 Trace retention & storage

Trace retention is configured in the backend (e.g., Jaeger or compatible system).

**Retention**

- Production:
  - Full-fidelity traces retained for **7 days** by default.
  - May extend to **14 days** for critical environments if budget permits.
- Non-production:
  - Shorter retention (e.g., **3–7 days**) to keep storage small.

Beyond the primary retention window, we rely on:

- Aggregated metrics (latency, error rates).
- Logs (structured with trace IDs).
- Exported trace summaries if needed (optional).

**Storage**

- Backend storage options:
  - For Jaeger:
    - Default: Elasticsearch / OpenSearch or a supported time-series store.
    - Alternative: cloud-native storage (e.g., S3-based backends in some distributions).
- Capacity planning:
  - Driven by:
    - Sample rate.
    - Average span count per trace.
    - Retention days.
  - Periodically reviewed and adjusted based on observed volume.

**Access control**

- Tracing UI (Jaeger, Tempo, etc.) is:
  - Restricted to engineering / ops roles.
  - Typically accessed via VPN or internal SSO.
- Tenants do **not** have direct access to raw traces in MVP; derived metrics and logs underpin tenant-visible dashboards.

#### 8.2.6 Usage & reporting

Traces are used to:

- Diagnose latency and error issues across services (end-to-end).
- Understand queue and worker behavior for DQ/compliance jobs.
- Correlate:
  - API calls → job enqueue → worker execution → downstream calls (DB, object storage, triple store).

Dashboards and runbooks should include:

- Links from SLO panels (e.g., “P95 latency high”) to example traces.
- Guidance for:
  - Finding traces by `job_id`, `asset_id`, or `tenant_id` attributes.
  - Using trace spans to identify which service or dependency is the bottleneck.

This tracing implementation ensures:

- A standard, OpenTelemetry-based instrumentation approach.
- Consistent context propagation across sync and async boundaries.
- Controlled sampling and retention to keep costs under control.
- Actionable traces for debugging complex, cross-service flows.

### 8.3 Alerting thresholds & escalation

This section defines **alert thresholds** and **escalation procedures** for key signals:

- Error rates.
- Latency (p95, p99).
- Queue depth and job lag.
- How alerts are routed and escalated.

These thresholds apply primarily to **production**. Non-production environments may run a reduced alert set (or higher thresholds) to avoid noise.

#### 8.3.1 Alerting principles

- Alerts should indicate **user-visible or soon-to-be user-visible issues**, not every minor blip.
- Use **SLO-inspired thresholds**:
  - Warning when approaching SLO limits.
  - Critical when clearly exceeding them.
- Use **rolling windows** (e.g., last 5–10 minutes) to avoid flapping on single spikes.
- Prefer **rate-of-change** or multi-condition alerts where helpful (e.g., high latency + increasing error rate).

Alerts are implemented using the metrics described in §8.1 and delivered via the selected alerting system (e.g., Alertmanager / cloud-native equivalent).

**Alert Deduplication & Grouping**

To prevent alert fatigue and ensure actionable notifications:

- **Deduplication window**: Alerts of the same type (same alert name, same affected service/endpoint) are **deduplicated** within a **5-minute window**.
  - If the same alert condition fires multiple times within 5 minutes, only the **first** alert is sent.
  - Subsequent firings within the window are logged but do not trigger new notifications.
  - After 5 minutes of the condition being resolved, a new alert can fire if the condition reoccurs.

- **Alert grouping**: Related alerts are grouped into **incident tickets**:
  - Alerts for the same service (e.g., `api-service` error rate + latency) are grouped into a single incident.
  - Alerts for related dependencies (e.g., DB errors + queue backlog) are grouped if they occur within 10 minutes of each other.

- **Escalation rules**:
  - **First alert**: Sent to engineering Slack/Teams channel, creates low-severity ticket.
  - **Alert persists > 15 minutes**: Escalates to on-call engineer (pager/SMS).
  - **Alert persists > 30 minutes**: Escalates to engineering manager and creates high-severity incident.
  - **Multiple services affected**: Immediately escalates to on-call and creates high-severity incident.

- **Resolution notifications**: When an alert condition resolves (returns to normal):
  - A **resolution notification** is sent to the same channels.
  - The incident ticket is automatically updated with resolution time and duration.

---

#### 8.3.2 Error rate thresholds

We monitor error rates at three levels:

1. **Global API error rate** (all `/api/v1` + `/graphql`).
2. **Service-level error rate** (per service).
3. **Critical endpoint categories** (e.g., job creation, file upload).

Error rate is defined as:

```text
error_rate = 5xx_responses / total_requests
```

over a sliding window.

**Global API error rate (production)**

- **Warning**:
  - Condition:
    - `error_rate >= 2%` over the last **5 minutes**, and
    - At least **1000 requests** in that period.
  - Action:
    - Send notification to engineering Slack/Teams channel.
    - Create low-severity incident ticket automatically.

- **Critical**:
  - Condition:
    - `error_rate >= 5%` over the last **5 minutes**, and
    - At least **1000 requests** in that period.
  - Action:
    - Page the on-call engineer.
    - Open SEV-2 (or SEV-1 if coupled with high latency/widespread impact) incident.
    - Notify broader on-call distribution (e.g., email/SMS).

**Service-level error rate**

- For each core service (API, worker/job service, semantic service):
  - **Critical**:
    - `service_error_rate >= 5%` over **5 minutes**.
  - Helps identify which service is causing global errors.

**Critical endpoint categories**

- E.g., `POST /dq-runs`, `POST /compliance-runs`, `POST /files`, `POST /datasets`.
- **Warning**:
  - `endpoint_error_rate >= 5%` over **10 minutes**.
- **Critical**:
  - `endpoint_error_rate >= 10%` over **10 minutes**.

These per-endpoint alerts ensure critical workflows are monitored even if global error rate remains low.

---

#### 8.3.3 Latency thresholds (p95, p99)

Latency is measured via histogram metrics and monitored primarily at **p95** and **p99**.

**Core API endpoints (reads)**

- Targets (from performance spec):
  - p95 ≤ **300 ms** under normal load.
- Alerts:

  - **Warning**:
    - `p95_latency >= 500 ms` for **5 minutes** on any of:
      - `GET /assets`, `GET /assets/{id}`, `GET /listings`, `GET /jobs/{id}`.
  - **Critical**:
    - `p95_latency >= 1000 ms` (1s) for **5 minutes**.

**Core API endpoints (writes)**

- Targets:
  - p95 ≤ **500 ms**.
- Alerts:

  - **Warning**:
    - `p95_latency >= 750 ms` for **5 minutes** on key writes:
      - `POST /dq-runs`, `POST /compliance-runs`, `POST /assets`, `POST /files`.
  - **Critical**:
    - `p95_latency >= 1500 ms` (1.5s) for **5 minutes**.

**p99 latency (global)**

- p99 is noisier but useful for catching tail problems:

  - **Critical**:
    - Global p99 across `/api/v1`:
      - `p99_latency >= 3000 ms` (3s) for **10 minutes**, and
      - `error_rate >= 1%` in the same period.

This combined condition helps avoid alerting solely on rare but harmless outliers.

---

#### 8.3.4 Queue depth & job lag thresholds

We monitor:

- **Queue depth** (number of pending messages/jobs).
- **Job lag** (time spent in `PENDING` state before `RUNNING`).
- **Throughput** (jobs processed per minute) to ensure it aligns with expectations.

**Queue depth**

Example for the main job queue (DQ/compliance):

- **Warning**:
  - `queue_depth >= 2 × expected_baseline` for **10 minutes**.
- **Critical**:
  - `queue_depth >= 5 × expected_baseline` for **10 minutes`, OR
  - `queue_depth >= ABS_MAX_QUEUE_DEPTH` (e.g., 10,000 jobs) at any time.

**Job lag (PENDING → RUNNING)**

Defined as:

```text
job_lag = now - job_created_at (for jobs still PENDING)
```

Monitored via metrics like `job_lag_seconds` or derived from job tables.

- **Warning**:
  - `p95_job_lag >= 10 minutes` for DQ/compliance jobs over **15 minutes**.
- **Critical**:
  - `p95_job_lag >= 30 minutes` over **15 minutes**.

These thresholds align with job throughput targets in the testing strategy; if violated, it suggests insufficient workers, resource saturation, or downstream dependency problems.

**Worker saturation**

Additional alerts:

- Worker CPU > 80% for **15 minutes**.
- Worker error rate > 5% (job failures) for **10 minutes**, excluding user-caused validation failures.

---

#### 8.3.5 Additional resource alerts (infrastructure)

Key infrastructure alerts to support the above SLOs:

- **Database**
  - CPU > 80% for **15 minutes** (warning), > 90% for **15 minutes** (critical).
  - Connection pool exhaustion (e.g., > 90% of max connections used) for **5 minutes**.
  - Slow query alerts (p95 query > 200 ms) for core query classes.

- **Object storage**
  - Error rate for control-plane calls (e.g., metadata, list, head) > 2% for **10 minutes**.

- **Triple store (semantic)**
  - SPARQL error rate > 5% for **10 minutes**.
  - SPARQL p95 latency > 1000 ms for **10 minutes**.

These are typically **warning** alerts that help root-cause API or job issues.

---

#### 8.3.6 Alert routing & escalation procedures

Alerts are classified and routed by **severity**:

- **INFO / NOTICE**
  - Used sparingly for non-urgent but important signals (e.g. early saturation).
  - Route to: shared engineering channel only.
  - No paging.

- **WARNING**
  - Indicates **degraded performance** or **approaching SLO violation**, but not yet severe.
  - Route to:
    - Engineering Slack/Teams channel.
    - Create ticket in issue tracker (optional, auto-created).
  - Response:
    - Investigate during business hours.
    - No immediate on-call wake-up unless persistent or trending worse.

- **CRITICAL**
  - Indicates user-visible outages or major degradation.
  - Route to:
    - On-call engineer pager (PagerDuty/Opsgenie/etc.).
    - Engineering incident channel.
  - Response:
    - On-call must acknowledge within **5 minutes**.
    - Incident is opened with severity level:
      - SEV-1: Widespread outage, major functionality broken (e.g., global error rate > 20%, core workflows unusable).
      - SEV-2: Significant degradation, but partial functionality remains.

**Escalation flow for CRITICAL alerts**

1. **On-call acknowledgment**
   - Within 5 minutes.
   - If unacknowledged, auto-escalate:
     - To secondary on-call.
     - Then to engineering manager, according to escalation policy.

2. **Incident handling**
   - Create an incident record summarizing:
     - Triggering alerts.
     - Impact (which tenants, which workflows).
     - Initial hypotheses.
   - Use runbooks attached to alerts where available (e.g., “Queue depth high” runbook).

3. **Resolution & follow-up**
   - Once metrics return to normal and root cause is addressed:
     - Close alerts and incident.
   - For SEV-1/SEV-2:
     - Conduct a lightweight post-incident review (PIR):
       - Timeline, root cause, fixes.
       - Potential adjustments to thresholds or runbooks.

**Environment-specific behavior**

- Production:
  - All WARNING and CRITICAL alerts enabled (with paging for CRITICAL).
- Staging / perf:
  - Subset of alerts (primarily WARNING-level) for performance testing and pre-prod validation.
  - No paging outside of scheduled test windows.

These alerting thresholds and procedures ensure that:

- Real issues are surfaced quickly.
- Noise is minimized through windows and combined conditions.
- Operators have clear guidance on when and how to respond.

## 9. Entitlements & Access Control

### 9.1 Entitlement expiration handling

Entitlements control tenant access to assets, datasets, or marketplace listings. Each entitlement record includes:

- `status`: `ACTIVE | PENDING | EXPIRED | REVOKED`
- `start_at`: datetime the entitlement becomes effective.
- `end_at`: datetime the entitlement expires (nullable for perpetual access).

This section defines:

- How expiration is detected and applied.
- Auto-revocation procedures.
- Notifications before expiration.
- Grace period and reactivation rules.

---

#### 9.1.1 Expiration detection mechanism

Two complementary mechanisms enforce entitlement expiration:

**A. Scheduled expiration checks (cron job)**

- A background scheduler (e.g., CronJob in Kubernetes or periodic job runner) runs **every 15 minutes**:
  - Queries all entitlements where:
    ```sql
    status = 'ACTIVE' AND end_at IS NOT NULL AND end_at <= now()
    ```
  - Updates their status to `EXPIRED`.
  - Emits audit events and notification triggers.
- The batch job processes entitlements in tenant-scoped batches (e.g., 1000 per tenant per run) to avoid long transactions.

**B. Real-time validation (event-driven / access check)**

- During any entitlement validation (API access, file download, data query):
  - The access layer validates `status = ACTIVE` and `end_at > now()`.
  - If expired, the access request fails immediately with:
    ```json
    { "code": "ENTITLEMENT_EXPIRED", "message": "Access expired on YYYY-MM-DD" }
    ```
  - The entitlement record may be updated asynchronously to `EXPIRED` if not already.

This hybrid approach guarantees:

- **No stale access** even if a cron job is delayed.
- **Predictable consistency** with batch updates for reporting and auditing.

---

#### 9.1.2 Auto-revocation procedure

When an entitlement expires or is explicitly revoked:

1. **Status update**
   - `status` → `EXPIRED` (auto) or `REVOKED` (manual/admin).
   - `revoked_at` timestamp recorded.
   - `revoked_by` recorded for manual revocations.

2. **Access cleanup**
   - The Access Service or Gateway removes associated access tokens or cache entries.
   - For object storage access:
     - Signed URLs, temporary credentials, and access grants are invalidated.
     - If integration with external data plane (e.g., cloud bucket ACLs), revoke ACLs via background task.
   - For compute/data jobs:
     - Any active sessions using the entitlement (e.g., DQ/compliance job reading restricted asset) are terminated gracefully.

3. **Audit trail**
   - An `ENTITLEMENT_EXPIRED` or `ENTITLEMENT_REVOKED` event is written to `audit_events`.
   - Details include:
     - `entitlement_id`, `tenant_id`, `asset_id`, `user_id`, `reason`, `trigger_type = AUTO|MANUAL`.

4. **Cascade updates**
   - Downstream caches or data warehouse records receive an event (via message bus) to update status.
   - If entitlement grants access to multiple assets, individual asset access links are marked inactive.

---

#### 9.1.3 Notification before expiration

Users should be proactively notified before their entitlements expire.

**Notification schedule**

| Time before expiration | Audience             | Channel               | Message purpose                   |
|------------------------|----------------------|------------------------|-----------------------------------|
| 7 days                 | Entitled user(s)     | Email / UI alert       | Reminder: “Access expires soon.” |
| 1 day                  | Entitled user(s)     | Email / UI alert       | Final reminder.                  |
| On expiration          | Owner + Admin        | Email / webhook event  | “Access expired.”                |

Implementation details:

- The notification service runs a **daily job** that queries:
  ```sql
  SELECT * FROM entitlements
  WHERE status = 'ACTIVE'
    AND end_at IS NOT NULL
    AND end_at BETWEEN now() + INTERVAL '1 day' AND now() + INTERVAL '7 days';
  ```
- Each matched record triggers:
  - A templated email.
  - Optional webhook event:
    ```json
    {
      "event": "entitlement.expiring_soon",
      "tenant_id": "uuid",
      "entitlement_id": "uuid",
      "expires_at": "2025-12-01T00:00:00Z"
    }
    ```

- Notification logs are stored for auditability (e.g., in `notification_events` table).

---

#### 9.1.4 Grace period handling

A configurable **grace period** provides continuity after expiration.

- Default grace period: **24 hours** after `end_at`.
- During grace period:
  - The entitlement remains **temporarily valid for read-only operations**.
  - New or write actions (e.g., downloads, purchases, job executions) are **blocked**.
  - `status` remains `ACTIVE`, but `grace_until` field is populated (`end_at + grace_period`).

**After grace period**

- Status automatically transitions to `EXPIRED`.
- Any residual access tokens or sessions are revoked.

**Configuration**

| Tier           | Grace period | Notes                             |
|----------------|-------------:|-----------------------------------|
| Free / Trial   | 0 hours      | No grace period.                  |
| Standard       | 24 hours     | Default.                          |
| Enterprise     | 72 hours     | Customizable via tenant config.   |

---

#### 9.1.5 Recovery & reactivation

If a user or tenant renews or extends an entitlement:

- The system updates:
  - `end_at` → new date.
  - `status` → `ACTIVE`.
  - `grace_until` → recalculated.
- A `ENTITLEMENT_REACTIVATED` event is emitted.
- If the previous entitlement was `EXPIRED` but still within 7 days of expiration:
  - The existing record may be reused (reactivated).
  - Otherwise, a new entitlement is created with a link to the previous one (`previous_entitlement_id`).

Reactivation tests verify:

- Access is restored within 5 minutes (post-cache-refresh).
- Notifications resume using new expiration timelines.

---

#### 9.1.6 Monitoring & reporting

Metrics and alerts:

- `entitlement_expired_total{tenant_id}` — count of expirations.
- `entitlement_reactivated_total{tenant_id}` — count of reactivations.
- `entitlement_expiry_job_duration_seconds` — cron job duration.
- `entitlement_expiry_job_errors_total` — job failures.

Alerting thresholds:

- Failure rate > 5% for the expiration job over 1h → Warning.
- Job runtime > 10 minutes → Performance alert.

Audit reporting:

- Daily report summarizing:
  - Entitlements expired.
  - Notifications sent.
  - Reactivations.

---

With this logic, entitlement expiration is:

- Checked reliably (hybrid event + scheduled model).
- Audited and reversible (reactivation supported).
- Predictable for users via proactive notifications.
- Aligned with system-wide access control and observability mechanisms.

### 9.2 Cross-tenant access audit

The marketplace enables **cross-tenant access** to assets, datasets, and listings. This section specifies:

- Audit events for cross-tenant access.
- Access logging (who accessed what, when, from where).
- Compliance reporting capabilities for cross-tenant access.

Cross-tenant access is defined as any access where:

- `consumer_tenant_id != provider_tenant_id`

even if both tenants are owned by the same organization.

---

#### 9.2.1 Audit model & event types

All cross-tenant access is captured in the **audit_events** table/stream. For each relevant action, we record:

- **Actor context**
  - `actor_user_id`
  - `actor_tenant_id` (consumer)
  - `actor_roles` (at time of action)
- **Target context**
  - `provider_tenant_id`
  - `asset_id`
  - `dataset_id` (if applicable)
  - `listing_id` / `contract_id` / `entitlement_id` (when access is marketplace- or contract-mediated)
- **Action & result**
  - `event_type`
  - `timestamp`
  - `result` (`SUCCESS`, `DENIED`, `ERROR`)
- **Technical metadata**
  - `ip_address`
  - `user_agent`
  - `request_id`
  - `auth_method` (e.g., `JWT`, `API_KEY`)

**Core cross-tenant event types**

At minimum, we emit:

- `CROSS_TENANT_ACCESS_GRANTED`
  - When an entitlement is created or activated that allows cross-tenant access.
  - Includes:
    - `entitlement_id`, `listing_id`, `contract_id`
    - `permissions` (e.g. `READ_METADATA`, `DOWNLOAD`, `RUN_DQ`)
    - `start_at`, `end_at`
- `CROSS_TENANT_ACCESS_USED`
  - When a consumer tenant actually uses an entitlement to:
    - View asset metadata.
    - Download or access data.
    - Trigger DQ/compliance jobs on provider data.
  - Includes:
    - `operation_type` (`READ_METADATA`, `DOWNLOAD_DATA`, `RUN_DQ`, `RUN_COMPLIANCE`, `SPARQL_QUERY`, etc.)
    - `resource_scope` (`ASSET`, `DATASET`, `FILE`, `SEMANTIC_VIEW`)
    - `bytes_transferred` (for downloads) or `rows_estimated` (if available).
- `CROSS_TENANT_ACCESS_DENIED`
  - When a cross-tenant request is blocked due to:
    - Missing or expired entitlement.
    - Insufficient role/permission.
    - Policy or compliance rules.
  - Includes:
    - `deny_reason` (`NO_ENTITLEMENT`, `ENTITLEMENT_EXPIRED`, `INSUFFICIENT_ROLE`, `POLICY_BLOCK`).

Optional additional events:

- `CROSS_TENANT_ACCESS_REVOKED`
  - When an entitlement that previously granted access is revoked or expires (see §9.1 for expiration handling).
- `CROSS_TENANT_JOB_SUBMITTED`
  - Specific to jobs (DQ, compliance) that operate on another tenant’s asset.

All such events are **immutable** and stored in append-only fashion to support forensic and compliance needs.

---

#### 9.2.2 Access logging (who accessed what, when)

Access logging combines:

1. **Audit events (structured, coarse-grained)**
2. **Application logs (technical, fine-grained)**

**Audit events**

- Primary source of truth for “who accessed what, when” at the **business level**.
- For each cross-tenant interaction, record:

  ```json
  {
    "event_type": "CROSS_TENANT_ACCESS_USED",
    "timestamp": "2025-11-22T10:00:00Z",
    "actor_tenant_id": "consumer-tenant-uuid",
    "actor_user_id": "user-uuid",
    "provider_tenant_id": "provider-tenant-uuid",
    "asset_id": "asset-uuid",
    "dataset_id": "dataset-uuid",
    "entitlement_id": "entitlement-uuid",
    "operation_type": "DOWNLOAD_DATA",
    "resource_scope": "FILE",
    "bytes_transferred": 104857600,
    "result": "SUCCESS",
    "ip_address": "203.0.113.10",
    "user_agent": "Chrome/123.0",
    "request_id": "req-abc123"
  }
  ```

- These records are used for:
  - Compliance and data protection reporting.
  - Internal investigations.
  - Tenant-facing access reports.

**Application logs**

- Contain technical details (trace IDs, internal errors, performance).
- Must not contain raw PII or raw data payloads (see PII scrubbing rules).
- Include `trace_id` and `request_id` to correlate with audit events and distributed traces.

**Access paths to audit**

We audit cross-tenant access for all meaningful paths:

- Marketplace UI:
  - Viewing cross-tenant listings and asset details.
  - Initiating access (purchasing / agreeing to contract).
- API:
  - Calls made by SDKs or systems acting on behalf of consumer tenants.
- Data-plane:
  - Download endpoints (where we gate access via entitlements).
  - Proxy queries to remote data stores (if supported in future).

All data-plane access must be mediated by a **control-plane check** that emits the appropriate audit event.

---

#### 9.2.3 Compliance reporting for cross-tenant access

The platform provides **reporting capabilities** on cross-tenant access for:

- Internal compliance teams.
- Tenant admins (provider and consumer).
- External auditors (via exported reports).

**Reporting model**

Cross-tenant access reports are generated from the `audit_events` table/stream, with a focus on:

- `event_type IN ('CROSS_TENANT_ACCESS_GRANTED', 'CROSS_TENANT_ACCESS_USED', 'CROSS_TENANT_ACCESS_DENIED', 'CROSS_TENANT_ACCESS_REVOKED')`
- Time range filters (`event_timestamp BETWEEN ...`).
- Tenant perspective:
  - Provider view (`provider_tenant_id = X`).
  - Consumer view (`actor_tenant_id = X`).

**Example report types**

1. **Provider view: “Who accessed my data?”**

   - Group by:
     - `actor_tenant_id`, `asset_id`.
   - Columns:
     - Consumer tenant.
     - Asset and dataset IDs.
     - Total number of accesses.
     - Total bytes transferred.
     - Access types (read/compliance/DQ).
     - Time of first/last access in the period.

2. **Consumer view: “What data did we access?”**

   - Group by:
     - `provider_tenant_id`, `asset_id`.
   - Columns:
     - Provider tenant.
     - Asset(s) accessed.
     - Entitlement IDs.
     - Access count and types.
     - Contract/listing reference.

3. **Regulatory view: “Cross-tenant access to sensitive data”**

   - Join audit events with:
     - Asset classification (e.g., `SENSITIVE`, `PII`, `PUBLIC`).
     - DQ/compliance status at time of access (if available).
   - Columns:
     - Sensitive assets accessed.
     - Which consumers accessed them.
     - Confirmed presence of valid entitlements at time of access.

**Delivery mechanisms**

- **In-app reports**:
  - Admin UI pages for provider and consumer tenants with filtering and export (CSV/JSON).
- **Scheduled exports** (optional):
  - Daily/weekly/monthly snapshots delivered to secure storage or via email to designated contacts.
- **APIs**:
  - `/api/v1/audit/cross-tenant-access` endpoints allowing tenants to pull their own reports.

---

#### 9.2.4 Retention & privacy constraints

Because cross-tenant access relates to data protection and contractual obligations, audit records are retained longer than typical logs.

**Retention**

- Default retention for cross-tenant access audit events:
  - **At least 1 year**, preferably up to **7 years** depending on:
    - Regulatory needs (e.g., SOC 2, ISO 27001, contractual requirements).
    - Tenant and region-specific policies.

- Older records may be:
  - Archived to cheaper storage (e.g., cold object storage).
  - Kept in a form that is not directly queryable in real-time but accessible for audits.

**Privacy & minimization**

- Audit events store only:
  - Pseudonymous IDs (`user_id`, `tenant_id`, `asset_id`).
  - Minimal contextual metadata (e.g., IP, user agent).
- No raw dataset values or PII content is stored in audit events.

If regulations require **subject-level access reports** (e.g., “Which tenants accessed data about subject X?”):

- This is implemented by:
  - Using subject IDs only as referenced in the underlying data model (not directly logged).
  - Running specialized queries over:
    - Dataset catalog and lineage.
    - Cross-tenant access events tied to those datasets.

---

With this design, cross-tenant marketplace access is:

- Fully auditable at both provider and consumer levels.
- Logically separated between technical logs and compliance-grade audit events.
- Reportable in a way that meets regulatory and contractual obligations without exposing raw data.

## 10. Operations & Runbooks

This system architecture doc defines the *design-time* view of the Interoperable Data Hub.
Day-2 operational behavior (how we run and recover the platform in production) is defined
in a separate runbooks document:

- `Runbooks_and_Operational_Procedures.md`

That document is **normative** for operations and incident response and currently covers:

- Common failures:
  - Database outage / degradation (`RB-DB-001`)
  - Queue backlog / throttling (`RB-QUEUE-001`)
  - Service crash / high error rate (`RB-SVC-001`)
- Deployment procedures:
  - Standard deployments and rollbacks (`RB-DEPLOY-001` and related)
- Data recovery:
  - DB restores, object storage recovery, triple-store rebuilds (`RB-DR-001`)
- Security incidents:
  - Containment, investigation, communication, and recovery (`RB-SEC-001`)

Architecture decisions that affect operability (e.g., observability, failover, data
recovery guarantees) MUST be reflected both here and in the corresponding runbooks so
that design-time and run-time views remain aligned.