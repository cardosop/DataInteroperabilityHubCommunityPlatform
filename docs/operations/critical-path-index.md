# Critical Path Index

**Version**: 1.0 | **Owner**: Infrastructure Engineering

## Critical Subsystems

| Subsystem | Runbook | ADR | Primary | Backup |
|-----------|---------|-----|---------|--------|
| RDS PostgreSQL | `RB-DR-001` | `docs/adr/api-surface/` | Infra Team | Platform Team |
| Redis (Cache + Queue) | `RB-SEC-005` | — | Infra Team | Data Team |
| Fuseki TDB2 | `RB-SEM-001` | — | Semantic Team | Platform Team |
| Stripe Billing | `RB-BILLING-001` | `docs/adr/business-rules/` | Billing Team | Platform Team |
| RLS Engine | `RB-SEC-004` | — | Security Team | Infra Team |
| EKS Cluster | `RB-OPS-001` | `docs/adr/api-surface/` | Infra Team | Data Team |
| CI/CD Pipeline | `docs/operations/production-deployment-runbook.md` | — | Platform Team | Infra Team |
| OpenLineage (Marquez) | `RB-LINEAGE-001` | — | Data Team | Infra Team |
| Compliance Service | `RB-COMP-001` | `docs/adr/compliance/discovery/` | Compliance Team | Platform Team |
| DQ Service | `RB-DQ-001` | `docs/adr/business-rules/` | DQ Team | Data Team |
| Semantic Service | `RB-SEM-001` | — | Semantic Team | Platform Team |
| Email (SES) | `docs/operations/email-deliverability.md` | — | Platform Team | Infra Team |

## Non-Critical Subsystems

| Subsystem | Runbook | Impact if down |
|-----------|---------|---------------|
| Observability (Prometheus) | — | No alerting; ops blind spot |
| Grafana Dashboards | — | No dashboards; ops use raw Prometheus |
| BaaS API | `RB-BAAS-001` | External developer access paused |
| ML Inference | `RB-ML-001` | ML predictions paused |
| Data Mesh Domains | `RB-MESH-001` | Domain management paused |
| Marketplace Sync | `RB-MKT-001` | External marketplace sync paused |
