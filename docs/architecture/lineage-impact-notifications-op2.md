# OP-2 sign-off scaffold — Phase 228.F3 Lineage Impact Notifications

Date: 2026-05-01
Phase: 228.F3
Status: AWAITING SIGN-OFF
Spec: [openspec/changes/preprod01/specs/lineage-impact-notifications/spec.md](../../openspec/changes/preprod01/specs/lineage-impact-notifications/spec.md)
Channel ADR: [docs/adr/lineage/ADR-LIN-F3-channels.md](../adr/lineage/ADR-LIN-F3-channels.md)

## Decision under review

Phase 228.F3 ships in-app + email notifications for lineage-impact events.  Slack is deferred to v2 per ADR-LIN-F3-channels.

## Summary

| Channel | v1 status | Default state | Where it lives |
|---|---|---|---|
| In-app | ON (always) | enabled per subscription | `UserNotification` rows + bell icon |
| Email  | OPT-IN | per-subscription `email=False` default | `notifications/templates/emails/lineage_impact.html` |
| Slack  | DEFERRED | hidden in UI, ignored by dispatcher | schema field exists; v2 wires the dispatch path |

## Operational invariants (defended in code)

| Invariant | Defense | Where |
|---|---|---|
| ≥ 1000 subscribers receive within 60 s | dispatcher iterator + bulk-create | `lineage_impact_dispatcher.handle_contract_updated` |
| No duplicates | per-(subscriber, source) Redis debounce, 1h TTL | `_debounce_holds` / `_debounce_set` |
| Per-tenant rate ≤ 1000/h | Redis INCR + EXPIRE, audit on drop | `_rate_limit_exceeded` / `_rate_limit_bump` |
| Cross-tenant detail tier respected | summary-only body when subscriber tenant ≠ source tenant | `_format_notification_body` |
| Capability-flag kill switch | `lineage.change_notifications` OFF → no dispatch | dispatcher early-return |

## Sign-off table

| Role | Signature | Date |
|---|---|---|
| Engineering owner (Phase 228) |  |  |
| SRE / Platform on-call |  |  |
| Compliance / DPO (cross-tenant detail-tier) |  |  |
| Product (channel decision) |  |  |

## What ops needs to know before flipping the flag

1. **Per-tenant rate limit (1000/hour) is enforced.** Tenants approaching the cap surface as `lineage_subscription_dispatched_total{result="rate_limited"}`.  See [docs/runbooks/lineage-notification-storm.md](../runbooks/lineage-notification-storm.md).
2. **Debounce is per (subscriber, source).** A subscriber with N source contracts can receive N notifications/hour, NOT 1.
3. **Cross-tenant subscriptions are blocked at create time** (the API rejects with 403).  The dispatcher's cross-tenant guard is defence-in-depth for backfilled rows.
4. **Email is opt-in.** A tenant onboarding doc should mention this knob.
5. **Slack is NOT delivered.**  The schema field accepts the value but the dispatcher ignores it.  Customer-facing copy must not mention Slack.

## Verification (signed off when checked)

- [ ] `pytest hub/apps/contracts/tests/test_lineage_severity.py` — all green.
- [ ] `pytest hub/apps/contracts/tests/test_lineage_subscription_endpoints.py` — all green.
- [ ] `pytest hub/apps/contracts/tests/test_lineage_impact_dispatcher.py` — all green.
- [ ] `pytest hub/apps/contracts/tests/test_lineage_notification_flow.py` — integration + 50-subscriber load smoke + chaos idempotency.
- [ ] `python tests/load/notification_storm.py` — 1000-subscriber load test (run on a dev environment once).
- [ ] OpenAPI snapshot regenerated and committed (Phase 228.F3.25): `bash scripts/regenerate_openapi_snapshot.sh staging` then commit the diff to `frontend/e2e/dimensions/__snapshots__/openapi-drift.snapshot.json`.
- [ ] Bundle-size gate green (F3.24): `node scripts/bundle_size_check.mjs` after `npm run build` shows the settings + notifications routes within the ±30 KB budget.
- [ ] The runbook at [docs/runbooks/lineage-notification-storm.md](../runbooks/lineage-notification-storm.md) is reviewed by on-call.

## Rollout plan (post-sign-off)

1. Land the migration + code on `staging`.
2. Confirm flag OFF → endpoints 404, dispatcher logs but does not enqueue.
3. Flip `lineage.change_notifications` ON for a single internal tenant on staging; re-run `notification_storm.py` against staging.
4. Soak for ≥ 7 days; track the dispatcher counters.  Zero P1.
5. Flip the flag for 10 % of production tenants.  Watch the same counters for 24 h.
6. Roll to 100 % over the following week.
