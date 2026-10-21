# Phase 250 DoD closure pass — 2026-05-04

## Scope

This report captures the objective closure status for Phase 250 Definition
of Done items `250.DoD.1` through `250.DoD.8` after a repo-grounded
verification pass on 2026-05-04, including a follow-up engineering pass
that landed the missing infrastructure called out below.

## Verification evidence collected

### 250.DoD.1 — quality gates, PR hygiene, feature-flag discipline

- `frontend`: `npm ci && npm run typecheck && npm run lint` executed.
  - Result: `eslint` fails with a large pre-existing baseline (`598`
    errors, `15` warnings as of 2026-05-04 re-run), including
    `e2e-guards/no-test-skip-true`, `@typescript-eslint/no-unused-vars`,
    and `react-hooks/refs`.
- `backend`: `ruff check hub/apps/assets hub/apps/orchestration hub/apps/audit`
  executed in `api-service-test` container.
  - Result: fails with large pre-existing baseline (`5726` errors).
- `CHANGELOG.md`: Phase 250 section already in place.
- Feature-flag and runbook artifacts exist in repo for Phase 250 (kill-
  switch, fail-closed, federated-import).
- Phase-250-only lint deltas (introduced files) are clean — verified via
  targeted `eslint`/`vitest`/`ruff` runs in the R7 / R8 baseline-
  remediation batches.

Conclusion: **NOT complete**. The repo-wide lint/type baselines must be
reduced before this DoD can be marked closed; the Phase 250 surface area
itself is clean.

### 250.DoD.2 — OpenSpec validation

- `openspec validate preprod01 --strict` returns `Change 'preprod01' is
  valid` (re-confirmed 2026-05-04 in the closure pass).

Conclusion: **complete**.

### 250.DoD.3 — per-phase exit checklist

Runbooks are present in `docs/runbooks/` and alert rules are present in
`monitoring/prometheus/alerts/asset-creation.yml`, but this DoD item
requires external lifecycle evidence (merged PR boundaries, staging/prod
rollout, soak window, canary progression, retro outcome). Sign-offs are
tracked in `docs/raci/asset-creation-hardening-signoffs.md`.

Conclusion: **NOT complete** (external execution evidence required).

### 250.DoD.4 — SLO miss escalation policy live

The escalation contract is **fully wired** in code/config; the remaining
work is the live drill that proves the path fires end-to-end.

- Prometheus rules: `monitoring/prometheus/alerts/asset-creation.yml`
  defines:
  - `AssetWorkflowDurationP95TwoXSLO` (`>60s` for `15m`, `severity=page`).
  - `AssetWorkflowDurationP95ThreeXSLOAutoRollback`
    (`>90s` for `30m`, `severity=critical`, `auto_rollback="true"`).
- Wired into both `monitoring/prometheus/prometheus.yml` and
  `monitoring/prometheus/prometheus.production.yml`.
- Alertmanager (`monitoring/alertmanager/alertmanager.yml`):
  - New route `auto_rollback="true"` → receiver
    `asset-creation-auto-rollback` (webhook to GitHub
    `repository_dispatch`).
  - New route `severity=page` → receiver `asset-creation-page-oncall`
    (PagerDuty events-v2).
  - New inhibit rule prevents the 2× page from re-firing once the
    auto-rollback route has dispatched.
- GitHub Actions workflow:
  `.github/workflows/auto-rollback-asset-creation.yml` accepts the
  dispatch, resolves the previous Helm revision, runs `helm rollback`,
  and posts to Slack `#incidents`. Supports `dry_run` for both staging
  and production drills.
- Operational runbook: `docs/runbooks/asset-creation-auto-rollback.md`
  documents pre-deployment checklist, drill procedure, and silence/
  override flow.

Conclusion: **wired but not live**. Closes after both staging and
production drills pass and sign-offs land in
`docs/raci/asset-creation-hardening-signoffs.md`.

### 250.DoD.5 — 30 % contingency buffer per pass-2 self-review

Self-review allocation recorded in this pass:

| Stream | Baseline days | +30 % contingency | Buffered total |
| --- | ---: | ---: | ---: |
| Engineering implementation | 20 | 6 | 26 |
| QA + staging verification | 10 | 3 | 13 |
| Operations rollout + soak handling | 10 | 3 | 13 |
| Governance / sign-offs | 5 | 1.5 | 6.5 |
| **Total** | **45** | **13.5** | **58.5** |

