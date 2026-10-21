# UC-CM-004: Manage Activity Feed

**Persona:** [Data Product Owner (DPO)](../personas/data-product-owner/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_activity_feed`

## Description

A Data Product Owner configures their activity feed preferences and
notification filters to stay informed about events that matter --
such as DQ alerts, new reviews, access requests, and compliance
findings -- while suppressing noise from irrelevant domains or asset
types.

## Preconditions

- The user is authenticated and has at least one asset, domain
  stewardship, or community membership that generates feed events.
- The notification service is operational.
- The user has default feed preferences (all event types enabled) set
  during account creation.

## Steps

1. DPO opens "Settings > Notifications & Feed" or calls
   `GET /api/v1/users/me/feed-preferences` to retrieve current
   settings.
2. The API returns the current configuration including:
   - **Event types enabled:** `DQ_ALERT`, `REVIEW_SUBMITTED`,
     `ACCESS_REQUEST`, `COMPLIANCE_FINDING`, `LISTING_PUBLISHED`,
     `COMMUNITY_POST`, `ASSET_STATUS_CHANGE`.
   - **Delivery channels:** In-app, email digest (daily/weekly), or
     real-time email.
   - **Scope filters:** Specific domains, tags, or asset IDs.
3. DPO adjusts the configuration:
   - Disables `COMMUNITY_POST` notifications for a non-relevant domain.
   - Switches `DQ_ALERT` from daily digest to real-time email.
   - Adds a tag filter so only assets tagged `production` trigger
     `ASSET_STATUS_CHANGE` alerts.
4. DPO saves the preferences via
   `PUT /api/v1/users/me/feed-preferences` with the updated payload.
5. The API validates the configuration and returns `200 OK`.
6. DPO views the activity feed via `GET /api/v1/users/me/feed` which
   returns a reverse-chronological, paginated list of events matching
   the saved filters.
7. DPO marks individual feed items as read or archives them via
   `PATCH /api/v1/users/me/feed/{event_id}` with `{ read: true }`.

## Expected Outcome

- The user's feed preferences are persisted and immediately effective.
- The activity feed shows only events matching the configured event
  types, channels, and scope filters.
- Email digests and real-time notifications respect the updated
  preferences.
- An `AUDIT_FEED_PREFERENCES_UPDATED` event is recorded in the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Invalid event type in filter | `422 Unprocessable Entity` |
| Unknown domain/tag in scope | `422 Unprocessable Entity` |
| Feed service unavailable | `503 Service Unavailable` |

## Related

- Concepts: [Audit Events](../../concepts/audit-events.md), [Webhooks](../../concepts/webhooks.md), [Assets](../../concepts/assets.md)
- Journeys: [JOURNEY-DPO-004 -- Monitor Asset Quality](../journeys/JOURNEY-DPO-004.md)
- Personas: [Data Product Owner](../personas/data-product-owner/index.md)
