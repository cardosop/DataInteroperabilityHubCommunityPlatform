# Lineage F3 — Change-impact notifications

**Audience:** Data consumers, downstream owners
**Capability flag:** `lineage.change_notifications`

## What it does

Subscribe to a contract (or an asset) to receive a notification
when its lineage changes. Per-user cap: 100 subscriptions.

Three severity tiers (computed by the dispatcher's pure-function
classifier):

- **Critical** — breaking change (column dropped, contract retired).
- **Warning** — non-breaking but consumer-visible (transformation
  changed, schema evolved additively).
- **Info** — metadata change (description, owner).

## How to use

1. Open a contract or marketplace listing.
2. Click "Subscribe to lineage changes" in the side panel.
3. Pick severity threshold (Critical / Warning / All).
4. Notifications surface in the in-app inbox + via email
   (1-hour debounce + per-tenant rate limit).

## Manage subscriptions

`/settings/subscriptions` — list / pause / unsubscribe.

## Related

- [Notification storm runbook](../runbooks/lineage-notification-storm.md)
- [Support FAQ](../support/lineage-faq.md)
