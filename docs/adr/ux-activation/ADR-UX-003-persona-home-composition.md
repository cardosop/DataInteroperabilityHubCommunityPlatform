# ADR-UX-003 — Persona-Aware Home Dashboard Composition

- **Status**: accepted
- **Date**: 2026-05-13
- **Deciders**: Frontend team, UX lead
- **Stakeholders**: All 6 personas (DPO, Data Engineer, Data Consumer, Compliance Officer, Platform Admin, External Developer)

## Context

Phase 278.B.3 required a home dashboard that adapts to the user's persona. A one-size-fits-all dashboard was causing cognitive overhead: Data Engineers saw GDPR widgets they never used, while DPOs scrolled past ingestion pipelines to find compliance status.

The implementation delivers two pieces: a `usePersona()` hook that resolves persona from user roles, and a widget-directory architecture where each persona gets its own set of home widgets. The hook is complete; widget directories are partially populated.

## Decision

1. **Role-based persona resolution**, not preference-based. The `usePersona()` hook maps user roles to personas deterministically:

   | Role | Persona |
   |------|---------|
   | `PLATFORM_ADMIN` | CPO (Chief Product Officer) |
   | `AUDITOR` | DPO (Data Protection Officer) |
   | `DATA_PROVIDER` | DE (Data Engineer) |
   | `DATA_CONSUMER` | DC (Data Consumer) |
   | `DEVELOPER` | DEV (External Developer) |
   | `TENANT_ADMIN` | MPA (Multi-Persona Admin) |

   Fallback is a "default" generic persona. Users cannot manually switch personas — the dashboard reflects their actual role-based capabilities.

2. **Widget-directory architecture:** Each persona gets a directory under `features/home/widgets/<persona>/`. The home page composes from the active persona's directory. This avoids a monolithic `HomePage.tsx` with 6-way conditional rendering.

3. **Incremental widget population:** The architecture is in place but individual persona widgets are deferred to follow-up sprints. Current state: `usePersona()` hook is complete; home page renders a persona-aware header with the generic widget set as fallback.

## Consequences

- **Positive:** Deterministic mapping means no user confusion about "which dashboard am I seeing." Role changes automatically update the dashboard.
- **Positive:** Widget-directory pattern keeps persona-specific code isolated and independently testable.
- **Negative:** Widget population is incomplete for 5 of 6 personas; the generic fallback is the de facto experience until widgets are built.
- **Negative:** Users with multiple roles get the first matched persona; there is no multi-persona dashboard composite.

## Cross-references

- Implementation: `frontend/src/features/home/hooks/usePersona.ts`
- Widget directories: `frontend/src/features/home/widgets/<persona>/`
- Related: Phase 278.B.3 (persona-aware home task), Phase 278.A.3 (persona-to-journey mapping)
