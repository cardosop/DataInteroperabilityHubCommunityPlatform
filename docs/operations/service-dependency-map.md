# Service Dependency Map — Meshant Platform

**Last updated:** 2026-05-15
**Audience:** Platform Engineering, SRE, On-call rotation

## Core Service Dependencies

```
                        ┌──────────────────┐
                        │   Traefik (LB)    │
                        │   :80 / :443      │
                        └──────┬───────────┘
                               │ routes to
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌──────────┐        ┌──────────┐         ┌──────────┐
   │ hub-api  │        │ frontend │         │  fuseki  │
   │  :8000   │        │  :5173   │         │  :3030   │
   └────┬─────┘        └──────────┘         └────┬─────┘
        │                                        │
        │ ┌──────────── data plane ────────────┐ │
        │ │                                   │ │
        ▼ ▼                                   ▼ ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ Postgres │  │  Redis   │  │  MinIO   │  │ PgBouncer│
   │  :5432   │  │ :6379    │  │ :9000    │  │  :6432   │
   └──────────┘  └──────────┘  └──────────┘  └──────────┘
        │              │
    ┌───┴──────────────┴───┐
    │  Redis instances:     │
    │  - cache  (:6379)     │
    │  - channels           │
    │  - events             │
    │  - queue              │
    └───────────────────────┘
```

## Async Workers & Orchestration

```
   ┌──────────┐     ┌──────────────────┐
   │ hub-api  │────▶│ redis-queue      │
   │ (enqueue)│     │ (rq task queue)  │
   └──────────┘     └────────┬─────────┘
                             │ pick up
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐  ┌──────────┐  ┌──────────────┐
       │  worker  │  │compliance│  │prefect-worker│
       │ (rq)     │  │-rq-worker│  │              │
       └────┬─────┘  └────┬─────┘  └──────┬───────┘
            │             │               │
            └─────────────┼───────────────┘
                          │ reads/writes
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
       ┌──────────┐           ┌──────────────┐
       │ Postgres │           │  Prefect DB   │
       └──────────┘           │  (postgres)   │
                              └──────────────┘

   ┌──────────────────┐
   │ prefect-server   │──▶ prefect-db (postgres)
   │ prefect-integration│
   └──────────────────┘
```

## Semantic / SPARQL Layer

```
   ┌──────────┐     SPARQL     ┌──────────┐
   │ hub-api  │───────────────▶│  fuseki  │
   └──────────┘                │  :3030   │
        │                      └────┬─────┘
        │ RDF ingest                 │ reads TDB
        ▼                            ▼
   ┌──────────┐               ┌──────────┐
   │ semantic │──────────────▶│ fuseki   │
   │ service  │   SPARQL      │ TDB2 DB  │
   └──────────┘               └──────────┘
```

## Observability Stack

```
   All services ──▶ OTEL Collector ──▶ Jaeger (traces)
                 ──▶ Prometheus    ──▶ Grafana (metrics)
                 ──▶ Loki          ──▶ Grafana (logs)
                 ──▶ Alertmanager  ──▶ PagerDuty (alerts)
```

## Failure Domains & Impact

| Dependency | Failure Impact | Graceful Degradation |
|---|---|---|
| **Postgres** | All CRUD operations fail. API returns 503. | Read-only cached responses from Redis for 30s TTL. Admin panel shows "DB Unavailable" banner. |
| **Redis cache** | Cache misses on all reads. Latency increases 2-5x. | Direct Postgres reads (auto-fallback in `django-redis` with `IGNORE_EXCEPTIONS=True`). |
| **Redis queue** | Async tasks (DQ runs, compliance scans, webhook delivery) stall. | Tasks queued in Postgres fallback table. Processed when Redis recovers within 5 min. |
| **Redis channels** | Real-time notifications (WebSocket) drop. | Polling fallback via REST polling every 30s. |
| **Fuseki** | SPARQL queries fail. Semantic features unavailable. | Semantic API returns 503 with `Retry-After` header. Non-semantic APIs unaffected. |
| **PgBouncer** | Connection pool unavailable — Postgres connections spike. | Django falls back to direct Postgres connection (settings.DATABASES router). |
| **Traefik** | All inbound traffic drops. | N/A — single point of ingress. Mitigation: health checks restart Traefik automatically. |
| **Prefect Server** | Scheduled workflows (ingestion, export) pause. | Manually trigger workflows via `datahub scheduled-ingestion trigger`. |
| **MinIO** | File uploads/downloads fail. | Uploads queued in `django-storages` fallback. Downloads return 503. |

## Service-to-Port Reference

| Service | Port | Protocol |
|---|---|---|
| Traefik | 80, 443 | HTTP, HTTPS |
| hub-api | 8000 | HTTP (Gunicorn) |
| frontend | 5173 | HTTP (Vite dev) |
| fuseki | 3030 | HTTP |
| postgres | 5432 | TCP (PostgreSQL) |
| pgbouncer | 6432 | TCP (PostgreSQL wire) |
| redis-cache | 6379 | TCP (Redis) |
| redis-queue | 6380 | TCP (Redis) |
| redis-channels | 6381 | TCP (Redis) |
| redis-events | 6382 | TCP (Redis) |
| minio | 9000 | HTTP (S3 API) |
| jaeger | 16686 | HTTP (UI) |
| prometheus | 9090 | HTTP |
| grafana | 3000 | HTTP |
| alertmanager | 9093 | HTTP |
| prefect-server | 4200 | HTTP |
| prefect-db | 5433 | TCP (PostgreSQL) |
