# ASVS Evidence Pack — V1–V14 (2026)

**Change:** `openspec/changes/oss-release-remediation` — W11.13
**Date:** 2026-10-16
**Standard:** OWASP Application Security Verification Standard 4.0.3
**Acceptance:** every category (V1–V14) at **Level 2 or higher** with
citations. Enforced mechanically by
`scripts/tests/test_w1113_asvs_evidence_pack_veracity.py` (CI no-django
lint): all fourteen chapters must exist, every chapter must declare
`**Declared level: Level ≥2**`, every named-test citation must resolve
on disk (AST), every line-anchor citation must sit inside a real test
function, every artifact citation must exist, and every chapter must
carry ≥3 citations (a prose-only chapter is not evidence).

**Citation grammar:** a backticked path ending in
`::TestClass::test_name` names a test (AST-resolved); a backticked
path ending in `:NNN` is a line anchor (for test files the line must
sit inside a test function); any other backticked committed
report/config path is an artifact citation (must exist on disk).

**Evidence-chain closure:** the pack leans on the W11.x verification
artifacts, and cites the veracity pins that keep THOSE honest:
`scripts/tests/test_w111_threat_model_veracity.py`,
`scripts/tests/test_w112_matrix_veracity.py`,
`scripts/tests/test_w113_idor_matrix_veracity.py`,
`scripts/tests/test_w114_property_suites_veracity.py`,
`scripts/tests/test_w115_crypto_random_sweep.py`,
`scripts/tests/test_w116_exc_str_leak_ban.py`,
`scripts/tests/test_w117_business_logic_matrix_veracity.py`,
`scripts/tests/test_w118_upload_abuse_veracity.py`,
`scripts/tests/test_w119_api_configuration_veracity.py`,
`scripts/tests/test_w1110_security_tooling_gates.py`,
`scripts/tests/test_w1112_ai_threat_model_veracity.py`.

**Paid-layer note (D5):** the AI/ML surfaces are paid-layer apps; their
evidence (V1.4, V13 AI throttles) travels with the scoping note — the
verification artifacts are committed, the feature is not advertised as
shipped.

## Summary

| Chapter | Declared level | Evidence anchors |
|---|---|---|
| V1 Architecture & Threat Modeling | Level 2 | STRIDE models ×6 surfaces, register, secure-SDLC gates |
| V2 Authentication | Level 2 | W11.2 adversarial matrix, SSO forgery/confusion, API-key scopes, PBKDF2 |
| V3 Session Management | Level 2 | JWT family revocation, refresh grace, secure cookies |
| V4 Access Control | Level 2 (L3-scale breadth) | W11.3: 836 tests / 588 keys / 99.66% probed; RLS arming |
| V5 Validation & Sanitization | Level 2 | SQL compiler grammar gates, SSRF multi-surface, CSV-injection |
| V6 Stored Cryptography | Level 2 | GATE-62 CSPRNG sweep, PBKDF2-first, Fernet/KMS rotation |
| V7 Error Handling & Logging | Level 2 | leak-ban source gate + runtime pins, typed envelopes |
| V8 Data Protection | Level 2 | PII map + redaction, encryption coverage, retention |
| V9 Communications | Level 2 | HSTS/CSP/XFO/nosniff at the edge, secure cookies, TLS upstream |
| V10 Malicious Code | Level 2 | pip-audit/npm-audit/trivy/gitleaks blocking, no-extraction gate |
| V11 Business Logic | Level 2 | W11.7 45-cell matrix, money path, race pins |
| V12 Files & Resources | Level 2 | W11.8 abuse suite, presigned-replay staging design, worker caps |
| V13 API & Web Service | Level 2 | rate-limit matrix + 429 audits, CORS/CSRF, GraphQL |
| V14 Configuration | Level 2 | real-boot config guards, kill-switch sync, key fail-closed |

---

