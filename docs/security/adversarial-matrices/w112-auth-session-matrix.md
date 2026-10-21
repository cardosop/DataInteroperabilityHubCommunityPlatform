# W11.2 — ASVS V2/V3 Auth & Session Adversarial Matrix

**Change:** `openspec/changes/oss-release-remediation` — W11.2
**Date:** 2026-10-15
**Register rows closed:** 6 (broken authentication) and 8 (scopes/roles as decoration)
**ASVS mapping:** V2.1–V2.5 (password/credential auth — JWT + refresh), V2.8 (token strength),
V2.9 (token lifecycle: mint/rotate/revoke), V3.2 (session binding), V3.3 (logout invalidation),
V3.5 (server-side session storage), V4.1 (API access control — the API-key scope surface).

Every cell carries ONE named test, run live against the real stack (real scripted IdP over
TCP, real DRF stack, real DB rows, real minted keys — no mocks). The cells are verified
mechanically by `scripts/tests/test_w112_matrix_veracity.py`: a cited test that does not
resolve on disk flips the pin RED.

Sessions/token storage: refresh tokens are stored SERVER-SIDE as SHA-256 hashes
(`hub/apps/auth/models.py` `RefreshToken` — plaintext never persisted), access JWTs are
stateless with a DB-checked `authz_version`, and browser delivery is httpOnly Secure
SameSite=Strict cookies (pinned by the cookie-precedence cells in
`hub/apps/auth/tests/test_security_hardening.py`).

---

## Matrix 1 — SSO forged-token (register row 6)

The OIDC callback verifies signature (JWKS), issuer, audience, expiry and sub BEFORE any
user lookup (`hub/apps/auth/oidc_verifier.py`); roles come from the DB only. Every
attacker-controlled token class is rejected with a classified 400 — never token material.

