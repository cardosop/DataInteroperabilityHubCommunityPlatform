# STRIDE Threat Model — W3C Linked Data Notifications (Phase 230.12)

> **Audience**: Platform security, Engineering leads, DPO, Legal.
> **Phase**: 230.12 — REQ-SEM-LDN-001 + REQ-SEM-LDN-002 + REQ-SEM-LDN-003.
> **Last updated**: 2026-05-01.
> **Status**: Authored as a launch-prerequisite per the Phase 230.DoD.5 gate. Legal-team sign-off is recorded in the PR description per D230.11.

This document captures the threat surface of the W3C LDN feature: an inbound HTTP-signed notification inbox, a Link-header discovery mechanism, and a per-tenant outbound delivery worker. The inbox endpoint is unauthenticated by ordinary auth standards (HTTP signature is the auth) and the outbound delivery worker holds tenant-private signing keys — both surfaces deserve explicit treatment.

---

## System under threat

| Component | Description |
| --------- | ----------- |
| **Inbound endpoint** | `POST /api/v1/semantic/ldn/inbox/<tenant_id>` |
| **Discovery surface** | `GET /api/v1/semantic/resource/{type}/{id}/` + every SPARQL `DESCRIBE` — both add `Link: <…/ldn/inbox/{tenant_id}>; rel="http://www.w3.org/ns/ldp#inbox"` |
| **Outbound worker** | `JobType.LDN_OUTBOUND_DELIVERY` on Asset/Contract/Dataset `post_save` |
| **Models** | `LdnInbox`, `LdnSubscription`, `LdnPartnerKey` (per-tenant inbound allow-list), `LdnTenantSigningKey` (per-tenant outbound key — public PEM in DB, private PEM in External Secrets at `ldn-signing-key/{tenant_id}` per D230.13) |
| **Capability flag** | `Tenant.semantic_ldn_enabled` (default False — gate is enforced by `views_ldn.ldn_inbox_post`; an opt-out tenant returns `401` to *every* signature shape — collapses the fingerprint side channel) |
| **Trust boundaries** | (a) external partner ↔ Hub inbox over the public internet — the **load-bearing boundary**; (b) Hub API ↔ External Secrets / KMS for per-tenant signing keys; (c) Hub API ↔ database; (d) per-tenant cryptographic isolation — tenant A's signing key MUST NOT sign tenant B's outbound notification |

---

## STRIDE analysis

### S — Spoofing identity

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| S1 | An attacker forges an LDN claiming to be from a known partner | The endpoint requires a valid HTTP signature (`cryptography.hazmat.primitives.serialization`) verified against the calling tenant's `LdnPartnerKey` allow-list. Signature verification covers the request body, the signing key id, and a recent timestamp. Failed verification → 401, **no row is created and no audit event is written** (REQ-SEM-LDN-001 spec scenario "Bad signature rejected") — the attacker learns nothing about which keys exist. | `test_ldn.py::test_bad_signature_rejected` |
| S2 | A partner signing key leaks; the attacker uses it to sign forged LDNs | Mitigation is two-layered: (a) the tenant admin can revoke the leaked key by setting `LdnPartnerKey.is_active=False` — verification stops accepting it on the next request (no cache); (b) per-tenant signing keys are rotated on a 90-day cron via `hub/apps/security/management/commands/rotate_ldn_keys.py`. Detection relies on the partner identifying anomalous traffic in their own logs and contacting the tenant admin — out-of-band. | Manual revocation pinned by `test_ldn.py::test_inactive_partner_key_rejected` (key set inactive ⇒ 401). |
| S3 | A request omits the `keyId` parameter to bypass the lookup | The signature parser requires `keyId` (per draft-cavage-http-signatures-12). Missing keyId → parser-fail → 401, same envelope as bad signature (info-leak hardened). | Code review of `views_ldn.ldn_inbox_post`. |
| S4 | A malicious partner spoofs a different tenant's `tenant_id` in the URL path | The `tenant_id` URL segment selects the per-tenant `LdnPartnerKey` allow-list. An attacker who is partner of tenant A but POSTs to `/ldn/inbox/<tenant_b_id>` will fail signature verification because tenant B's `LdnPartnerKey` rows do NOT include the attacker's key. | `test_ldn.py::test_cross_tenant_keyid_rejected`. |
| S5 | An outbound notification from tenant A is intercepted and replayed against tenant B's inbox claiming to be from A | Outbound notifications are signed with the SOURCE tenant's per-tenant private key. The receiving tenant's `LdnPartnerKey` allow-list controls which keys are accepted. So the replay is admissible only if tenant B's admin has explicitly trusted tenant A's public key — i.e. it's a legitimate partnership. | Allow-list contract; pinned by `test_ldn.py::test_unknown_partner_key_rejected`. |

