# JOURNEY-DE-006: Manage LDN Inbox Subscriptions

**Persona:** [Data Engineer](../personas/data-engineer/)
**Use Cases:** UC-SEM-LDN-001
**Phase:** 284 (GA Promotion)
**Status:** Implemented
**E2E:** `ldn-inbox.spec.ts`
**Routes:** `/semantic?tab=ldn`

## Overview

A Data Engineer manages W3C Linked Data Notifications (LDN) for the tenant: viewing incoming notifications in the LDN inbox, subscribing to external LDN inboxes to receive updates when resources change, and managing subscription lifecycle (create, list, deactivate). LDN enables cross-tenant semantic interoperability — when another tenant publishes a dataset matching a subscription, the subscriber receives a notification.

## Journey Steps

1. **Navigate to LDN settings** — From the Semantic page, the DE clicks the "LDN" tab (TENANT_ADMIN only). The `LdnSettings` component renders with inbox view and subscription management.
2. **View LDN inbox** — The inbox lists received notifications with type (Offer/Announcement/Accept), origin tenant, resource URI, received timestamp. Source: `GET /api/v1/semantic/ldn/inbox/{tenant_id}/`.
3. **Subscribe to external inbox** — Fill target inbox URL and optional resource type filter (asset/contract/dataset). POSTs to `POST /api/v1/semantic/ldn/subscriptions/` → creates an outbound subscription. Backend emits `SEMANTIC_LDN_SUBSCRIPTION_CREATED`.
4. **List active subscriptions** — `GET /api/v1/semantic/ldn/subscriptions/` returns all subscriptions with target URL, resource type filter, active status, and creation date.
5. **Unsubscribe** — Clicks "Unsubscribe" on a subscription → `PATCH /api/v1/semantic/ldn/subscriptions/{id}/` with `is_active: false`. Soft-delete — subscription record is preserved for audit.

## Error Handling

- **Invalid inbox URL** — Backend validates URL format and reachability (SSRF protection applies).
- **Duplicate subscription** — Same target URL + resource type returns 409 CONFLICT.
- **Inbox fetch failure** — `<ErrorDisplay>` with retry; inbox list shows last-known state.
- **Unsubscribe failure** — Inline error; subscription state unchanged.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `SEMANTIC_LDN_SUBSCRIPTION_CREATED` | New subscription | 90 days |
| `SEMANTIC_LDN_SUBSCRIPTION_DEACTIVATED` | Unsubscribe | 90 days |
| `LDN_NOTIFICATION_RECEIVED` | Inbound notification from external source | 90 days |

## Success Criteria

- DE can subscribe to an external LDN inbox and see the subscription appear in the active list.
- Incoming notifications appear in the tenant's LDN inbox.
- Unsubscribing soft-deletes the subscription; audit record preserved.
- Cross-tenant isolation: tenant A cannot see tenant B's inbox or subscriptions.

## Related

- E2E: `frontend/e2e/journeys/ai-ml-semantic/ldn-inbox.spec.ts`
- Runbook: [semantic-ldn.md](../../runbooks/semantic-ldn.md)
- Components: `LdnSettings`
- CLI: `datahub semantic ldn inbox-list/subscribe/unsubscribe`
- SDK: `client.semantic.ldn_list_inbox/ldn_subscribe/ldn_unsubscribe`
- Phase: 230.12, 284.B (GA promotion)