| # | Attack class | Named test | Expected | Status |
|---|---|---|---|---|
| 1.1 | Unsigned / garbage token | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_forged_garbage_token_400s_and_creates_no_user` | 400 `OIDC_TOKEN_SIGNATURE_INVALID`, no user row | PASS |
| 1.2 | alg=none | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_alg_none_token_400s` | 400, classified | PASS |
| 1.3 | Alg-swap RS256→HS256 (public key as HMAC secret) | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_hs256_confusion_token_400s` | 400, classified | PASS |
| 1.4 | Key substitution — attacker RSA key claiming the IdP's `kid` | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::SSOForgedTokenMatrixExtensionTest::test_attacker_rsa_key_signed_token_400s` | 400 `OIDC_TOKEN_SIGNATURE_INVALID`, no user row | PASS |
| 1.5 | Unknown `kid` | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_unknown_kid_token_400s` | 400, classified | PASS |
| 1.6 | Wrong audience | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_wrong_audience_token_400s` | 400 `OIDC_TOKEN_AUDIENCE_MISMATCH` | PASS |
| 1.7 | Wrong issuer | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_wrong_issuer_token_400s` | 400 `OIDC_TOKEN_ISSUER_MISMATCH` | PASS |
| 1.8 | Expired (validly signed) | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_expired_token_400s` | 400 `OIDC_TOKEN_EXPIRED` | PASS |
| 1.9 | Missing `sub` | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_missing_sub_token_400s` | 400 `OIDC_TOKEN_SUB_MISSING` | PASS |
| 1.10 | Role forgery — `roles`/`groups` claims | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_role_claims_are_ignored` | claims ignored; DB roles only | PASS |
| 1.11 | Missing state (no unverified-claims fallback) | `hub/apps/auth/tests/test_sso_state_binding.py::SSOStateBindingOIDCTest::test_missing_state_with_multi_membership_fails_closed` | 400 `SSO_STATE_MISSING` | PASS |
| 1.12 | State replay | `hub/apps/auth/tests/test_sso_state_binding.py::SSOStateBindingOIDCTest::test_replayed_state_returns_400_sso_state_reused` | 400 `SSO_STATE_REUSED` | PASS |
| 1.13 | State IP-class mismatch | `hub/apps/auth/tests/test_sso_state_binding.py::SSOStateBindingOIDCTest::test_state_with_different_ip_class_returns_400` | 400 `SSO_STATE_IP_MISMATCH` | PASS |
| 1.14 | ES256 positive control (EC JWK path) | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::SSOES256PositiveControlTest::test_es256_id_token_authenticates` | 200, user created | PASS |
| 1.15 | Callback abuse throttle | `hub/apps/auth/tests/test_sso_security_tokens.py::SSOCallbackThrottleTest::test_eleventh_callback_is_throttled` | 429 + `SSO_RATE_LIMIT_EXCEEDED` audit | PASS |

## Matrix 2 — JWT lifecycle: rotation / revocation / grace / versioning (register row 6)

Refresh tokens rotate as families (`family_id` + `sequence_number`, SHA-256-hashed at
rest, 30-day absolute cap); theft detection revokes the whole family; `authz_version`
invalidates access JWTs at the DB layer.

| # | Lifecycle cell | Named test | Expected | Status |
|---|---|---|---|---|
| 2.1 | Rotation — current token → old revoked, sibling seq+1, same family, tenant pinned | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::JWTLifecycleMatrixTest::test_refresh_rotation_revokes_old_and_mints_tenant_pinned_sibling` | 200; exactly 2 family rows | PASS |
| 2.2 | Rotation — SSO-originated session rotates via /auth/refresh | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::SSOSessionLifecycleTest::test_sso_session_rotates_via_refresh_endpoint` | 200; seq 0→1 | PASS |
| 2.3 | SSO login mints a refresh family (lifecycle parity with password login) | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::SSOSessionLifecycleTest::test_sso_login_mints_refresh_family_and_links_session` | refresh row + cookie + linked claim | PASS |
| 2.4 | Revocation — theft replay outside window revokes the whole family | `hub/apps/auth/tests/test_refresh_grace_w110.py::RefreshGraceRetryOnlyTest::test_replay_outside_window_revokes_family` | 401, family revoked | PASS |
| 2.5 | Revocation — logout-all bumps `token_version` → access JWT 401s | `hub/apps/auth/tests/test_logout_all_revokes_access_jwt.py::LogoutAllRevokesAccessJWTTest::test_logout_all_invalidates_existing_access_token` | 401 `TOKEN_INVALIDATED`; relogin works (`test_relogin_issues_new_version_and_access_succeeds`) | PASS |
| 2.6 | Revocation — sessions listing identifies the bearer's session | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::JWTLifecycleMatrixTest::test_list_sessions_marks_bearer_session_current` | `is_current` on the `refresh_token_id`-linked row | PASS |
| 2.7 | Grace — stale token inside window: 401 `TOKEN_STALE`, nothing minted, nothing revoked | `hub/apps/auth/tests/test_refresh_grace_w110.py::RefreshGraceRetryOnlyTest::test_stale_presenter_inside_window_gets_401_and_nothing_else` | 401 `TOKEN_STALE`, no cookies, sibling survives | PASS |
| 2.8 | Grace — original holder retries with the current token | `hub/apps/auth/tests/test_refresh_grace_w110.py::RefreshGraceRetryOnlyTest::test_original_holder_retry_with_current_token_succeeds` | 200 | PASS |
| 2.9 | Grace disabled → immediate family revocation | `hub/apps/auth/tests/test_refresh_grace_w110.py::RefreshGraceRetryOnlyTest::test_grace_disabled_revokes_family_immediately` | 401, family revoked | PASS |
| 2.10 | Versioning — REST per-request `authz_version` check | `hub/apps/auth/tests/test_authentication_edge_cases.py::JWTAuthenticationEdgeCases::test_token_version_invalidated` | 401 `TOKEN_INVALIDATED` | PASS |
| 2.11 | Versioning — GraphQL path rejects version-bumped tokens | `hub/apps/graphql/tests/test_graphql_auth.py::StrawberryGraphQLAuthTest::test_revoked_token_returns_401` | HTTP 401, `TOKEN_INVALIDATED` | PASS |
| 2.12 | Expiry — expired refresh token | `hub/apps/auth/tests/test_authentication_flows.py::AuthenticationFlowsTest::test_refresh_token_expired` | 401 `TOKEN_EXPIRED` | PASS |

## Matrix 3 — API-key: scope x endpoint x role (register row 8)

Minting is bounded by `disallowed_mint_scopes` (per-role allowlist, `"*"` PLATFORM_ADMIN-only,
worker-internal scopes unmintable, owner-or-admin mutations). Enforcement is live on the
scope-gated surfaces; keys always scope-checked regardless of `ENFORCE_JWT_SCOPES`.

**Enforcement cells** (real keys, real DRF endpoints):

