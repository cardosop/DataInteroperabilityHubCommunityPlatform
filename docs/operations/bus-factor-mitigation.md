# Bus Factor Mitigation

**Version**: 1.0 | **Owner**: Engineering Leadership

## Critical Subsystems & Backup Owners

| Subsystem | Primary | Backup | Documentation | Last KT Session |
|-----------|---------|--------|---------------|-----------------|
| Fuseki TDB2 (Triple Store) | Semantic Team | Platform Team | `RB-SEM-001` | 2026-Q2 |
| OpenLineage (Marquez) | Data Team | Infra Team | `RB-LINEAGE-001` | 2026-Q2 |
| RLS Engine (PostgreSQL policies) | Security Team | Infra Team | `RB-SEC-004` | 2026-Q2 |
| Vault / AWS Secrets Manager | Infra Team | Security Team | `infrastructure/terraform/` | 2026-Q1 |
| Helm Charts | Infra Team | Platform Team | `helm/` | 2026-Q1 |
| Stripe Billing Pipeline | Billing Team | Platform Team | `RB-BILLING-001` | 2026-Q2 |
| EKS Cluster | Infra Team | Data Team | `infrastructure/terraform/eks.tf` | 2026-Q1 |
| CI/CD Pipeline (GitHub Actions) | Platform Team | Infra Team | `.github/workflows/` | 2026-Q1 |

## Knowledge Transfer Schedule

- **Monthly**: 1-hour deep-dive on rotating subsystem
- **Quarterly**: Backup owner demonstrates ability to handle a simulated incident
- **Onboarding**: New hires spend week 2 pairing with primary owner on their subsystem

## Mitigation Rules

1. No subsystem may have a bus factor of 1 (single person)
2. Every critical subsystem must have a documented runbook (RB-*)
3. Backup owners must have production access and have performed the recovery procedure at least once
4. Knowledge transfer sessions must be documented (notes + recording link)
