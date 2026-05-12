# ADR-FE-001: Central useActiveTenantId() Hook

**Status:** Accepted
**Date:** 2026-05-12
**Phase:** 276.B.002

## Context

The AUTH-007 audit found that 40+ frontend files read `user.tenant_id`
directly from the auth store. After a tenant switch, stale reads persisted
because there was no centralized mechanism to re-read the JWT claim.

## Decision

Introduce a single `useActiveTenantId()` hook at
`frontend/src/features/auth/hooks/useActiveTenantId.ts`.

- Reads `tenant_id` from the JWT claim in the access token on every render
- Listens for `storage` events so a switch in one tab propagates to others
- Subscribes to Zustand auth store changes for in-tab reactivity

All existing `user.tenant_id` reads MUST be migrated to this hook.

## Consequences

- Single source of truth for tenant identity in the FE
- Cross-tab sync works without polling
- Backward-compatible: the hook returns `string | null`, same as `user.tenant_id`
