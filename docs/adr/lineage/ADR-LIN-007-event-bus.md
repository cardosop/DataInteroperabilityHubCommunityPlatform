# ADR-LIN-007 — Phase 0 audit: existing event-bus framework

**Status:** Accepted (Phase 228 Foundations — audit document)
**Date:** 2026-04-30
**Related:** REQ-LIN-002, REQ-LIN-007; ADR-LIN-003 (OpenLineage adapter consumes the bus)

## Audit summary

Phase 228's lineage-sync handler, OpenLineage adapter, and change-notification dispatcher all need an event-bus. The audit confirms **a comprehensive event-bus framework already exists** under `hub/apps/core/events/` and is the canonical surface for new event producers/consumers. **Phase 228 does NOT introduce a new bus** — it subscribes to and publishes on the existing one.

## What exists

`hub/apps/core/events/` (audit findings, file-by-file):

| File | Role | Phase 228 use |
|---|---|---|
| [`bus.py`](../../../hub/apps/core/events/bus.py) | `EventBus` core class with `publish()`, `subscribe()`, `EventBusError` | Lineage-sync emits via `EventBus.publish('lineage.edge.created', ...)`. |
| [`publisher.py`](../../../hub/apps/core/events/publisher.py) | `EventPublisher` mixin + `publish_event()` free-function | `LineageEventPublisher` (already exists, extends mixin) gets new emit methods. |
| [`subscriber.py`](../../../hub/apps/core/events/subscriber.py) | `Subscriber` base class | OpenLineage adapter subclasses it. |
| [`event_types.py`](../../../hub/apps/core/events/event_types.py) | Canonical `EventType` registry | New types: `lineage.edge.created`, `lineage.edge.removed`, `lineage.edge.updated`. |
| [`schema.py`](../../../hub/apps/core/events/schema.py) | Pydantic event schemas | New schemas: `LineageEdgeCreatedEvent`, `LineageEdgeRemovedEvent`. |
| [`deduplication.py`](../../../hub/apps/core/events/deduplication.py) | Event-ID-based dedup with Redis TTL | Idempotency for the change-notification dispatcher leverages this directly. |
| [`retry_policy.py`](../../../hub/apps/core/events/retry_policy.py) | Exponential backoff + DLQ routing | OpenLineage adapter retries via this. |
| [`dlq_processor.py`](../../../hub/apps/core/events/dlq_processor.py) | Dead-letter-queue replay | Failed lineage events route to DLQ via existing infrastructure. |
| [`outbox.py`](../../../hub/apps/core/events/outbox.py) | Transactional outbox pattern | The `post_save` signal handler uses outbox so the event is committed atomically with the contract row. |
| [`metrics.py`](../../../hub/apps/core/events/metrics.py) | Bus-level Prometheus metrics | Lineage events emit through the existing `events_published_total{event_type}` counter for free. |
| [`acknowledgment.py`](../../../hub/apps/core/events/acknowledgment.py) | At-least-once ack tracking | Used by OpenLineage adapter and change-notification dispatcher. |
| [`service_publishers.py`](../../../hub/apps/core/events/service_publishers.py) | Per-service publisher mixins (already includes `LineageEventPublisher`!) | Phase 228 adds new methods `publish_lineage_edge_created` / `publish_lineage_edge_removed`. |

## What Phase 228 adds

| Addition | File | Rationale |
|---|---|---|
| New event types | `event_types.py` | Adds `lineage.edge.created`, `lineage.edge.removed`, `lineage.edge.updated`. |
| New event schemas | `schema.py` | Pydantic models for the three new event payloads. |
| New publisher methods | `service_publishers.py::LineageEventPublisher` | `publish_lineage_edge_created`, `publish_lineage_edge_removed`. |
| New subscriber for OpenLineage | `hub/apps/contracts/openlineage_adapter.py` (Phase 228 F4) | Subscribes to lineage events, translates to OpenLineage `RunEvent`. |
| New subscriber for change-notification | `hub/apps/contracts/lineage_notification_dispatcher.py` (Phase 228 F3) | Subscribes, applies severity gate + debounce per ADR-LIN-004. |

## What Phase 228 does NOT add

- **No new bus implementation.** The existing `EventBus` covers every Phase 228 need (publish, subscribe, dedup, retry, DLQ, outbox, metrics).
- **No new transport.** The existing bus is Kafka-backed in production with Redis fallback in test/dev; Phase 228 uses both transparently.
- **No new event-versioning scheme.** The existing `versioning.py` covers schema evolution.

## Risks identified during audit

- **Risk:** Lineage events at sync-frequency (one per contract save) could exceed the bus's per-tenant rate-limit. **Mitigation:** the dedup layer (`deduplication.py`) collapses identical-payload events with the same `event_id` within the TTL, so noop saves don't propagate. The severity gate (ADR-LIN-004) further reduces volume by suppressing minor edits at the source.
- **Risk:** A bus outage stalls the OpenLineage adapter. **Mitigation:** events route to DLQ; the OpenLineage adapter is best-effort by design (the spec doesn't require sync delivery), so a backlog drains naturally when the bus recovers.

## Conclusion

The existing event-bus framework is sufficient for Phase 228. Phase 228 contributes new event types, schemas, and subscribers, but no new infrastructure.
