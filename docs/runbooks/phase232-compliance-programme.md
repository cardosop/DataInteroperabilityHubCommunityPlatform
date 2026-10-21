# Runbook — Phase 232 compliance runs (`/api/v1/compliance/*`)

## Symptoms

- Alert **Phase232ComplianceRuns5xxRate** or dashboard **Phase 232 — Compliance runs** shows elevated 5xx.

## Checklist

1. Inspect compliance worker queue / RQ (or Celery) for stuck jobs; retry dead-letter paths per `docs/TEST_EXECUTION_PLAN.md`.
2. Validate tenant `tenant_context` in API logs for multi-tenant compliance scans.
3. Check external scanner connectivity if `scan_mode=external`.
4. Review recent migrations on `compliance` app.

## Escalation

- Compliance-platform on-call; enable feature-flag rollback per tenant if a single tenant triggers systemic failures.

## Maintenance

- **Owner**: Compliance Team
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
