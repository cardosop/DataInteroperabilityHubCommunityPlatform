# Event Bus RLS Audit — 285.12.4.9 CC2

**Date:** 2026-05-20
**Auditor:** Platform Engineering

## Scope

Three models in `hub/apps/core/events/models.py`:

| Model | Table | Has tenant_id? | RLS Needed? |
|-------|-------|---------------|-------------|
| Event | `events` | Yes (UUIDField, nullable) | No — service-scoped |
| DeadLetterQueue | `dead_letter_queue` | No | No — service-scoped |
| EventSubscription | `event_subscriptions` | No | No — service-scoped |

## Rationale for Exclusion

- **Event**: `tenant_id` is a nullable UUIDField (not a ForeignKey). Events are published
  by services and consumed by subscribers — they are not user-facing. The event bus
  is an internal infrastructure component. RLS would break cross-tenant event
  delivery patterns (e.g., marketplace events that span tenants).

- **DeadLetterQueue**: No `tenant_id` field. Failed event deliveries are
  service-scoped. Operators process DLQ entries at the platform level.

- **EventSubscription**: No `tenant_id` field. Subscriptions are registered
  at service startup, not per-tenant.

## Decision

**Excluded from RLS.** These models are service-scoped infrastructure, not
tenant-scoped data. The `tenant_id` on `Event` is informational (for routing
and filtering), not a security boundary. Applying RLS to the events table
would break legitimate cross-tenant event flows (marketplace, federated import,
lineage federation).

## Related

- CLAUDE.md: "Tenant Isolation RLS Contract" — applies to tenant-scoped models
  with ForeignKey to Tenant, not service infrastructure.
- Phase 285.12.1: Quick Win RLS covered 14 tables across files, dq, webhooks, social.
