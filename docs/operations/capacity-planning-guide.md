# Capacity Planning Guide — Meshant Hub (280.C.6.2)

**Date:** 2026-05-15  
**Owner:** Platform Engineering  
**Scope:** Production capacity model, scaling thresholds, instance sizing

## 1. Load Model

### 1.1 — Per-Tenant Baseline

| Metric | Small Tenant (<100 assets) | Medium Tenant (100-1K assets) | Large Tenant (>1K assets) |
|---|---|---|---|
| API requests/min | ~200 | ~800 | ~3,000 |
| Search queries/min | ~20 | ~80 | ~300 |
| File uploads/day | ~5 (avg 10MB) | ~20 (avg 50MB) | ~100 (avg 100MB) |
| SPARQL queries/min | ~2 | ~10 | ~40 |
| Compliance scans/week | ~2 | ~5 | ~20 |
| Webhook deliveries/min | ~5 | ~20 | ~80 |
| Peak/average ratio | 3:1 | 4:1 | 5:1 |

### 1.2 — Aggregate Production Load (10 tenants, mixed sizes)

| Resource | Steady State | Peak Burst | Scaling Trigger |
|---|---|---|---|
| API req/s | ~50 | ~250 | >80 req/s sustained for 10m |
| DB connections | ~30 | ~80 | >60 active connections for 5m |
| Redis ops/s | ~500 | ~2,500 | >1,500 ops/s for 5m |
| File upload bandwidth | ~5 MB/s | ~50 MB/s | >20 MB/s for 5m |
| Log volume | ~2 GB/day | ~10 GB/day | >5 GB/day for 2 days |

## 2. Instance Sizing

### 2.1 — Compute (EKS Node Groups)

| Node Group | Instance Type | vCPU | Memory | Desired | Max | Purpose |
|---|---|---|---|---|---|---|
| system-ng | t3.medium | 2 | 4 GB | 3 | 6 | Cluster add-ons (CoreDNS, metrics-server, CSI) |
| app-ng | m6i.xlarge | 4 | 16 GB | 3 | 10 | Django API, frontend, observability sidecars |
| worker-ng | m6i.large | 2 | 8 GB | 2 | 4 | RQ workers (light + heavy), batch jobs |
| gpu-ng | g4dn.xlarge | 4 | 16 GB | 0 | 4 | ML training/inference (scale-up on demand) |

**Sizing rationale:** 1 m6i.xlarge fits ~4 API pods (500m CPU req each) + headroom. 3 nodes = 12 pods, covering 3 API replicas + frontend + observability.

### 2.2 — Database (Aurora PostgreSQL via RDS)

| Environment | Instance | vCPU | Memory | Multi-AZ | Max Connections |
|---|---|---|---|---|---|
| Staging | db.t4g.small | 2 | 2 GB | No | 50 |
| Production | db.r7g.large | 2 | 16 GB | Yes | 200 (via PgBouncer) |

**Connection budget:** PgBouncer pool (defaultPoolSize=10 per pod) × 3 API pods + 2 worker pods = 50 effective connections. 200 PostgreSQL max_connections provides 4× headroom.

### 2.3 — Cache (ElastiCache Redis)

| Environment | Instance | Multi-AZ | Instances |
|---|---|---|---|
| Staging | cache.t4g.micro | No | 1 (collapsed) |
| Production | cache.r7g.large | Yes | 4 (cache, queue, events, channels) |

### 2.4 — Object Storage (S3)

| Bucket Class | Lifecycle | Versioning | Expected Size (Year 1) |
|---|---|---|---|
| files (hot) | → IA after 90 days | Yes | ~500 GB |
| logs | → Glacier after 30 days | No | ~200 GB |
| traces | → Expire after 14 days | No | ~50 GB |
| backups | → IA after 30 days, Glacier after 90 days | Yes | ~1 TB |

## 3. Scaling Thresholds

### 3.1 — Horizontal Pod Autoscaling (HPA)

| Service | Metric | Scale-Up Threshold | Scale-Down Threshold | Min/Max Replicas |
|---|---|---|---|---|
| api-service | CPU >70% OR req/s >80 | Sustained 5m | Sustained 10m below 30% | 3/10 |
| worker-light | Queue depth >100 | Sustained 2m | Sustained 5m at <10 | 3/8 |
| worker-heavy | Queue depth >10 | Sustained 2m | Sustained 5m at <2 | 2/4 |
| frontend | CPU >60% | Sustained 3m | Sustained 10m below 20% | 2/6 |

### 3.2 — Cluster Autoscaling (Karpenter / Cluster Autoscaler)

| Node Group | Scale-Up Trigger | Cooldown |
|---|---|---|
| app-ng | Pending pods for >60s | 5 min |
| worker-ng | Pending pods for >60s | 5 min |
| gpu-ng | Manual only | N/A |

### 3.3 — Database Scaling

| Trigger | Action | Lead Time |
|---|---|---|
| CPU >70% sustained for 30m | Manual upgrade to next instance class | 10 min (Aurora modification) |
| Storage >80% allocated | Increase allocated storage by 20% | Auto (Aurora auto-scaling) |
| Connection count >80% of max | Add PgBouncer replicas | 5 min (Helm upgrade) |

### 3.4 — Redis Scaling

| Trigger | Action | Lead Time |
|---|---|---|
| Cache hit rate <80% | Increase maxmemory or add read replicas | 10 min |
| Evictions >0/sec sustained | Increase maxmemory | 5 min |
| CPU >70% sustained for 5m | Upgrade to next instance class | 15 min (ElastiCache modification) |

## 4. Capacity Planning Cadence

| Frequency | Activity | Owner |
|---|---|---|
| Weekly | Review resource dashboards (CPU, memory, disk, connections) | Platform |
| Monthly | Trend analysis: project 3-month growth from 4-week slope | Platform |
| Quarterly | Full capacity review: instance sizing, scaling thresholds, cost optimization | Platform + Finance |
| Pre-launch | Dry-run peak load test at 2× expected load | Platform |

## 5. Cost Model (Monthly Estimate — 10 Tenants)

| Resource | Monthly Cost | % of Total |
|---|---|---|
| EKS (4 node groups) | ~$800 | 25% |
| RDS (db.r7g.large, Multi-AZ) | ~$500 | 16% |
| ElastiCache (4× r7g.large) | ~$600 | 19% |
| S3 (1.5 TB) | ~$50 | 2% |
| NAT Gateways (3) | ~$100 | 3% |
| ALB/NLB | ~$100 | 3% |
| CloudWatch + other | ~$200 | 6% |
| Reserve/savings plan discount | -$400 | -12% |
| **Total (estimated)** | **~$1,950/month** | |

Cost per tenant: ~$195/month at 10 tenants. Target: <$100/tenant at 50 tenants (economies of scale on shared infra).
