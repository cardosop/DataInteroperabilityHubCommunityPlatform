# W3C Linked Data Notifications

**Phase:** 230.12
**Spec:** REQ-SEM-LDN-001 / 002 / 003
**Owners:** Platform / Semantic
**Status:** Per-tenant feature, default OFF. Flip via
`Tenant.semantic_ldn_enabled`.

## Overview

LDN lets external partners send signed RDF notifications to a
tenant's inbox + lets the platform fire signed notifications to
partner inboxes when resources change. Three surfaces:

1. **Inbox POST** — `POST /api/v1/semantic/ldn/inbox/<tenant_id>` —
   unauthenticated; HTTP signature against the tenant's
   `LdnPartnerKey` allow-list.
2. **Discovery** — every dereference response carries
   `Link: <inbox-url>; rel="ldp#inbox"` so off-the-shelf LDN
   clients discover the inbox via the protocol.
3. **Outbound delivery** — Asset / Contract / Dataset post_save
   signal handler enqueues `LDN_OUTBOUND_DELIVERY` jobs per active
   matching `LdnSubscription`; jobs sign with the tenant's
   per-tenant private key and POST to the partner inbox.

## Wire path — inbound

```
Partner system
  └─ POST /ldn/inbox/<tid> with Signature, Date, Digest headers
       └─ Django api pod
            ├─ resolve tenant + capability flag (401 if missing)
            ├─ rate-limit check (10/min/IP) → 429 + Retry-After
            ├─ payload size cap (1 MB) → 413
            ├─ parse Signature header → keyId
            ├─ lookup LdnPartnerKey(tenant=T, key_id=keyId, is_active=True)
            ├─ verify signature (cryptography RSA / ECDSA)
            │     ├─ canonical signed-headers: (request-target), host, date, digest
            │     ├─ Digest body match
            │     └─ Date skew ±5min
            ├─ create LdnInbox row (status=pending, signature_verified=True)
            └─ emit SEMANTIC_LDN_INBOUND audit event
```

## Wire path — outbound

```
Asset / Contract / Dataset post_save
  └─ transaction.on_commit(_maybe_schedule_ldn_outbound)
       ├─ check Tenant.semantic_ldn_enabled
       ├─ check semantic_federate_optout (skip if True)
       └─ for each active LdnSubscription matching resource_type_filter:
            └─ enqueue Job(type=LDN_OUTBOUND_DELIVERY, attempt=1)
                 └─ worker: _execute_ldn_outbound_delivery_job
                      ├─ resolve LdnTenantSigningKey + private PEM (External Secrets)
                      ├─ build AS2 RDF body
                      ├─ sign_request (Date, Digest, Signature headers)
                      ├─ POST partner inbox URL (timeout 10s)
                      ├─ on 2xx: emit SEMANTIC_LDN_OUTBOUND audit
                      └─ on failure: re-enqueue with backoff
                           (1m, 5m, 30m, 4h, 24h)
                           dead-letter at attempt 6
```

## Operational scenarios

### Enabling the feature for a tenant

```python
from hub.apps.tenants.models import Tenant
Tenant.objects.filter(slug="acme").update(semantic_ldn_enabled=True)
```

Then bootstrap the tenant's signing key:

```
python manage.py rotate_ldn_keys --tenant-id <tenant_uuid>
```

This generates an RSA-2048 keypair, publishes the private PEM to
External Secrets at `ldn-signing-key/<tenant_uuid>`, and writes
the public PEM + key_id to `LdnTenantSigningKey`. Without this
step, outbound delivery jobs fail loudly.

### Allow-listing a partner's public key

A partner sends you their public PEM out-of-band (signed email,
in-person handshake, signed PR). Then:

```python
from hub.apps.semantic.models import LdnPartnerKey
LdnPartnerKey.objects.create(
    tenant=tenant,
    key_id="partner-acme-prod-2026",
    public_key_pem="-----BEGIN PUBLIC KEY-----\n…",
    partner_label="Acme Corp Production",
    is_active=True,
)
```

Partner can immediately POST signed notifications. No restart, no
cache eviction.

### Revoking a compromised partner key

```python
LdnPartnerKey.objects.filter(key_id="partner-acme-prod-2026").update(is_active=False)
```

The row is preserved (audit trail) but signatures verifying with
this key are now rejected. The partner sees 401 on the next POST.

### Tenant subscribes to outbound deliveries TO a partner

```
meshant semantic ldn subscribe \
  --target-url https://partner.example/ldn/inbox \
  --resource-type contract
```

