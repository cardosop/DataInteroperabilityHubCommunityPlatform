# Runbook — Phase 232 DSAR tenant console (`/api/v1/governance/dsar-*`)

## Symptoms

- Alert **Phase232DsarConsole5xxRate**; handlers cannot unlock cases while public ingress still works.

## Checklist

1. Inspect `dsar_statutory_clock_check` CronJob and `DSAR_SLA_*` webhook emissions.
2. Validate response bundle generation (ZIP), KMS fields, and S3 presign lifetime.
3. OTP / Mail backend: confirm `EMAIL_*` settings and provider quotas.
4. Legal hold: ensure suspended timers are audited when toggled.

## Escalation

- Privacy counsel if SLA breach imminent; compliance-platform for code defects.

## Maintenance

- **Owner**: Compliance Team
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