## V1 — Architecture, Design and Threat Modeling

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V1.1 Secure SDLC | Blocking gates on every PR: semgrep local rules, bandit ratchet, dependency-vuln triage, trivy on images, gitleaks — each with planted-violation pins | `scripts/tests/test_w1110_security_tooling_gates.py::test_semgrep_local_rules_clean_on_the_tree`, `scripts/tests/test_w1110_security_tooling_gates.py::test_bandit_ratchet_is_blocking_in_code_quality_workflow`, `scripts/tests/test_w1110_security_tooling_gates.py::test_deploy_trivy_gate_is_blocking_critical_high`, `scripts/tests/test_w1110_security_tooling_gates.py::test_gitleaks_ci_job_is_blocking` |
| V1.2 Secrets & key management | No committed dev-secret fallbacks; every Django process requires explicit keys; compose files declare keys explicitly | `scripts/tests/test_w92_bootstrap.py::test_settings_has_no_well_known_dev_secret_fallbacks`, `scripts/tests/test_w92_bootstrap.py::test_settings_has_universal_fail_closed_key_guard`, `scripts/tests/test_w92_bootstrap.py::test_staging_compose_declares_keys_explicitly` |
| V1.4 Threat modeling | STRIDE one-pagers for six shipped surfaces, each mitigation citing its verifying test (P4) — pin-enforced | `scripts/tests/test_w111_threat_model_veracity.py::test_all_five_stride_pages_exist`, `scripts/tests/test_w111_threat_model_veracity.py::test_every_cited_artifact_exists`, `docs/security/threat-models/stride-ai-surfaces-w11.md`, `docs/security/threat-models/stride-money-w2.md` |
| V1.5 Component inventory | The vibe-code register maps the OWASP/CWE failure classes to repo evidence with EXECUTED annotations per lane | `openspec/changes/oss-release-remediation/design.md` |
| V1.10 Malicious-input handling in architecture | The AI/LLM surfaces carry a dedicated threat model + red-team matrix (paid layer) | `docs/security/adversarial-matrices/w1112-ai-prompt-injection-matrix.md`, `scripts/tests/test_w1112_ai_threat_model_veracity.py::test_matrix_doc_exists_with_required_sections` |

## V2 — Authentication

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V2.1 Password security | PBKDF2-first production hashing declaration; iterations meet ASVS V6 guidance; legacy-hash verify-only | `hub/apps/auth/tests/test_w115_password_hashing.py::test_production_block_declares_pbkdf2_first`, `hub/apps/auth/tests/test_w115_password_hashing.py::test_pbkdf2_iterations_meet_asvs_v6` |
| V2.2 General authenticator security | SSO callback rejects forged/expired/garbage tokens, alg=none, HS256-confusion, wrong issuer/audience, unknown kid — no user created | `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_alg_none_token_400s`, `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_hs256_confusion_token_400s`, `hub/apps/auth/tests/test_sso_security_tokens.py::OIDCCallbackSecurityTest::test_wrong_issuer_token_400s` |
| V2.4 Credential storage | Hashing-strength audit committed; rotation command skips non-Fernet ciphertext instead of double-wrapping | `docs/audits/w115-crypto-audit-2026-10-16.md`, `hub/apps/webhooks/tests/test_key_rotation_command.py::test_rotation_skips_aws_kms_prefixed_rows` |
| V2.7/2.8 Logout & one-time tokens | SSO state is IP-bound + single-use; logout-all revokes the live access JWT family | `hub/apps/auth/tests/test_sso_state_binding.py::SSOStateBindingOIDCTest::test_replayed_state_returns_400_sso_state_reused`, `hub/apps/auth/tests/test_logout_all_revokes_access_jwt.py::LogoutAllRevokesAccessJWTTest::test_logout_all_invalidates_existing_access_token` |
| V2.9 Credential recovery / lockout | Login IP rate-limit + account lockout both audited; register throttle per-IP | `hub/apps/auth/tests/test_w119_rate_limit_matrix.py::LoginRateLimitMatrixTest::test_login_ip_rate_429_emits_login_rate_limit_audit`, `hub/apps/auth/tests/test_register_me.py::test_eleventh_register_in_a_minute_is_throttled` |
| V2.10 Service credentials | API-key minting is role-scope-bounded; internal scopes unmintable; cross-member patch 404s | `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_member_cannot_mint_out_of_role_scopes`, `hub/apps/auth/tests/test_api_key_auth.py::APIKeyMintingRestrictionsTest::test_internal_scope_unmintable_by_member`, `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py::APIKeyScopeEndpointRoleMatrixTest::test_api_key_authenticated_mint_cannot_exceed_owner_roles` |
| V2 matrix (whole surface) | The W11.2 adversarial matrix pins every cell | `docs/security/adversarial-matrices/w112-auth-session-matrix.md`, `scripts/tests/test_w112_matrix_veracity.py::test_every_cell_citation_resolves` |

