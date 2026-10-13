# Pilot Readiness Plan — First Company Deployment (AWS + Databricks)

Companion to `TEST_COVERAGE_CLOSURE_PLAN.md`. Executes the four-week path
to a first-company pilot. Owners: **C** = Claude (this session), **U** =
user (external actions only you can take).

Revision 2 (2026-10-04) — incorporates the critical review: atomic
commits, working email, HTTPS domain, backups-before-first-data,
privacy/legal prep, pilot operations, stop-the-line criteria, and reuse
of the repo's existing go/no-go machinery.

---

## Week 1 — Commit the tree, credential re-init rehearsal, staging bring-up

**Exit criteria:** stack survives two full re-creates with zero manual
steps; CI green from a clean checkout; staging serves HTTPS with
working email, verified backups, and a recorded perf baseline.

### 1.1 Commit the working tree (C + U)
- **Partition the diff**: ~3,000 dirty files include pre-campaign
  preprod01 work. U confirms which files belong to this campaign;
  everything else goes to its own commit or stays stashed.
- **Atomic per-domain commits — code and its tests land together**
  (a tests-first layering would fail CI: new tests import code that
  hasn't landed yet):
  1. docs only: plan/runbook docs, regenerated
     `docs/api-audit/test-fixtures-and-factories-report.json`
  2. connectors domain: azure/dados connector tests + the
     `test_ckan_env_config.py` leak fix (code+tests)
  3. smoke/security domain: smoke guards, security test fixes,
     billing-upgrade spec hardening
  4. test infra: `tests/conftest.py` (flush retry, advisory-lock
     guard), `tests/utils/cli_config.py`, `provision_smoke_fixtures.py`,
     `TEST_DB=auto` batch mode
  5. hub domain: `hub/settings.py` MAILERS + the settings-contract
     test, `internal_views.py` dlt payload fix + prefect suite,
     permissions/views docstrings
  6. services domain: datacontract `main.py`, dq `soda_adapter.py`,
     `timeliness_check.py`, their pytest.ini filters
  7. compose/CI: `docker-compose.test.yml` (JVM_ARGS, ADMIN_PASSWORD
     comment), `.env.test.example` key template (`.env.test` stays
     gitignored)
- **Clean-checkout proof**: `git worktree add` a fresh checkout, run
  `make quality-gates` + batch families 1, 6-4, 10-5b, 12-2 there.

### 1.2 Credential re-init rehearsal (C — maintenance window required)
- **Coordinate first**: announce the window to the peer sessions
  (SendMessage), verify zero live pytest (`ps` check). The
  `down -v minio-test-data` step corrupts any in-flight batch on the
  shared stack.
- Fuseki/semantic already force-recreated with `.env.test` (verified
  493/493) — confirm, don't repeat.
- MinIO: `docker compose -f docker-compose.test.yml --env-file .env.test
  down -v minio-test-data` → `up` → verify S3 presigned-upload tests
  (batch 1 family) + storage-sensitive e2e specs.
- CKAN: re-mint token via ckan CLI → `.env.test` →
  `verify_connector_creds.py ckan`.
- **Durable fix**: `make test-stack-reinit` (idempotent) +
  `scripts/verify_test_stack_creds.py` (detects volume-vs-env MinIO
  mismatch BEFORE tests 401).
- Run the reinit twice back-to-back — exit criterion.

### 1.3 Staging bring-up — complete pilot surface (C + U)
U provides the AWS staging environment (compute + RDS + S3 + secrets
store + a DNS record). This week delivers the **full pilot surface**,
not just the API:

1. **Infra**: `docker-compose.staging.yml`/helm bring-up with
   `.env.staging`; ExternalSecrets wired (all secrets live there —
   never plaintext in `.env.staging`).
2. **Domain + HTTPS**: DNS record, TLS certificate (ACM/Let's
   Encrypt), nginx/ALB termination. Wire `check_production_cors.py`
   into the pre-deploy gate (today it's an orphan).
3. **Email delivery (Day-1 blocker)**: configure `EMAIL_PROVIDER`
   smtp/sendgrid/ses with a real sender — invitations, password
   resets, and notifications must reach the company's users. Verified
   by an end-to-end invitation email test.
4. **Frontend deployment**: production build, hosting (S3/CloudFront
   or web container), `VITE_API_BASE_URL` set for staging (U.8-known
   trap), SPA smoke.
5. **Backups before first data**: RDS snapshot schedule + S3
   versioning enabled and a restore verified NOW (not in Week 4).
6. **Perf baseline**: run the perf suite against staging; record
   numbers.
7. **Scale definition (U)**: company's expected users, concurrent
   sessions, data volumes — recorded for the Week-4 load test.
8. **Gate checks**: `make staging-smoke` + `check_pre_staging_gate.py`.
9. **Pilot operations from day one**: dashboard access (Grafana),
   alert routing to a named on-call (U), escalation path, incident
   runbook stub.

---

## Week 2 — Their-account smoke pass (Databricks control plane + warehouse + dlt)

**Exit criteria:** live connector suite green against THEIR account;
written smoke report. **Stop-the-line:** if the real Databricks API
surface is fundamentally mismatched (version drift, missing endpoints,
rate limits), STOP and re-scope — do not paper over with mocks.

### 2.1 While blocked on U's credentials (C — starts immediately)
1. Reproduce the 22 Databricks live failures against the EXISTING
   sandbox creds; classify each: reachability vs real code bug.
2. Fix every code-bug classification with a unit test in the same
   commit.
3. Build the nightly CI job skeleton pinned to pilot credentials.

### 2.2 Credential acquisition (U — per `CREDENTIAL_PROVISIONING.md`,
for THEIR account)
Databricks workspace host + token (or M2M SP), one SQL warehouse id,
AWS keys (Athena/S3/optional Data Exchange), dlt destination config.
**Budget guardrail: set workspace/warehouse budget caps before any
query runs.**

### 2.3 Verification (C)
- Run `python hub/manage.py test_connectors_e2e` against their creds;
  warehouse live classes; one dlt ingest end-to-end; one
  dbt-databricks transformation; verify cost-ledger rows.
- Written smoke report: every exercised path, results, API-shape
  mismatches, gaps.

---

## Week 3 — IdP (OIDC) wiring + pilot scope + journeys E2E

**Exit criteria:** documented end-to-end user story on their account:
login (SSO) → connect Databricks → ingest → contract → publish →
consume. **Stop-the-line:** any journey marked critical in the
registry that cannot be demonstrated → it blocks, not ships.

### 3.1 OIDC wiring (C + U)
- U provides IdP (Okta/Auth0/Entra) application credentials → stored
  in ExternalSecrets (staging), NOT env files.
- Configure `hub/apps/auth/sso.py`; run `tests/auth/test_sso*` +
  UC-AUTH-006 specs; add an IdP-metadata integration test (env-gated,
  W16).
- SCIM is NOT built — if their IT requires it, decide: OIDC +
  invitation flow for the pilot, or scope SCIM as a feature.

### 3.2 Pilot scope workshop (C + U)
1. **Journey selection anchored to the critical registry**: pick from
   `docs/CRITICAL_UC_JOURNEY_IDS.yaml` FIRST (33 journeys / 37 UCs),
   then supplement — target ~20 total for their data-platform
   workflow.
2. **Capability manifest**: which surfaces are ON for the pilot
   (MVP/capability flags) — the company must not see half-finished
   features; everything OFF is documented as out-of-scope.
3. **Feature expectations**: Unity Catalog / Delta Sharing are NOT
   built — decide now whether that's a pilot requirement (if yes,
   re-scope the plan before E2E work starts).
