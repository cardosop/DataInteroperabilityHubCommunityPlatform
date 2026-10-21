# Test Coverage Closure Plan

**Status:** proposed (2026-10-04) — based on the batch-campaign assessment
(audit of 123 backend batch logs, 8 frontend batch logs, traceability
registries, security suite, and connector/env wiring).

**Goal:** close every remaining coverage gap so the application can be
tested "as a whole" — every shipped feature, journey, integration, and
security contract has a test that actually runs, and every skip is either
eliminated or is a deliberate, tracked, expiring decision.

**Conventions used:** W16 environment policy (`envpolicy.py`), GATE-40
skip-expiry annotations (`TICKET=… EXPIRES=…`), Documentation Sync
Contract (journey/UC registries + markers), openspec for task tracking.
Recommended tracking: `openspec/changes/coverage-closure/` with one task
per numbered item below.

---

## Phase 0 — Stabilize the foundation (do first; unblocks everything)

### 0.1 Credential re-init rehearsal (operational landmine)
**Root cause:** the 2026-10-02 rotation (313.0.1) changed `.env.test`
MinIO/Fuseki/CKAN values, but the running stack still bakes the OLD
credentials: the `minio-test-data` volume holds the old root pair,
fuseki/semantic containers hold the old password, and the CKAN token
must be re-minted after any CKAN DB re-init. The next `test-stack-up`
will break S3 and semantic silently (healthchecks stay green).

**Steps:**
1. Snapshot the running state (`docker compose ps`, volume list).
2. `docker compose -f docker-compose.test.yml --env-file .env.test down -v minio-test-data`
3. Recreate the stack with `--env-file .env.test` (fuseki + semantic
   together — the shiro.ini sync converges to the env password).
4. Re-mint the CKAN token via the ckan CLI (see
   `docs/runbooks/LOCAL_FULL_TEST_SWEEP.md` CKAN section) and write it
   into `.env.test` without echoing it.
5. Verify: presigned-upload/S3 tests (b1 family), semantic mapping tests
   (b102i), marketplace connector tests (b64), smoke auth (b105b).

**Hardening (root-cause, not just re-run):**
- Add `make test-stack-reinit` that performs steps 2–4 idempotently.
- Add a pre-up verification script (`scripts/verify_test_stack_creds.py`)
  that detects volume-vs-env credential mismatch (probe MinIO with both
  pairs) and fails fast with the remedy instead of letting tests 401.
- Add `make test-seed-connectors` (see 1.1) as a dependency of the
  stack-up flow.

**Acceptance:** two consecutive stack re-creates with zero storage/auth
failures, zero manual steps beyond `make`.

### 0.2 Commit / snapshot the working tree
**Root cause:** the entire campaign's fixes (conftest guard + flush
retry, env rotations, provisioners, settings MAILERS, spec fixes,
report regen) live in a ~3,000-file dirty tree. A reset loses them.

**Steps:** split into logical commits per domain (test-infra conftest /
env+compose / provisioners+seeders / settings MAILERS / spec fixes /
regenerated artifacts), run the affected batch + `make quality-gates`
per commit. Snapshot the gitignored env-file KEYS into a documented
template (`.env.test.example` updated) so rotations are reconstructible.

**Acceptance:** `git status` clean (or explicitly ignored files only);
each commit's batch is green.

### 0.3 Shared-DB nondeterminism
**Root cause:** parallel sessions run batches against
`hub_test_test_shared` (wipe cycles every ~20–30 min) and the live API
writes audit rows into it. The per-DB advisory lock serializes
pytest-vs-pytest only.

**Steps:**
1. Add `TEST_DB=auto` mode to the batch Makefile targets: auto-create a
   per-invocation schema+django_migrations clone (the fast pg_dump
   recipe), migrate to HEAD, run, drop. Keep `hub_test_test_shared` the
   default for solo use; document `TEST_DB=auto` as the multi-session
   default in `LOCAL_FULL_TEST_SWEEP.md`.
