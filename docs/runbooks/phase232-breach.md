# Runbook — Phase 232 breach(notification) (`/api/v1/governance/breach-*`)

## Symptoms

- Alert **Phase232BreachModule5xxRate**; missed statutory notification deadlines.

## Checklist

1. Runbook SLA: confirm `breach_notification_clock_check` CronJob and queue depth.
2. Validate SES (or transactional email provider) throttling / suppression list.
3. Proof artefacts: check Phase 232.8 breach-archive bucket write permissions.
4. Review template overrides per tenant for rendering errors.

## Escalation

- Legal + compliance-platform for regulator-facing comms; page on-call if email provider outage.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
