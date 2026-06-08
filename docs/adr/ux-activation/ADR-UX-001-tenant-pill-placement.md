# ADR-UX-001 — Tenant Pill Placement (Header vs Sidebar)

- **Status**: accepted
- **Date**: 2026-05-13
- **Deciders**: Frontend team, UX lead
- **Stakeholders**: All personas (tenant context awareness is safety-critical)

## Context

Phase 276.B added cross-tenant navigation. Users reported losing track of which tenant they were operating in, leading to near-miss incidents where admin actions were narrowly averted in the wrong tenant. Two placements were evaluated for the persistent tenant indicator:

1. **Header (right side, between tenant-switcher and theme-toggle):** Always visible, adjacent to other identity controls, no scroll dependency.
2. **Sidebar (top, above navigation):** Larger footprint, groupable with workspace branding, but scrolls off-screen on long pages.

## Decision

**Place the tenant pill in the header**, color-coded by environment:

- **prod**: red left-border + red dot
- **staging**: amber left-border + amber dot
- **sandbox**: blue left-border + blue dot
- **development**: neutral gray

The pill shows the current tenant name (truncated with ellipsis), is keyboard-focusable, and has `aria-label` including both tenant name and environment for screen readers. Clicking the pill clears the active tenant switch state.

Rationale:
- Header placement guarantees visibility regardless of scroll position or sidebar collapse state.
- Environment color-coding provides an ambient safety signal — users subconsciously register the color before reading the name.
- Adjacency to the tenant-switcher creates a coherent "tenant context zone" in the header.

Rejected alternative — sidebar placement: larger visual footprint but disappears when the sidebar collapses on mobile, defeating the safety purpose for the highest-risk personas (Platform Admins operating across tenants).

## Consequences

- **Positive:** Always-visible tenant indicator reduces cross-tenant operating risk.
- **Positive:** Environment color coding gives immediate ambient awareness.
- **Neutral:** Consumes ~200px of header space; acceptable given the safety benefit.
- **Negative:** Requires `VITE_ENVIRONMENT` to be set correctly per deployment; misconfiguration would show wrong color (non-destructive — only visual).

## Cross-references

- Implementation: `frontend/src/shared/components/TenantPill.tsx`, `TenantPill.css`
- Integration: `frontend/src/shared/components/Header.tsx`
- Config: `.env.example` — `VITE_ENVIRONMENT` variable
- Related: Phase 276.B (cross-tenant navigation), Phase 278.C.1 (tenant pill task)
