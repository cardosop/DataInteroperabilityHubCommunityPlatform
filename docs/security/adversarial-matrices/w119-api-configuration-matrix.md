# W11.9 — ASVS V13/V14 API & Configuration Matrix

**Change:** `openspec/changes/oss-release-remediation` — W11.9
**Date:** 2026-10-16
**Register rows closed:** 12 (missing rate limiting / abuse controls) and 13
(insecure defaults in infra/config)
**ASVS mapping:** V13.1/V13.2 (rate limiting), V13.5 (CORS/headers), V14.1
(default-secure configuration), V14.4 (fail-closed config validation).

Every cell carries ONE named test. Rate-limit cells are endpoint-level with
the per-surface 429-audit assertion (the Phase 273 contract). Configuration
cells are REAL subprocess boots of the production settings (the W1.18
harness — no replica logic).

## Matrix 1 — Rate-limit matrix (row 12)

| # | Surface | Named test | Expected |
|---|---|---|---|
| 1.1 | Login — IP rate | `hub/apps/auth/tests/test_w119_rate_limit_matrix.py::LoginRateLimitMatrixTest::test_login_ip_rate_429_emits_login_rate_limit_audit` | 429 + `LOGIN_RATE_LIMIT_EXCEEDED` (the pre-fix 429 emitted only a metric) |
| 1.2 | Login — account lockout | `...::test_login_lockout_429_emits_lockout_audit` | 429 + `LOGIN_LOCKOUT_EXCEEDED` |
| 1.3 | Register | `hub/apps/auth/tests/test_register_me.py::test_eleventh_register_in_a_minute_is_throttled` + `test_throttled_register_emits_rate_limit_audit` | 429 + `REGISTRATION_RATE_LIMIT_EXCEEDED` |
| 1.4 | SSO | `...::SSOThrottleAuditTest::test_sso_throttle_exhaustion_emits_sso_audit` | throttled + `SSO_RATE_LIMIT_EXCEEDED` (the emission existed since W1.5 — ZERO assertions until this cell) |
| 1.5 | Password-reset request | `...::PasswordResetRateLimitMatrixTest::test_reset_request_429_emits_audit_at_the_endpoint` | 6th request 429 + `PASSWORD_RESET_RATE_LIMIT_EXCEEDED` (endpoint-level — the pre-fix pins were function-level only) |
| 1.6 | Password-reset CONFIRM | `...::test_reset_confirm_is_throttled` | throttled at ALL (the pre-fix GAP: no throttle existed on the confirmation surface) |
| 1.7 | Upload init | `hub/apps/files/tests/test_file_init_rate_limits.py::FileInitThrottleAuditTest::test_second_init_within_window_emits_upload_rate_limit_audit` | 429 + `FILE_UPLOAD_RATE_LIMIT_EXCEEDED` (pre-fix: no audit) |
| 1.8 | Search / SPARQL / Marketplace / BaaS / API-key | `tests/security/test_throttle_audit_contract.py` | per-surface audit rows — 7/7 (TWO were RED pre-fix: BaaSUsageThrottle had NO emission, and the SPARQL emission crashed on WSGIRequest — both root-fixed) |
| 1.9 | Webhooks outbound | `hub/apps/webhooks/tests/test_outbound_rate_limit.py` | per-tenant delivery cap + `WEBHOOK_RATE_LIMIT_EXCEEDED` |

## Matrix 2 — Default-secure configuration assertions (row 13)

| # | Guard | Named test | Expected |
|---|---|---|---|
| 2.1 | Secure cookies + SSL redirect + HSTS in production | `tests/security/test_w119_configuration_guards.py::TestProductionCookieSslRedirectGuard::test_production_boot_has_secure_cookies_and_redirect` | REAL boot: all True, HSTS 63072000 (the first real-subprocess pin for these — the pre-existing pins were source replicas) |
| 2.2 | Insecure cookie in production fails closed | `...::test_insecure_cookie_in_production_fails_closed` | boot crash |
| 2.3 | CORS — no origins in production fails closed | `TestProductionCORSGuard::test_production_without_cors_origins_fails_closed` | boot crash |
| 2.4 | CORS — origins exact, no localhost | `...::test_production_cors_origins_are_exact` | exact list |
| 2.5 | ALLOWED_HOSTS — unknown Host raises | `TestAllowedHostsValidation::test_unknown_host_header_is_rejected` | `DisallowedHost` (the request-level Host validation — previously untested anywhere) |
| 2.6 | ALLOWED_HOSTS — known Host passes | `...::test_known_host_is_accepted` | passes |
| 2.7 | CORS wildcard checker | `TestProductionCorsChecker::test_check_production_cors_exits_zero` | exit 0 on the tree |
| 2.8 | Cited guards (existing pins) | G12 key fail-closed (real boots), JWT key-pair guard, cookie-domain host-only, ENFORCE_JWT_SCOPES default + helm, magic-byte default + helm, websocket query-param off, RLS arming defaults + GUC sync, CLAMAV policy validation | all cited in the doc below |

## Root fixes shipped by this suite (TDD, RED-first)

1. **BaaSUsageThrottle emitted NOTHING** — the Phase 273 contract pin was RED
   ("found RED, fixed in the same task" per the test docstring — the fix never
   landed). The class now emits `BAAS_RATE_LIMIT_EXCEEDED` in the
   `allow_request` failure branch (the G10 pattern).
2. **SPARQL throttle's audit emission crashed on WSGIRequest** (`request.data`
   AttributeError) — the contract pin was RED. Fixed with a DRF-safe accessor.
3. **Login/lockout/reset-request 429s emitted no audit** — new
   `LOGIN_RATE_LIMIT_EXCEEDED`, `LOGIN_LOCKOUT_EXCEEDED`,
   `PASSWORD_RESET_RATE_LIMIT_EXCEEDED` events + best-effort emission.
4. **Password-reset CONFIRM had no throttle at all** — new
   `PasswordResetConfirmThrottle` (per-IP, 10/hour via
   `AUTH_PASSWORD_RESET_CONFIRM_RATE_LIMIT`). RED-caught en route: the first
   draft assigned `self.rate` AFTER `super().__init__()` — SimpleRateThrottle
   parses num_requests/duration in `__init__`, so the default stayed parsed
   (the BaaS throttle's documented trap, hit again).
5. **File-init 429s emitted no audit** — `FILE_UPLOAD_RATE_LIMIT_EXCEEDED` via
   the `allow_request`-hooked mixin (DRF's base never calls `_on_throttled`).

## OPEN-THREATS (recorded, not claimed fixed)

* **Central `RateLimitMiddleware` 429s emit no audit** — pre-auth context
  (no reliable actor) + audit volume on the backstop path; the per-surface
  throttles own the audit contract. Recorded as a deliberate exclusion.
* **Inbound webhook endpoints have no DRF throttle** — Stripe signature
  verification is the abuse control; throttling legitimate senders would
  drop events. Recorded.
* **Hub API sends no CSP header** (`CSP_DEFAULT_SRC` empty) — the API returns
  JSON only; the nginx edge owns CSP for the frontend location (pinned by the
  nginx/e2e suites). Recorded.
* **Staging helm ships `ALLOWED_HOSTS: "*"`** — the deliberate staging
  posture (unpinned). Recorded for the deploy-tree review.
* `ENFORCE_JWT_SCOPES` production check is warn-only by design (W7.5's
  rollback hatch).
