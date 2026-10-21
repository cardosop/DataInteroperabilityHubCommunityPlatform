# Lineage — Support FAQ

**Phase:** 228 X (228.X.12 / REQ-LIN-X-008)
**Owner:** Customer Support + Data Platform Eng
**Last reviewed:** 2026-05-01

This FAQ is the front-line CS reference for every lineage-related
ticket. Each question links to the corresponding runbook /
user-guide / engineering doc when escalation is needed.

## General

### Q. The Lineage tab is empty for my contract.

Two cohorts (see also [lineage-edge-sync-drift.md](../runbooks/lineage-edge-sync-drift.md)):

1. **No relationships declared.** The contract's `hub_contract_json.lineage`
   subtree is empty AND no other contract in the tenant references
   it. Action: educate the customer on declaring lineage in the
   contract document.
2. **Sync drift.** The contract HAS lineage entries but the index
   diverged. Action: open a P2 against Data Platform Eng + run
   `python manage.py backfill_lineage_edges --resume-key=<ticket-id>`.

### Q. Why is the Lineage tab slow?

Check the dashboard panel "p99 read latency" first. If healthy
(<1s), the tab is hitting an unusually wide graph for that contract.
If unhealthy, page on-call (`LineageQueryHighLatency` alert).

### Q. The customer's lineage diff doesn't match what they expect.

Ask which two anchors they used (`from`/`to`) — the diff is computed
between those exact instants. Common causes:

- They picked a `from` BEFORE the contract was created.
- The contract was rotated/re-saved between the anchors and the
  `transformation_ref` changed (close-and-reopen surfaces as
  remove+add, not as "modified").

## OpenLineage (F4)

### Q. The customer's external producer is getting 401.

Check `X-Meshant-OpenLineage-Key` header is set + matches an active
key. The auth is a CUSTOM header, NOT `Authorization: Bearer`.
See [openlineage.md §"Auth — why a custom header?"](../integrations/openlineage.md).

### Q. DLQ is growing.

Page on-call. Runbook: [openlineage-dlq-replay.md](../runbooks/openlineage-dlq-replay.md).

### Q. Marquez is down / unreachable.

Runbook: [marquez-outage.md](../runbooks/marquez-outage.md).

## Time-travel + diff (F5)

### Q. The "as of" date picker is grayed out.

The `lineage.snapshots` capability flag is OFF for the customer's
deployment. Check capability via `GET /api/v1/capabilities/`.
Either flip the flag for that tenant (per-tenant rollout knob) OR
explain the feature is not yet available.

### Q. The customer says "modified is empty even though I changed transformation_ref".

This is by-design (REQ-LIN-F5-002). Under SCD-2, a transformation
change closes the old row + opens a new one — diff sees them as
remove + add. The `modified` bucket is intentionally always empty.
Document at [docs/user-guides/lineage-f5.md](../user-guides/lineage-f5.md).

## Notifications (F3)

### Q. I'm getting too many lineage notifications.

Check the customer's subscription patterns + the dispatcher's debounce
setting. Per-tenant cap is 100 subscriptions. Runbook:
[lineage-notification-storm.md](../runbooks/lineage-notification-storm.md).

## GDPR / data residency

### Q. A tenant requested deletion of all their lineage data.

Run `python manage.py delete_lineage_edges_for_tenant --tenant=<uuid>`
(228.X.3.1). This purges hot tier + archive tier + S3 blobs.
Idempotent.

### Q. A user requested their personal data be removed.

Run `python manage.py delete_lineage_edges_for_user --user=<uuid>`
(228.X.3.2). This SCRUBS user identifiers from audit rows + edge
markers. Tenant-scoped lineage is preserved (other users in the
tenant rely on it).

### Q. The customer says cross-region access is blocked.

Expected when the customer's tenant has `data_residency_region` set
and the request originates from a different region without consent.
The customer can grant consent per-request via the
`X-Lineage-Cross-Region-Consent: true` header. See
[REQ-LIN-X-004 spec](../../openspec/changes/preprod01/specs/).

## Per-phase training

CS training sessions run once per major phase rollout:

| Phase | Topic | Materials |
|---|---|---|
| F1 | Cross-tenant marketplace lineage | [lineage-f1.md](../user-guides/lineage-f1.md) |
| F2 | Field-level mapping editor | [lineage-f2.md](../user-guides/lineage-f2.md) |
| F3 | Lineage notifications | [lineage-f3.md](../user-guides/lineage-f3.md) |
| F4 | OpenLineage integration | [lineage-f4.md](../user-guides/lineage-f4.md) |
| F5 | Time-travel + diff | [lineage-f5.md](../user-guides/lineage-f5.md) |

## Escalation

| Severity | Path |
|---|---|
| P1 (data loss / availability) | Page on-call via PagerDuty `lineage` schedule. |
| P2 (degraded; workaround exists) | File issue with `lineage` label + `gh issue assign`. |
| P3 (UX / docs) | Triage queue; review at the weekly standup. |
