# Runbook — Phase 232 consent & processor agreements (`consent-*`, `processor-*`)

## Symptoms

- Alert **Phase232ConsentProcessor5xxRate**; consent dashboard or processor link CRUD failing.

## Checklist

1. Consent signing key rotation CronJob: verify keys in ExternalSecrets and grace period.
2. Processor agreement expiry checker: validate notifications and webhook emits.
3. Asset–processor M2M integrity errors in API logs.
4. Feature flags: `compliance_consent_enabled`, `compliance_processor_agreements_enabled` per tenant.

## Escalation

- Compliance-platform; involve billing if subscription tier blocks programme features.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
