# UC-UX-001: Complete First-Login Product Tour

**Persona:** All (persona-aware copy per role)
**Phase:** 278 (UX Activation)
**Phase 278 Task:** `278.B.1`, `278.R.6`

## Description

A first-time user completes a 5-step product tour overlay that introduces
the core Meshant surfaces: Assets, Contracts, Marketplace, Compliance,
and Help. The tour copy adapts to the user's detected persona (DE sees
ingestion flow, DPO sees GDPR, CPO sees billing). The tour dismisses on
completion or skip, persists the dismissed state to localStorage and
backend, and does not reappear on subsequent logins.

## Preconditions

- The user is authenticated and `ux_v2_enabled` is true for their tenant.
- The user has NOT previously completed the tour (`has_seen_tour=false`
  on the User model).
- `ProductTourGate` is mounted in `App.tsx` (Phase 278.R.6).

## Steps

1. User logs in for the first time. The `ProductTourGate` evaluates:
   `ux_v2` capability enabled AND `!user.has_seen_tour`.
2. The `ProductTour` overlay renders with `role="dialog"` and
   `aria-label="Product tour"`.
3. User sees 5 progress dots below the heading; the first dot is active.
4. User reads the first step's persona-aware title and description.
5. User clicks "Next" to advance to step 2. The progress dot updates
   (step 1 → done, step 2 → active).
6. User advances through all 5 steps, each showing unique content.
7. On the last step, the button changes from "Next" to "Got it!".
8. User clicks "Got it!". The tour dismisses, `meshant.tour.completed`
   is set to `"true"` in localStorage, and `PATCH /auth/me/` sets
   `has_seen_tour: true` on the backend.
9. Alternatively, the user clicks "Skip tour" at any step. The tour
   dismisses immediately with the same persistence behavior.

## Expected Outcome

- Tour renders on first login; does NOT render on subsequent logins.
- All 5 steps have unique, persona-aware content.
- `meshant.tour.completed === "true"` in localStorage after completion.
- `User.has_seen_tour` set to `true` via PATCH `/auth/me/`.
- Screen-reader: `role="dialog"`, `aria-label="Product tour"`, Radix
  Dialog Title/Description in sr-only.
- Tour does NOT render when `ux_v2` is disabled.

## Error Handling

| Condition | Expected Response |
|---|---|
| Backend PATCH fails | localStorage flag still set; tour stays dismissed |
| Capabilities endpoint slow | `gateLoading` → ProductTourGate returns null (no flash) |
| User navigates away mid-tour | Tour dismissed on un-mount; state not persisted |

## Related

- Concepts: [Users and Roles](../../concepts/users-and-roles.md)
- Journeys: [JOURNEY-DEV-001](../journeys/JOURNEY-DEV-001.md) (External Developer Marketplace Browsing — references ProductTour)
- Components: `ProductTour`, `ProductTourGate`, `usePersona`, `useUxV2Gate`
- Phase 278 tasks: `278.B.1` (ProductTour), `278.R.6` (Gate wiring), `278.R.6` (has_seen_tour field)
- E2E: `product-tour.spec.ts` (278.V.4)