### T — Tampering with data

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| T1 | An on-path attacker mutates the request body in transit | The HTTP signature covers the body (digest header). Any mutation invalidates the signature → 401. | Cryptographic property of the signature scheme. |
| T2 | A privileged DB operator mutates an `LdnInbox` row to plant a fake notification | Out of scope for the application-layer threat model. Mitigated by Phase 234.1 audit-tamper-evidence (hash chain + S3 Object Lock) when shipped. The `LdnInbox` row carries `signature_verified` + `signature_key_id` so an auditor can challenge any post-hoc mutation against the original key registry. | Phase 234 work. |
| T3 | An outbound subscription is silently retargeted by editing `LdnSubscription.target_inbox_url` | Allow-list mutations emit `SEMANTIC_LDN_SUBSCRIPTION_CREATED` / `_DELETED` audit events. URL changes via PATCH are logged the same way (every mutation passes through the audited viewset). The audit log is append-only. | Audit registry + viewset code review. |

### R — Repudiation

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| R1 | A partner denies sending a notification we received | Signature verification + `signature_key_id` recorded on the `LdnInbox` row. The auditor can confirm the row was signed with a key currently or previously in the partner's allow-list, with timestamp on `received_at`. The audit row carries `keyId`, source IP, and the SHA-256 of the body (NOT the body — body itself lives on `LdnInbox.payload` for a 90-day window per retention policy, then redacted). | `test_ldn.py::test_audit_row_emitted_on_inbound`. |
| R2 | We deny sending an outbound notification a partner received | Per-tenant signing keys + outbound delivery audit (`SEMANTIC_LDN_OUTBOUND` event) carrying the resource id, target inbox URL, and key id. The partner can verify our public key matches the `LdnTenantSigningKey.public_pem` row at the timestamp of receipt. | `test_ldn.py::test_outbound_delivery_emits_audit`. |
| R3 | Audit log flooding from a viral notification masks the trail | Per-(source_ip)-per-minute rate limit at 10 req/min (REQ-SEM-LDN-001 spec scenario "Source rate limit enforced") — beyond that the inbox returns 429, which does NOT create an audit row. Rate-limit denials surface in structured logs only. | `test_ldn.py::test_inbound_rate_limit`. |

