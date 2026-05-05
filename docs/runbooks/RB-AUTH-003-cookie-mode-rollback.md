# RB-AUTH-003 — Cookie Mode Rollback

## Status

Stub created in Phase 260.0. Populate during Phase 260 implementation.

## Purpose

Rollback procedure for browser auth cookie-mode default (`USE_HTTPONLY_AUTH_COOKIES`)
if production regressions are detected.

## Scope

- Preconditions and rollback triggers
- Feature-flag/settings rollback steps
- Session/token invalidation and client-impact notes
- Verification checklist (login, refresh, logout, CSRF, cross-subdomain)
- Forward-fix and re-enable criteria
