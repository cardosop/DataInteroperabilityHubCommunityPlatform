# Stub / Placeholder Inventory — 2026

Tracked disposition of every shipped stub/placeholder class (W12.7,
oss-release-remediation). Each row is either **WIRED** (the real
implementation shipped and is pinned), **DELETED** (removed — git
history preserves it, a reintroduction flips GATE-61 RED), or
**TICKET-DEFERRED** (annotated at the site with `TICKET=<id>
EXPIRES=<date>`, GATE-40-compatible). Zero untriaged rows.

| ID | Stub class | Status | Evidence (what shipped / where it went) |
|---|---|---|---|
| STUB-001 | SAML SSO (`SAML returns {}`) | DELETED | D4/W1.5 decision: OIDC-with-JWKS is the only SSO. `hub/apps/auth/sso.py:4` records the deletion; the `NotImplementedError` at `sso.py:44` is the abstract base `SSOProvider.authenticate`, not a shipped stub. GATE-61 marker: no `SAMLProvider` class in non-test hub code. |
| STUB-002 | MFA (dead feature) | DELETED | Phase-removed; `hub/apps/auth/tests/test_mfa_removed.py` pins the absence. GATE-61 marker: no `mfa` URL route in non-test hub code. |
| STUB-003 | Audit-log pagination (`console.log('Next page')`, `useState(1)` no setter) | WIRED | Real prev/next pagination shipped (the sibling `AdminAuditLogPage` pattern: `setPage`-driven requests, wire-derived disabled states, reset-on-filter, `count · Page N`); the dead Phase-234.3 load-more reducer (18 tests, zero consumers) was DELETED. Pins: `frontend/src/features/audit/components/AuditEventListPage.test.tsx` 3/3 + `frontend/src/features/audit/services/auditService.test.ts` +3. |
| STUB-004 | E2E suite all-commented-out | WIRED | `frontend/e2e/features/*.spec.ts` run real flows under the 1.3/1.4 contracts (every skip CONDITIONAL — no `test.skip(true)`; real backend only). |
| STUB-005 | Web-vitals collected-then-discarded (280.B.1.5) | WIRED | `frontend/src/main.tsx` imports `shared/telemetry/webVitals` (side-effect registration of onCLS/onFCP/onLCP/onTTFB → beacon to `/api/v1/analytics/web-vitals/`); the documented placeholder `reportCurrentVitals()` was DELETED (web-vitals are page-load metrics, not route metrics). |
| STUB-006 | Dead `sw.js` (shipped, never registered) | WIRED | `frontend/src/main.tsx` registers `/sw.js` in production builds only (dev/E2E stay SW-free so cached assets can't mask regressions); non-blocking per the SW's own contract. |
| STUB-007 | Deprecation-sunset enforcement (sunset dates never 410) | WIRED | `APIVersionMiddleware.process_request` now returns **410 `ENDPOINT_SUNSET`** (canonical envelope + `replacement`/`migration_guide` details) for endpoints past their `sunset_date` — the pre-fix path only SKIPPED the warning header, so sunset endpoints served silently. Pins: `hub/apps/api/tests/test_versioning_comprehensive.py::APIVersionMiddlewareTest` (+2: past-sunset → 410, future-sunset → serves). The registry is empty — enforcement is dormant until a sunset date registers. |
| STUB-008 | `CI_CD_SUMMARY` reconciliation ("6 workflows" vs 79) | DELETED | W12.8 correction: the W12.7 disposition had watched `docs/CI_CD_SUMMARY.md` (never shipped) while the liar lived at `.github/workflows/CI_CD_SUMMARY.md` — a stale "Total Workflows: 6" summary vs ~79 shipped yml files. The real file is now DELETED (`git rm`); the maintained workflow overview is `.github/workflows/README.md`. GATE-61 marker: `.github/workflows/CI_CD_SUMMARY.md` absent. |

All eight rows triaged; the gate (`scripts/check_stub_inventory.py`,
GATE-61) enforces the statuses above against the live tree.
