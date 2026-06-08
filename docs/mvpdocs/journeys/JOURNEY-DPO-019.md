# JOURNEY-DPO-019: First-Time User Activation

**Persona:** [Data Product Owner](../personas/data-product-owner/)
**Use Cases:** UC-UX-ACT-001, UC-UX-ACT-002
**Phase:** 278 (UX Activation)
**Status:** Implemented (278.R.6, 278.V.1)
**E2E:** `frontend/e2e/journeys/features/tenant-pill-visibility.spec.ts`

## Overview

A first-time Data Product Owner logs into Meshant after their tenant has been
provisioned. The UX v2 activation flow guides them through product tour
orientation, establishes situational awareness through the tenant pill, and
surfaces a sample-data call-to-action so they can immediately experience the
platform's value. The flow is gated behind the `ux_v2` capability flag so
existing tenants are unaffected until their staged rollout wave activates.

## Journey Steps

1. **Login** — The DPO authenticates with their credentials. The capabilities
   API resolves `ux_v2` for the tenant. If enabled, the activation flow
   proceeds; otherwise the classic dashboard renders unchanged.

2. **Product tour** — After a short delay (800 ms), the `ProductTour` overlay
   appears. It walks the DPO through key surfaces: tenant pill (header,
   environment-coded trim), global search (`/`), command palette (`Cmd-K`),
   and persona-aware home dashboard. Each step has a "Next" action and the
   tour can be dismissed at any point. Dismissal persists to both
   `localStorage` and the backend (`PATCH /auth/me/` with `has_seen_tour:
   true`).

3. **Tenant pill awareness** — The `TenantPill` in the header shows the active
   tenant name and environment via color-coded trim (red = production, amber =
   staging, blue = sandbox, neutral = development). The aria-label reads
   "Current tenant: {name}. Environment: {env}. Click to switch." Hovering
   shows a tooltip with the tenant name and environment separated by a
   middle-dot.

4. **Cross-tab sync awareness** — If the DPO switches tenants in another
   browser tab, a `TenantSyncBanner` appears in the current tab: "Tenant
   changed in another tab. [Refresh →]". The banner has `role="alert"` and
   `aria-live="polite"` for screen-reader announcement. It can be dismissed.

5. **Home dashboard** — The `HomePage` renders a persona-aware dashboard
   using `usePersona()`. The subtitle reads "Your Data Product Owner
   Dashboard". Quick-action cards are tailored: draft assets, pending
   approvals, recent datasets. The "For You" section shows persona-specific
   metrics.

6. **Sample data CTA** — A call-to-action card invites the DPO to explore
   sample data or create their first asset. The CTA links to
   `/assets/create` (with the asset-creation kill-switch check so a disabled
   tenant sees an explanatory page rather than a broken form).

## Success Criteria

- Product tour appears on first login for `ux_v2`-enabled tenants.
- Product tour does NOT appear for `ux_v2`-disabled tenants or users who
  have already seen the tour (`has_seen_tour: true`).
- Tenant pill renders on every authenticated page with correct environment
  color class (`tenant-pill--red` / `--amber` / `--blue` / `--neutral`).
- Cross-tab tenant switch triggers the `TenantSyncBanner` within 2 seconds.
- Home page shows persona-aware subtitle and quick-action cards.
- No data loss or broken surfaces when `ux_v2` is disabled (classic UX
  renders identically).
- All surfaces meet WCAG 2.1 AA: `role="dialog"` / `role="alert"` /
  `aria-live="polite"` as appropriate.

## Related

- Phase 278 tasks: 278.R.6 (persona-aware home), 278.C.1 (tenant pill),
  278.C.2 (cross-tab sync), 278.M.6 (product tour), 278.M.4 (ux_v2 gate)
- E2E tests: `tenant-pill-visibility.spec.ts`, `tenant-sync-banner.spec.ts`,
  `ux-v2-gating.spec.ts`, `keyboard-shortcuts-cheatsheet.spec.ts`
- Concepts: [Personas](../concepts/personas.md), [Capabilities](../concepts/capabilities.md)
- Journeys: [JOURNEY-AUTH-001](JOURNEY-AUTH-001.md) (Registration),
  [JOURNEY-DC-002](JOURNEY-DC-002.md) (Marketplace Discovery)
