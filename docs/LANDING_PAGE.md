# Landing Page

**Last Updated**: 2026-02-20

## Scope

The **public landing page** is implemented **frontend-only**. The backend does not serve a dedicated landing route; the SPA handles the root path with an auth-based switch.

## Behaviour

- **Route:** Single route `/` (no separate `/landing`).
- **Unauthenticated:** At `/`, the frontend shows the **Landing** component (hero, value proposition, Sign in and Create account links). No redirect to `/login`; the user stays on `/`.
- **Authenticated:** At `/`, the frontend shows the **App shell** and **Dashboard** (current home). No redirect.
- **Auth check:** The frontend uses the auth store (Zustand) and shows a loading state until initialization completes, then renders either Landing or ProtectedRoute + AppShell.

## Backend

No backend change is required for the landing page. The Hub API does not serve HTML for `/`; it exposes API routes under `/api/v1/`, `/health/`, etc. The SPA is typically served by a static server or reverse proxy (e.g. Vite dev server, or nginx serving the built frontend). Unauthenticated access to the landing is entirely handled by the frontend; no backend auth bypass or special route is needed.

## References

- [FEATURES.md](FEATURES.md) — Visitor persona and public capabilities (optional landing)
- [USER_JOURNEYS.md](USER_JOURNEYS.md) — JOURNEY-AUTH-001–004 (Visitor / Authentication)
- [USE_CASES.md](USE_CASES.md) — UC-AUTH-004 (Unauthenticated user accesses public resources)