## V3 — Session Management

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V3.5 Token-based session (JWT) | Refresh-grace window: a stale presenter gets 401 and nothing else; replay outside the window revokes the family; original holder retry succeeds | `hub/apps/auth/tests/test_refresh_grace_w110.py::RefreshGraceRetryOnlyTest::test_stale_presenter_inside_window_gets_401_and_nothing_else`, `hub/apps/auth/tests/test_refresh_grace_w110.py::RefreshGraceRetryOnlyTest::test_replay_outside_window_revokes_family` |
| V3.3 Logout invalidation | Logout-all invalidates existing access tokens (the family, not just the refresh side) | `hub/apps/auth/tests/test_logout_all_revokes_access_jwt.py::LogoutAllRevokesAccessJWTTest::test_logout_all_invalidates_existing_access_token` |
| V3.4 Cookie attributes | Production boot: `SESSION_COOKIE_SECURE=true` enforced; insecure cookie in production FAILS CLOSED (real subprocess boot) | `tests/security/test_w119_configuration_guards.py::TestProductionCookieSslRedirectGuard::test_production_boot_has_secure_cookies_and_redirect`, `tests/security/test_w119_configuration_guards.py::TestProductionCookieSslRedirectGuard::test_insecure_cookie_in_production_fails_closed` |
| V3.2/3.7 Session binding & expiry | Token-version invalidation + refresh expiry pins | `hub/apps/auth/tests/test_authentication_edge_cases.py::JWTAuthenticationEdgeCases::test_token_version_invalidated`, `hub/apps/auth/tests/test_authentication_flows.py::AuthenticationFlowsTest::test_refresh_token_expired` |

## V4 — Access Control

