# Infrastructure HA / SPOF Verification — Meshant Platform

**Last updated:** 2026-05-15

## A.4.1 — Redis Sentinel / HA

**Status:** ✅ ElastiCache replication groups with Multi-AZ. Sentinel not needed.

### Current State
- `infrastructure/terraform/modules/elasticache/main.tf`: 4 Redis 7.1 replication groups (cache, channels, events, queue)
- `multi_az_enabled`: true (variables.tf:27)
- Automatic failover: ElastiCache promotes replica to primary within 60s
- Recovery target: <30s (ElastiCache SLA)

### Failover Test Procedure
```bash
# 1. Identify current primary
aws elasticache describe-replication-groups --replication-group-id meshant-staging-cache \
  --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint' --profile staging

# 2. Trigger failover (reboot primary with failover)
aws elasticache reboot-cache-cluster --cache-cluster-id <primary-node-id> \
  --engine redis --no-cache-cluster-id-needed --profile staging

# 3. Verify recovery time
# Monitor: aws elasticache describe-events --source-type replication-group
```

## A.4.2 — PgBouncer HA

**Status:** ⚠️ Single instance on staging (replicaCount=1). Multi-instance documented.

### Current State
- `helm/values.staging.yaml`: `replicaCount: 1`
- Single t3.large node — no headroom for surge pods
- `strategy: Recreate` (not RollingUpdate)

### HA Configuration
```yaml
# Production: 2+ PgBouncer instances behind internal LB
pgbouncer:
  replicaCount: 2  # Minimum 2 for HA
  podAntiAffinity:
    requiredDuringScheduling:
      - topologyKey: topology.kubernetes.io/zone
  service:
    type: ClusterIP
    sessionAffinity: None
  readinessProbe:
    tcpSocket:
      port: 6432
    initialDelaySeconds: 5
    periodSeconds: 10
```

## A.4.3 — PostgreSQL Read Replicas

**Status:** ✅ RDS Multi-AZ enabled. Read replica URL configured. Django router not implemented.

### Current State
- `infrastructure/terraform/modules/rds/main.tf:128`: `multi_az = var.multi_az`
- `DATABASE_REPLICA_URL` env var configured (main.tf:269)
- RLS role verification on replica (main.tf:268-280)

### Django Read Routing (Pending)
```python
# hub/settings.py
DATABASES = {
    'default': {...},  # Primary (writes)
    'replica': {       # Replica (reads)
        'HOST': os.environ['DATABASE_REPLICA_URL'],
        ...
    },
}
DATABASE_ROUTERS = ['hub.db_router.PrimaryReplicaRouter']
```

## A.4.4 — SPOF Verification Report

### Service Instance Audit (staging)

| Service | Replicas | Multi-AZ | SPOF? | Notes |
|---|---|---|---|---|
| **API (Gunicorn)** | 1 (staging) / 3 (prod values) | — | No (prod) | `replicaCount: 3` in values.yaml |
| **Worker (RQ)** | 1 (staging) / 3 (prod values) | — | No (prod) | `replicaCount: 3` |
| **Compliance Worker** | 1 (staging) / 2 (prod values) | — | No (prod) | `replicaCount: 2` |
| **DQ Service** | 1 (staging) / 1 (prod values) | — | Yes | Single-replica |
| **Semantic Service** | 1 (staging) / 1 (prod values) | — | Yes | Single-replica |
| **Prefect Server** | 1 (staging) / 1 (prod values) | — | Yes | Stateful — single replica by design |
| **Prefect Worker** | 0 (staging) / 2 (prod values) | — | No (prod) | `replicaCount: 2` |
| **Fuseki** | 1 (staging) / 1 (prod values) | — | Yes | TDB2 file-locked — single replica by design |
| **PgBouncer** | 1 (staging) / 1 (prod values) | — | Yes | Single instance |
| **Traefik** | 1 (staging) / 2 (prod values) | — | No (prod) | `replicaCount: 2` |
| **Redis (×4)** | ElastiCache Multi-AZ | ✅ | No | Automatic failover |
| **PostgreSQL** | RDS Multi-AZ | ✅ | No | Multi-AZ with automatic failover |
| **MinIO** | 1 (staging) / 1 (prod values) | — | Yes | Single instance |

### SPOFs Identified (5)

| Service | Risk | Mitigation |
|---|---|---|
| DQ Service | Low | Stateless — K8s restarts in <30s |
| Semantic Service | Low | Stateless — K8s restarts in <30s |
| Prefect Server | Medium | Stateful — must be single-replica (orchestrator) |
| Fuseki | Medium | TDB2 file-locked — must be single-replica |
| PgBouncer | High | Connection pool SPOF — needs 2+ instances behind LB |

### Recommended Actions (Priority Order)
1. **PgBouncer**: bump to 2 replicas with podAntiAffinity (A.4.2) — highest impact SPOF
2. **DQ Service**: bump to 2 replicas (low effort, low risk)
3. **Semantic Service**: bump to 2 replicas (low effort, low risk)
4. **Prefect Server**: accept single-replica (stateful orchestrator — documented risk)
5. **Fuseki**: accept single-replica (TDB2 constraints — documented risk)