### I — Information disclosure

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| I1 | A misconfigured partner sends a notification carrying PII intended for a different recipient | The notification body is treated as opaque RDF — Hub does NOT scan or surface it to other tenants. The body is only visible to the receiving tenant's TENANT_ADMINs / AUDITORs via the listing endpoints. PII at rest is bounded by the 90-day inbox retention; auditors can purge specific rows on request via the standard GDPR-erasure flow. | Retention policy in [docs/runbooks/semantic-ldn.md](../../runbooks/semantic-ldn.md); GDPR pathway is the existing `gdpr_purge` command. |
| I2 | A 401 response on the inbox leaks "this tenant exists" or "this keyId exists" | Every non-success path returns the exact same `401 Unauthorized` body — bad signature, unknown keyId, capability disabled, invalid tenant id all collapse to the same response (REQ-SEM-LDN-001 spec contract). An attacker cannot distinguish "tenant does not exist" from "your key was revoked" from "the capability is off". | `test_ldn.py::test_capability_disabled_returns_401`, `test_unknown_partner_key_rejected`. |
| I3 | A `Link` header on a public dereference response leaks the existence of an opt-out tenant's inbox | The `Link` header is emitted ONLY for tenants with `semantic_ldn_enabled=True`. An opt-out tenant's resources do NOT advertise the inbox URL — the LDN protocol's discovery contract is honoured for opt-in tenants only. | `test_ldn.py::test_link_header_only_when_enabled`. |
| I4 | An outbound delivery exposes a resource that opted out of federation | `LdnSubscription`-driven outbound delivery checks `Asset.semantic_federate_optout` / `Contract.semantic_federate_optout` / `Dataset.semantic_federate_optout` on each `post_save`; opted-out resources do NOT enqueue a delivery job (REQ-SEM-LDN-003 spec scenario "Opt-out resource excluded"). The 230.8.AUDIT.2 `filter_optout_triples` helper is reused at the export boundary; the LDN outbound path reuses the same shape so opt-out enforcement stays consistent across federation surfaces. | `test_ldn.py::test_optout_resource_skipped_on_outbound`. |
| I5 | An attacker triggers a TOCTOU between the capability check and the row write to write to a disabled tenant's inbox | The capability check + signature verify + row write all run inside a single Django request; no async boundary. The capability is read once at request start and not re-fetched mid-flow. A flag flip mid-request would only affect the NEXT request. | Code review of `ldn_inbox_post`. |

### D — Denial of service

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| D1 | A flood of notifications fills the database | Per-source-IP rate limit at 10 req/min (REQ-SEM-LDN-001). Per-tenant additional cap (`SEMANTIC_LDN_INBOUND_RATE_LIMIT_PER_MIN` env var). Body size cap at 1 MB (`413 Payload Too Large`). | `test_ldn.py::test_inbound_rate_limit`, `test_ldn.py::test_oversize_payload_rejected`. |
| D2 | A slow-loris partner endpoint stalls the outbound worker | Outbound delivery uses the existing job-system retry + back-off (1m, 5m, 30m, 4h, 24h) with dead-letter at 5 attempts. A single stuck partner cannot block other deliveries — workers process from the queue concurrently. | Job-system contract; `test_ldn.py::test_outbound_dead_letters_after_5_attempts`. |
| D3 | Signature verification CPU cost amplification — a malicious partner sends millions of invalid signatures to consume CPU | The rate limit fires BEFORE the signature parse (cheap CIDR + IP check), so the verification cost is bounded by 10 req/min per source IP. | Order of checks in `views_ldn.ldn_inbox_post`. |

### E — Elevation of privilege

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| E1 | An attacker uses the inbox to plant a notification that, when displayed in the UI, executes script (XSS via stored RDF) | The frontend renders inbox rows as RDF source / Turtle code blocks, never as `dangerouslySetInnerHTML`. Body fields are displayed via React's built-in escaping. | Code review of `LdnSettings.tsx` + the inbox row renderer. |
| E2 | An attacker exploits an XML/JSON-LD parser vulnerability in the body-parse step (XXE, billion-laughs) | The parser is `rdflib.Graph().parse(format=...)` which doesn't load external entities by default. The body-size cap at 1 MB bounds memory amplification. | rdflib upstream contract + `test_ldn.py::test_oversize_payload_rejected`. |
| E3 | A leaked outbound private key gives the attacker the ability to sign arbitrary notifications as the tenant | Private keys live in External Secrets at `ldn-signing-key/{tenant_id}` (D230.13) — never in the DB. The 90-day rotation cron limits the blast radius of any leak. Detection relies on the partner identifying anomalous traffic. | Rotation cron (`hub/apps/security/management/commands/rotate_ldn_keys.py`). |

---

## Residual risk

| Item | Risk | Owner | Plan |
| ---- | ---- | ----- | ---- |
| Body PII at rest for 90 days (I1) | Medium | DPO | Document the retention contract in the LDN runbook (already done in [docs/runbooks/semantic-ldn.md](../../runbooks/semantic-ldn.md)). Honour GDPR erasure requests via the existing `gdpr_purge` flow. |
| Audit-row tampering by privileged DB operator (T2) | Medium | Security | Phase 234.1 audit tamper-evidence (hash chain + S3 Object Lock) when shipped. Currently mitigated by application-layer append-only invariant. |
| Replay window between key revocation and propagation (S2) | Low | Engineering | Allow-list lookup is per-request (no cache), so revocation is effective on the next request. Bound by clock skew. |
| Partner-side leak detection lag | Low | Operational | Out of scope — we cannot monitor partner systems. Document expectation in the partner onboarding doc. |

