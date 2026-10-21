# STRIDE Threat Model — Frontend Identity (W5)

One-pager for the oss-release-remediation W5 surface (impersonation
token handling + identity-cache boundaries). Every mitigation cites its
verifying test or gate (P4). Ledger:
`docs/audits/w111-threat-model-refresh-2026-10-15.md`.

## Scope / assets

- The impersonation token lifecycle (persist → attach → clear), the
  identity-cache bus (login/logout/auth-failed/tenant-switch), the
  query-client singleton, the tenant-keyed capabilities cache, and the
  effective-tenant resolution in `ApiClient`.

## Trust boundaries

- Browser (sessionStorage) → SPA.
- SPA → API (bearer selection: impersonation token replaces the
  operator token, X-Tenant-ID scoped to the impersonated tenant).
- Identity events → cache registries (query client, capabilities).

## Spoofing

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Impersonation without an operator gate | Backend flag-or-role platform-admin gate; the banner signals the session state | `hub/apps/auth/tests/test_impersonation.py` |
| Impersonation token attached to the wrong tenant | `_buildHeaders` swaps the bearer AND scopes `X-Tenant-ID` to the impersonated tenant | `frontend/src/shared/api/client.impersonation.test.ts` |
| Stale identity after reload | The token persists to sessionStorage and is re-read at client construction | `frontend/src/shared/api/client.impersonation.test.ts` |

## Tampering

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Impersonation token survives logout | `clearTokens()` clears the impersonation token with the operator token; exit clears it | `frontend/src/features/admin/impersonation/impersonationStore.test.ts` |
| Cross-tenant cache poisoning after a switch | The capabilities cache holds ONE ENTRY PER TENANT keyed by the impersonation-aware effective tenant; identity-end clears all | `frontend/src/features/capabilities/services/capabilitiesService.identityBoundaries.test.ts` |

## Repudiation

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Impersonation actions unattributable | Start carries `{user_id, reason, max_minutes?}`; the backend audits the session | `hub/apps/auth/tests/test_impersonation.py` |
| Identity-boundary events undocumented | The four bus boundaries (login/logout/auth-failed/tenant-switch) are the pinned contract | `frontend/src/shared/services/cacheIdentity.test.ts` |

## Information disclosure

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Cross-tenant data rendered after a switch | The identity cache bus invalidates the query client + tenant caches at every boundary; E2E proves no cross-tenant render | `frontend/e2e/journeys/cross-persona/identity-boundaries.spec.ts` |
| In-flight queries commit stale tenant data | `cancelQueries()` marks in-flight queries cancelled — their resolutions must NOT commit | `frontend/src/shared/services/cacheIdentity.test.ts` |

## Denial of service

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Capability-fetch storms per render | The capabilities manifest is tenant-cached with switch-back TTL reuse | `frontend/src/features/capabilities/services/capabilitiesService.core.test.ts` |
| Cache-bus throw cascades into the app | Throw-isolation pinned (one invalidator failing never breaks the others) | `frontend/src/shared/services/cacheIdentity.test.ts` |

## Elevation of privilege

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Impersonated bearer leaks into subsequent sessions | sessionStorage dies with the tab; the store clears on exit | `frontend/src/features/admin/impersonation/impersonationStore.test.ts` |
| Anonymous requests carry the impersonation token | The header builder skips the impersonation token for anonymous requests | `frontend/src/shared/api/client.impersonation.test.ts` |

## Open threats (not yet shipped — documented, not claimed)

- The impersonation wire contract is exercised in E2E against the live
  stack (JOURNEY-MPA-010 / UC-AUTH-008) — the spec suite is part of the
  nightly lanes, not the PR gate.
- Service-worker caching of impersonated responses is explicitly
  out of scope (SW is PROD-only and identity-agnostic — W12.7).
