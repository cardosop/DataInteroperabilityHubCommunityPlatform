# Wave 4 Maturity Planning — Meshant Platform

**Last updated:** 2026-05-15 | **Target:** Month 3-6 (P3)

## D.1 — Multi-Region / Cross-AZ Failover

**Status:** ⏭️ Terraform foundation exists. Cross-AZ config for RDS (MultiAZ=true) and ElastiCache (replication group with multi-AZ). Multi-region active-passive not implemented.

### Existing Infrastructure
- RDS: `infrastructure/terraform/modules/rds/main.tf` — `multi_az = true`
- ElastiCache: `infrastructure/terraform/modules/elasticache/main.tf` — replication group

### Remaining for Multi-Region
1. Deploy secondary region (eu-west-1) with read replicas
2. Configure Route 53 latency-based routing or failover records
3. S3 cross-region replication for backups + file storage
4. Aurora Global Database for <1s cross-region replication (future)

## D.2 — Automated Canary Deployments

**Status:** ⏭️ Not implemented. Helm supports phased rollouts via `values.f5-rollout-phase{1,2,3}.yaml` but no automated canary analysis.

### Implementation Path
1. Argo Rollouts for progressive delivery
2. Canary metrics: error rate, p95 latency, CPU
3. Auto-promote on success, auto-rollback on threshold breach
4. Integrate with existing `helm-rollback.yml` workflow

## D.3 — Noisy-Neighbor Detection

**Status:** ⏭️ Per-tenant monitoring not yet configured. Prometheus metrics are aggregated across all tenants.

### Implementation Path
1. Add `tenant_id` label to all Prometheus metrics
2. Per-tenant dashboards: API calls, error rate, latency, storage
3. Alert: any single tenant consuming >30% of cluster resources

## D.4 — PostgreSQL Read Replica

**Status:** ⏭️ Not configured. RDS has multi-AZ but no read replica. Application reads all go to primary.

### Implementation Path
1. Create RDS read replica in same region
2. Configure Django DATABASES router: writes→primary, reads→replica
3. Add `POSTGRES_READ_REPLICA_HOST` to helm values

## D.5 — Per-Tenant Cost Attribution

**Status:** ⏭️ Not configured. AWS cost allocation tags not applied to tenant-scoped resources.

### Implementation Path
1. Tag all resources with `tenant_id` and `environment` tags
2. Enable AWS Cost Explorer + cost allocation tags
3. Monthly per-tenant cost report → chargeback/showback

## D.6 — Screen-Reader Audit (NVDA/VoiceOver)

**Status:** ⏭️ Not executed. a11y infrastructure exists (axe-core E2E tests, skip links, ARIA labels, focus management). Manual screen-reader audit requires human tester.

### Test Plan
1. NVDA + Chrome on Windows: 10 critical journeys
2. VoiceOver + Safari on macOS: 10 critical journeys
3. Document P0 issues, fix, re-audit

## D.7 — Redis Failover Strategy

**Status:** ⏭️ ElastiCache replication group provides instance-level failover. No Redis Cluster or Sentinel mode.

### Current State
- Redis instances: cache, channels, events, queue (4 separate ElastiCache instances)
- No cross-region Redis replication
- Failover: ElastiCache auto-failover to replica (Multi-AZ)

## D.8 — Business Continuity Plan (BCP)

**Status:** ⏭️ Created 2026-05-15. No existing BCP document found.

### Maximum Acceptable Outage (MAO)
| Service | MAO | RPO | RTO |
|---|---|---|---|
| API / Frontend | 4 hours | 5 min | 30 min |
| Marketplace Payments | 2 hours | 0 (Stripe queue) | 15 min |
| Data Ingestion/Export | 24 hours | 1 hour | 4 hours |
| Semantic (SPARQL) | 8 hours | 1 hour | 30 min |
| Compliance Scans | 24 hours | 1 hour | 4 hours |

### Recovery Priority Order
1. API + Frontend (core platform)
2. Marketplace + Payments (revenue)
3. Database (all services depend on it)
4. Redis (sessions, queue, cache)
5. Semantic / SPARQL
6. Worker / Async processing
7. Observability (Grafana, Prometheus, Alertmanager)
8. Scheduled ingestion/export
9. Prefect workflows