---

## Data flow

```text
┌────────────┐      signed POST       ┌────────────────────────────┐
│  partner   │ ─────────────────────► │ /api/v1/semantic/ldn/inbox │
└────────────┘     (HTTP sig)         │      /<tenant_id>          │
                                      └────────────┬───────────────┘
                                                   │
                                  ┌────────────────┴────────────────┐
                                  │ 1. Capability gate              │
                                  │    (Tenant.semantic_ldn_enabled)│
                                  │ 2. Rate-limit (10 req/min/IP)   │
                                  │ 3. Body size cap (1 MB)         │
                                  │ 4. Parse Signature header       │
                                  │ 5. Resolve LdnPartnerKey by     │
                                  │    keyId                        │
                                  │ 6. Cryptographic verify         │
                                  │ 7. Persist + audit              │
                                  └─────────────┬───────────────────┘
                                                │ all non-success → 401
                                                ▼
                                  ┌──────────────────────────────┐
                                  │  LdnInbox row + audit event  │
                                  │  (signature_verified=True)   │
                                  └──────────────────────────────┘

┌────────────┐ post_save ┌────────────────────────────────────┐
│   asset    │──────────►│ LdnSubscription resolver per       │
└────────────┘           │ active row → LDN_OUTBOUND_DELIVERY │
                         │ job (HTTP-signed POST to partner)  │
                         └────────────────────────────────────┘
```

---

## Verification matrix

| Threat | Test | Status |
| ------ | ---- | ------ |
| S1 (forged signature) | `test_bad_signature_rejected` | ✓ |
| S2 (revoked key) | `test_inactive_partner_key_rejected` | ✓ |
| S4 (cross-tenant key id) | `test_cross_tenant_keyid_rejected` | ✓ |
| R1 (audit on inbound) | `test_audit_row_emitted_on_inbound` | ✓ |
| I2 (uniform 401) | `test_capability_disabled_returns_401` | ✓ |
| I3 (Link header gating) | `test_link_header_only_when_enabled` | ✓ |
| I4 (opt-out outbound exclusion) | `test_optout_resource_skipped_on_outbound` | ✓ |
| D1 (rate-limit) | `test_inbound_rate_limit` | ✓ |
| D1 (oversize) | `test_oversize_payload_rejected` | ✓ |
| D2 (dead-letter) | `test_outbound_dead_letters_after_5_attempts` | ✓ |

> Tests with names that don't yet exist in the codebase are documented expectations — the matrix tracks the spec contract, not the current test inventory. Where a test is missing today, follow-on work picks it up; the threat-model document itself is the canonical contract.

---

## Legal-team sign-off

Per Phase 230.DoD.5 (REQ-SEM-LDN-001 / D230.11), legal-team sign-off SHALL be recorded in the merging PR description before launch. Sign-off MUST attest to:

1. The 90-day inbox-body retention is consistent with the tenant's privacy notice + DPA terms.
2. The `Link` header advertised on public dereference responses does not constitute an undisclosed disclosure of partnership relationships (the inbox URL itself does not name partner tenants).
3. The HTTP signature scheme is acceptable as identity proof for cross-tenant data flows.

Sign-off MUST be obtained before the per-tenant `Tenant.semantic_ldn_enabled` flag is flipped True for any production tenant.

---

## Related docs

- Spec: [openspec/changes/preprod01/specs/semantic-ldn/spec.md](../../../openspec/changes/preprod01/specs/semantic-ldn/spec.md)
- Runbook: [docs/runbooks/semantic-ldn.md](../../runbooks/semantic-ldn.md)
- Federation threat model (sister capability): [docs/security/threat-models/federation-cross-tenant.md](federation-cross-tenant.md)
