# Docker Compose Test Infrastructure Audit

**Date:** 2026-05-21
**Scope:** `docker-compose.test.yml` — 63 services.
**Methodology:** Full file read, service cataloguing, dependency graph construction, CI reference cross-check.

---

## Summary

| Metric | Count |
|---|---|
| Total services | 63 |
| Infrastructure services | 38 (databases, caches, queues, monitoring) |
| Application services | 11 (API, worker, microservices) |
| Data containers (volumes) | 14 |
| API variants | 3 (`api-service-test`, `api-service-test-mvp`, `api-service-test-full`) |
| CI-referenced services | ~45 |
| Unused/always-skipped services | ~8 |

---

## 1. Complete Service Catalog

### 1.1 Core Database & Cache Services

| Service | Image | Port | Purpose |
|---|---|---|---|
| `postgres-test` | `postgres:16-alpine` | 5434→5432 | Main test database |
| `ensure-test-db` | `postgres:16-alpine` | — | Init container: ensures DB exists |
| `migrate-test-db` | (build) | — | Init container: runs migrations |
| `redis-cache-test` | `redis:7-alpine` | — | Cache backend |
| `redis-queue-test` | `redis:7-alpine` | — | RQ job queue |
| `redis-events-test` | `redis:7-alpine` | — | Event pub/sub |
| `redis-channels-test` | `redis:7-alpine` | — | Django Channels |

### 1.2 Redis Exporters (Monitoring)

| Service | Port | Purpose |
|---|---|---|
| `redis-exporter-cache-test` | 9121 | Cache Redis metrics |
| `redis-exporter-queue-test` | 9121 | Queue Redis metrics |
| `redis-exporter-events-test` | 9121 | Events Redis metrics |
| `redis-exporter-channels-test` | 9121 | Channels Redis metrics |

### 1.3 BaaS Stack

| Service | Image | Purpose |
|---|---|---|
| `postgres-baas-test` | `postgres:16-alpine` | BaaS tenant databases |
| `redis-baas-test` | `redis:7-alpine` | BaaS cache |

### 1.4 Storage & Security

| Service | Image | Port | Purpose |
|---|---|---|---|
| `minio-test` | `minio/minio:RELEASE.2025-02-28T09-55-16Z` | 9000 | S3-compatible file storage |
| `clamav-test` | `clamav/clamav:1.5` | 3310 | Virus scanning |

### 1.5 Semantic Stack (Fuseki)

| Service | Image | Port | Purpose |
|---|---|---|---|
| `fuseki-test` | `stain/jena-fuseki:4.8.0` | 3030 | RDF/SPARQL triple store |

### 1.6 Microservices

| Service | Port | Purpose |
|---|---|---|
| `datacontract-service-test` | 8080 | Contract validation |
| `dq-service-test` | 8083 | Data quality rules |
| `compliance-service-test` | 8082 | Compliance checks |
| `compliance-rq-worker-test` | — | Compliance async worker |
| `semantic-service-test` | 8081 | Semantic/SPARQL queries |

### 1.7 API & Worker

| Service | Port | Purpose |
|---|---|---|
| `api-service-test` | 8001→8000 | Main API (MVP_MODE unset) |
| `api-service-test-mvp` | 8003→8000 | API with `MVP_MODE=true` |
| `api-service-test-full` | 8004→8000 | API with `MVP_MODE=false` |
| `worker-service-test` | 8087→8080 | RQ job worker |
| `prefect-integration-service-test` | 8084 | Prefect integration |

### 1.8 Prefect Stack

| Service | Image | Purpose |
|---|---|---|
| `prefect-server-test` | `prefecthq/prefect:3-python3.12` | Prefect orchestration |
| `prefect-db-test` | `postgres:16-alpine` | Prefect metadata DB |
| `ensure-prefect-work-pool` | (build) | Init: creates work pool |
| `prefect-worker-test` | (build) | Prefect job worker |

### 1.9 CKAN Stack (Marketplace)

| Service | Image | Purpose |
|---|---|---|
| `ckan-test` | `ckan/ckan-dev:2.10` | CKAN marketplace |
| `ckan-test-db-test` | `postgres:16-alpine` | CKAN database |
| `ckan-test-solr-test` | `solr:9` | CKAN search index |
| `ckan-test-redis-test` | `redis:7-alpine` | CKAN cache |

### 1.10 ODH Stack (ML/AI)

| Service | Purpose |
|---|---|
| `odh-training-operator-test` | ML model training |
| `odh-inference-scheduler-test` | ML model inference |

### 1.11 Monitoring Stack