4. **Data migration**: how their existing data/users arrive
   (connector, CSV, invitations).

### 3.3 Privacy & legal for real company data (C + U)
- Run the app's own DPIA + RoPA modules for the pilot tenant
  (LGPD/GDPR posture), sign the DPA, and document the pilot
  exit/deletion path (erasure journey) — exercised before go-live.

### 3.4 E2E the pilot journeys (C)
- For each selected journey: existing E2E spec or new one. New specs
  follow the Documentation Sync Contract (docs journey/UC entry +
  backend marker + persona aggregator import — GATE-26/27/28).
- User-facing quickstart docs for the company's data engineers.
- Run the covering frontend batches + backend batches with explicit
  sequencing (`TEST_DB=auto` for DB-only batches; shared stack only
  for smoke/uat) to avoid the known contention.

---

## Week 4+ — Security edges, vuln policy, Stripe, ops rehearsals, go/no-go

**Exit criteria:** the repo's existing go/no-go gate passes with an
evidence pack.

### 4.1 Security edges (C)
Coverage-closure Phase 5: SSRF tests for marketplace/warehouse
connectors; `tests/security/test_api_key_scopes.py` matrix; Phase 273
throttle-audit assertion.

### 4.2 Dependency-vuln policy — block MEDIUM+ (C)
Wire pip-audit/trivy blocking per the decision; triage the current
MEDIUM/LOW list; fix the truncated audit log output.