**Declared level: Level 2** (breadth is L3-scale: 836 tests, 588 route-keys, 99.66% probed)

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V4.1 Object-level authorization | Every tenant-scoped route key probed with the strict cross-tenant contract (404 never 403; created rows land in the caller's tenant; foreign references 404 before execution) — 586 probed + 2 allowlisted | `tests/security/test_w113_asvs_v4_access_control.py`, `docs/api-audit/idor-probe-manifest.json`, `docs/audits/w113-asvs-v4-access-control-2026-10-15.md` |
| V4.1 enforcement ratchet | Manifest parses; every allowlist entry has a reason; coverage ≥ 95% static threshold | `scripts/tests/test_w113_idor_matrix_veracity.py::test_manifest_exists_and_parses`, `scripts/tests/test_w113_idor_matrix_veracity.py::test_static_coverage_meets_the_95_percent_threshold`, `scripts/tests/test_w113_idor_matrix_veracity.py::test_every_allowlist_entry_matches_a_manifest_route` |
| V4.2/Database layer (defense in depth) | RLS arming contract: every deployed policy GUC has a paired settings kill switch, bidirectionally pinned; master switch never a table flag | `hub/apps/auth/tests/test_rls_guc_settings_sync.py::test_every_deployed_policy_guc_has_a_paired_settings_kill_switch`, `hub/apps/auth/tests/test_rls_guc_settings_sync.py::test_master_switch_is_not_treated_as_a_table_flag` |
| V4.2 AI surface | NL-search tenant isolation through the real stack: tenant B never sees tenant A's rows | `tests/security/test_ai_security.py::AITenantIsolationSecurityTest::test_natural_language_search_tenant_b_does_not_see_tenant_a_assets` |
| V4.3 Functional access control | Scopes enforced by default (`ENFORCE_JWT_SCOPES` code-default True); platform-admin gate checks the flag, not role names | `hub/apps/auth/tests/test_scope_bypass_prevention.py::TestEnforceJwtScopesDefault::test_code_default_is_true` |

## V5 — Validation, Sanitization and Encoding

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V5.3.4-5.3.6 SQL injection | Both warehouse SQL compilers are the ONLY SQL construction in both apps; strict identifier/FQN grammar gates — property-tested that invalid columns/FQNs never reach SQL | `hub/apps/dq/tests/test_w29_sql_injection_properties.py`, `hub/apps/compliance/tests/test_w29_sql_injection_properties.py::test_grammar_invalid_columns_never_reach_sql`, `hub/apps/compliance/tests/test_w29_sql_injection_properties.py::test_grammar_invalid_table_fqns_never_reach_sql` |
| V5.5 Deserialization / V5.2 sanitization | Archive extraction ABSENT from the non-test tree (AST gate) — zip containers rejected at every gate, never decompressed | `scripts/tests/test_w118_upload_abuse_veracity.py::test_no_archive_extraction_anywhere_in_the_non_test_tree` |
| V5.2.4-5.2.6 SSRF | SSRFGuard fail-closed on warehouse private endpoints (re-validated on EVERY save), webhook single-redirect policy, DQ alerting clients, federation query-time re-validation, LDN inbox URLs | `hub/apps/integrations/tests/security/test_ssrf.py`, `hub/apps/warehouses/tests/test_signals.py`, `hub/apps/dq/tests/test_alerting_clients.py` |
| V5.2.3 Output encoding (CSV/formula injection) | Formula prefixes neutralized for spreadsheet sinks; benign strings unchanged | `hub/apps/core/tests/test_output_safety.py::test_equals_prefix_neutralised`, `hub/apps/core/tests/test_output_safety.py::test_benign_strings_pass_through_unchanged` |
| V5 property coverage | ODPS payload property suites + fuzz corpus (6 suites 51/51, corpus replayed) | `scripts/tests/test_w114_property_suites_veracity.py`, `docs/security/fuzz/w114-property-corpus.json` |
| V5.2 XSS (frontend) | React-escaped rendering + CSP with script-src 'self' at the edge | `frontend/nginx.conf:139`, `frontend/src/features/ai/components/SchemaMatchingPage.tsx` |

## V6 — Stored Cryptography

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V6.2.1/V6.4 Password hashing | PBKDF2 declared FIRST in production; the only MD5-first block is the test-env speed swap; iterations pinned to ASVS guidance | `hub/apps/auth/tests/test_w115_password_hashing.py::test_production_block_declares_pbkdf2_first`, `hub/apps/auth/tests/test_w115_password_hashing.py::test_pbkdf2_iterations_meet_asvs_v6`, `hub/apps/auth/tests/test_w115_password_hashing.py::test_test_env_block_is_the_only_md5_first_site` |
| V6.4.1 Randomness | GATE-62 CSPRNG sweep over hub/cli/scripts: any token/key-context `random.*` site flips the gate (planted-violation pins, both import forms) | `scripts/tests/test_w115_crypto_random_sweep.py::test_sweep_is_clean_on_the_real_tree`, `scripts/tests/test_w115_crypto_random_sweep.py::test_planted_token_context_violation_flips_red` |
| V6.2.3 Key rotation | Webhook-encryption key rotation re-encrypts Fernet rows, SKIPS `aws-kms:`/`vault:` ciphertext (the pre-fix double-wrap corruption fixed), migrates plaintext | `hub/apps/webhooks/tests/test_key_rotation_command.py::test_rotation_re_encrypts_all_secrets`, `hub/apps/webhooks/tests/test_key_rotation_command.py::test_rotation_skips_vault_prefixed_rows`, `hub/apps/webhooks/tests/test_key_rotation_command.py::test_rotation_migrates_plaintext_rows` |
| V6.4.2 Encryption in use | Fernet + KMS seams and their field-level consumers audited, `--ci` ratchets drift | `docs/audits/w116-encryption-coverage-2026-10-16.md`, `scripts/tests/test_w116_exc_str_leak_ban.py::test_encryption_coverage_artifacts_exist` |
| V6 audit | Hash-strength audit names the finding + fixes | `docs/audits/w115-crypto-audit-2026-10-16.md` |

## V7 — Error Handling and Logging

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V7.4.1 No sensitive data in errors | SOURCE-LEVEL leak ban: `str(exc)` interpolation in the client-facing envelope modules is AST-banned (only the typed-4xx conditional allowlisted, line-anchored); planted violations flip it | `scripts/tests/test_w116_exc_str_leak_ban.py::test_envelope_modules_carry_no_exception_text_interpolation`, `scripts/tests/test_w116_exc_str_leak_ban.py::test_scanner_bites_on_a_planted_violation` |
| V7.4.1 Runtime (GraphQL) | Resolver errors generic; 500 path never carries exception text; validation messages preserved | `hub/apps/graphql_ld/tests/test_resolvers.py::test_execution_500_path_never_carries_exception_text`, `hub/apps/graphql_ld/tests/test_resolvers.py::test_validation_error_message_preserved` |
| V7.4.1 Runtime (ML third-party) | All 16 ODH exception echoes removed; secret-bearing third-party errors stay server-side | `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLPredictBoundaries::test_odh_error_details_never_reach_the_client`, `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLPredictBoundaries::test_unexpected_prediction_failure_is_generic` |
| V7.1 Logging / audit trail | Every search/SPARQL/AI/ML execution + every 429 emits an audit event (best-effort — audit-DB outage never blocks the response) | `tests/security/test_throttle_audit_contract.py::test_search_429_emits_search_rate_limit_exceeded`, `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestAIViewRedTeam::test_benign_nl_search_emits_performed_audit` |
| V7.3 Log protection | Audit payloads sanitized + PII-redacted before persist; PII map regenerated by script (CI ratchet) | `docs/PII_DATA_MAP.md`, `scripts/tests/test_w116_exc_str_leak_ban.py::test_pii_map_and_redaction_artifacts_exist` |

## V8 — Data Protection

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V8.3 Sensitive data at rest | PII redaction coverage audited per-type (email/phone/ssn/card covered by both redactors; deliberate gaps recorded with rationale) | `docs/audits/w116-pii-redaction-coverage-2026-10-16.md`, `docs/PII_DATA_MAP.md` |
| V8.3 Encryption at rest | Fernet/KMS encryption-coverage audit: 2 seams + 8 field-level consumers, `--ci` drift ratchet | `docs/audits/w116-encryption-coverage-2026-10-16.md`, `scripts/tests/test_w116_exc_str_leak_ban.py::test_encryption_coverage_artifacts_exist` |
| V8.1/8.2 Data minimization & retention | Audit-event retention policies: explicit days, regulation-key derivation, registry-override precedence | `hub/apps/audit/tests/test_audit_event_retention_policy.py::test_explicit_retention_days_persists`, `hub/apps/audit/tests/test_audit_event_retention_policy.py::test_registry_derived_overrides_explicit_retention` |
| V8.3 Cross-tenant isolation | RLS arming fail-closed + the V4 IDOR matrix (836 tests) back the data-protection boundary | `hub/apps/auth/tests/test_rls_guc_settings_sync.py::test_every_rls_enabled_setting_maps_to_a_real_policy_guc` |
| V8.3 Secrets in config | No well-known secret fallbacks anywhere; fail-closed key guards | `scripts/tests/test_w92_bootstrap.py::test_settings_has_no_postgres_password_guessing_matrix` |

## V9 — Communications

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V9.1 TLS everywhere | TLS terminated upstream (Traefik) at the edge; app-level fail-closed guardrails for the TLS-dependent posture | `frontend/nginx.conf:91` |
| V9.2.1 HSTS | `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` emitted always | `frontend/nginx.conf:92` |
| V9.2.2/9.3 Security headers | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, CSP with script-src 'self' | `frontend/nginx.conf:74`, `frontend/nginx.conf:77`, `frontend/nginx.conf:139` |
| V9.3 Cookie security over TLS | Production boot guard: secure cookies + SSL redirect + HSTS 63072000 (real subprocess boot — the first real-boot pins for these) | `tests/security/test_w119_configuration_guards.py::TestProductionCookieSslRedirectGuard::test_production_boot_has_secure_cookies_and_redirect` |
| V9.3 Downstream plaintext guard | A non-TLS `LLM_API_URL` disables the provider path (the API key is never sent over plaintext) | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptHardening::test_http_provider_url_fails_closed_to_rule_based` |
| V9.4 CORS | Evil-origin preflight gets no ACAO; production CORS origins exact, no localhost, empty-origin boot fails closed | `tests/security/test_cors.py::test_evil_origin_no_cors_header`, `tests/security/test_w119_configuration_guards.py::TestProductionCORSGuard::test_production_cors_origins_are_exact` |

## V10 — Malicious Code

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V10.1 Code integrity / toolchain | Bandit ratchet BLOCKING in the code-quality workflow (debt growth fails); semgrep local rules enforced by the repo runner (parse errors fail, never skip); gitleaks blocking; trivy on built images | `scripts/tests/test_w1110_security_tooling_gates.py::test_bandit_ratchet_is_blocking_in_code_quality_workflow`, `scripts/tests/test_w1110_security_tooling_gates.py::test_semgrep_rule_parse_error_is_a_gate_failure_not_a_skip`, `scripts/tests/test_w1110_security_tooling_gates.py::test_gitleaks_ci_job_is_blocking` |
| V10.3 Dependency integrity | Every dependency finding must be TRIAGED (MEDIUM+ policy, expiry-reviewed) — untriaged/expired findings block; npm-audit blocking on high/critical | `scripts/tests/test_check_dependency_vulns.py::test_untriaged_vuln_blocks`, `scripts/tests/test_check_dependency_vulns.py::test_expired_review_blocks`, `.pip-audit-allowlist.yaml` |
| V10.3.3 Malicious payload handling | No archive extraction anywhere in the non-test tree (zip-bomb/slip class dead at the source — AST gate); the one read-side ZipFile pinned namelist/read-only | `scripts/tests/test_w118_upload_abuse_veracity.py::test_no_archive_extraction_anywhere_in_the_non_test_tree`, `scripts/tests/test_w118_upload_abuse_veracity.py::test_the_drill_script_zip_is_namelist_read_only` |
| V10.4 Agent/tool agency | Agentic-framework imports + tool-call sites ABSENT from the non-test tree (AST-proven — the LLM surfaces are prompt-only) | `scripts/tests/test_w1112_ai_threat_model_veracity.py::test_no_agent_tool_call_code_in_the_non_test_tree` |

## V11 — Business Logic

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V11.1 State machines | Full transition matrices for orders/payments/runs/ARs — every legal AND illegal hop has a named test; illegal hops blocked at the API | `hub/apps/marketplace/tests/test_w23_order_state_machine.py::OrderStateMachineMatrixTest::test_every_illegal_hop_is_blocked`, `hub/apps/governance/tests/test_w117_ar_transition_matrix.py::ARMatrixCoverageTest::test_matrix_covers_the_real_surface_hops`, `docs/security/adversarial-matrices/w117-business-logic-matrix.md` |
| V11.1 Money path | Decimal cents end-to-end; double-purchase short-circuit; double-refund rejected; refund idempotency | `hub/apps/marketplace/tests/test_w21_decimal_end_to_end.py::AmountToCentsConversionTests::test_idempotency_key_embeds_canonical_cents`, `hub/apps/marketplace/tests/test_refunds.py::MarketplaceRefundApiTests::test_double_refund_rejected_after_refunded_status`, `hub/apps/marketplace/tests/test_seller_refund_endpoint.py::TestRefundIdempotency::test_full_refund_retry_after_completion_is_idempotent` |
| V11.1 Concurrency | Real-thread race pins: concurrent double-approve/double-order single-winner; concurrent refunds single-winner (row-lock across guard→wire→persist) | `hub/apps/marketplace/tests/test_race_condition_locking.py::DoubleApproveRaceConditionTest::test_concurrent_double_approve_one_wins`, `hub/apps/marketplace/tests/test_w117_refund_race.py::ConcurrentRefundRaceTest::test_concurrent_different_amount_refunds_single_winner` |
| V11.1 Metering idempotency | Keyed replay no-op; per-tenant key isolation; concurrent same-key single row; concurrent sync exactly one Stripe record | `hub/apps/billing/tests/test_w25_metering.py::RecordUsageIdempotencyTest::test_idempotency_key_replay_is_a_no_op`, `hub/apps/billing/tests/test_w25_metering.py::SyncUsageToStripeConcurrencyTest::test_concurrent_sync_produces_single_stripe_record` |
| V11.1 Webhook replay | Stripe webhook atomic processed-claim: one winner; marketplace claim concurrent single-winner | `hub/apps/billing/tests/test_webhook_idempotency.py::TestConcurrentClaim::test_concurrent_claim_single_winner`, `hub/apps/marketplace/tests/test_stripe_webhooks.py::TestConcurrentMarketplaceClaim::test_concurrent_claim_single_winner` |
| V11 matrix veracity | The 45-cell matrix is AST-verified against the real tests | `scripts/tests/test_w117_business_logic_matrix_veracity.py` |

## V12 — Files and Resources

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V12.1 Upload validation | View-level magic-byte bypass (PE-as-CSV) and content-type spoof (ZIP-as-CSV) rejected with the row FAILED and the object deleted | `hub/apps/files/tests/test_w118_upload_abuse.py::UploadAbuseViewTest::test_magic_byte_bypass_pe_as_csv_rejected_at_complete`, `hub/apps/files/tests/test_w118_upload_abuse.py::UploadAbuseViewTest::test_content_type_spoof_zip_as_csv_rejected` |
| V12.2 File integrity | Presigned-replay staging design: PUTs run on a staging key; completion verifies existence/size/SHA/magic bytes and the SERVER copies staging → final — a replayed PUT cannot serve as CLEAN | `hub/apps/files/tests/test_presigned_replay_w112.py::PresignedReplayPinTest::test_replay_put_after_completion_cannot_serve_as_clean`, `scripts/tests/test_w118_upload_abuse_veracity.py::test_staging_design_is_live_in_the_source` |
| V12.3 Size limits | Worker-internal path caps the file BEFORE the full read (oversized → 400, no row) | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py::InternalWorkerFileHardeningTest::test_oversized_file_rejected` |
| V12.4 Filename safety | Overlong names REJECTED (never truncated); RTL/bidi roundtrip; unicode handled | `hub/apps/files/tests/test_w118_upload_abuse.py::UploadAbuseViewTest::test_unicode_overlong_and_rtl_names_roundtrip` |
| V12.5/12.6 Download & archive safety | No extraction anywhere (zip containers rejected at every gate); XLSX/XLS parse bounded by the inference cap; compliance service rejects banned binary prefixes | `scripts/tests/test_w118_upload_abuse_veracity.py::test_no_archive_extraction_anywhere_in_the_non_test_tree`, `services/compliance-service/tests/test_file_type_validation.py::TestBannedBinaryPrefixes` |
| V12 matrix veracity | The abuse matrix is AST-verified | `scripts/tests/test_w118_upload_abuse_veracity.py::test_the_abuse_suite_exists_with_the_named_cells` |

## V13 — API and Web Service

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V13.4/V13.5 Rate limiting | Endpoint-level rate-limit matrix: login IP, lockout, register, SSO, reset request AND confirm, upload init, search/SPARQL/marketplace/BaaS/API-key — every 429 emits its per-surface audit event | `tests/security/test_throttle_audit_contract.py::test_marketplace_429_emits_marketplace_rate_limit_exceeded`, `hub/apps/files/tests/test_file_init_rate_limits.py::FileInitThrottleAuditTest::test_second_init_within_window_emits_upload_rate_limit_audit`, `docs/security/adversarial-matrices/w119-api-configuration-matrix.md` |
| V13.5 Tenant-scoped throttles | Throttle keys carry tenant_id (tenant A's exhaustion never affects tenant B) — pinned per surface | `tests/security/test_throttle_audit_contract.py::test_throttled_rows_are_tenant_scoped` |
| V13.2 REST security | JWT auth on the API (CSRF exempt by design, HttpOnly CSRF cookie flag pinned); GraphQL typed errors, no exception-text echo | `tests/security/test_csrf.py::test_api_uses_jwt_not_session_auth`, `hub/apps/graphql_ld/tests/test_resolvers.py::test_execution_error_returns_200_with_errors` |
| V13.1.1 CORS | Evil-origin requests get no ACAO header; preflight blocked | `tests/security/test_cors.py::test_preflight_evil_origin_blocked` |
| V13.4 GraphQL/Search abuse | SPARQL complexity gates + per-surface 429 audits; search throttled + audited | `tests/security/test_throttle_audit_contract.py::test_sparql_429_emits_sparql_rate_limit_exceeded` |
| V13 rate-limit matrix veracity | The W11.9 matrix + config guards are AST-verified | `scripts/tests/test_w119_api_configuration_veracity.py` |

## V14 — Configuration

**Declared level: Level 2**

| ASVS requirement | Verification summary | Evidence |
|---|---|---|
| V14.2.1 Secure defaults | REAL subprocess boots of production settings: secure cookies + SSL redirect + HSTS; insecure cookie fails closed; ALLOWED_HOSTS rejects unknown Host | `tests/security/test_w119_configuration_guards.py::TestProductionCookieSslRedirectGuard::test_production_boot_has_secure_cookies_and_redirect`, `tests/security/test_w119_configuration_guards.py::TestProductionCookieSslRedirectGuard::test_insecure_cookie_in_production_fails_closed`, `tests/security/test_w119_configuration_guards.py::TestAllowedHostsValidation::test_unknown_host_header_is_rejected` |
| V14.2.2 Kill switches / fail-closed arming | RLS arming GUCs ↔ settings kill switches pinned bidirectionally; magic-byte validation default-ON in BOTH settings and helm (the pre-fix helm "false" flip is pinned gone) | `hub/apps/auth/tests/test_rls_guc_settings_sync.py::test_every_deployed_policy_guc_has_a_paired_settings_kill_switch`, `scripts/tests/test_w118_upload_abuse_veracity.py::test_helm_and_settings_magic_byte_posture_agree` |
| V14.3 Secrets in config | Universal fail-closed key guard; no guessing matrix; compose files declare keys explicitly | `scripts/tests/test_w92_bootstrap.py::test_settings_has_universal_fail_closed_key_guard`, `scripts/tests/test_w92_bootstrap.py::test_test_compose_django_services_declare_all_three_keys` |
| V14.4.3 Dependency config | Dependency-vuln triage with expiry reviews; bandit ratchet baseline committed | `scripts/tests/test_check_dependency_vulns.py::test_expired_review_blocks`, `scripts/bandit_debt_baseline.json` |
| V14.5 HTTP security headers | CSP/XFO/nosniff/HSTS pinned at the edge config (the nginx/security-header suites) | `frontend/nginx.conf:74`, `frontend/nginx.conf:92`, `frontend/nginx.conf:139` |

---

## Honesty notes (recorded, not claimed)

- **Level claims are L2, not L3**, even where breadth is L3-scale (V4's
  836-test matrix). ASVS L3 requires abuse-case coverage and defense
  for advanced threat actors per requirement — declared only where the
  evidence shows it.
- **V9 TLS termination is infrastructure** (Traefik upstream) — the
  pack cites the edge config + the app-level fail-closed guards; a
  TLS-termination integration test is an open item for the staging
  soak (W10.2).
- **V10.2 vendor security** (patch cadence verification of third-party
  services) is an ops process, not code — the pip/npm/trivy gates are
  the committed evidence.
- **Paid-layer surfaces** (AI/ML) are verified in the public tree with
  the D5 scoping note — see V1.10/V13 rows.
- The W11.3 IDOR manifest records 2 allowlisted keys (reasons recorded);
  the probe manifest is the single source of truth for V4.1 coverage.
