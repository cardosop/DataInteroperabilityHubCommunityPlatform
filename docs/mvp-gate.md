# The MVP Gate

A three-layer soft-gate that hides non-MVP features until the product
team is ready to ship them. Enforced on staging via `MVP_MODE=true`;
off on production. **Not** a security boundary — a feature-visibility
filter that staging surfaces use to keep half-built work invisible.

## The three layers

```
┌────────────────────────────────────────────────────────────────────┐
│ Layer 1 — Sidebar / CommandPalette filter                          │
│   filterVisibleNavItems(...) reads NON_MVP_PATHS in mvpNav.ts      │
│   → User can't navigate to a non-MVP feature from the chrome       │
├────────────────────────────────────────────────────────────────────┤
│ Layer 2 — Frontend route guard                                     │
│   <MvpGatedRoute> wraps each non-MVP route in routes.tsx           │
│   → Direct URL navigation (typed, bookmarked, deep-linked) is      │
│     redirected to /coming-soon                                     │
├────────────────────────────────────────────────────────────────────┤
│ Layer 3 — Backend middleware                                       │
│   MvpModeApiGateMiddleware reads MVP_GATED_RELATIVE_PREFIXES       │
│   → /api/v1/<gated>/* returns 404 from the API                     │
└────────────────────────────────────────────────────────────────────┘
```

If the frontend gate ever fails open (regression in MvpGatedRoute,
typo in NON_MVP_PATHS), Layer 3 still 404s the underlying data, so
the page renders empty/broken — never with real non-MVP data.

## Adding a new non-MVP feature

If your feature is **not yet** part of the MVP scope and you want it
hidden in MVP mode:

1. **Frontend — add the route path to `NON_MVP_PATHS`** in
   `frontend/src/features/shell/utils/mvpNav.ts`:

   ```ts
   export const NON_MVP_PATHS: ReadonlySet<string> = new Set([
     // ...existing entries
     '/your-new-feature',
   ]);
   ```

2. **Frontend — wrap the route element in `<MvpGatedRoute>`** in
   `frontend/src/app/routes/routes.tsx`:

   ```tsx
   {
     path: 'your-new-feature',
     element: (
       <MvpGatedRoute>
         <YourFeaturePage />
       </MvpGatedRoute>
     ),
   }
   ```

   For routes with capability/role wrappers, place `<MvpGatedRoute>`
   on the **outermost** position (above `<CapabilityRoute>` /
   `<ErrorBoundary>`) — the drift test asserts this convention.

3. **Backend (only if your feature has API endpoints) — add the URL
   prefix to `MVP_GATED_RELATIVE_PREFIXES`** in
   `hub/apps/api/mvp_mode.py`:

   ```python
   MVP_GATED_RELATIVE_PREFIXES = (
       # ...existing entries
       "your-new-feature/",
   )
   ```

That's it — one line per layer, three lines total.

## Drift safety net (PR 4 tests)

Two automated checks catch incomplete work before it merges:

| Test | Catches |
|---|---|
| `frontend/src/app/routes/mvpGateDrift.test.tsx` | A path in `NON_MVP_PATHS` that has **no** `<MvpGatedRoute>` wrapper in `routes.tsx`. Inverse direction also: a wrapped route whose path isn't in `NON_MVP_PATHS` (dead gate). |
| `hub/apps/api/tests/test_mvp_mode_middleware.py` `test_every_mounted_prefix_is_classified` | A new `path("foo/", include(...))` in `hub/apps/api/urls.py` that's neither in `MVP_CORE_PREFIXES` nor in `MVP_GATED_RELATIVE_PREFIXES`. Forces a deliberate classification choice. |

If either fails, the convention has drifted from intent — fix it
before merging.

## What to do when an MVP feature graduates

When a non-MVP feature ships into the MVP:

1. Remove its path from `NON_MVP_PATHS`.
2. Remove the `<MvpGatedRoute>` wrapper from `routes.tsx`.
3. Remove the prefix from `MVP_GATED_RELATIVE_PREFIXES`.
4. The drift tests verify the change is consistent across all layers.

## Now-MVP features (never gated)

| Feature | Path | Decision date | Rationale |
|---|---|---|---|
| Semantic | `/semantic` | 2026-04-22 | Permanent MVP scope (`project_mvp_scope.md`) |
| Search | `/search` | 2026-05-12 | Phase 273.1 — restored per REQ-MVP-001/002 |

## Permanent exception: `/semantic`

`/semantic` is in MVP scope and should remain visible/reachable
even though the underlying feature is still under development.
**Do not** add it to `NON_MVP_PATHS`. Documented user decision
2026-04-22.

`/search` (Phase 273.1) is likewise permanently MVP-in-scope.
The three-layer gate was removed on 2026-05-12; search is no
longer a non-MVP feature. **Do not** add it back.

## Build-time vs runtime

- `VITE_MVP_MODE=true` is **inlined at Vite build time** — it is a
  compile-time constant per deploy. Switching MVP off requires a
  rebuild + redeploy of the frontend image.
- `MVP_MODE=true` on the backend is **read per-request** from
  `settings.MVP_MODE`, so `@override_settings(MVP_MODE=...)` works
  in tests and the value can be changed via Helm without rebuilding
  the image (just restart pods).

## Observability

- `mvp_gate_blocked` (INFO log) — every backend 404 from the
  middleware. Shows up via the Django logger
  `hub.apps.api.middleware.mvp_mode_gate`.
- `mvp_gate_redirect` (frontend telemetry, optional) — fired on
  `<MvpGatedRoute>` redirect. Currently a no-op until a telemetry
  helper exists. Useful for spotting bookmark drift after launch.

## Decision history

- 2026-04-22 — Track A PR 1: added `search/` and `developer/` to
  `MVP_GATED_RELATIVE_PREFIXES` after audit found them mounted but
  unguarded on the backend.
- 2026-04-22 — Track A PR 3: extended `NON_MVP_PATHS` (renamed from
  internal `MVP_EXACT_PATHS`) to include `/search`, `/developer`,
  `/observability` and added `<MvpGatedRoute>` wrappers on every
  affected route.
- 2026-05-12 — Phase 273.1: **removed** `/search` from all three
  gating layers (NON_MVP_PATHS, MvpGatedRoute, MVP_GATED_RELATIVE_PREFIXES)
  per spec REQ-MVP-001/002. Search is now permanently MVP-in-scope
  alongside `/semantic`. Frontend service swapped to canonical
  `/api/search/` endpoint.
- 2026-04-22 — Track A PR 1: tightened `/admin/` and `/api-docs/` to
  disappear on staging (previously gated only on production), since
  staging is publicly reachable.
