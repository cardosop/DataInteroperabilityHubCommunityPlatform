# ADR-LIN-003 — OpenLineage adapter shape

**Status:** Accepted (Phase 228 Foundations)
**Date:** 2026-04-30
**Related:** Phase 228 F4 (OpenLineage export, capability flag `lineage.openlineage_export`)

## Context

Phase 228 ships an OpenLineage export capability so external lineage consumers (Marquez, Datakin, custom OpenLineage receivers) can ingest Meshant lineage events without bespoke adapters. The OpenLineage spec (https://openlineage.io/spec/) defines `RunEvent`, `Job`, `Run`, and `Dataset` facets that do not map 1:1 to Meshant's internal `LineageEdge` shape.

Three integration models are viable:

1. **Replace internal events with OpenLineage events.** Make OpenLineage `RunEvent` the canonical internal format; downstream consumers (webhooks, audit logs, sync handler) all read OpenLineage shape.
2. **Translate at the edge.** Keep internal `LineageEdge` events; expose a separate OpenLineage HTTP endpoint that translates on demand.
3. **Adapter pattern (shadow internal events).** Internal events stay in the Meshant shape; an adapter component in `hub/apps/contracts/openlineage_adapter.py` subscribes to internal lineage events and emits OpenLineage `RunEvent`s shadowed in parallel.

## Decision

**Adopt the adapter pattern (option 3).** Internal events stay in Meshant shape; the OpenLineage adapter is a shadow consumer that translates and forwards.

Adapter scope:

- Subscribe to internal lineage events on the existing event bus (`hub/apps/core/events/`, see ADR-LIN-007).
- Translate each `LineageEdge` mutation into an OpenLineage `RunEvent` with `eventType=COMPLETE`, populating `producer`, `inputs`, `outputs`, `job`, `run`, and the Meshant-specific facet `meshant.contract_ref`.
- POST the event to subscriber-configured OpenLineage endpoints (URL stored in `OpenLineageSubscription` model, gated by `lineage.openlineage_export` capability flag).
- Retry on 5xx with exponential backoff via the existing `WebhookDeliveryService` retry policy.

## Consequences

**Positive:**

- Internal code (lineage_sync, LineageService, audit-event emission) is unchanged by the existence of the adapter — the OpenLineage feature is fully isolated.
- The adapter can be disabled (capability flag OFF) without affecting any internal consumer.
- The adapter is the only place that needs to track OpenLineage spec evolution; internal code is insulated from spec churn.
- Multiple OpenLineage receivers can subscribe to the same internal event stream with different translation rules (e.g., Marquez vs. Datakin both want subtly different facet shapes).

**Negative:**

- Two write paths: a save produces both internal and OpenLineage events. Mitigated by the adapter being a passive subscriber on an already-existing event bus — no extra write-amplification at the source.
- Translation lag: OpenLineage subscribers see events ~50-200 ms after internal subscribers. Acceptable for OpenLineage's typical use case (lineage browsers, not low-latency alerting).

**Neutral:**

- The `meshant.contract_ref` custom facet documents the edge's Meshant origin (contract id, tenant id, edge type) so consumers can correlate OpenLineage events back to Meshant resources.

## Alternatives Considered

- **Replace internal events with OpenLineage (option 1):** rejected because OpenLineage's `RunEvent` shape is too job-centric for Meshant's contract-centric lineage. Forcing internal code to translate every contract reference into a synthetic `Job + Run` makes the internal code harder to reason about. The adapter pattern keeps each shape native to its consumers.
- **Translate at the edge (option 2):** rejected because it forces every OpenLineage subscriber to poll an HTTP endpoint, defeating the push semantics OpenLineage consumers expect. The adapter pattern emits push events identical to OpenLineage's reference behaviour.
