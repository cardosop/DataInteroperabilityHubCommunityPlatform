# Threat Model — Semantic Phase 3 (W3C LDN)

**Phase:** 230.12
**Spec:** REQ-SEM-LDN-001 / 002 / 003
**Owners:** Platform Security
**Legal sign-off required:** YES (D230.11)

## Scope

This document is the threat model for Phase 230.12 — W3C Linked
Data Notifications inbox + outbound delivery + discovery. The new
attack surface introduced:

1. An **unauthenticated POST** at `/api/v1/semantic/ldn/inbox/<tenant_id>`
   that anyone on the public internet can hit.
2. **Outbound HTTP requests** from the platform to partner inboxes,
   carrying signed payloads that other systems will trust.
3. **Per-tenant private keys** stored in External Secrets, used to
   authenticate outbound deliveries.

Out of scope: existing semantic surfaces (SPARQL, ontology, dereference)
are covered by earlier threat models.

## Trust boundaries

```
[Public internet]
       │  (unauthenticated POST, HTTP signature)
       ▼
[traefik / nginx ingress]
       │  (TLS termination, rate limit at edge)
       ▼
[Django api pod] ──────► [PostgreSQL]
       │
       │  (signed outbound POST, HTTP signature)
       ▼
[Partner inbox URL]      ◄─── [External Secrets / AWS SM]
                                  (per-tenant private PEM)
```

## STRIDE per surface

### Inbox POST `/api/v1/semantic/ldn/inbox/<tenant_id>`

**Spoofing.** Mitigation: HTTP signature verification against per-
tenant `LdnPartnerKey` allow-list. Unknown `keyId` → 401 (no row
created, no audit event). Signature failure → 401. The `keyId`
parsed from the Signature header is used to FIND the partner key,
not to authenticate alone — the cryptographic verify is the gate.

**Tampering.** Mitigation: signed `Digest: SHA-256=...` header
covers the body bytes. An attacker who replays signed headers but
swaps the body is rejected by the digest comparison.

**Repudiation.** Mitigation: every accepted notification writes a
`SEMANTIC_LDN_INBOUND` audit event with `key_id`, `source_ip`, and
`payload_bytes`. Rejected requests do NOT write audit (spec
mandate) but DO log structured warnings for triage.

**Information disclosure.** Mitigation: 401 responses are
indistinguishable across {invalid tenant_id, capability flag off,
signature failure, unknown keyId} — this collapses fingerprinting
side channels. The Link header advertises the inbox URL on every
dereference response REGARDLESS of the per-tenant flag, so header
presence/absence does not leak per-tenant state either.

**Denial of service.** Mitigations:
1. Per-IP / per-tenant rate limit (10 req/min/IP, Django cache INCR
   with per-bucket key + 120s TTL).
2. 1 MB payload cap — bodies above the cap are rejected with 413
   BEFORE rdflib parse, so an attacker can't exhaust memory by
   posting a 100 GB body.
3. Edge layer: traefik / nginx ingress rate limits BEFORE Django.

**Elevation of privilege.** Mitigation: the inbox POST is
unauthenticated (signature is the auth) but the GET endpoints
require `IsTenantAdmin OR AUDITOR` role + tenant scoping (the URL
tenant_id MUST match the request's active tenant unless the user
is a platform admin). A signed POST cannot become a GET — no
session cookies are issued.

### Outbound delivery

**Spoofing.** Mitigation: outbound requests are signed with the
tenant's per-tenant private key. The `key_id` embeds tenant id +
version (`meshant:tenant:{tid}:ldn:v{version}`) so partners can
distinguish pre-rotation from post-rotation signatures.

**Tampering.** Mitigation: Digest header covers body, same as
inbox. Partners verifying with the wrong public key get a verify
failure, NOT a "signature OK but wrong content".

**Replay.** Mitigation: signed Date header + ±5min skew window
enforced by partners (and by our own inbox).

