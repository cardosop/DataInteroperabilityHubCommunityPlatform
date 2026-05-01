# ADR-LIN-F3-channels — Notification channels for Phase 228.F3 v1

Date: 2026-05-01
Status: ACCEPTED
Phase: 228.F3 (Lineage-driven change-impact notifications)
Spec: [REQ-LIN-F3-008](../../../openspec/changes/preprod01/specs/lineage-impact-notifications/spec.md#requirement-f3-channel-decision-req-lin-f3-008)

## Context

Phase 228.F3 ships lineage-impact notifications.  The spec
(REQ-LIN-F3-006) lists three channel options:

1. **In-app** — `UserNotification` row + bell-icon badge (existing
   infrastructure since Phase 223.1).
2. **Email** — leveraging the existing `notifications/templates/emails/`
   pipeline (existing since Phase 218).
3. **Slack** — would require an OAuth integration, per-tenant
   workspace mapping, and outbound-message audit hooks.

For F3 v1 we must decide which channels are in-scope.

## Decision

For F3 v1 (this phase):

- **In-app: ALWAYS ON.**  Every dispatched notification creates a
  `UserNotification` row with `category=LINEAGE_IMPACT`.  No way for a
  subscriber to opt out at the channel level (the severity threshold
  is the opt-out knob).
- **Email: OPT-IN.**  Each `LineageSubscription` row has an `email`
  boolean, default `False`.  When `True`, the dispatcher additionally
  enqueues an email via the existing `send_mail` pipeline using the
  `notifications/emails/lineage_impact.html` template.
- **Slack: DEFERRED to v2.**  The schema includes a `slack` boolean
  field but the dispatcher ignores it; the UI hides the toggle (or
  shows it disabled with a "Coming in v2" tooltip).

## Why defer Slack

Slack adds three categorical concerns that are not present for in-app
or email:

1. **OAuth + workspace mapping.**  A tenant can use one Slack
   workspace; users in the tenant must be matched to Slack user ids.
   We don't have a tenant↔Slack-workspace table, and adding one is
   itself a Phase 220-ish workstream (audit, key rotation, support
   for workspace rename, support for user de-provisioning when a
   user leaves the workspace).
2. **Quotas + rate limits at Slack's API layer.**  Slack's outbound
   API caps per-app messages at ~1 message/second per channel.  The
   F3 dispatcher's per-tenant rate limit is 1000/hour (REQ-LIN-F3-005),
   which translates to ~16/minute average — within Slack's per-app
   budget for one channel, but bursty enough that we need a token
   bucket on top of the dispatcher's rate counter.  Building that is
   a v2 cost we haven't budgeted for v1.
3. **Auditability.**  Outbound messages to a third party need an
   "outbound audit" hook so support can answer "did the user receive
   this notification".  In-app rows are queryable in our DB; email
   rows go through the existing email-log; Slack would need a
   parallel audit table or third-party lookup.

These costs are real but not blocking for v1's value proposition
(the field-level editor's downstream subscribers want to know about
breaking changes).  In-app + email are sufficient to deliver that
value; Slack is a "nice-to-have" we'll add when ≥ N tenants ask.

## Consequences

- The `LineageSubscription.slack` field exists in the schema (so v2
  doesn't need a migration) but the dispatcher's
  `_process_subscription` does NOT branch on it.
- The frontend `LineageSubscriptionsPage` does NOT render a Slack
  toggle.  When v2 ships, a one-line frontend change re-enables it.
- The runbook at [docs/runbooks/lineage-notification-storm.md](../../runbooks/lineage-notification-storm.md)
  references in-app + email only.

## Alternatives considered

- **All three in v1.**  Rejected — Slack OAuth + audit hooks is ~6
  eng-days of work that would push F3 past its 12 eng-day budget.
- **Email-only (no in-app).**  Rejected — in-app is free since the
  `UserNotification` row already exists; removing it would reduce
  feature parity vs other notification surfaces.
- **In-app only (defer email too).**  Rejected — email is the primary
  channel for users who don't open the app daily; without it the
  feature is too easy to miss for occasional subscribers.

## Reference scenarios

> Scenario: Slack option not exposed in v1
>
> WHEN the subscription create form is rendered for v1
> THEN the Slack channel toggle is not visible OR is disabled with a
> "Coming soon" tooltip

The frontend in `LineageSubscriptionPanel.tsx` and
`LineageSubscriptionsPage.tsx` does not render the Slack control; the
backend `LineageSubscriptionPatchSerializer` accepts the field for
forward-compatibility but the dispatcher ignores it.
