# CLAUDE.md Veracity Pass (G10) — 2026-10-14

Every contract section of `CLAUDE.md` was checked against the code it
describes.  One claim was FALSE (the DRF-3.16 throttle claim) and is
corrected in `CLAUDE.md` + the five throttle modules that repeated it;
the remaining claims verified TRUE and are now cited to their
enforcing tests/gates.  The pins that keep the ledger honest:
`scripts/tests/test_w93_community_and_veracity.py`.

| CLAUDE.md claim | Verdict | Verification (how it was checked) | Cited to |
|---|---|---|---|
| DRF 3.16 "REMOVED the `throttled()` override hook"; "a `throttled()` override is dead code" | **FALSE — corrected** | Installed DRF = 3.16.1 (`requirements.txt:12`); `rest_framework/views.py:183` DEFINES `throttled()` and `:377` CALLS it (`APIView.check_throttles` → `self.throttled(request, duration)`; base raises `Throttled`). The two view-level `throttled()` methods are LIVE and correctly terminate the request: graphql_ld's emits the audit then raises; search's is a dispatcher that forwards to per-throttle hooks (a no-op loop today — the throttle classes emit via `_on_throttled` in `allow_request`'s failure branch) and ends in `super().throttled()`, which raises `Throttled`. The repo's `_on_throttled` helpers remain the single audit point per throttle surface (tenant key + action in one place) — the mechanism stands; the justification was rewritten to the verified truth. | `test_drf_316_throttled_claim_is_true`, `test_no_false_drf_claim_lingers_in_docstrings` |
| RLS request-path arming: middleware sets GUCs transaction-locally inside `transaction.atomic()`; `RLS_REQUEST_PATH_ENABLED` master kill switch default armed; fails closed; pre-tenant reads via `user_lookup_alias()`; paired GUC↔settings pinned | **TRUE** | `hub/settings.py:2199` `default=True`; `hub/apps/auth/middleware.py` `SET LOCAL` inside `transaction.atomic()`; `hub/apps/auth/db_aliases.py` exists; the bidirectional pin lives at `hub/apps/auth/tests/test_rls_guc_settings_sync.py` | `test_rls_arming_prose_matches_the_code` + `hub/apps/auth/tests/test_rls_guc_settings_sync.py` |
| Business-rules chain table (6 chains) | **TRUE** | `@register_chain("contract.publish")` / `asset.activate` / `governance.approval.advance` in `hub/apps/core/business_rules/chain_registry.py`; `marketplace.listing.publish` in `hub/apps/marketplace/chains.py`; `semantic.query.execute` in `hub/apps/semantic/chains.py`; the 6 `databricks.*` chains in `hub/apps/databricks_admin/chains.py` (the 313.1 owning-app convention) | `test_chain_table_matches_registered_chains` |
| 274.16.13 per-tenant chain enablement RETRACTED (no per-tenant switch) | **TRUE** | The retraction text is present and accurate — no `business_rules_chain_*_enabled` field/migration exists | `test_retracted_per_tenant_chain_claim_stays_retracted` |
| `ENFORCE_JWT_SCOPES` settings comment ("default True since W7.5") | **TRUE** | `hub/settings.py` — the comment was rewritten by the W7.5 flip itself; `env.bool(..., default=True)` verified | `test_enforce_jwt_scopes_settings_comment_is_current` |
| Search/throttle contract: `check_throttle_coverage` enforcement; `_on_throttled` audit emission; `/search` permanently MVP-in-scope | **TRUE** | Management command `hub/apps/observability/management/commands/check_throttle_coverage.py`; `_on_throttled` helpers in `hub/apps/{search,marketplace,ai,core,ml,transformation,baas,auth,mesh}/throttles.py`; `/search` absent from the MVP gating surfaces | test_w93 community suite + `check_throttle_coverage` in CI |
| Environment-failure policy (envpolicy.py, skip_or_fail, probe_service; frontend envPolicy.cjs) | **TRUE** | `envpolicy.py` at repo root; `cli/tests/_env_skip.py`; `frontend/e2e/fixtures/envPolicy.cjs`; TDD pins `scripts/tests/test_env_policy_py.py` / `test_cli_env_skip.py` / `test_env_policy.cjs` | the W16 pin files (CI) |
| Skip/placeholder debt contract (GATE-40, TICKET=/EXPIRES=, baseline) | **TRUE** | `scripts/check_skip_expiry.py` + `scripts/skip_expiry_baseline.json` exist and run in CI | `test_check_skip_expiry.py` + GATE-40 |
| Control-plane provider boundary (GATE-54 checker + allowlist) | **TRUE** | `scripts/check_provider_boundary.py` + `scripts/provider_boundary_allowlist.txt` wired into the lint workflow + `make quality-gates` | `test_check_provider_boundary.py` (CI) |

**Root causes fixed rather than papered over:**
1. The false DRF claim was repeated in five throttle modules
   (`hub/apps/{core,search,ai,ml,transformation}/throttles.py`
   `_on_throttled` docstrings) — each now carries the verified truth
   ("DRF 3.16.1 retains the `throttled()` hook; `_on_throttled` is the
   single audit point per surface") and the pin FAILS if the old line
   returns anywhere.
2. The correction keeps the mechanism intact — no behavior change; the
   two live `throttled()` overrides were audited and are correct (they
   emit then raise).
