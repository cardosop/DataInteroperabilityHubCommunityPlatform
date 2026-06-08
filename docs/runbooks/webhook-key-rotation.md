# Webhook key rotation — operations runbook

**Phase:** 233 (Webhook Feature Hardening)
**Owner:** Webhooks Engineering Lead + on-call SRE
**Last reviewed:** 2026-05-07
**Cadence:** on-demand (operator-initiated rotation) + automatic prune (hourly cron)

This runbook is the operational playbook for rotating a tenant's webhook signing keys, troubleshooting the rotation lifecycle, and responding to alerts emitted by the webhook surface (Phase 233.6 alert rules at [`monitoring/prometheus/alerts/webhook.yml`](../../monitoring/prometheus/alerts/webhook.yml)). The customer-facing migration guide for subscribers adopting the rolling-key model lives separately at [`docs/migrations/webhook-rolling-key-rotation.md`](../migrations/webhook-rolling-key-rotation.md); this document is for OPERATORS responding to incidents or executing planned rotations.

## Table of contents

- [What rotation does](#what-rotation-does)
- [Planned rotation procedure](#planned-rotation-procedure)
- [Compromise response (immediate rotation)](#compromise-response-immediate-rotation)
- [Reading the dashboard](#reading-the-dashboard)
- [Alert response playbook](#alert-response-playbook)
- [Common failure modes](#common-failure-modes)
- [Sign-off](#sign-off)

## What rotation does

A `Webhook` row holds a rolling 3-key window of `WebhookSigningKey` records. At any time at most ONE row per webhook has `status=ACTIVE` (enforced by partial unique index — see [`hub/apps/webhooks/models.py`](../../hub/apps/webhooks/models.py) `webhook_signing_keys_one_active_per_webhook`); up to TWO rows are in `RETIRING` state during the 24h overlap window; any number of `RETIRED` rows accumulate before the auto-prune cron sweeps them after 7 days.

When `POST /api/v1/webhooks/{id}/rotate_secret/` is called:

1. A new `WebhookSigningKey` is INSERTED with `status=ACTIVE`.
2. The previous `ACTIVE` key (if any) is transitioned to `status=RETIRING` with `retired_at = now() + 24h`.
3. If 2 retiring keys already existed, the OLDEST is force-transitioned to `RETIRED` (FIFO eviction).
4. A `WEBHOOK_KEY_ROTATED` audit row commits in the same transaction.

All four steps run in a single `transaction.atomic()` block — partial states are not observable.

## Planned rotation procedure

### Pre-flight checks

```bash
# 1. Confirm the webhook is ACTIVE and the tenant is in good standing.
curl -H "Authorization: Bearer ${OPS_TOKEN}" \
  "${API_BASE}/api/v1/webhooks/webhooks/${WEBHOOK_ID}/" | jq

# 2. Confirm the subscriber has been notified that rotation is imminent
#    (24h notice is the customer-facing SLA — see migration guide).

# 3. Confirm Redis is reachable (the auto-rotate cron uses it for the
#    distributed lock).
kubectl exec -n hub-production deploy/api -- redis-cli ping
```

### Execute the rotation

```bash
curl -X POST -H "Authorization: Bearer ${TENANT_ADMIN_TOKEN}" \
  "${API_BASE}/api/v1/webhooks/webhooks/${WEBHOOK_ID}/rotate_secret/" \
  | jq

# Expected response:
#   {
#     "key_id": "<new-uuid>",
#     "previous_key_id": "<old-uuid>",
#     "retired_at": "2026-05-08T10:00:00.000000+00:00"
#   }
```

### Post-rotation verification

```bash
# 1. The new ACTIVE key is in place.
psql -c "
  SELECT key_id, status, created_at, retired_at
  FROM webhook_signing_keys
  WHERE webhook_id = '${WEBHOOK_ID}'
  ORDER BY created_at DESC;
"
# Expected: 1 ACTIVE row + ≤2 RETIRING rows + N RETIRED rows.

# 2. The audit event committed.
psql -c "
  SELECT id, action, created_at, details_json->'new_key_id' AS new_key
  FROM audit_audit_event
  WHERE action = 'WEBHOOK_KEY_ROTATED'
    AND details_json->>'webhook_id' = '${WEBHOOK_ID}'
  ORDER BY created_at DESC LIMIT 5;
"

# 3. The next outbound delivery uses the new key (validates the
#    subscriber-side cache update). Trigger a test:
curl -X POST -H "Authorization: Bearer ${TENANT_ADMIN_TOKEN}" \
  "${API_BASE}/api/v1/webhooks/webhooks/${WEBHOOK_ID}/test/"

# 4. Inspect the test delivery's signing_key_uuid.
psql -c "
  SELECT id, event_type, signing_key_uuid, status
  FROM webhook_deliveries
  WHERE webhook_id = '${WEBHOOK_ID}'
  ORDER BY created_at DESC LIMIT 3;
"
# Expected: signing_key_uuid matches the NEW key_id from step 1.
```

If any check fails, see [Common failure modes](#common-failure-modes) below.

## Compromise response (immediate rotation)

If a tenant suspects the webhook secret has leaked:

1. **PAUSE the webhook** to halt outbound deliveries entirely. The 24h overlap window means the leaked secret is still valid for verification during the window; pausing prevents any further deliveries from being signed with the leaked key.

   ```bash
   curl -X PATCH -H "Authorization: Bearer ${TENANT_ADMIN_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"status": "PAUSED"}' \
     "${API_BASE}/api/v1/webhooks/webhooks/${WEBHOOK_ID}/"
   ```

2. **Rotate the secret** to issue a new active key.

   ```bash
   curl -X POST -H "Authorization: Bearer ${TENANT_ADMIN_TOKEN}" \
     "${API_BASE}/api/v1/webhooks/webhooks/${WEBHOOK_ID}/rotate_secret/"
   ```

3. **Coordinate with the subscriber** to update their cache with the new secret out-of-band. Wait for confirmation.

4. **Force-retire the leaked key** by directly transitioning it to `RETIRED` (overrides the 24h overlap — appropriate ONLY for compromise response):

   ```sql
   -- Run in the production database.
   UPDATE webhook_signing_keys
   SET status = 'RETIRED', retired_at = NOW()
   WHERE webhook_id = '${WEBHOOK_ID}'
     AND status = 'RETIRING'
     AND key_id = '${LEAKED_KEY_ID}';
   ```

   Document the manual override in the incident timeline — the cron's `WEBHOOK_KEY_RETIRED` audit will NOT fire for a manually-forced retire.

5. **Resume the webhook** once the subscriber confirms the new secret is in their cache.

   ```bash
   curl -X PATCH -H "Authorization: Bearer ${TENANT_ADMIN_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"status": "ACTIVE"}' \
     "${API_BASE}/api/v1/webhooks/webhooks/${WEBHOOK_ID}/"
   ```

6. **File an incident report** documenting the compromise window, the rotation timestamp, and any deliveries during the leaked window (queryable via `WebhookDelivery.signing_key_uuid = '${LEAKED_KEY_ID}'`).

## Reading the dashboard

The Phase 233.6 dashboard at [`monitoring/grafana/dashboards/webhook-health.json`](../../monitoring/grafana/dashboards/webhook-health.json) (Grafana UID `webhook-health`) surfaces the load-bearing observables:

| Panel | What it tells you |
|---|---|
| Outbound trigger rate by outcome | Healthy traffic is mostly `triggered` with thin `rate_limited` + `duplicate_skipped`. A spike in `rate_limited` for a single tenant means their subscriber is misconfigured OR the per-tenant limit is too low. |
| Top-10 tenants by outbound rate | Identifies the noisy neighbour. If one tenant's rate is >5× the next-busiest tenant's rate, audit their `event_types` subscription for a runaway. |
| Signature compute duration percentiles | Typical p95 is sub-millisecond. >100ms triggers `WebhookSignatureComputeDurationHigh` — usually a slow KMS round-trip in `decrypt_secret`. |
| Rate-limit blocks/sec by tenant | Reads `meshant_webhook_rate_limit_blocks_total`. Sustained spikes indicate the tenant should consider raising `Tenant.webhook_outbound_rate_limit_per_minute` (default 300). |
| Distinct tenants firing rate-limit | Mirrors `WebhookRateLimitBlockedAcrossManyTenants`. >10 → page on-call. |
| Alert state stats | Three indicators showing whether the load-bearing alerts are firing. |

## Alert response playbook

### `WebhookRateLimitedSpikePerTenant` (warning)

A single tenant is hitting their outbound rate limit at >5/sec for 10+ minutes.

1. Identify the tenant via the `tenant_id` label on the alert.
2. Query `WEBHOOK_RATE_LIMIT_EXCEEDED` audit events:
   ```sql
   SELECT details_json->>'webhook_id' AS webhook_id,
          details_json->>'event_type' AS event_type,
          COUNT(*) AS hits
   FROM audit_audit_event
   WHERE action = 'WEBHOOK_RATE_LIMIT_EXCEEDED'
     AND details_json->>'tenant_id' = '${TENANT_ID}'
     AND created_at > NOW() - INTERVAL '1 hour'
   GROUP BY 1, 2 ORDER BY 3 DESC;
   ```
3. If a single `webhook_id` + `event_type` dominates: contact the tenant — their automation is firing too often.
4. If multiple webhooks are affected: consider raising `Tenant.webhook_outbound_rate_limit_per_minute` (default 300) for that tenant.

### `WebhookSignatureComputeDurationHigh` (warning)

P95 of HMAC + decrypt_secret is >100ms.

1. Check the AWS KMS service health dashboard (or Fernet key-derivation host CPU if KMS is down).
2. Inspect recent `WebhookDelivery.payload` row sizes — a payload >1MB will inflate HMAC time.
3. If KMS is the cause: the fail-open path in `encryption._decrypt` falls back to Fernet for `vault:v1:` and `v1:` prefixes, so deliveries don't fail outright; but the slowdown is an SLO miss until KMS recovers.

### `WebhookTriggerVolumeAnomalyHigh` (warning)

Sustained outbound trigger volume above 100/sec for 30+ minutes.

1. Inspect the top-N `event_type` labels on the metric:
   ```promql
   topk(5, sum by (event_type) (rate(meshant_webhook_outbound_total{outcome="triggered"}[5m])))
   ```
2. If a single `event_type` dominates: the upstream emitter for that event type is firing too often. Common causes:
   - A misconfigured federated-import job emitting `asset.created` for the entire shared catalog.
   - A model-drift loop re-firing `ml.training.failed`.
   - An automation client without exponential backoff retry-storming `compliance.completed`.
3. If multiple `event_type`s are affected: the platform may be processing a large batch import or migration. Confirm with the Engineering team before intervening.
4. Mitigation options (in order of escalation):
   - Contact the tenant whose `event_type` is dominating (`topk(5, sum by (tenant_id, event_type) (...))`) and ask them to throttle.
   - Lower the affected tenant's `webhook_outbound_rate_limit_per_minute` temporarily so excess traffic surfaces as `rate_limited` instead of overwhelming subscribers.
   - As a platform-wide kill-switch, set `webhook_outbound_rate_limit_per_minute = 0` for the affected tenants.

### `WebhookRateLimitBlockedAcrossManyTenants` (page)

>10 distinct tenants are hitting rate limit simultaneously. PAGE.

1. Likely causes: an upstream event source is fan-out-storming the platform (e.g. a federated-import job emitting `asset.created` for the entire shared catalog), OR an attacker is stress-testing outbound webhooks via stolen tenant-admin tokens.
2. Triage: query the audit events grouped by `event_type`:
   ```sql
   SELECT details_json->>'event_type' AS event_type, COUNT(*) AS hits
   FROM audit_audit_event
   WHERE action = 'WEBHOOK_RATE_LIMIT_EXCEEDED'
     AND created_at > NOW() - INTERVAL '15 minutes'
   GROUP BY 1 ORDER BY 2 DESC;
   ```
3. If a single `event_type` dominates: identify and pause the upstream emitter.
4. If multiple `event_types` are affected: consider activating the platform-wide kill-switch by setting `Tenant.webhook_outbound_rate_limit_per_minute = 0` for affected tenants.

### `WebhookDuplicateSkipRateHigh` (info)

>20% of trigger attempts are duplicates. Not urgent.

1. Inspect the `event_type` distribution:
   ```sql
   SELECT event_type, COUNT(*) AS dup_skips
   FROM webhook_deliveries
   WHERE created_at > NOW() - INTERVAL '1 hour'
     AND status = 'SUCCESS'
   GROUP BY event_type
   HAVING COUNT(*) > 100
   ORDER BY 2 DESC;
   ```
2. The upstream emitter for the dominant event type is double-firing. File a backlog ticket.

## Common failure modes

### Rotation API returns 409 `WEBHOOK_ROTATION_RACE`

Two concurrent rotation calls both tried to insert an `ACTIVE` row; the partial unique index rejected the second one. Retry the rotation — the first one already succeeded.

### Subscriber returns 401 after rotation

Subscriber's cache is stale. Check:

1. The subscriber's `SECRETS_BY_KEY_ID` cache is populated with the new `key_id`.
2. The `X-Meshant-Signature-Key-Id` header matches the new `key_id` (inspect via `WebhookDelivery.signing_key_uuid`).
3. The 24h overlap window is still open — the OLD key is still valid for verification until `retired_at`. If the subscriber has not yet updated their cache and the 24h window has passed, deliveries will fail until they do. Pause the webhook + extend the rotation window manually if necessary.

### Hourly cron `expire_retiring_webhook_keys` not firing

Check the Redis distributed lock isn't stuck:

```bash
kubectl exec -n hub-production deploy/api -- \
  redis-cli get "meshant:expire_retiring_webhook_keys:v1"
```

If the key is present and `TTL > 0`, the lock is held by an ongoing run (normal during the hourly tick). If the key is present and `TTL = -1` (no expiry), it's stuck — manually delete:

```bash
kubectl exec -n hub-production deploy/api -- \
  redis-cli del "meshant:expire_retiring_webhook_keys:v1"
```

Then trigger a manual run:

```bash
kubectl exec -n hub-production deploy/api -- \
  python manage.py expire_retiring_webhook_keys
```

## Sign-off

| Role | Name | Date |
|---|---|---|
| Webhooks Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |
| SRE on-call | _to be filled_ | _YYYY-MM-DD_ |
| Security review (compromise-response section) | _to be filled_ | _YYYY-MM-DD_ |

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
