# Webhook signing-key rotation — subscriber migration guide

**Phase:** 233.1
**Audience:** subscribers (you) of Meshant webhooks
**Status:** required reading before the rotation feature is enabled in production
**Last reviewed:** 2026-05-07

This guide covers what changes for subscribers when Meshant's webhook
signing-key rotation feature ships. The change is **non-breaking**:
your existing single-secret verification keeps working, but you can opt
into the new rolling-key model to get a 24h overlap window during
rotations and zero-downtime secret rollovers.

## What's changing

### Today (pre-Phase 233.1)

Each webhook has ONE secret. Signature verification is:

```
verify(received_body, header[X-Webhook-Signature], cached_secret)
```

When Meshant rotates the secret (currently a manual operation by the
tenant), your verifier fails for the brief window between the new
secret being active in Meshant and your cache being updated with the
new value.

### After Phase 233.1

Each webhook has up to THREE signing keys:
* one **ACTIVE** key (signs all new outbound deliveries)
* up to two **RETIRING** keys (kept for 24h after rotation; verifies
  old deliveries that haven't yet been retried)
* any number of **RETIRED** keys (auto-pruned after 7 days; never
  verifies anything)

Every outbound delivery now carries an additional header:

```
X-Meshant-Signature-Key-Id: <uuid>
```

The `<uuid>` identifies WHICH key signed this delivery. Your verifier
looks up the cached secret for that `key_id` and verifies. During the
24h overlap after a rotation, deliveries signed with EITHER the old
(retiring) or new (active) key both verify cleanly — eliminating the
race window that single-key rotation suffers from today.

## Required subscriber-side changes

**None.** Phase 233.1 is non-breaking by design (decision D233.7 in the
[change proposal](../../openspec/changes/preprod01/proposal.md)). Your
existing verifier — even one that completely ignores the new
`X-Meshant-Signature-Key-Id` header — keeps working. Both the active
and retiring keys are valid HMAC keys, and your single-secret cache
already verifies signatures from any of them.

## Recommended subscriber-side changes (zero-downtime rotation)

Adopt the key-id-aware verifier to GET the 24h overlap benefit during
rotations. This is a small refactor to your existing code:

### Before

```python
# Hard-coded single-secret verifier.
import hmac
import hashlib

WEBHOOK_SECRET = os.environ["MESHANT_WEBHOOK_SECRET"]

def verify(body: bytes, signature_header: str) -> bool:
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

### After

```python
# Multi-key verifier — keyed by Meshant's X-Meshant-Signature-Key-Id.
import hmac
import hashlib

# Cache populated from your secrets store. Key = Meshant's key_id; value
# = the secret you stored when Meshant told you about that key.
SECRETS_BY_KEY_ID: dict[str, str] = {
    # "key-uuid-1": "secret-1",
    # "key-uuid-2": "secret-2",
    ...
}

def verify(
    body: bytes,
    signature_header: str,
    key_id_header: str | None,
) -> bool:
    if key_id_header is None:
        # Legacy delivery from a webhook that pre-dates the rolling-key
        # feature — fall back to the legacy single-secret verifier.
        return _verify_legacy(body, signature_header)

    secret = SECRETS_BY_KEY_ID.get(key_id_header)
    if secret is None:
        # Unknown key_id — your secret cache is stale. Fail closed
        # AND log so ops can refresh the cache.
        return False

    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

The `SECRETS_BY_KEY_ID` cache should be populated from your secrets
store (Vault, AWS Secrets Manager, etc.) at process start AND refreshed
when verification against a known `key_id` fails — that's the signal
that a rotation has occurred and your cache is stale.

## Rotation flow (operator playbook)

When Meshant tenant-admin triggers a rotation:

1. Meshant performs an **atomic transaction**:
   - inserts a new ACTIVE key with a fresh secret
   - transitions the previous ACTIVE key to RETIRING (24h overlap)
   - emits a `WEBHOOK_KEY_ROTATED` audit event
2. The `POST /api/v1/webhooks/{id}/rotate_secret/` response carries
   the new + previous `key_id`s and the `retired_at` timestamp.
3. The tenant copies the new `key_id` + secret into the subscriber's
   `SECRETS_BY_KEY_ID` cache (out-of-band; via a runbook your team
   owns).
4. For 24 hours, both the old (retiring) and new (active) keys verify
   signatures successfully. After 24h, an hourly Meshant cron
   transitions the retiring key to RETIRED — at which point only the
   new key signs and the old secret can be safely removed from your
   cache.
5. After 7 more days the RETIRED key is auto-pruned from Meshant's
   database; you SHOULD remove the corresponding entry from your
   cache too at this point.

## How rotations are scheduled

* **Customer-initiated rotations**: any tenant-admin can call
  `POST /api/v1/webhooks/{id}/rotate_secret/` at any time.
* **Compromise response**: if a webhook secret is suspected leaked,
  the tenant-admin SHOULD rotate immediately. The 24h overlap window
  means subscribers don't break, but the retiring key remains valid
  for 24h by design — for compromise responses, follow up with
  `PATCH /api/v1/webhooks/{id}/` setting `status=PAUSED` to halt
  outbound deliveries entirely until the subscriber confirms the new
  secret is in their cache.
* **Scheduled rotations**: Meshant does NOT auto-rotate webhook keys
  on a schedule today; rotation cadence is a customer-policy choice.

## Detecting a stale cache

If your verifier sees a `X-Meshant-Signature-Key-Id` value that's NOT
in your `SECRETS_BY_KEY_ID` cache, two scenarios are possible:

1. A rotation happened recently and your secrets-store fetch hasn't
   propagated yet. Refresh your cache from the secrets store and
   retry verification.
2. An attacker is sending requests to your webhook endpoint with a
   forged `key_id`. Your verifier MUST fail closed (return 4xx) in
   this case. The `key_id` header is informational only — it does NOT
   shortcut verification; an unknown `key_id` is treated identically
   to a wrong signature.

## Rollback / kill-switch

Subscribers cannot disable the feature on Meshant's side. Two safe
rollback patterns if your verifier breaks:

1. **Code rollback**: revert your verifier to the legacy single-secret
   form. The active and retiring secrets are both valid HMAC keys —
   your single-secret cache will continue to verify signatures from
   either key as long as you have ONE of them cached.
2. **Pause the webhook**: `PATCH /api/v1/webhooks/{id}/` with
   `status=PAUSED`. Meshant stops issuing deliveries. Resume with
   `status=ACTIVE` once your cache is fixed.

## Reference

* Capability spec — [`webhook-signing-rotation/spec.md`](../../openspec/changes/preprod01/specs/webhook-signing-rotation/spec.md)
  (REQ-WH-ROT-001 through REQ-WH-ROT-006).
* Audit events emitted — `WEBHOOK_KEY_ROTATED` (rotation),
  `WEBHOOK_KEY_RETIRED` (cron transition retiring → retired).
* Hourly cron command — `expire_retiring_webhook_keys` — see
  [`hub/apps/webhooks/management/commands/expire_retiring_webhook_keys.py`](../../hub/apps/webhooks/management/commands/expire_retiring_webhook_keys.py).
