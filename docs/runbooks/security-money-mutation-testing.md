# Security & money paths — mutation testing (W16 / Phase T.4)

Extends the repo's scoped mutation-testing practice (lineage validator
`mutmut-lineage-validator.yml`, asset saga `mutmut-asset-saga.yml`) to the two
paths W16 cares most about. Workflow: `.github/workflows/mutmut-security-money.yml`
(dormant; scheduled 04:30 UTC + manual dispatch).

## Scope (W8.3 constraint respected — scoped, not repo-wide)

| Path | Module | Detector suite |
|---|---|---|
| security | `hub/apps/auth/jwt_utils.py` | `hub/apps/auth/tests/test_jwt_utils.py` (25 tests) |
| money | `hub/apps/marketplace/payment_amount_utils.py` | `hub/apps/marketplace/tests/test_payment_amount_cents_dual_write.py` (13 tests) |

Why these two:

- **jwt_utils** is the auth boundary. A mutation that survives (e.g. a
  weakened signature check, an inverted expiry comparison) ships silently.
- **payment_amount_utils** is the decimal↔cents dual-write boundary. A
  rounding mutation that survives corrupts money state — the highest-severity
  bug class this repo can ship.

## Target

**Every injected mutation caught** — `mutmut results` reports
`Survived: 0`. A survived mutant is not a bug; it is a missing assertion in
the detector suite. Harden the tests until it is killed, or record a
reasoned exception in the run summary.

## Running locally

Both detector suites touch Django models (jwt tests create Tenant rows in
`setUp`), so the runner executes IN-CONTAINER against the compose-provided
`postgres-test` — the `test-backend` job convention. Host-side DB runs hit
the p313-pg schema drift (`warehouse_dq_enabled` and friends); do not use
them for this. The repo is bind-mounted at `/app` in `api-service-test`, so
host-side mutmut mutates the file tree and the in-container runner sees it.

```bash
# The test stack must be up: docker compose -f docker-compose.test.yml up -d --wait
pip install 'mutmut<3'   # host-side, once (repo venv)
rm -f .mutmut-cache

# security
venv/bin/python -m mutmut run \
  --paths-to-mutate=hub/apps/auth/jwt_utils.py \
  --tests-dir=hub/apps/auth/tests \
  --runner='docker compose -f docker-compose.test.yml exec -T api-service-test python -m pytest hub/apps/auth/tests/test_jwt_utils.py -x -q --no-header --reuse-db'

# money (STRIPE_SECRET_KEY comes from the compose test env; the suite's
# settings-level key check is satisfied, the Stripe HTTP call is patched)
venv/bin/python -m mutmut run \
  --paths-to-mutate=hub/apps/marketplace/payment_amount_utils.py \
  --tests-dir=hub/apps/marketplace/tests \
  --runner='docker compose -f docker-compose.test.yml exec -T api-service-test python -m pytest hub/apps/marketplace/tests/test_payment_amount_cents_dual_write.py -x -q --no-header --reuse-db'

venv/bin/python -m mutmut results
```

`mutmut <3` is pinned (Q.5.3: 3.x renames every key and its stats collector
fails against this repo's Django-boot pytest setup). `--no-backup` does not
exist on 2.5.1; backup behavior comes from pyproject `[tool.mutmut]
backup = false`.

## Triaging a survivor

1. `mutmut show <id>` — read the mutation.
2. Decide: is the mutated behavior observable? If yes, add the missing
   assertion to the detector suite and re-run that mutant
   (`mutmut run --paths-to-mutate=... --mutation-id=<id>`).
3. If the mutant is genuinely behavior-preserving (e.g. a redundant
   comparison), record it in the run summary with the ID — do NOT leave it
   unexplained.

## Baseline (first run, 2026-08-30)

- **security/jwt_utils: 81 mutants — 75 killed, 6 survived, 0 unaccounted.**
  All 6 survivors are documented equivalent mutants (mutmut 2.x has no
  equivalence marker; the IDs below are recorded here instead):
  - `2, 43, 52, 67, 74` — `@staticmethod` removals. Behavior-preserving for
    self-free methods: class-attribute access returns the plain function, so
    both `Cls.f(…)` and `Cls().f(…)` bind identically.
  - `9` — `roles = []` → `roles = None` in the derivation branch. The value
    is immediately overwritten when `user_roles` exists and is falsy either
    way when it does not — no observable difference.
  Detector hardening that produced the 75 kills:
  `JWTMutationCoverageTests` in `hub/apps/auth/tests/test_jwt_utils.py`
  (19 tests: tenant/roles derivation, tenant_slug/name/scopes/refresh_token_id/
  nbf/iss claims incl. the JWT_ISSUER fallback, RS256 round-trip, verify_version
  default, `_validate_token_version` None/missing-sub/unknown-user/default-0
  branches, positional staticmethod contract).
- **money/payment_amount_utils: 19 mutants — 19 killed, 0 survived.**
  Detector hardening: `TestPaymentAmountCentsMutationCoverage` in
  `hub/apps/marketplace/tests/test_payment_amount_cents_dual_write.py`
  (4 tests: disagreeing-columns preference for both readers, both-columns-
  absent zero, refund Decimal fallback with NULL cents).