After subscription, the tenant's contract updates fan out to that
URL. To deactivate:

```
meshant semantic ldn unsubscribe <subscription_id>
```

### 90-day key rotation

Cron-driven (k8s CronJob) — runs `python manage.py rotate_ldn_keys`
without a tenant filter, rotating all `semantic_ldn_enabled=True`
tenants.

```
# k8s CronJob spec — 90 days = 7,776,000 seconds, conventionally
# expressed as the 1st of the month every 3 months.
schedule: "0 4 1 */3 *"
```

The new public PEM is immediately advertised at
`GET /api/v1/semantic/ldn/keys/<tenant_id>` (todo: surface this
endpoint; partners currently fetch via the LdnTenantSigningKey
row's `public_key_pem` field). Partners that don't refresh see
verify failures on the next inbound delivery — by design, this is
the signal to refresh.

### Failed outbound delivery — back-off + dead-letter

A failing partner inbox triggers retries at 1m / 5m / 30m / 4h /
24h. After 5 attempts the delivery is dead-lettered and a structured
log fires (`ldn_outbound_dead_letter`).

To replay a dead-lettered delivery: re-enqueue the original Job
manually. Long-term: dead-letter UI is a follow-up ticket.

### Inbox is filling with junk

Each row is up to 1 MB. A spammy partner could fill the table —
even with rate limit, 10 req/min × 1 MB × 1440 min/day = 14 GB/day
worst case per partner. Triage:

1. Check `LdnInbox.objects.filter(tenant=T).count()` and the
   per-`signature_key_id` distribution.
2. If a single partner is pathological: deactivate their
   `LdnPartnerKey`.
3. Long-term: add per-partner rate cap (follow-up ticket #4 in
   threat model).

## Known limitations

- **No subscribe-time URL allow-listing.** A motivated TENANT_ADMIN
  can subscribe to `http://169.254.169.254/...` (AWS metadata) or
  internal IPs. Defence-in-depth via NetworkPolicy in production.
  Threat model risk #1.
- **No grace-period overlap on key rotation.** Partners verifying
  with the old key see verify failures the moment we publish the
  new one. Follow-up ticket.
- **No per-tenant outbound rate cap.** A tenant with thousands of
  subscriptions could fan out unbounded jobs. Follow-up ticket.
- **`semantic_federate_optout` is a per-resource attribute referenced
  by spec REQ-SEM-LDN-003 but defined in Phase 230.8 (federation).**
  The signal handler reads it via `getattr(..., False)`; resources
  without the attribute default to NOT opted-out, which is the
  conservative posture for a feature behind a tenant flag.

## On-call escalations

| Symptom | Likely cause | First action |
|---------|--------------|--------------|
| Tenant reports "partner posts always 401" | LdnPartnerKey not registered, or wrong public PEM | Verify the row exists, is_active=True, public_pem matches partner's published key |
| Outbound jobs accumulate in PENDING | Worker queue backed up OR signing-key resolution failing | Check worker pod count; check `ldn_outbound_sign_failed` log lines |
| `ldn_outbound_dead_letter` fires repeatedly | Partner inbox is permanently down OR signature mismatch (partner upgraded their verify lib) | Contact partner; if verify mismatch, check our key rotation against their published key |
| Inbox row count balloons | Partner spamming OR rate limit broken | Check `LdnInbox` per-partner distribution; deactivate partner key if needed |
| `ldn_signature_date_skew_too_large` warnings | Partner's clock drifted >5min OR replay attempt | Contact partner re NTP; if skew is 24h+ assume replay attempt |

## Reference

- Spec: `openspec/changes/preprod01/specs/semantic-ldn/spec.md`
- Threat model: `docs/security/threat-model-semantic-3.md`
- Tasks: `openspec/changes/preprod01/tasks.md` § 230.12
- Tenant flag: `Tenant.semantic_ldn_enabled` (`tenants/0028`)
- Models: `hub/apps/semantic/models.py` — LdnInbox, LdnPartnerKey, LdnSubscription, LdnTenantSigningKey
- Migration: `hub/apps/semantic/migrations/0008_ldn_models.py`
- Signature lib: `hub/apps/semantic/ldn_signature.py`
- Inbox view: `hub/apps/semantic/views_ldn.py`
- Outbound job: `hub/apps/semantic/tasks_ldn.py`
- Rotation: `hub/apps/security/management/commands/rotate_ldn_keys.py`
- Backend tests: `hub/apps/semantic/tests/test_ldn.py`
- CLI: `cli/datahub_cli/commands/semantic.py::ldn` group