2. Extend the advisory-lock guard message to suggest `TEST_DB=auto`
   when contention is detected.

**Acceptance:** two concurrent batch runs on one tree complete green
with zero cross-talk (one shared, one auto clone).

---

## Phase 1 — Live connector coverage (b64: 12 skips + Azure + Stripe)

### 1.1 CKAN write-token provisioning (7 tests)
**Root cause:** token provisioning is manual; the baked seed token is
stale (predates the last `ckan db init`); any DB re-init silently
invalidates it again.

**Fix:** `scripts/ensure_ckan_test_token.sh` — idempotent: `ckan user
token add admin seed_token` (or revoke+add), write `CKAN_TEST_API_KEY`
into `.env.test` without echoing; wire into `make test-seed-connectors`
and the stack-up flow; update the runbook note.

**Acceptance:** fresh stack → `make test-seed-connectors` → b64 CKAN
class: 0 skips.

### 1.2 Dados.gov.br (5 tests)
**Root cause:** no `DADOS_GOV_BR_API_KEY`/`CKAN_DADOS_GOV_BR_API_KEY`
exists anywhere — external credential acquisition required (user
action).

**Steps:**
1. Document exact acquisition steps + destination keys in the runbook
   (user provides keys — blocked until then).
2. Until provisioned: convert the runtime skip to W16 envpolicy
   (`skip_or_fail`) with an explicit reason naming the missing key, and
   add `TICKET=DADOS-LIVE-CREDS EXPIRES=2027-01-31` so GATE-40 tracks it.
3. Independent of creds: add mock-mode contract tests for the Dados
   parser/serializer/shape so the mapping logic is covered today.

**Acceptance:** with creds: 0 skips. Without: exactly one tracked,
expiring, policy-governed skip (CI raises).

### 1.3 GCP marketplace runtime skips (6 tests)
**Root cause:** module-level `pytest.mark.skipif(not
GOOGLE_CLOUD_AVAILABLE)` can silently pass as skipped; runtime auth
skips; known stale-SA-key issue (reissue via console).

**Fix:**
1. Replace the module-level skipif with W16 envpolicy guards.
2. Reissue the GCP SA key per the documented recipe; verify with a
   connectivity self-check fixture that prints a diagnostic on failure.
3. `make test-connectors-live` target documenting the required sandbox
   state (runs b64 + b87 live classes).

**Acceptance:** GCP class runs or fails loudly in CI; local skip shows
the diagnostic.

### 1.4 Azure marketplace connector — NO tests exist
**Root cause:** shipped connector without any test file.

**Fix:** `hub/apps/integrations/tests/test_azure_marketplace_connector.py`
following the Snowflake/AWS patterns: httpx-mocked unit tests (auth
flow, request signing, error mapping, retry/backoff) + a live class
gated by envpolicy on `AZURE_CLIENT_SECRET`.

**Acceptance:** file exists with unit coverage; live class is
policy-governed; batch 6-4 includes it.

### 1.5 Stripe billing layer
**Root cause:** no Stripe credentials; `JOURNEY-TA-BILLING-UPGRADE`
runs business logic only and annotation-skips the Stripe assertions —
a pass that disguises a hole.

**Steps (needs a decision, see open questions):**
1. Decision A (live): provision a Stripe test-mode key set
   (`STRIPE_SECRET_KEY` etc. in `.env.test`), wire the spec assertions.
2. Decision B (accepted mock-only): document the decision in
   `docs/`, convert the annotation-skip to a tracked skip
   (`TICKET=STRIPE-LIVE EXPIRES=…`), keep the webhook
   signature/idempotency unit tests as the contract pin.
3. Either way: add the missing Stripe webhook-signature verification
   and idempotency edge tests for the billing-upgrade flow.

**Acceptance:** no untracked conditional skip in that spec.

---

## Phase 2 — RoPA/warehouse edges (b87: 4 skips)

### 2.1 DOCX/PDF renderers never execute
**Root cause:** `python-docx`/`WeasyPrint` are in requirements.txt but
not installed in the api-service-test image (and WeasyPrint needs
Cairo/Pango system libraries).

