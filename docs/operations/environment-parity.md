# Environment Parity: Staging vs Production

**Version**: 1.0 | **Owner**: Infrastructure Engineering

## Infrastructure Comparison

| Component | Staging | Production | Parity |
|-----------|---------|------------|--------|
| DB Engine | PostgreSQL 16.2 | PostgreSQL 16.2 | ✅ |
| K8s Version | EKS 1.30 | EKS 1.30 | ✅ |
| Node Count | 2 (`general-ng`) | 3 (`general-ng`) | ⚠️ 2 vs 3 |
| Node Type | t4g.medium | t4g.large | ⚠️ Smaller instance |
| Replica Count (api) | 1 | 3 | ⚠️ Single vs HA |
| Replica Count (worker) | 1 | 2 | ⚠️ Single vs HA |
| RDS Instance | db.t4g.medium | db.t4g.large | ⚠️ Smaller instance |
| Redis | Single node | Cluster (3 nodes) | ⚠️ No HA in staging |
| Fuseki | Single Fuseki | Standalone (EBS) | ✅ |
| S3 | `hub-files-staging` | `hub-files-production` | ✅ Same config |
| Stripe | Test mode | Live mode | ⚠️ Test vs Live |

## Configuration Parity

| Setting | Staging | Production | Parity |
|---------|---------|------------|--------|
| DEBUG | False | False | ✅ |
| MVP_MODE | True | False | ⚠️ Different |
| STRIPE_TAX_ENABLED | False | True | ⚠️ Different |
| STRIPE_CONNECT_ENABLED | False | True | ⚠️ Different |
| RLS_ENABLED | True | True | ✅ |
| OPENTELEMETRY | True | True | ✅ |

## Intentional Differences

- Staging uses smaller instances to reduce cost (~$X vs ~$Y/month)
- Staging uses Stripe test mode (no real charges)
- MVP_MODE gates non-MVP features in staging for smoke testing
- Staging allows force-approve for compliance gate testing

## Drift Detection

Run `scripts/audit_env_drift.py` monthly to detect configuration drift between environments.
