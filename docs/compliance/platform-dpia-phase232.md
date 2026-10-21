# Platform recursive DPIA posture (Phase 232.0)

This document satisfies **232.0.12 — platform-side recursive DPIA** scaffolding prior to automated tooling (`232.3`).

## Recursive model

Processing activities form a directed acyclic graph:

1. **Ingress** — signup, SSO, marketplace checkout, federated connectors.
2. **Core SaaS** — tenancy isolation, ODPS ingestion, DQ/compliance jobs,
   semantic indexing, virtualization queries.
3. **Egress** — webhooks, scheduled exports, email/support channels.

Child activities inherit controller obligations from parents until a transfer
safeguard leaf is satisfied (SCC stack, adequacy decision, or BCR). When an edge
lacks safeguards the compilation step MUST fail closed (`DPIA_TRANSFER_MECHANISM_MISSING`).

## Artefacts

For each subsystem release train we maintain:

- DPIA markdown snapshot with version tag (`semver`).
- Threat scenarios aligned with `docs/security/threat-model-tenant-isolation.md`.
- Mapping from `hub/apps/core/pii_registry.py` inventory rows to activities.

Artifacts are disclosed to designated customer legal contacts through the DPA /
security review programme (not publicly downloadable raw binaries).

## Tooling hooks

Future automation emits `domain.dpia.*` events exclusively via
`hub.apps.core.events.DomainEventPublisher` so observability stays aligned with the
canonical domain envelope validated in `event_types.validate_event_data`.

## D232.17 — register implementation (`derived_from`)

The `hub.apps.dpia.Dpia` model exposes `derived_from` (self-referential FK) so tenant
assessments can chain from a platform or supplier template without duplicating scope.
API validation enforces same-tenant parents; indexes support `(tenant, derived_from)`.
