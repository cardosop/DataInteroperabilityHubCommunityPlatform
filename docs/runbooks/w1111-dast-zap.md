# W11.11 — Authenticated ZAP DAST runbook

**Owner:** Security Engineering Lead
**Gate:** GATE-64 (`scripts/check_zap_delta.py`) — delta vs baseline **zero new HIGHs**
**Workflow:** [.github/workflows/phase232-public-zap-baseline.yml](../../.github/workflows/phase232-public-zap-baseline.yml)

## What this is

Weekly (and on-demand) authenticated dynamic analysis of the staging API:
ZAP **full scans** logged in as one role at a time, compared against
committed baselines. The public unauthenticated baseline scan (Phase 232)
runs in the same workflow; the W11.11 matrix adds five authenticated
surfaces:

| Surface | Role | Access class exercised |
| --- | --- | --- |
| `public` | — | unauthenticated origin |
| `PLATFORM_ADMIN` | platform admin | cross-tenant administration |
| `TENANT_ADMIN` | tenant admin | tenant administration |
| `DATA_PROVIDER` | data provider | provisioning surface |
| `DATA_CONSUMER` | data consumer | consumption surface |
| `AUDITOR` | auditor | read-only compliance/DQ/audit surface |

The matrix lives in [scripts/zap/w1111_role_matrix.json](../../scripts/zap/w1111_role_matrix.json)
and MUST agree with the workflow matrix (pinned by
`scripts/tests/test_w1111_zap_delta.py`).

## How the authenticated scans reach the real surface

Role scans are **OpenAPI-driven automation plans** (`zap.sh -cmd
-autorun`): the JSON API root has no link surface (a plain spider crawl
stops at ~7 URLs), so the plan imports a REDUCED copy of the live spec
(`/api/v1/openapi.json` — 395 paths → 532 imported URLs). The reducer
(`scripts/zap/w1111_reduce_spec.py`) is structurally
identity-preserving; the full ~12 MB spec never finishes in ZAP's
importer. The reduced spec is served from a dedicated loopback-only
directory per run (never the scan workdir — it holds the minted token)
and the plan targets the ORIGIN (the spec's paths are absolute — a
prefixed targetUrl doubles every URL). The active scan is capped by
`maxScanDurationInMins` (the `maxDuration` parameter does not exist —
an uncapped active scan ran for hours during bring-up).

## How authentication is injected

1. `scripts/zap/w1111_zap_auth_config.py login-config` performs a real
   login (`POST {target}/api/v1/auth/login/`) and writes ZAP `-config`
   replacer arguments that inject `Authorization: Bearer <token>` into
   every scanner request.
2. The scan runs with `-T 30` (30-minute cap) so the 1-hour access
   token always outlives the scan.
3. The token is `::add-mask::`-ed in workflow logs and
   `verify-report` fails the job if the token string appears in the
   scan report (an app echoing the Authorization header must never be
   committed).

## The delta gate (GATE-64)

`scripts/check_zap_delta.py` compares each surface's report with its
committed baseline in [docs/security/zap/baselines/](../security/zap/baselines/).
Alert identity = `(pluginid, normalized-URI)`:

* **NEW HIGH** (pair absent from the baseline entirely) → **FAIL**
* **ESCALATION** (baseline MEDIUM/LOW pair now HIGH) → **FAIL**
* new MEDIUM/LOW, resolved HIGHs, count drift on known HIGHs → reported, pass

Matching is conservative: only scheme/host case, default-port, trailing
slash, and fragment are normalized — query values stay in the identity,
so a HIGH at a new query value counts as new (false-positive gate
failures are the safe direction). A missing report is a FAILURE, never
a skip (W16 environment policy).

## Running against hosted staging (CI)

* Trigger: `workflow_dispatch` on `phase232-public-zap-baseline.yml`, or
  the Monday 05:30 UTC schedule.
