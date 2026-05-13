# Security Policy

**Maintained by:** Meshant Data Platform Eng
**Last updated:** 2026-05-13

## Reporting a vulnerability

Please email security disclosures to **security@meshant.com**.

For sensitive disclosures we strongly recommend encrypting your report
with the PGP key published below.  Plaintext reports are also accepted
and will be handled identically; encryption protects the reporter as
well as Meshant during the pre-disclosure coordination window.

We aim to acknowledge every report within 1 business day and to
publish a fix or mitigation within:

- **Critical / RCE / data-loss** — 7 calendar days.
- **High / privilege-escalation / auth-bypass** — 30 days.
- **Medium / DoS / info-leak** — 90 days.

For pre-disclosure coordination contact us at the email above. Do
NOT open public GitHub issues for vulnerability reports.

## PGP public key

Fingerprint: `F219 918A B3C5 E65B 838E  523F 5F07 9ACC 88CE 5E9F`

This key is rotated annually.  The current key expires 2027-05-13.
A new key will be published here at least 30 days before expiry.
If you receive a signed message from a key that does not match the
fingerprint above, contact security@meshant.com via an out-of-band
channel before proceeding.

```
-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBGoESxYBEADAzO/XXufW+ovlZVcxgSHesK5twBB1otufSbrDCTluMEe9f6zj
qkCZ/Ea+Mgdq6idVJQeKl9CqW3g1lxWqv6ZjncIPnSm4FdwrDUc5xvTFVQcaOXg8
EcOX41/uXZkwSFHfnrBv/N+o+vzViIDN6VMPlEFiz6wzj4i9dtruHcXqXvimJTrn
EPIhm1VHgj2U7aY/FbkNVGwWAGueKRaULFbmx4In96ehMB6vlXmyD8wTeyHg8aUs
I6sCanoBaEF5XFesDMPDMMhlq7HZZvDlmEULQAgdBFMIbZ1dGENCqrTF8hQYqkU2
TbRXfs7S9CwDZnjtWNwgNhMOYhyoJsjmNQ+dvrl4hNvgWsJMCrpv4sQDbUPxfWdU
Ye06hcLFfKa2H5lYNCraF8Ua1Ez2tzOj/B7DIAGtTU9LlX3UnWuuGOu7y5LUMfIa
RyC70liE4Emgh1UWuIrGkDKeYrqHOUdC/IIbekMooNyzEYrqM0m+tq3fHk/KL1Ll
ZBYI4ZY0YVH2MJhg18P1qO8d8RIUmkcW3bp/8Xn/utKj5/gIGgPo3jaWEulCuWnh
xzueIp1kB/vnFRN9z4UZyRDAxqtRQojs9d5W++vRFFuV4Dt7GrPhdyX8iDTPosyD
gw0luLQhMBAFcSB3a7WxjW4Wju0KasxTdiTTz5ECxO2gKeYFppIMNEcgCwARAQAB
tCdNZXNoYW50IFNlY3VyaXR5IDxzZWN1cml0eUBtZXNoYW50LmNvbT6JAlgEEwEK
AEIWIQTyGZGKs8XmW4OOUj9fB5rMiM5enwUCagRLFgMbLwQFCQHheloFCwkIBwIC
IgIGFQoJCAsCBBYCAwECHgcCF4AACgkQXweazIjOXp+4cRAAsteaESBFjDxY/VRc
Yb+FlMciLAXGxEUhOpWTj9sHQXa6OeoJ1kyc0euNrkqgbtZPSIBBmfc7T1b5OiN8
TsBhHSHBgfRswR7geLKDwRdVWe7JMCXHTNtl7r4h3Qo+2FWTDWG4FaygIO6PKl3z
hJHyrReijAuuq8oB84/ezGAe25jVhZvRx1E115EkNu622/X0usGZPqRU4gmgIpIV
wFCR5y+tcTiJBbwSUJVcVqvUlrC+NQwywyy2W6EIaf0u6h6/EW/I4pkHqeZtYqR8
Y2VrdWJoYZnPcsOpZ4VzQRID4quDLt6bLITrDZpeWcEdMDTjrGaOgqgY0RR1Lw1J
PrTZ3OixkLWd27tsM+oZmUlS6GKGjo7MuL6pHwamoV3D0YvTf/ned1T9pQe8prNS
DEhl4fLcJR+lk08fLOIivI/gaH55PDXXmUWMh+Ad4LFoRq5yvoONvLD2Z71pd32t
Rk9AQNAaQ66Fs9KPOmwYfB7tSeutJGO+zYuRJGK9v1MW3P/kli6sOP/HKriQXivw
XvsfpsiSxTMLgSlurvmQlcF2/KMP9KekcCCQTktScwChgqdOrUyuNQk1rkSzKksA
uwnP/JpwQdSo8VlOuB1ezJOU4cld23vWwemmmcp+F4vmu01XcjkX80WCvADuzyej
Ksf8NopvNYNW6tX3tnXFFNwdqKI=
=wsXj
-----END PGP PUBLIC KEY BLOCK-----
```

## Bug Bounty Program

Meshant operates a public bug-bounty program for the production
deployment at `meshant.com` and its subdomains.  We welcome reports
from independent security researchers, academics, and the broader
community.

