# Runbook — Phase 232 RoPA (`/api/v1/ropa/*`)

## Symptoms

- Alert **Phase232Ropa5xxRate** or export failures from RoPA generation.

## Checklist

1. Verify RoPA output S3 bucket credentials and KMS permissions.
2. Check `ropa` job handlers and regulation registry JSON/YAML load errors.
3. Confirm worker can reach Postgres with `meshant_admin` only for cross-tenant cron, API paths with RLS for tenant views.

## Escalation

- Platform storage on-call if bucket policy drift; compliance-platform for business logic.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
