# Environment Differences: Staging vs Production

**Version**: 1.0 | **311.1**: Sprint 1 — G1 Staging .env parity

## Intentional Differences

| Variable | Staging Value | Production Value | Reason |
|----------|--------------|------------------|--------|
| `DEBUG` | `False` | `False` | Same |
| `ENVIRONMENT` | `staging` | `production` | Different by design |
| `MVP_MODE` | `true` | `false` | Staging tests MVP gating |
| `STRIPE_TAX_ENABLED` | `false` | `true` | No tax in staging |
| `STRIPE_CONNECT_ENABLED` | `false` | `true` | Connect disabled in staging |
| `SECRET_KEY` | Staging key | Production key | Separate keys |
| `JWT_SECRET_KEY` | Staging key | Production key | Separate keys |
| `RDS_INSTANCE_IDENTIFIER` | `meshant-staging-postgres` | `meshant-production-postgres` | Different instances |
| `GUNICORN_WORKERS` | `3` | `9` | Smaller staging |

## Backfill Required

Missing variables from production template that need staging defaults:
- AWS KMS key IDs (staging uses separate keys)
- Production-only Stripe IDs (staging uses test mode)
- Sentry DSNs (staging points to separate project)
- OTLP exporter endpoints (different collectors)

Run `scripts/diff_env_vars.sh` to check current parity percentage.