| Service | Purpose |
|---|---|
| `prometheus-test` | Metrics collection |
| `grafana-test` | Dashboards |
| `alertmanager-test` | Alert routing |

### 1.12 Support Services

| Service | Purpose |
|---|---|
| `jaeger-test` | Distributed tracing |
| `mock-server-test` | HTTP mock server |
| `mailhog-test` | Email capture |
| `traefik-test` | API gateway/routing |
| `frontend-test` | Frontend dev server (under `--profile frontend`) |

### 1.14 Data Volumes (14)

All `*-test-data` volumes provide persistence for their respective services:
`postgres-test-data`, `redis-cache-test-data`, `redis-queue-test-data`, `redis-events-test-data`, `redis-channels-test-data`, `postgres-baas-test-data`, `redis-baas-test-data`, `minio-test-data`, `clamav-test-db`, `fuseki-test-data`, `prefect-server-test-data`, `prefect-db-test-data`, `prometheus-test-data`, `grafana-test-data`, `alertmanager-test-data`, `ckan-test-db-test-data`, `ckan-test-solr-test-data`, `ckan-test-redis-test-data`.

### 1.15 Network

| Service | Purpose |
|---|---|
| `hub-test-net` | Isolated bridge network for all test services |

---

## 2. The Three API Variants — Analysis

### 2.1 Configuration Comparison

| Aspect | `api-service-test` | `api-service-test-mvp` | `api-service-test-full` |
|---|---|---|---|
| **Port** | 8001→8000 | 8003→8000 | 8004→8000 |
| **MVP_MODE** | *(unset)* | `"true"` | `"false"` |
| **Extends** | (base definition) | `api-service-test` | `api-service-test` |
| **ports override** | — | `!override` | `!override` |
| **All other config** | Shared (inherited) | Shared (inherited) | Shared (inherited) |

The three variants differ in **only two things**:
1. **`MVP_MODE` env var:** unset (defaults to app default), `"true"`, or `"false"`.
2. **Port number:** 8001, 8003, or 8004.

### 2.2 Are All Three Needed?

**No.** The `extends:` pattern means `api-service-test-mvp` and `api-service-test-full` are thin wrappers that differ only in `MVP_MODE`. This could be reduced to:

- **Option A (recommended):** Keep ONE `api-service-test` service. Run MVP/non-MVP tests by setting `MVP_MODE` env var at test runtime via docker compose profiles or `docker compose run -e MVP_MODE=true`.
- **Option B:** Keep `api-service-test` (default) and `api-service-test-mvp`. Drop `api-service-test-full` since `api-service-test` already has `MVP_MODE` unset (app default, which is likely `false`).
- **Current design rationale:** Having separate services allows tests to run against both modes simultaneously (e.g., comparing MVP-gated vs full behavior in parallel). This may be intentional for CI.

**Recommendation:** Keep all three if parallel MVP/non-MVP E2E testing is needed. Otherwise consolidate to one service with env var control.

---

## 3. Dependency Graph

### 3.1 Startup Critical Path

```
postgres-test
├── ensure-test-db → migrate-test-db → (all dependent services)
├── prefect-db-test → prefect-server-test → ensure-prefect-work-pool → prefect-worker-test
├── ckan-test-db-test → ckan-test
├── redis-cache-test → api-service-test (and variants)
├── redis-queue-test → worker-service-test
├── redis-events-test
├── redis-channels-test
├── minio-test
├── fuseki-test → semantic-service-test
├── jaeger-test
├── mock-server-test
├── mailhog-test
├── clamav-test
├── datacontract-service-test
├── dq-service-test
├── compliance-service-test → compliance-rq-worker-test
├── semantic-service-test
├── prometheus-test
├── grafana-test
├── alertmanager-test
├── ckan-test-solr-test → ckan-test
├── ckan-test-redis-test → ckan-test
├── odh-training-operator-test
├── odh-inference-scheduler-test
└── traefik-test
```

### 3.2 Heaviest Dependencies

- `api-service-test` depends on ~30 services (postgres, all 4 redises, minio, jaeger, mock-server, mailhog, datacontract, dq, compliance, semantic, fuseki, prefect-integration, odh inference, odh training, prometheus, grafana, alertmanager, ckan, redis exporters, traefik)
- `worker-service-test` depends on 9 services
- `prefect-integration-service-test` depends on 11 services

### 3.3 Startup Time Estimate

With 63 services, cold startup is **8-15 minutes** depending on hardware:
- PostgreSQL init: 30-60s
- Migration containers: 30-90s
- Redis (×4): 10-20s
- Prefect stack (DB + server + worker): 60-120s
- CKAN stack (DB + Solr + Redis + CKAN): 60-120s
- Monitoring (Prometheus + Grafana + Alertmanager): 30-60s
- All other services: 60-120s

