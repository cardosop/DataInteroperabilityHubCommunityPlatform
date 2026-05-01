# Security Policy

**Maintained by:** Meshant Data Platform Eng
**Last updated:** 2026-04-30

## Reporting a vulnerability

Please email security disclosures to **security@meshant.com**.

We aim to acknowledge every report within 1 business day and to
publish a fix or mitigation within:

- **Critical / RCE / data-loss** — 7 calendar days.
- **High / privilege-escalation / auth-bypass** — 30 days.
- **Medium / DoS / info-leak** — 90 days.

For pre-disclosure coordination contact us at the email above. Do
NOT open public GitHub issues for vulnerability reports.

## In-scope endpoints

The following endpoints are in-scope for the public bug-bounty
programme. Findings on non-listed endpoints are accepted but
prioritised below the in-scope set.

- `https://meshant-internal.example.com/api/v1/auth/*` — authentication / token issuance.
- `https://meshant-internal.example.com/api/v1/contracts/*` — contract create / update / read.
- `https://meshant-internal.example.com/api/v1/marketplace/*` — marketplace listings + access.
- `https://meshant-internal.example.com/api/v1/lineage/openlineage/events/` — Phase 228 F4 inbound OpenLineage RunEvent endpoint (see `docs/integrations/openlineage.md`).
- `https://meshant-internal.example.com/api/v1/lineage/openlineage/keys/` — Phase 228 F4 admin key management.
- `https://meshant-internal.example.com/api/v1/capabilities/` — feature-flag discovery.

## Out of scope

- Self-XSS that requires the user to paste payload into their own console.
- Volumetric DoS without a separate authentication or authorisation bypass.
- Findings against non-production environments (`*.stagingmeshant-internal.example.com`) UNLESS the same finding reproduces in production.
- Rate-limit bypass via legitimate API-key parallelism (the limits are per-key, not per-IP).
- Issues fixed in a release < 30 days old at the time of report.

## Encryption + key rotation

- TLS 1.2+ everywhere; HSTS preload list.
- Webhook secrets, OpenLineage ingest keys, and DLQ payloads are encrypted at rest. See `hub/apps/webhooks/encryption.py` for the canonical helper.
- AWS Secrets Manager hosts production secrets with a 90-day rotation policy (Phase 228 F4: `meshant/staging/openlineage/{marquez_admin,producer_keys/<tenant>,hmac_signing_key,mtls_cert}`).
- The `rotate_openlineage_keys` management command (Phase 228 F4) supports a 7-day grace window during ingest-key rotation so external producers can deploy the new key without a hard cutover.

## Responsible disclosure

We credit researchers (with permission) in the release notes that
ship the fix. Anonymous disclosures are also accepted; we'll skip
the credit but the fix workflow is identical.
