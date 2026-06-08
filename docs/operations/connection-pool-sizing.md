# Connection Pool Sizing

**Date:** 2026-05-20
**Owner:** Platform Engineering
**Last reviewed:** 2026-05-20

## 1. Current Connection Counts

| Component | Connections | Notes |
|---|---|---|
| Django API (gunicorn, 3 workers × 2 threads) | 6–54 | Default `CONN_MAX_AGE=600`; peak at 6 per worker when idle, up to 9 per thread under load. With 3 replicas: 3×3×6 = 54 max. |
| Django Worker (RQ, 2 workers × 1 thread) | 2–6 | Heavy workers single-threaded; light workers may use 2 threads. |
| dlt pipelines (data movement) | 1–15 | One connection per active pipeline; peak when all 15 scheduled ingestions run concurrently. |
| PgBouncer (transaction mode) | 0 | PgBouncer itself holds no persistent connections; pools client connections transparently. |
| Management commands | 0–3 | Ephemeral; `migrate`, `reconcile_stripe`, `enforce_audit_retention` each open one connection. |
| **Total (worst-case)** | **~78** | 54 Django + 15 dlt + 6 worker + 3 management = ~78 |

## 2. PostgreSQL Configuration

```
max_connections = 100
superuser_reserved_connections = 3
```

**Effective:** 97 connections available for application use.

**Headroom:** 97 − 78 = 19 connections (20% headroom at peak).

### Shared buffers and work_mem

```
shared_buffers = 256MB            # 25% of instance RAM (1GB)
work_mem = 4MB                    # per-operation sort memory
maintenance_work_mem = 64MB       # VACUUM, CREATE INDEX
effective_cache_size = 768MB      # 75% of RAM for planner
```

## 3. PgBouncer Pool Configuration

| Setting | Value | Rationale |
|---|---|---|
| `default_pool_size` | 20 | Each API pod connects through PgBouncer; 20 server-side connections per pool is generous for 2–6 concurrent queries per pod. |
| `max_client_conn` | 100 | Matches PostgreSQL `max_connections`. |
| `pool_mode` | `transaction` | Required when `CONN_MAX_AGE=0` with PgBouncer. Each transaction gets a fresh backend connection; no session state leaks. |
| `reserve_pool_size` | 5 | Emergency headroom; activated when `default_pool_size` is exhausted. |
| `reserve_pool_timeout` | 3 | Seconds before reserve pool activates. |
| `server_idle_timeout` | 600 | 10 min — matches `CONN_MAX_AGE`. |

### PgBouncer connection flow (transaction mode)

```
Client (Django) ──► PgBouncer ──► PostgreSQL
                     │
                     │ pool of 20 server connections
                     │ shared across all clients
                     │
Client connects → PgBouncer assigns a free server connection
Transaction runs → server connection returned to pool
Client disconnects → PgBouncer holds the server connection for reuse
```

## 4. Headroom Calculation

| Scenario | Application Connections | PostgreSQL Max | Headroom |
|---|---|---|---|
| Idle (3 API pods × 2 conn each) | 6 | 97 | 91 (94%) |
| Normal load (3 pods × 6 conn + 5 dlt) | 23 | 97 | 74 (76%) |
| Peak load (3 pods × 18 conn + 15 dlt + 3 worker + 3 mgmt) | 78 | 97 | 19 (20%) |
| Overload (> 97 connections) | >97 | 97 | **Exhausted** — new connections rejected |

**Alert threshold:** >80 connections active for >5 min fires `HubPostgresConnectionsHigh` (P2).

## 5. Scaling Guidance

### When to increase `max_connections`

- Sustained `HubPostgresConnectionsHigh` alerts
- `pg_stat_activity` shows >80 non-idle connections for >30 min
- Application logs show `FATAL: sorry, too many clients already`
- **Before increasing:** Verify PgBouncer is properly pooling. Most "too many clients" issues are fixed by tuning PgBouncer, not by raising `max_connections`.

### When to increase `default_pool_size`

- PgBouncer logs show `no usable server connection` or `cl_waiting` > 0
- `PgBouncerPoolSaturation` alert fires (active/total > 90%)
- Application latency increases without CPU/memory pressure on PostgreSQL

### Horizontal scaling

| Component | Current | Scale To | Trigger |
|---|---|---|---|
| API pods | 3 | 6 | CPU >70% or request queue depth >10 |
| Worker pods (heavy) | 2 | 4 | `job_critical` queue depth >10 |
| Worker pods (light) | 2 | 4 | `job_default` + `job_low` queue depth >100 |
| PgBouncer replicas | 1 | 2 | Single point of failure; add for HA |

## 6. Connection Monitoring Queries

### Current connections by state

```sql
SELECT state, COUNT(*) AS count
FROM pg_stat_activity
WHERE datname = 'meshant'
GROUP BY state
ORDER BY count DESC;
```

### Connections by application

```sql
SELECT application_name, COUNT(*) AS count
FROM pg_stat_activity
WHERE datname = 'meshant' AND state != 'idle'
GROUP BY application_name
ORDER BY count DESC;
```

### Long-running queries (>5 min)

```sql
SELECT pid, now() - xact_start AS duration, state, query
FROM pg_stat_activity
WHERE datname = 'meshant'
  AND xact_start < now() - interval '5 minutes'
  AND state != 'idle'
ORDER BY xact_start;
```

### PgBouncer pool status

```sql
-- Run against PgBouncer admin database
SHOW POOLS;
SHOW STATS;
SHOW CLIENTS;
```

## 7. Related

- **PostgreSQL runbook:** `docs/runbooks/postgres-runbook.md`
- **PgBouncer alerts:** `monitoring/prometheus/alerts/pgbouncer.yml`
- **Database dashboard:** `monitoring/grafana/dashboards/database-performance.json`
- **Capacity planning:** `docs/operations/capacity-planning-guide.md`
- **Disaster recovery:** `docs/operations/disaster-recovery-policy.md`

## 8. Maintenance

- **Owner:** Platform Engineering
- **Last reviewed:** 2026-05-20
- **Next review:** 2026-08-18