**Fix:** add the packages + `libcairo2`/`libpango-1.0-0` to the test
image layer used by api-service-test (Dockerfile or compose pip stage),
rebuild, verify `python -c "import docx, weasyprint"` in-container.

**Acceptance:** b87 renderer tests run (0 skips for those two).

### 2.2 Real-Redis cost recording skipped
**Root cause:** in-container tests resolve REDIS_URL to
127.0.0.1:63799 (host-only port).

**Fix:** point the api-service-test REDIS_URL at the compose redis
service (`redis-test:6379`) in docker-compose.test.yml env.

**Acceptance:** `test_cost_recording.py` runs without the redis skip.

### 2.3 Warehouse live classes reachability
**Root cause:** sandbox infra is optional; guards are reachability-
dependent.

**Fix:** W16 envpolicy guards with clear diagnostics + extend the
databricks nightly job (or `make test-connectors-live`) to run the
warehouse live classes when sandbox vars are present.

**Acceptance:** CI-nightly exercises them; local skip explains itself.

---

## Phase 3 — Email / MAILERS verification

**Root cause:** the MAILERS migration (Django 6.1, `hub/settings.py`)
is verified only by the prefect-integration suite; hub-wide email paths
(notifications, invitations, scheduled-export emails) haven't re-run
against it.

**Fix:**
1. Update `hub/apps/notifications/tests/test_services.py` to override
   `MAILERS` instead of the deprecated `EMAIL_BACKEND` in
   `self.settings(...)`.
2. Run the email-adjacent suites: notifications, users (invitation
   emails), scheduled_export, api/mailhog proxy.
3. Add a settings-contract test (security-family): asserts `MAILERS` is
   defined and no `EMAIL_*` attribute exists on settings (regression
   pin against the deprecation returning).

**Acceptance:** suites green with 0 RemovedInDjango70Warning; contract
test present.

---

## Phase 4 — UI/E2E journey & UC coverage (largest workstream)

**Root cause of the gap:** 12 journeys and 89/147 UCs have no E2E
presence. Many of those UCs are API/CLI/SDK-shaped (Databricks control
plane, semantic, transformation, virtualization), not UI-shaped — the
honest testing surface for them is SDK/CLI-level E2E, not a browser
spec.

### 4.1 Classification decision (one-time, per domain)
For every uncovered UC/journey decide: **UI-relevant** (browser spec
required) vs **API/SDK/CLI-only** (declare satisfied by backend marker +
SDK/CLI E2E; record the decision in the UC registry as a coverage-mode
field). This prevents writing 89 hollow browser specs.

### 4.2 Write the missing UI specs (UI-relevant subset)
- 12 zero-coverage journeys: CPO-011…016, DEV-010, ODPS-001…005.
- Critical UC-DB-007/008 (Databricks control plane — likely SDK/CLI
  shape; verify before classifying).
- Register each new spec in the Documentation Sync Contract: docs
  entries, `@pytest.mark.journey/uc` on ≥1 backend test, persona
  aggregator import.

### 4.3 Fix the 3 invisible E2E IDs
- Extend `check_doc_journey_marker_sync.py`'s filename regex to match
  digit-in-segment IDs (`JOURNEY-…-V310-…`).
- Register `JOURNEY-EXPORT-003` in USER_JOURNEYS.md + backend marker
  (or delete the describe if superseded).
- Register `JOURNEY-CONTRACT-V310-LIFECYCLE` in the docs.

### 4.4 Persona aggregator imports
Import the 223 orphan journey spec files into their persona aggregators
(or add a second cookie-auth entrypoint so they run in the auth path);
re-run the persona drift checker.

**Acceptance:** every critical UC has UI or SDK/CLI E2E (as classified);
all checker gates green; 0 invisible IDs.

---

## Phase 5 — Security gaps

