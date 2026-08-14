# ADR: Open-Source Split — OSS Core + Hosted-SaaS Paid Layer

**Status**: Accepted (implemented, Phases 313.0–313.5)
**Date**: 2026-08-14

## Context

The Meshant Data Interoperability Hub is a single Django monorepo (52 apps)
whose business model is being restructured: the platform core becomes open
source (Apache-2.0, community-contributed) while the semantic layer,
marketplace, and monetization rails stay private as a hosted SaaS. The
repository had no dependency direction between the two sides; core apps
imported paid apps freely.

## Decision

1. **Boundary** — CORE (public): tenants, users, auth, api (+ analytics),
   core, assets, datasets, files, contracts (whole), dq, transformation,
   virtualization, orchestration, jobs, integrations, warehouses,
   data_movement, scheduled ingestion/export, governance, audit,
   compliance, consent, dsar, ropa, dpia, breach, processor_agreements,
   regulation_policies, mesh, search, webhooks, websocket, notifications,
   observability, health, platform, security, versioning, developer,
   testing, gdpr. PRIVATE (SaaS): semantic, marketplace, social, billing,
   baas, rate_limiting, ai, ml, graphql, graphql_ld, graphql_graphene.
2. **Direction rule** — core apps MUST NOT import paid apps. Enforced by
   `scripts/check_core_boundary.py` (GATE-29) with a ratchet allowlist
   (only ever shrinks).
3. **Single source of truth** — `hub/apps/manifest.py`
   (`ALL_HUB_APPS` ordered, `CORE_APPS`, `PAID_APPS`, `is_core_only()`).
   Settings, gates, and the publish pipeline all consume it.
4. **Seam pattern** — every core→paid dependency inverts to a core-owned
   registry/hook with a no-op default (job handlers, commercial hooks,
   paid URL registry, event-schema registration); paid apps register
   providers from `AppConfig.ready()`. Entitlement fails OPEN in core
   (no paywall).
5. **Repository strategy** — private monorepo remains the dev home; a
   publish pipeline (`scripts/publish_public.sh`) mirrors the core subset
   (index-based tree + manifest-generated exclusions + overlay) into the
   public repo (`DataInteroperabilityHubCommunityPlatform`) on
   `mirror/public-core` with sync commits + `vYYYY.MM.DD` tags. The public
   history was scrubbed once by `git filter-repo` (no shared commits with
   private history).
6. **Pull-back** — community PRs integrate via `scripts/pull_public_pr.sh`:
   verification against PUBLIC `main` (histories are disjoint — merge-base
   is meaningless), core-path scope check, `cherry-pick -x`, GATE-29.
   Public branches are never merged into private history.
7. **Clients publish fully** — frontend, CLI, SDKs ship in the public repo
   (they are API clients, not the paid backend); capability gating derives
   from the served OpenAPI, so paid UI hides automatically on core-only
   deployments.
8. **Control plane in core** — plan tiers, limit keys, and per-tenant
   capability flags stay in core (`tenants`); the paid layer owns the
   features the flags toggle.

## Consequences

- Core-only deployments (`HUB_CORE_ONLY=1`) boot with 42 apps, no paid
  middleware/routers, and a reduced OpenAPI surface (verified).
- The paid layer keeps zero-friction development in the private monorepo.
- Two core→paid lazy FKs (`AccessRequest.order`, `APIKey.tier`) are
  declared conditionally under `HUB_CORE_ONLY`; their paid-ward migration
  (fresh core-only DB support) is tracked as post-launch work.
- Publishing is operator-driven (no automation yet): run
  `publish_public.sh` per release; weekly sync optional.

## See also

- `TRICKLE_DOWN_RUNBOOK.md` — moving an app from paid to core
- `openspec/changes/preprod01/tasks.md` — Phase 313 task ledger