**Server-side request forgery (SSRF).** Risk: the outbound delivery
job POSTs to `LdnSubscription.target_inbox_url`. A motivated
TENANT_ADMIN could subscribe to `http://169.254.169.254/...` (EC2
metadata) or `http://localhost:.../`. Mitigation: in production,
egress NetworkPolicy on the worker pod denies AWS link-local +
RFC1918 ranges. Documented in [docs/runbooks/semantic-ldn.md](../runbooks/semantic-ldn.md);
follow-up ticket to harden subscribe-time URL validation (reject
private IP ranges, link-local, file://, etc.).

**Key compromise.** Mitigation:
1. Private keys NEVER stored in DB or audit log — only in External
   Secrets, accessed at signing time via the secrets backend.
2. 90-day rotation cron (`hub/apps/security/management/commands/rotate_ldn_keys.py`).
3. `LdnPartnerKey.is_active=False` is the incident-response toggle
   — flipping False blocks signatures verifying with that key
   without losing the row (preserves audit trail).

**Failed-delivery DoS on partners.** Mitigation: exponential
back-off (1m / 5m / 30m / 4h / 24h, dead-letter at 5 attempts) so
a failing partner doesn't get a retry loop hammering it.

### Per-tenant private keys

**Storage.** External Secrets path
`ldn-signing-key/{tenant_id}` (AWS Secrets Manager in production;
Kubernetes Secret in staging). The `LdnTenantSigningKey` DB row
stores ONLY the public half + version metadata.

**Retrieval.** At sign time, `tasks_ldn._resolve_tenant_private_key`
calls `hub.aws_secrets_loader.load_secret`. Failure to resolve →
hard-fail the job (re-enqueue with back-off; eventually
dead-letter) — better to drop a notification than to sign with a
wrong / stale key.

**Rotation.** The rotate command publishes the NEW private PEM to
External Secrets BEFORE flipping the DB row's `key_id`. Mid-
rotation crashes leave the secrets backend ahead of the DB; the
next outbound delivery signs with the new private key but
advertises the OLD `key_id` until the DB write lands. Partners
reject with 401, the job back-offs, ops re-runs the rotate
command. Acceptable failure mode.

## Identified risks NOT yet mitigated

| # | Risk | Severity | Owner | Target |
|---|------|----------|-------|--------|
| 1 | Subscribe-time URL allow-listing not enforced (partial SSRF) | M | platform-sec | follow-up ticket |
| 2 | Inbox 1MB cap not enforced at edge layer (only at Django) | M | platform-ops | nginx config change |
| 3 | Rotation does not preserve old public key for grace-period overlap | L | platform-sec | follow-up ticket |
| 4 | No per-tenant outbound delivery rate cap (a tenant with thousands of subscriptions could fan out unbounded jobs) | L | platform-sec | follow-up ticket |

## Legal sign-off checklist (D230.11)

- [ ] Contracts team reviewed the inbox UNAUTHENTICATED POST surface.
- [ ] Privacy team reviewed retention semantics: inbox rows live
      until tenant delete cascades them.
- [ ] DPO reviewed cross-border data flow implications (notifications
      may carry PII fragments — partner contracts MUST cover this).
- [ ] Security team approved 90-day rotation cadence.

Sign-off lives in the PR description per D230.11; this file is the
input.

## Reference

- Spec: `openspec/changes/preprod01/specs/semantic-ldn/spec.md`
- Runbook: `docs/runbooks/semantic-ldn.md`
- Signature lib: `hub/apps/semantic/ldn_signature.py`
- Models: `hub/apps/semantic/models.py` (LdnInbox / LdnPartnerKey / LdnSubscription / LdnTenantSigningKey)
- Inbox view: `hub/apps/semantic/views_ldn.py`
- Outbound job: `hub/apps/semantic/tasks_ldn.py`
- Rotation command: `hub/apps/security/management/commands/rotate_ldn_keys.py`