1. **SSRF for marketplace/warehouse connectors:** add adversarial URL
   tests (localhost, 169.254.169.254, private ranges, scheme confusion)
   for each connector endpoint builder, reusing the
   `contracts/test_ssrf_port_contractURL.py` pattern + the residency
   validator.
2. **API-key scope enforcement:** new
   `tests/security/test_api_key_scopes.py` — matrix of
   `ROLE_SCOPE_MAP` scopes × endpoints asserting 403 out-of-scope and
   200 in-scope (align with the account-plane 8.x envelope).
3. **Phase 273 throttle-audit contract:** add a security test that
   forces a 429 (overridden throttle rate) and asserts the
   `SEARCH_RATE_LIMIT_EXCEEDED` audit event is emitted (and no audit
   outage blocks the response).
4. **Dependency vulns:** capture the full pip-audit output (fix the
   truncated logs), triage each MEDIUM/LOW: patch or add to an
   allowlist file with rationale; decide the blocking policy for
   MEDIUM+ (open question).
5. **a11y:** snapshot the current violation allowlist, then flip the
   CI job from `continue-on-error` to blocking-on-new-violations.
6. **dependency-review monthly → per-PR for critical paths** (decide
   scope).

**Acceptance:** each gap has a test file in `tests/security/`; CI
security job includes them.

---

## Phase 6 — Tooling & hygiene

1. **Orphan checkers (~35):** triage into (a) wire into GATE job,
   (b) pre-commit, (c) delete with rationale, (d) document as local-
   only. Prioritize `lint_helm_charts`, `lint_env_file`,
   `check_minimum_tests`, `semgrep/rules/prefer-chain.yaml` (advisory
   per Phase P.9 — either wire or delete).
2. **18 deselected tests:** 16 docker-compose runtime tests → dedicated
   CI job or documented `make test-docker-compose-runtime` in the sweep
   runbook; 2 CLI fixtures → confirm the exclusion is intentional and
   document, else include.
3. **Asset.visibility deprecation (b105c):** remove the deprecated
   write from `tests/concurrency/test_concurrent_mutations.py`; create
   a ticket for the phase-2 column removal so the countdown has an
   owner.
4. **CLI ai.py guard:** implement the AI CLI module or extend
   `TICKET=PH216-AI-CLI EXPIRES=…` before GATE-40 flips it
   (2026-12-31).
5. **Conditional E2E skips:** convert login-redirect/Stripe/timeout
   conditionals to W16 envpolicy (CI raises) — the b8-era failures
   they masked were real bugs.
6. **Commit hygiene:** land Phase 0.2 first so every later phase lands
   on a clean base.

---

## Ordering & dependencies

| Phase | Effort (approx) | Depends on |
|---|---|---|
| 0 — foundation | 1–2 d | — |
| 1 — connectors | 2–4 d + external creds | 0 |
| 2 — RoPA/warehouse | 1–2 d | 0 |
| 3 — MAILERS | 1 d | 0.2 |
| 4 — E2E coverage | 2–3 w (by domain) | 0.2, 4.1 decision |
| 5 — security | 1 w | 0.2 |
| 6 — tooling | 1 w | 0.2 |

## Decisions (user, 2026-10-04)

1. **Credentials:** provision live/test creds for Dados.gov.br,
   Snowflake, Stripe (test mode), Azure — see
   `docs/runbooks/CREDENTIAL_PROVISIONING.md` for the per-connector
   acquisition steps (user-executed externally) and the code-side prep
   already landed.
2. **Stripe:** live test-mode account.
3. **UC classification:** APPROVED — "API/SDK-only coverage mode" is a
   first-class registry concept (Phase 4.1 proceeds as designed).
4. **Vuln policy:** block on MEDIUM+ (Phase 5.4 implements).
5. **Auto-clone default:** DB-only batch targets get `TEST_DB=auto` as
   default; smoke/resilience/uat and frontend-driven targets stay on
   `hub_test_test_shared` (they test the live API whose DB it is).
   Escape hatch `TEST_DB=shared` on DB-only targets.