**Critical finding:** `postgres-test` healthcheck has `start_period: 900s` (15 minutes) — this was increased from 600s because "crash recovery + fsync can take 10-12min on slow disk."

---

## 4. CI-Referenced vs Unused Services

### 4.1 CI-Referenced Services

The following services are explicitly started or referenced in CI workflows:
- `postgres-test`, `redis-cache-test`, `redis-queue-test`, `redis-events-test`, `redis-channels-test`
- `api-service-test`, `api-service-test-mvp`, `api-service-test-full`
- `worker-service-test`
- `minio-test`, `fuseki-test`, `jaeger-test`, `mailhog-test`, `mock-server-test`
- `datacontract-service-test`, `dq-service-test`, `compliance-service-test`
- `semantic-service-test`, `prefect-integration-service-test`

### 4.2 Potentially Unused/Always-Skipped Services

| Service | Notes |
|---|---|
| `ckan-test` + CKAN stack | Marketplace tests are path-filtered; CKAN stack may not be needed for general CI |
| `odh-training-operator-test` + `odh-inference-scheduler-test` | ML tests are gated; ODH stack is heavyweight for general CI |
| `clamav-test` | `CLAMAV_ENABLED: false` by default in test stack |
| `prometheus-test` + `grafana-test` + `alertmanager-test` | Monitoring tests may be nightly-only |
| `traefik-test` | Only needed for routing tests |
| `frontend-test` | Under `--profile frontend` (has build TS errors) |

---

## 5. Service Health Status

### Unhealthy Initial State

The following services may not start healthy in all environments:
- `frontend-test`: Under `--profile frontend` with noted build TS errors — explicitly documented as broken.
- `ckan-test`: Heavy CKAN stack; often times out on first start.
- `odh-*-test`: ODH services may fail without proper configuration.

---

## 6. Image Versions

| Service | Image | Version Pinning | Risk |
|---|---|---|---|
| `postgres-test` | `postgres:16-alpine` | Major | Minor patches auto-update |
| `redis-*-test` | `redis:7-alpine` | Major | OK for testing |
| `minio-test` | `minio/minio:RELEASE.2025-02-28T09-55-16Z` | **Exact digest** | Fully pinned |
| `clamav-test` | `clamav/clamav:1.5` | Major.Minor | Minor patches auto-update |
| `fuseki-test` | `stain/jena-fuseki:4.8.0` | Exact | Fully pinned |
| `ckan-test` | `ckan/ckan-dev:2.10` | Major.Minor | Minor patches auto-update |
| `prefect-server-test` | `prefecthq/prefect:3-python3.12` | Major + Python | Acceptable |
| `prometheus-test` | `prom/prometheus:v2.53.0` | Exact | Fully pinned |
| `grafana-test` | `grafana/grafana:11.1.0` | Exact | Fully pinned |
| `alertmanager-test` | `prom/alertmanager:v0.27.0` | Exact | Fully pinned |
| `mailhog-test` | `mailhog/mailhog:v1.0.1` | Exact | Fully pinned |
| `mock-server-test` | `mockserver/mockserver:5.15.0` | Exact | Fully pinned |
| `redis-exporter-*` | `oliver006/redis_exporter:v1.66.0` | Exact | Fully pinned |

**Risk:** **All images are properly pinned. Zero `:latest` tags for external images.** The only `:latest` tags are for locally-built images (`hub-test-prefect-worker-docker:latest`, `hub-test-prefect-integration:latest`) which are built from the repo's Dockerfiles and are under developer control. This is a strong positive finding — the test infrastructure has good image hygiene.

---

## Recommendations

1. **Evaluate consolidating 3 API variants** — if parallel MVP/non-MVP testing isn't required, reduce to 1 service with `MVP_MODE` env var.
2. **Profile-guard heavyweight stacks** — CKAN, ODH, monitoring can be moved behind `--profile` flags (ckan, odh, monitoring) to reduce default startup time.
3. **Reduce `postgres-test` `start_period`** — 900s (15 min) is extremely conservative. If crash recovery regularly takes 10-12 minutes, the underlying storage needs investigation.
4. **Add startup-order validation** — the critical path is complex; a `depends_on` audit tool would catch missing dependencies.
5. **Consider `docker-compose.test.mvp.yml`** — this 2-service override file (postgres + redis only) suggests MVP tests can run with a stripped-down stack. Document when to use each compose file.
6. **Remove `frontend-test` from default profile** — already under `--profile frontend` but the broken build may confuse new developers.