Conclusion: **complete** (pass-2 self-review buffer explicitly documented).

### 250.DoD.6 — stakeholder RACI sign-off

The RACI matrix exists at `docs/raci/asset-creation-hardening.md`. A
companion sign-off ledger is now established at
`docs/raci/asset-creation-hardening-signoffs.md`, listing every required
phase × stakeholder approval and an auditor checklist for closeout.

Conclusion: **wired but not live**. Closes once each ledger row records
the verifiable approval reference (PR review link or transcribed
attestation).

### 250.DoD.7 — production smoke test post-deploy

Smoke test is now implemented at
`tests/smoke/test_phase250_data_first.py`, exercising all four DoD.7
criteria against a real deployed environment (no mocks):

1. Data-first creation P95 latency ≤ 8 s — runs N (default 5) real
   data-first creations through the full /files/init →presigned-upload
   →/files/{id}/complete →/assets/data-first/ flow and asserts the
   measured P95 against the 8 000 ms budget.
2. Fail-closed → zero orphan DRAFTs — submits a fail-closed-targeting
   payload and verifies the unique key has zero matching asset rows
   afterwards.
3. Federated import + compliance gate — opt-in via
   `SMOKE_PHASE250_FEDERATED_IMPORT_ENABLED=1`; asserts the import
   response surfaces compliance-gate metadata.
4. If-Match 412 — creates an asset, sends a stale `If-Match`, and
   asserts the 412 response carries `code=PRECONDITION_FAILED` plus
   structured `details.expected_version` / `details.provided_version`.

Conclusion: **wired but not live**. Closes after the smoke job runs
green against staging (and, for the federated check, the smoke tenant
has `federated_import_enabled=True`).

### 250.DoD.8 — OpenSpec archive after deploy

A Phase-250-specific archive runbook now exists at
`docs/runbooks/openspec-archive-preprod01-phase250.md` with:

- Pre-flight prerequisite check that scans `tasks.md` for any open
  Phase 228 / 240 / 250 / 260 DoD items before allowing the archive.
- Step-by-step `openspec archive preprod01 --skip-specs --yes` procedure
  including pre-archive snapshot capture and the archive PR template.
- Rollback procedure in case the archive needs to be undone.
- Sign-off section.

Conclusion: **wired but not live**. Runs only after `250.DoD.1`–`.7`
all close.

## Immediate next actions

1. Reduce frontend eslint and backend ruff baselines to unblock
   `250.DoD.1`. Phase-250-only files are already clean.
2. Configure the GitHub Secrets / Variables called out in
   `docs/runbooks/asset-creation-auto-rollback.md`, then run the staging
   and production drills (`dry_run=true`). Sign off in the RACI ledger.
3. Run `tests/smoke/test_phase250_data_first.py` against staging once
   `SMOKE_PHASE250_*` env vars are set; capture the run URL in the RACI
   ledger to close `250.DoD.7`.
4. Collect explicit RACI sign-off records to close `250.DoD.6`.
5. Archive OpenSpec (`250.DoD.8`) only after `.1`, `.3`, `.4`, `.6`,
   `.7` have all closed.

## Artifacts produced in this pass

| Artifact | Path |
| --- | --- |
| Production smoke test (DoD.7) | [tests/smoke/test_phase250_data_first.py](../../tests/smoke/test_phase250_data_first.py) |
| Auto-rollback runbook (DoD.4) | [docs/runbooks/asset-creation-auto-rollback.md](../runbooks/asset-creation-auto-rollback.md) |
| Auto-rollback workflow (DoD.4) | [.github/workflows/auto-rollback-asset-creation.yml](../../.github/workflows/auto-rollback-asset-creation.yml) |
| Alertmanager auto-rollback wiring (DoD.4) | [monitoring/alertmanager/alertmanager.yml](../../monitoring/alertmanager/alertmanager.yml) |
| RACI sign-off ledger (DoD.6) | [docs/raci/asset-creation-hardening-signoffs.md](../raci/asset-creation-hardening-signoffs.md) |
| Phase 250 archive runbook (DoD.8) | [docs/runbooks/openspec-archive-preprod01-phase250.md](../runbooks/openspec-archive-preprod01-phase250.md) |
