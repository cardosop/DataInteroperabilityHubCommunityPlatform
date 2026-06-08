# Flaky Test Quarantine Policy

**Date:** 2026-05-22
**Phase:** 312.12.5 — Test Performance & Developer Workflow
**Status:** Active (warn-only for first 2 sprints)

---

## Overview

A **flaky test** is one that passes on retry but fails on first run when the code under test has not changed. Flaky tests erode trust in CI — developers learn to ignore red builds.

This policy defines the quarantine lifecycle for flaky tests across backend (pytest) and frontend (Playwright).

---

## Detection

### Backend (pytest)
- CI runs with `pytest -m "integration or e2e" --reruns 2 --reruns-delay 5`
- A test that fails on pass 1 but succeeds on pass 2 or 3 is **flagged as flaky**
- `--durations=50` output identifies slowest tests (often correlated with flakiness)

### Frontend (Playwright)
- Main config: `retries: 2` in CI
- A test that passes on retry is logged in the Playwright report
- Quarantine config: `playwright.mvp.quarantine.config.ts` tags tests as `@quarantine`

---

## Quarantine Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│  Test fails on 1st run, passes on retry                 │
│        ↓                                                │
│  Flagged: add @quarantine tag (Playwright) or           │
│           @pytest.mark.flaky (backend)                  │
│        ↓                                                │
│  MOVED to quarantine suite:                             │
│    - Frontend: removed from default MVP CI run          │
│    - Backend: excluded from -m "not flaky" filter       │
│        ↓                                                │
│  Quarantine suite runs NIGHTLY (does not block merge)   │
│        ↓                                                │
│  Reviewed weekly by feature owner                       │
│        ↓                                                │
│  ┌──────────────────────────────────────────┐           │
│  │ Passes 5 consecutive nightly runs?        │           │
│  │  YES → Strip @quarantine → re-join CI     │           │
│  │  NO  → Keep in quarantine, investigate    │           │
│  └──────────────────────────────────────────┘           │
│        ↓                                                │
│  NOT fixed within 2 sprints → PERMANENTLY REMOVED      │
└─────────────────────────────────────────────────────────┘
```

---

## Quarantine Suites

### Backend — `@pytest.mark.flaky`

Register in `pytest.ini`:
```ini
flaky: Tests with known intermittent failures (quarantined, nightly only)
```

Run quarantine suite:
```bash
pytest -m "flaky" --reruns 5 --reruns-delay 2 -x --durations=20
```

CI workflow: nightly schedule, does not block merge.

### Frontend — `@quarantine` tag

Already implemented in `playwright.mvp.quarantine.config.ts` (Phase 225.4):
- Inherits `playwright.mvp.config.ts`
- `grep: /@quarantine\b/`
- Runs against staging environment daily at 02:30 UTC
- 3 retries (more budget than main 2)

---

## Tracking

### CI Metrics
- Track pass/fail per test across last 10 CI runs
- `_reusable.lint.yml` uploads test results as artifacts
- `test-results-reporting.yml` aggregates across workflows

### Review Cadence
| Event | Action |
|---|---|
| Weekly review | Feature owner reviews quarantined tests |
| 5 consecutive passes | Strip quarantine tag, re-join main CI |
| 2 sprints without fix | Permanently remove the test (document reason) |
| New flaky test found | Add to quarantine within 24 hours |

---

## Prevention

1. **Never use `time.sleep()` in tests** — use `wait_for` / `poll.until` / `Event.wait` (GATE-05)
2. **Never use `pytest.skip()` in test bodies** — use decorator-level `@pytest.mark.skipif` (GATE-07)
3. **Use `@pytest.mark.xdist_group("serial")`** for tests that cannot run in parallel
4. **Use `@pytest.mark.xdist_group("db_write_heavy")`** for tests contending on DB writes
5. **Clean up test data** — each test should create its own fixtures or use `--reuse-db`
6. **Mock external dependencies** in unit tests — integration tests use real services

---

## Related Documentation
- [e2e-batch-strategy.md](e2e-batch-strategy.md) — E2E batch execution
- [marker-audit.md](marker-audit.md) — Pytest marker inventory
- [ci-workflow-audit.md](ci-workflow-audit.md) — CI workflow catalog
