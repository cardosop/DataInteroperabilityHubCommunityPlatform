# Runbook — Phase 232 DPIA register (`/api/v1/dpia/*`)

## Symptoms

- Alert **Phase232DpiaRegister5xxRate** or Grafana **Phase 232 — DPIA register** anomalies.

## Checklist

1. Validate recursive `derived_from` integrity (no cross-tenant parents); check recent `dpia` migrations.
2. Confirm RLS policies enabled for `dpia` tables and middleware sets GUC per request.
3. Review serializer validation errors in logs for nested assessments.

## Escalation

- Compliance-platform + DBA if RLS or migration-related.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
