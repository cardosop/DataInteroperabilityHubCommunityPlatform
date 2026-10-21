# Beta Go/No-Go Sign-Off Ledger

Machine-parseable sign-off records for the U.8 go/no-go decision. The gate
(`scripts/check_go_nogo.py`) reads the table below: a criterion whose row
has `confirmed = no` is reported as **OWNER** (human sign-off pending) and
the gate exits 4 (AWAITING-OWNER) instead of 0 (GO). Never edit a row to
`yes` without actually performing the confirmation — the gate is the
machine half of the decision; this file is the human half.

| key | criterion | owner | confirmed | date |
|-----|-----------|-------|-----------|------|
| oncall-confirmed | Alerting + on-call confirmed (runbook §on-call: admin, 48h/4h SLA; alertmanager-staging.yml live) | admin | no | — |
| freeze-agreed | Beta freeze window agreed (change-freeze-calendar.md; no non-critical deploys during the cohort window) | admin | no | — |

## a11y failure ledger (fix-or-annotate)

The gate cross-checks the E2E batch-1b FAILED count against this table —
a failure not listed here blocks the go decision. Keep rows in sync with
`frontend/e2e/a11y/*` reality; annotate every row with TICKET + EXPIRES.

| spec | failure | ticket | expires |
|------|---------|--------|---------|
| e2e/a11y/axe-ml.spec.ts | ML dark-mode wcag2aa violations | TICKET=U5-A11Y-1 | 2026-09-14 |
| e2e/a11y/axe-phase278-pages.spec.ts | marketplace listing page — 1 serious axe violation | TICKET=U5-A11Y-2 | 2026-09-14 |
| e2e/a11y/axe-phase278-pages.spec.ts | keyboard-shortcuts cheatsheet — 1 serious violation | TICKET=U5-A11Y-3 | 2026-09-14 |
| e2e/a11y/axe-phase278-pages.spec.ts | GraphQL-LD playground — 30s locator timeout | TICKET=U5-A11Y-4 | 2026-09-14 |

## vitest unit-test debt (fix-or-annotate)

The frontend unit suite carries pre-existing assertion-drift debt (mock
expectations vs implementation) — measured live on the U.8 gate run.
The `vitest` go criterion stays RED until this is fixed at root; the
batch below is the triage list for the fix wave.

| scope | count | ticket | expires |
|-------|-------|--------|---------|
| 23 test files / 74 tests / 4 OOM workers (diverse assertion drift: ApiClient 401 refresh, ModelsEditor, FileUpload resume prompt, downloadFileWithVerification, audit filters, …) | 74 | TICKET=U8-VITEST-74 | 2026-09-14 |

## Machine results (filled by the gate run)

| criterion | verdict | evidence |
|-----------|---------|----------|
| lint-ratchet | | |
| ci-local | | |
| ci-remote | | |
| secrets-contract | | |
| staging-smoke | | |
| data-rehearsal | | |
| makemigrations | | |
| backup-restore | | |
| frontend-baseline | | |
| vitest | | |
| a11y | | |
| eks-ticket | | |
| alerting-oncall | | |
| freeze-agreed | | |