### 4.3 Stripe (C + U, if charging at pilot)
Test-mode keys; enable `E2E_STRIPE_ENABLED=1` assertions in the
billing-upgrade spec; webhook idempotency/signature tests against the
Stripe CLI.

### 4.4 Ops rehearsals (C + U)
- DR drill: restore RDS from snapshot → re-seed → verify (the
  disaster_recovery suite as a REAL drill).
- TLS rotation rehearsal; load test at the Week-1 scale numbers;
  compare against the perf baseline.
- Pilot exit-clause drill: tenant data export + deletion path
  verified end-to-end (protects both sides if the pilot ends).

### 4.5 Go/no-go decision (U)
Run the repo's existing go/no-go gate process (U.6–U.8 staging
series) — evidence pack: clean-checkout CI green; live-connector
smoke report; pilot journey runbook; security suite + vuln policy
green; Stripe verdict; ops rehearsal logs; privacy pack (DPIA/DPA).

---

## Dependencies & risks

| Risk | Mitigation |
|---|---|
| U's credential acquisition slips | 2.1 runs immediately: classification + code-bug fixes + CI skeleton land before creds arrive |
| The 22 Databricks failures are real code bugs | Pre-classified in 2.1; each fix unit-tested same-commit |
| SCIM/SAML required by company IT | Raised in 3.1; fallback OIDC + invitation flow |
| Unity Catalog / Delta Sharing expectation | 3.2 decision point; re-scope before E2E work |
| Pre-existing uncommitted work unrelated to the campaign | 1.1 partition step — U confirms scope per commit |
| Shared-stack contention during pilot weeks | Maintenance window for 1.2; `TEST_DB=auto` for DB-only batches; explicit test sequencing in 3.4 |
| Pilot bills surprise (Databricks/AWS costs) | Budget caps set in 2.2 before first query; cost ledger verified |
| Email/TLS/backups forgotten | All are Week-1 exit criteria now |
| Pilot fails or ends | Exit-clause drill in 4.4; erasure path documented in 3.3 |

## Success criteria for the pilot itself

1. The company completes the Week-3 user story end-to-end on their
   AWS/Databricks account with no manual intervention by us.
2. Email, HTTPS, backups, and on-call verified before their first login.
3. Zero critical/blocking defects open on the pilot path; every
   critical-registry journey on the manifest is demonstrable.
4. CI (backend + frontend + security) green from a clean checkout.
5. Privacy pack (DPIA/DPA/exit path) signed off.
6. Go/no-go evidence pack delivered through the repo's existing gate.
