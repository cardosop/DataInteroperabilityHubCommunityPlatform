# Runbook — Lineage Notification Storm (Phase 228.F3.22)

## Symptom

Operators see one or more of:

- Spike in `lineage_subscription_dispatched_total{result="success"}` exceeding 5× the per-tenant baseline.
- Spike in `lineage_subscription_dispatched_total{result="rate_limited"}` indicating the per-tenant cap is firing.
- Customer complaint that they're getting many duplicate-looking lineage emails / in-app notifications.
- Audit log shows many `LINEAGE_SUBSCRIPTION:DISPATCH_RATE_LIMITED` rows for one tenant.

## Likely cause

A contract's lineage subtree is being mutated rapidly — usually by:

1. An automation (CI pipeline, batch job) that re-applies a lineage patch on every commit.
2. A bug in a normalizer that re-sets the lineage to a structurally-identical but key-order-different value (the SHA-256 hash should reject this, but a bug could surface).
3. A legitimate bulk migration where one team is re-keying many contracts in a short window.

## Defenses already in place

| Defense | Where | TTL / cap |
|---|---|---|
| Per-(subscriber, source) debounce | Redis `lineage:debounce:*` | 1 hour (env: `F3_DEBOUNCE_TTL_SECONDS`) |
| Per-tenant rate limit | Redis `lineage:rate:{tenant_id}` | 1000 / hour (env: `F3_PER_TENANT_RATE_LIMIT`) |
| Hash-based change detection | post_save signal | identical hash → no event |
| Capability flag | `lineage.change_notifications` | OFF by default |

## Triage

1. **Identify the source contract.** Check the audit log:
   ```sql
   SELECT resource_id, COUNT(*) AS rate_limit_drops
   FROM audit_event
   WHERE action = 'DISPATCH_RATE_LIMITED'
     AND created_at > NOW() - INTERVAL '1 hour'
   GROUP BY resource_id
   ORDER BY rate_limit_drops DESC LIMIT 10;
   ```

2. **Inspect the dispatcher counters per source.** Prometheus query:
   ```promql
   sum(rate(lineage_subscription_dispatched_total[5m])) by (severity, result)
   ```
   A sustained `result="success"` spike on a single severity tier likely indicates a single contract is fluctuating rapidly.

3. **Check the contract's recent saves.**  Look at `Contract.updated_at` deltas and the `LineageEdge` rows where `source_contract_id` matches.  A handful of saves per minute indicates an upstream automation loop.

## Mitigation — staged

### Stage 1 — Reduce blast radius (no customer impact)

- Increase the per-(subscriber, source) debounce window for the affected tenant:
  ```
  kubectl set env deploy/dispatcher F3_DEBOUNCE_TTL_SECONDS=21600   # 6 hours
  ```
- Subscribers continue to receive notifications, just less frequently.

### Stage 2 — Rate limit the source

- Lower the per-tenant cap for the offending tenant via the platform's per-tenant settings:
  ```
  Tenant.objects.filter(id=<tenant_id>).update(
      lineage_dispatch_rate_limit_per_hour=100
  )
  ```
- (Above field is read by the dispatcher; if not present in your build, fall back to the global env override and accept that other tenants on the same pod inherit the lower limit until the spike clears.)

### Stage 3 — Kill switch (customer impact)

- Flip `lineage.change_notifications` OFF for the tenant via the capability admin UI.  In-app notifications stop arriving until the flag flips back ON.  Document the flip in the on-call log.

### Stage 4 — Code change

- If the spike is caused by a normalizer producing structurally-identical lineage with key-reordering, file a P1 to fix the canonical-form serializer in [hub/apps/contracts/signals.py:_hash_lineage](../../hub/apps/contracts/signals.py).  Add a regression test pinning the hash invariance under key reordering.

## Recovery

1. The debounce + rate-limit windows naturally drain on TTL expiry (≤ 1 hour).  Operators should NOT manually flush the Redis keys — that re-opens the storm window and produces duplicates.
2. After the spike resolves, restore environment defaults:
   ```
   kubectl set env deploy/dispatcher F3_DEBOUNCE_TTL_SECONDS-
   kubectl set env deploy/dispatcher F3_PER_TENANT_RATE_LIMIT-
   ```
3. Document the incident in the on-call log with: tenant id, source contract id, peak dispatch rate, mitigation applied, time-to-mitigation.

## Postmortem checklist

- Was the spike caused by user behaviour or a system bug?  If a bug: file the root-cause fix.
- Were the dispatch counters / metric labels sufficient to identify the source within 10 minutes?  If not: add the missing labels.
- Did the rate-limit drops correlate 1:1 with audit rows?  If not: the audit emission path has a bug.
- Did any subscriber receive a duplicate?  If yes: the debounce isn't working — reproduce the failure and patch the SETEX path.

## Related runbooks

- [Lineage edge sync drift](./lineage-edge-sync-drift.md)
- [Lineage edge backfill failure](./lineage-edge-backfill-failure.md)
- [Lineage soak period](./lineage-soak-period.md)
