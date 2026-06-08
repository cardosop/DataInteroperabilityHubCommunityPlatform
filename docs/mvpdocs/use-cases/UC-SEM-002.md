# UC-SEM-002: Subscribe to LDN Inbox

**ID:** UC-SEM-002
**Title:** Subscribe to Linked Data Notifications (LDN) Inbox
**Persona:** Data Engineer (DE)
**Priority:** Low
**Phase:** 283.4 (GA)
**Feature Flag:** `semantic_ldn_enabled` (OFF by default, opt-in power-user)

## Summary

A Data Engineer subscribes the tenant's LDN inbox to an external partner's
notification endpoint, enabling automated receipt of W3C Linked Data
Notifications for federated knowledge graph updates.

## Preconditions

- Tenant has `semantic_ldn_enabled = True`
- User has DE or TENANT_ADMIN role
- External LDN inbox URL is reachable and accepts subscriptions

## Main Flow

1. DE navigates to LDN Settings
2. DE registers a subscription: target inbox URL, resource type filter
   (dataset, asset, contract)
3. Hub sends an LDN subscription request to the target inbox
4. On acceptance, the subscription is active and the tenant inbox
   receives notifications when the target resource type changes
5. DE can list active subscriptions and their status
6. DE can unsubscribe from an inbox, stopping notification delivery

## Acceptance Criteria

- Subscription created with target URL and resource type filter
- Inbox list shows received notifications
- Unsubscribe stops notification delivery
- Outbound delivery retries with exponential backoff (1m/5m/30m/4h/24h)
