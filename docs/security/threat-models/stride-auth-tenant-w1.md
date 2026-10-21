# STRIDE Threat Model — Auth & Tenant Isolation (W1)

One-pager for the oss-release-remediation W1 surface (auth/tenant).
Every mitigation cites its verifying test or gate (P4: a mitigation
with no pin is prose). Ledger:
`docs/audits/w111-threat-model-refresh-2026-10-15.md`.

## Scope / assets

- Tenant identity resolution (JWT users, API keys, impersonation,
  worker keys) and the per-request tenant scope.
- Tenant-scoped data in PostgreSQL (RLS), the SSO/OIDC callback, the
  public register/user-create surfaces, API-key minting, the warehouse
  SQL compilers, the SSRF guard, the internal worker file path, the
  error envelope, and the Stripe webhook receivers.

## Trust boundaries

- External caller → API (JWT / API key / SSO callback).
- API/worker process → PostgreSQL (RLS).
- Admin-role maintenance (`meshant_admin`) vs app-role (`meshant_app`).
- Worker internal HTTP surface (shared key) vs public API.

## Spoofing

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| SSO callback accepts forged/expired/wrong-audience id_tokens | `verify_oidc_id_token` checks JWKS signature + pinned iss/aud/exp/sub BEFORE user lookup; RS256/ES256 only (alg confusion closed); roles DB-only; SAML stub deleted | `hub/apps/auth/tests/test_sso_security_tokens.py` |
| Cross-tenant identity spoofing by request | `TenantScopingMiddleware` arms `app.current_tenant_id` + per-table `rls_*_enabled` GUCs transaction-locally (SET LOCAL); fail-closed (NULL/empty → every row hidden); arming failure → 503 | `hub/apps/auth/tests/test_rls_request_path_arming.py` |
| API-key scope self-minting | Per-role scope allowlist on create AND update; `"*"` PLATFORM_ADMIN-only; `scheduled_ingestion:internal` unmintable via the public API | `hub/apps/auth/tests/test_api_key_auth.py` |
| Worker internal surface without auth | Fail-closed env-key comparison (no dev fallback); `HUB_WORKER_API_KEY:?` compose fail-fast | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py` |

## Tampering

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Client-supplied tenant_id on register / user create | Removed from public registration; user create gated like update/destroy; tenant resolved from the REQUEST (divergence → 403); blocking `lint-no-client-tenant-id` CI job | `scripts/tests/test_lint_no_client_tenant_id.py` |
| Warehouse SQL injection via identifiers | Strict unquoted-identifier grammar + ANSI quote doubling + dialect-aware regex escaping + numeric validation in `hub/apps/dq/sql_safety.py`, wired into BOTH compilers | `hub/apps/dq/tests/test_warehouse_sql_compiler.py` |
| SSRF via connection endpoints / redirects | `SSRFGuard` re-validates on every save; webhook single-redirect policy (hop-3 blocked); DQ webhook/Slack deliver-time gates; federation + LDN query-time re-validation | `hub/apps/webhooks/tests/test_asset_webhook_delivery.py` |
| Stripe webhook double-delivery | Atomic `processed` claim (`claim_stripe_event` — one winner via `UPDATE ... WHERE processed=false`); release-on-failure on the billing side | `hub/apps/billing/tests/test_webhook_idempotency.py` |
| Tenant row writes without RLS | Paired RLS policy migration enforced by CI (`lint-rls-policies`); GUC↔settings sync pinned bidirectionally | `scripts/lint_rls_policies.py` |

## Repudiation

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Enforcement actions leave no trace | Every W1.1–W1.18 enforcement point emits its audit event (SSRF blocks, scope-mint denials, registration joins, worker rejections, SQL-safety rejections) | `hub/apps/dq/tests/test_alerting_clients.py` |
| Stripe webhook claims can't be audited | Per-delivery `attempts` counters via `F()` (no read-modify-write) + processed state | `hub/apps/billing/tests/test_webhook_idempotency.py` |

## Information disclosure

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| `str(exc)` leaked in 5xx envelopes | Flat `{detail, code, details}` envelope; no raw exception text; error codes catalogue-gated | `hub/apps/api/tests/test_error_response_contract.py` |
| Pre-tenant identity reads bypass RLS | Routed through `user_lookup_alias()` (the BYPASSRLS admin alias) | `hub/apps/auth/tests/test_rls_middleware_preauth_alias.py` |
| Cross-tenant query leakage | Every tenant-scoped ModelViewSet filters its queryset (automated audit + allowlist, `scripts/lint_queryset_coverage.py` in `make quality-gates`) | `scripts/lint_queryset_coverage.py` |

## Denial of service

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Registration / SSO abuse | `RegisterThrottle` + `SSOThrottle` (10/min per IP) with audited 429s | `hub/apps/auth/tests/test_register_me.py` |
| Oversized/malicious worker uploads | Per-file cap enforced BEFORE the full read (`FILE_TOO_LARGE`); unknown extensions rejected (`UNSUPPORTED_FORMAT`) | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py` |
| Malware via uploads | Magic-byte detection default-ON; ClamAV enqueue on the internal path; `SCAN_UNAVAILABLE_POLICY` boot-validated | `hub/apps/files/tests/test_magic_bytes.py` |

## Elevation of privilege

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Impersonation without gate | Flag-or-role platform-admin gate; impersonation audit trail | `hub/apps/auth/tests/test_impersonation.py` |
| RLS kill-switch abuse | Every `app.rls_*_enabled` policy GUC paired with an `RLS_*_ENABLED` settings switch, pinned bidirectionally | `hub/apps/auth/tests/test_rls_guc_settings_sync.py` |
| Cross-tenant scope leak across pooled connections | GUCs are `SET LOCAL` inside the request transaction (evaporate at COMMIT/ROLLBACK — PgBouncer-safe) | `hub/apps/auth/tests/test_rls_middleware_guc.py` |
| User-role self-escalation | `role_ids` ∩ requester-assignable → 403 `ROLE_ASSIGNMENT_FORBIDDEN` | `hub/apps/users/tests/test_user_create_hardening.py` |

## Open threats (not yet shipped — documented, not claimed)

- W1.20 RLS arming: the 72h staging soak + production flip are
  ops-scheduled, not yet run (the arming path itself ships armed).
- Unchecked tasks.md boxes: W1.6 GraphQL token-version, W1.8
  stop-the-line, W1.9 pip-audit, W1.10 refresh grace, W1.12 presigned
  replay, W1.15 SPARQL validator — tracked as open lanes, not
  mitigations.