| # | Scope x endpoint x role cell | Named test | Expected | Status |
|---|---|---|---|---|
| 3.1 | `assets:read` key → asset write | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_assets_read_cannot_create_asset` | 403 | PASS |
| 3.2 | `assets:write` key → asset write | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_assets_write_creates_asset` | 201 | PASS |
| 3.3 | Empty-scope key → asset write | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_empty_scopes_denied_asset_create` | 403 | PASS |
| 3.4 | Wildcard key → asset write | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_wildcard_creates_asset` | 201 | PASS |
| 3.5 | `assets:read` key → asset list (reads are IsAuthenticated-only by design) | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_assets_read_can_list_assets` | 200 | PASS |
| 3.6 | Unrelated scope → transformation read | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_unrelated_scope_denied_transformation_read` | 403 | PASS |
| 3.7 | `transformation:read` key → pipeline list | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_transformation_read_lists_pipelines` | 200 | PASS |
| 3.8 | `transformation:read` key → pipeline write | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_transformation_read_cannot_create_pipeline` | 403 | PASS |
| 3.9 | `transformation:write` key → pipeline write | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_transformation_write_creates_pipeline` | 201 | PASS |
| 3.10 | Role gate — DATA_CONSUMER owner + `integrations:write` key | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_integrations_write_without_role_denied` | 403 | PASS |
| 3.11 | Scope gate — DATA_PROVIDER owner + `integrations:read` key | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_integrations_read_with_role_denied` | 403 | PASS |
| 3.12 | Role + scope both satisfied | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_integrations_write_with_role_allowed` | 201 | PASS |
| 3.13 | Platform-admin owner WITHOUT the scope — scope gate still applies | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_platform_admin_key_without_scope_denied` | 403 | PASS |
| 3.14 | Cross-tenant — key + foreign `X-Tenant-Id` header | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_key_with_foreign_xtenant_header_403` | 403 (tenant bound to the credential) | PASS |
| 3.15 | `HasAnyScope` honors the wildcard on the key branch | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_has_any_scope_wildcard_covers_api_key` | allowed | PASS |
| 3.16 | `HasAnyScope` limited key misses | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_has_any_scope_limited_key_misses` | denied | PASS |

**Minting-restriction cells**:

