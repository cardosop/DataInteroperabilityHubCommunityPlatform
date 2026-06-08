# Maintenance Notification Cadence (281.A.14.3)

**Date:** 2026-05-15  
**Owner:** Platform Engineering  
**Channels:** In-app banner + email + status page

## Standard Maintenance Cadence

### Scheduled Maintenance (planned 72h+ notice)

| Timeline | Action | Channel | Template |
|---|---|---|---|
| **T-7 days** | Initial notice | Email to tenant admins | `docs/operations/maintenance-template.md` §Scheduled |
| **T-72 hours** | Reminder | Email + in-app banner | Maintenance banner (warning variant) |
| **T-24 hours** | Final reminder | Email + in-app banner + status page banner | Status page: "Upcoming maintenance" |
| **T-1 hour** | Window approaching | In-app banner (persistent, non-dismissible) + status page | Status page: "Maintenance starting soon" |
| **T-0** | Window start | Status page update | "Maintenance in progress" |
| **During** | Status updates | Status page (every 30 min or on milestone) | Brief status line |
| **T+completion** | Window end | Email + in-app banner dismiss + status page clear | `maintenance-template.md` §Complete |

### Emergency Maintenance (SEV1, <1h notice)

| Timeline | Action | Channel |
|---|---|---|
| **Immediately** | Incident declared | Status page + `#meshant-incidents` Slack |
| **Within 5 min** | Initial communication | Email to tenant admins + in-app banner (error variant, non-dismissible) |
| **Every 30 min** | Status updates | Status page + Slack |
| **On resolution** | All-clear | Email + clear banner + status page green |

## In-App Banner Configuration

Banners are rendered by `AnnouncementBanner` component (281.A.14.1):

| Period | Variant | Dismissible | Persistence |
|---|---|---|---|
| T-72h to T-1h | `warning` | Yes (per-session) | localStorage |
| T-1h to T-0 | `warning` | No | Forced |
| During maintenance | `error` | No | Forced |
| Post-completion | `success` | Yes | Dismissed after 1 view |

## Status Page Integration

| Event | Status Page State | Auto-update? |
|---|---|---|
| Scheduled window approaching | `under-maintenance` scheduled | Yes (via Terraform/API) |
| Maintenance in progress | `major-outage` or `degraded-performance` | Yes (via synthetic probers) |
| Maintenance complete | `operational` | Yes (probers green for 5 min) |

## Email Templates

See `docs/operations/maintenance-template.md` for the full variable-based templates:
- **Scheduled notification:** `[NON-URGENT] Scheduled Maintenance — {DATE}`
- **Maintenance complete:** `[COMPLETE] Scheduled Maintenance — {DATE}`
- **Emergency:** `[URGENT] Emergency Maintenance — In Progress`

## Newsletter Cadence (281.A.14.2)

| Frequency | Content | Audience |
|---|---|---|
| Monthly (1st weekday) | Feature highlights, upcoming changes, platform health summary | All tenant admins |
| On release | What's new in vX.Y.Z — linked from changelog | Opt-in mailing list |
| Security advisory | Immediate, no schedule | All tenant admins (mandatory) |

Each newsletter includes:
- Unsubscribe link (one-click, audit-logged)
- "View in browser" link (hosted on meshant.com)
- Feature highlight with screenshot
- Breaking change warning (if applicable)

## Audit Trail

All notifications emit audit events:
- `MAINTENANCE_NOTIFICATION_SENT` — email/in-app/status page notification sent
- `MAINTENANCE_WINDOW_STARTED` — window opened
- `MAINTENANCE_WINDOW_COMPLETED` — window closed
- `NEWSLETTER_SENT` — monthly newsletter dispatched
- `NEWSLETTER_UNSUBSCRIBED` — user unsubscribed

## Review Cadence

- **Quarterly:** Review notification cadence metrics (open rate, click rate, unsubscribe rate)
- **After every SEV1:** Post-incident review of communication timeline