### Stakeholder Communication Plan
- **SEV1**: CEO + CTO + VP Eng notified within 15 min via PagerDuty
- **SEV2**: VP Eng + Product Owner notified within 30 min via Slack
- **Status page**: `meshant-internal.example.com` updated within 15 min of incident declaration
- **Customer comms**: Template in `INCIDENT_RESPONSE.md`

## D.9 — Vendor Lock-in Assessment

**Status:** ⏭️ Created 2026-05-15.

### AWS Service Dependency Inventory

| AWS Service | Meshant Usage | Open-Source Alternative | Migration Effort |
|---|---|---|---|
| RDS (PostgreSQL) | Primary database | Self-hosted PostgreSQL | Low (2 weeks) |
| ElastiCache (Redis) | Cache + queue | Self-hosted Redis | Low (1 week) |
| S3 | File storage | MinIO (already in staging) | Low (1 week) |
| SES | Email | SendGrid, Mailgun | Medium (2 weeks) |
| EKS | Kubernetes | Self-managed K8s (kubeadm) | High (4 weeks) |
| ECR | Container registry | Harbor, Docker Hub | Low (1 week) |
| ACM | TLS certificates | cert-manager + Let's Encrypt | Low (1 week) |
| Route 53 | DNS | Cloudflare, self-hosted DNS | Medium (2 weeks) |
| IAM | AuthN/AuthZ | Keycloak, Vault | High (4 weeks) |
| CloudWatch | Logs + metrics | Loki + Grafana (already used) | Low (1 week) |
| Stripe (3rd party) | Payments | Adyen, Braintree | High (6 weeks) |

### Migration Feasibility
- **Compute (EKS→self-managed K8s)**: Feasible. AWS-specific: IRSA, EBS CSI driver, ALB Ingress Controller. Replacements: service accounts, local CSI, nginx ingress.
- **Database (RDS→self-hosted)**: Feasible. AWS-specific: automated backups, Multi-AZ. Replacements: pgBackRest, Patroni for HA.
- **Storage (S3→MinIO)**: Already tested in staging. Migration: 1 week.
- **Email (SES→SendGrid)**: SMTP abstraction layer exists. Migration: 2 weeks.

## D.10 — Bus Factor Assessment

**Status:** ⏭️ Created 2026-05-15.

### Single-Knowledge-Owner Systems

| System | Primary Owner | Backup Owner | Documentation Quality | Risk |
|---|---|---|---|---|
| Stripe Connect integration | (unknown) | — | `docs/runbooks/vendor-failure-stripe.md` | Medium |
| Prefect workflow orchestration | (unknown) | — | `runbooks/prefect-runbook.md` | Low |
| Fuseki / SPARQL engine | (unknown) | — | `docs/runbooks/semantic-degraded.md` | Low |
| OpenLineage integration | (unknown) | — | `runbooks/RB-DB-001.md` | Low |
| CKAN connector | (unknown) | — | `docs/runbooks/warehouse-connectivity.md` | Medium |
| Webhook key rotation | (unknown) | — | `docs/runbooks/webhook-key-rotation.md` | Low |

**Risk ratings:**
- **Low**: Runbook exists + at least 1 backup engineer can recover.
- **Medium**: Runbook exists but backup engineer not confirmed.
- **High**: No runbook + single owner.

### Cross-Training Schedule
1. Stripe Connect → cross-train 1 engineer (Week 1-2)
2. CKAN connector → cross-train 1 engineer (Week 3-4)
3. All other systems → runbook review session (Week 1)

## D.11 — Database Migration Squash

**Status:** ✅ NOT NEEDED (verified 2026-05-15).

`scripts/check_migration_count.py` audit:
- 39 Django apps audited
- Max migrations: 78 (well below 200 threshold)
- **Zero violations** — no squash required

**Recommendation:** Re-run audit quarterly. Threshold: trigger squash when any app exceeds 200 migrations.