| # | Cell | Named test | Expected |
|---|---|---|---|
| 3.17 | Member cannot mint `"*"` | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_member_cannot_mint_wildcard` | 400 `API_KEY_SCOPE_MINT_DENIED` |
| 3.18 | TENANT_ADMIN cannot mint `"*"` | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_tenant_admin_cannot_mint_wildcard` | 400 |
| 3.19 | PLATFORM_ADMIN can mint `"*"` | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_platform_admin_can_mint_wildcard` | 201 |
| 3.20 | Out-of-role scope denied | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_member_cannot_mint_out_of_role_scopes` | 400 |
| 3.21 | Role-subset mint allowed | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_member_can_mint_role_subset` | 201 |
| 3.22 | Consumer cannot mint provider-write scope | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_consumer_cannot_mint_provider_write_scope` | 400 |
| 3.23 | `scheduled_ingestion:internal` unmintable by a member | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_internal_scope_unmintable_by_member` | 400 |
| 3.23b | `scheduled_ingestion:internal` unmintable by a platform admin | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_internal_scope_unmintable_by_platform_admin` | 400 |
| 3.24 | `scheduled_export:internal` unmintable by platform admin (W11.2 fix) | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_platform_admin_cannot_mint_scheduled_export_internal` | 400 `API_KEY_SCOPE_MINT_DENIED` |
| 3.25 | Key-authenticated mint bounded by the OWNER's live roles (downgraded owner) | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_api_key_authenticated_mint_cannot_exceed_owner_roles` | 400 `API_KEY_SCOPE_MINT_DENIED` |
| 3.26 | Control — within owner's live roles | `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_api_key_authenticated_mint_within_owner_roles_succeeds` | 201 |
| 3.27 | Another member's key 404s (owner-or-admin) | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_patch_other_members_key_404s` | 404 |
| 3.28 | Own-key scope escalation on PATCH denied | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_patch_own_key_scope_escalation_400s` | 400 |

**Worker-internal surface**:

| # | Cell | Named test | Expected |
|---|---|---|---|
| 3.29 | No key → fail-closed (env key unset) | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py::InternalWorkerFileHardeningTest::test_no_key_fail_closed_with_env_key_unset` | 401 |
| 3.30 | DB key without the internal scope | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py::InternalWorkerAPITest::test_reject_token_without_scope` | 401/403 |
| 3.31 | Key + foreign `X-Tenant-Id` | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py::InternalWorkerFileHardeningTest::test_db_api_key_tenant_mismatch_rejected` | 403 |
| 3.32 | Key + own tenant header (control) | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py::InternalWorkerFileHardeningTest::test_db_api_key_matching_tenant_header_allowed` | 201 |

## Root causes fixed by this suite (TDD RED-first)

The RED phase exposed five live defects, each root-fixed in the same change:

1. **The W1.10 grace contract had never landed in the view.** `hub/apps/auth/views.py`
   still minted the replay presenter a fresh pair and revoked the victim's sibling
   (200) — the takeover primitive G5 forbids. The branch now implements the
   retry-only contract: 401 `TOKEN_STALE`, nothing minted, nothing revoked
   (cells 2.7–2.9 + the legacy-permissive pin in
   `hub/apps/auth/tests/test_security_hardening.py` rewritten to the
   enforced contract).
2. **SSO sessions were lifecycle orphans.** The callback minted only an access JWT —
   no `RefreshToken` row, no refresh cookie. SSO sessions now mint a refresh family
   linked into the access JWT (cells 2.2, 2.3) — parity with password login.
3. **Sessions listing read the wrong claim.** `list_active_sessions` decoded
   `refresh_token_jti`/`jti` (a random uuid) while the JWT mints `refresh_token_id` —
   the current-session marker silently fell back to "most recent". Fixed to the real
   claim (cell 2.6).
4. **API-key-authenticated minting used the key's own scopes as the allowlist.** A
   leaked key minted sibling keys with its own scope set, and a downgraded owner's old
   key kept minting its former scopes. The mint allowlist now derives from the OWNER's
   live role-derived scopes (cells 3.25, 3.26; `_get_mint_scope_allowlist` in
   `hub/apps/auth/permissions.py`).
5. **`scheduled_export:internal` was mintable by a wildcard holder.** Both
   worker-internal scopes are now name-blocked in `disallowed_mint_scopes`, and the
   export scope moved into the shared vocabulary
   (`hub/apps/auth/scopes.py` `SCOPE_SCHEDULED_EXPORT_INTERNAL`, re-imported by
   `hub/apps/scheduled_export/internal_auth.py` and the scoping middleware)
   (cell 3.24). `HasAnyScope`'s API-key branch also honors the wildcard like the
   JWT branch (cells 3.15/3.16).

## OPEN-THREATS (recorded, not claimed fixed)

* **Scoped keys do not constrain role-only / IsAuthenticated-only endpoints.** A key
  with `["assets:read"]` still authenticates AS the owner against surfaces with no
  scope gate (files upload, marketplace orders, jobs, users, search, audit, billing,
  governance, compliance, consent, datasets, warehouses…). Scope enforcement is live
  on the HasScope surfaces (ml, assets writes, integrations, transformation, mesh,
  virtualization, the two worker-internal surfaces) only. Assigning scopes to the
  remaining endpoints is an access-control design change — owned by **W11.3**
  (access-control regression matrix), not this suite.
* **BaaS-minted keys carry empty scopes.** The BaaS workflow creates auth-model keys
  without scopes — they pass IsAuthenticated-only endpoints and fail every scope gate.
  Same ownership as above.
* **Bare SHA-256 key hashes** (no salt/HMAC). Mitigated by 43-char `token_urlsafe`
  keys, but a slow-hash (bcrypt/argon2) is the long-term fix — tracked with the W11.5
  crypto row (18).
* **API keys always scope-checked; `ENFORCE_JWT_SCOPES=false` is a JWT-only hatch**
  (pinned by
  `hub/apps/auth/tests/test_scope_bypass_prevention.py::TestEnforceJwtScopesDefault::test_code_default_is_true`).

## Verification

* New suite: `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py` — 25 named
  tests, live, no mocks.
* Cited pre-existing cells re-run green in the same verification pass (W1.5 SSO
  battery, W1.10 grace matrix, W1.3a minting pins, W1.14 worker pins, W7.5 scope
  enforcement, W1.6 GraphQL 401).
* Veracity pin: `scripts/tests/test_w112_matrix_veracity.py` — every cell's cited
  test resolves on disk (AST), every backticked artifact citation exists, the
  register rows 6/8 in `openspec/changes/oss-release-remediation/design.md` cite this
  doc.