* Repository variables: `PHASE232_ZAP_TARGET` (staging origin; the whole
  workflow is gated on it), optional `W1111_ZAP_TARGET` (dedicated DAST
  clone override).
* Repository secrets — one pair per matrix role, **DAST-only accounts**
  (never reuse a human's credentials; a DAST account's session history
  and audit trail are noise by design), named
  `DAST_<ROLE>_USERNAME` / `DAST_<ROLE>_PASSWORD`:
  `DAST_PLATFORM_ADMIN_USERNAME` / `DAST_PLATFORM_ADMIN_PASSWORD`,
  `DAST_TENANT_ADMIN_*`, `DAST_DATA_PROVIDER_*`, `DAST_DATA_CONSUMER_*`,
  `DAST_AUDITOR_*`.
* A missing secret pair FAILS the matrix job with an actionable message
  (never a silent skip).
* Provisioning: create the five accounts in staging (one per role),
  enable email verification, and set a long random password. Rotate on
  the credential-rotation schedule (see the staging secrets registry).

## Running locally (compose staging)

```bash
make staging-up
make staging-post-deploy            # migrates + seeds the E2E personas
DAST_LOCAL_PASSWORD=<persona-password> make dast-local
```

Fresh-volume note: the chainguard MinIO image runs as uid 65532 and the
prefect server as uid 1000 — brand-new volumes are root-owned and both
services fail their first boot. Fix once (idempotent):

```bash
docker run --rm -v hub-staging_minio-data-staging:/data alpine \
  chown -R 65532:65532 /data
docker run --rm -v hub-staging_prefect-server-data-staging:/prefect alpine \
  chown -R 1000:1000 /prefect
```

The local runner (`scripts/zap/w1111_dast_local.sh`) reuses the CI
auth script and the same ZAP image/args; role personas are the E2E
personas seeded by `ensure_e2e_user_roles` (`e2e_platform@`,
`e2e_admin@`, `e2e_test@`, `e2e_consumer@`, `e2e_auditor@` —
example.com), whose password is supplied at runtime
(`DAST_LOCAL_PASSWORD` — deliberately NO committed fallback, G12).
Reports land in `docs/security/zap/reports/`; the delta gate runs
against the committed baselines.

## Triaging a FAIL

1. Download the delta artifacts (`w1111-zap-delta-<run_id>` and the
   per-role reports) from the run.
2. For each NEW HIGH / escalation:
   * **Real finding** → fix it (TDD, per the W-series convention), then
     re-run the scan.
   * **False positive** (scanner artifact, staging-only behaviour,
     WAF/edge difference) → record the triage in
     [docs/security/zap/triage.md](../security/zap/triage.md)
     (pluginid, URI, why it is not exploitable, sign-off), THEN
     re-baseline (below).
3. Re-run the delta gate — it must PASS before merge.

## Re-baselining (deliberate, never automatic)

Baselines change ONLY through a reviewed PR — the workflow runs with
`contents: read` and cannot rewrite them (no self-healing baseline
drift):

* Local: `DAST_LOCAL_PASSWORD=... make dast-local REBASELINE=1`
* Hosted: download the run's reports and open a PR that replaces the
  baseline JSONs in `docs/security/zap/baselines/`, citing the triage
  entries.

A baseline promotion without a triage entry for every accepted new
alert is a process violation (peer-reviewed in the PR).

## Notes and known characteristics

* The scan target is the API origin (`{target}/api/v1/`) — role scans
  cover the REST surface; the SPA is covered by the public origin scan
  in CI.
* The scanner runs as a single client IP; per-tenant rate limits
  (W11.9) may return 429s during the scan. Those are recorded, not
  retried; they are not HIGH findings.
* Scans write test data into staging (crawled create-flows). Staging
  is disposable; do not point this at production.
* Evidence ledger: every run emits `ledger-row.json` artifacts
  (kind `zap-baseline` / `zap-delta`) for the
  `docs/audit-reports/232-pen-test-ledger.md` consumer.