### Scope

The following subsystems are **in-scope** for bounty awards:

| Subsystem | Endpoints / surface |
|---|---|
| Authentication & sessions | `meshant-internal.example.com/api/v1/auth/*`, OAuth2 flows, JWT issuance, refresh-token rotation, impersonation |
| Contracts | `meshant-internal.example.com/api/v1/contracts/*` — create, update, read, versioning, ODPS linking |
| Marketplace | `meshant-internal.example.com/api/v1/marketplace/*` — listings, orders, payments, entitlements |
| Lineage / OpenLineage | `meshant-internal.example.com/api/v1/lineage/openlineage/events/`, `/keys/` |
| Semantic / SPARQL | `meshant-internal.example.com/api/v1/semantic/*` — SPARQL endpoint, dereference, inference, LDN inbox |
| Webhooks | `meshant-internal.example.com/api/v1/webhooks/*` — outbound delivery, signing, retry |
| GDPR / DSAR | `meshant-internal.example.com/api/v1/gdpr/*` — data export, right-to-be-forgotten |
| API keys | `meshant-internal.example.com/api/v1/auth/api-keys/*` — key management, scoping |

Findings on endpoints not listed above are accepted but prioritized
below the in-scope set.  We may still award bounties for
high-severity out-of-scope findings at our discretion.

### Exclusions

The following are **out of scope** for bounty awards:

- Self-XSS that requires the user to paste payload into their own console.
- Volumetric DoS without a separate authentication or authorisation bypass.
- Findings against non-production environments (`*.stagingmeshant-internal.example.com`) UNLESS the same finding reproduces in production.
- Rate-limit bypass via legitimate API-key parallelism (the limits are per-key, not per-IP).
- Issues fixed in a release less than 30 days old at the time of report.
- Social engineering, phishing, or physical security of Meshant offices.
- Scanner output or automated tool reports without manual verification and a working proof-of-concept.
- Missing HTTP security headers that do not lead to a demonstrable exploit (e.g. missing `X-Frame-Options` on an API-only endpoint).
- Clickjacking on pages that require authentication and have no sensitive state-changing actions.
- `CVSS < 4.0` issues without a plausible attack chain.

### Rewards

Bounty amounts are determined by severity and report quality.
The following table is a guide; final awards are at Meshant's discretion.

| Severity | Examples | Reward range (USD) |
|---|---|---|
| Critical | RCE, unauthenticated data exfiltration, auth bypass granting platform-admin | $5,000 – $15,000 |
| High | Privilege escalation (tenant → platform), IDOR across tenants, SQL injection, JWT forgery | $1,500 – $5,000 |
| Medium | Stored XSS, CSRF on state-changing endpoints, info-leak of PII, SSRF to internal metadata services | $500 – $1,500 |
| Low | Reflected XSS, open redirect used in phishing chain, missing auth on non-sensitive endpoint | $100 – $500 |

Duplicate reports are awarded to the first reporter.  We may award a
partial bounty for partial findings that lead to a confirmed issue.

### Safe Harbor

When conducting vulnerability research in accordance with this policy:

- We consider such research to be **authorized** under applicable
  anti-hacking laws and we will not pursue civil or criminal action
  against you.
- If legal action is initiated by a third party against you for
  research conducted under this policy, we will make this
  authorization known.
- You may not exfiltrate, modify, or delete data beyond what is
  necessary to demonstrate the vulnerability.  If you accidentally
  access data beyond the proof-of-concept, stop and report it
  immediately.
- You may not publicly disclose the vulnerability before we have
  published a fix (see SLA table above).  Coordinated disclosure is
  appreciated; we will credit you (with permission) in the release
  notes.

We credit researchers (with permission) in the release notes that
ship the fix. Anonymous disclosures are also accepted; we'll skip
the credit but the fix workflow is identical.

## Penetration Testing

Meshant commissions independent penetration tests on the following
cadence:

| Test type | Cadence | Scope | Provider |
|---|---|---|---|
| External network + web-application | Quarterly (Mar, Jun, Sep, Dec) | Public-facing API surface, auth, marketplace, lineage, semantic | Third-party CREST-accredited firm |
| Internal / assumed-breach | Per major release (roughly quarterly) | Internal services, worker mesh, RQ jobs, DB layer, RLS policies | Third-party CREST-accredited firm |
| Cloud-infrastructure review | Bi-annual | AWS account posture, IAM, Secrets Manager, EKS, RDS | Third-party CREST-accredited firm |

The most recent test report (executive summary) is available to
enterprise customers under NDA.  Contact **security@meshant.com**
to request a copy.

## Encryption + key rotation

- TLS 1.2+ everywhere; HSTS preload list.
- Webhook secrets, OpenLineage ingest keys, and DLQ payloads are encrypted at rest. See `hub/apps/webhooks/encryption.py` for the canonical helper.
- AWS Secrets Manager hosts production secrets with a 90-day rotation policy (Phase 228 F4: `meshant/staging/openlineage/{marquez_admin,producer_keys/<tenant>,hmac_signing_key,mtls_cert}`).
- The `rotate_openlineage_keys` management command (Phase 228 F4) supports a 7-day grace window during ingest-key rotation so external producers can deploy the new key without a hard cutover.
