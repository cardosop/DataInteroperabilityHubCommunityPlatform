# CI Test Runtime Benchmarks

**Date:** 2026-05-22
**Phase:** 312.17.6 — Performance Baseline
**Status:** Active — tracked weekly in `_reusable.performance.yml`

---

## Benchmark Targets

| Suite | Target | Current (2026-05-22) | Notes |
|---|---|---|---|
| Backend (pytest) | < 30 min | TBD — measured in CI | `make test-backend` with `-n auto --reuse-db` |
| Frontend (vitest) | < 10 min | TBD — measured in CI | `make test-frontend-unit` |
| E2E (Playwright) | < 60 min | ~45-65 min (8 batches) | `make test-frontend-e2e` with 1-2 workers |

---

## Measurement

### Backend Runtime

```bash
# CI: time the backend test suite
time make test-backend
# Or in CI workflow:
#   /usr/bin/time -f "%e" python -m pytest hub/apps/ tests/ -n auto --reuse-db -q
```

Tracked weekly via `_reusable.performance.yml`:
- `--durations=20` in pytest.ini addopts captures slowest 20 tests
- CI uploads pytest durations as artifact for trend analysis

### Frontend Runtime

```bash
# CI: time the frontend unit suite
cd frontend && time npx vitest --run
```

Tracked in `frontend-tests.yml` CI job.

### E2E Runtime

```bash
# CI: time the full E2E suite
time npm run test:e2e:batch1; time npm run test:e2e:batch2; ... # through batch 8
```

Tracked per-batch in `playwright-e2e.yml`. Each batch has its own timeout (typically 15-25 min).

---

## Trend Analysis

### Weekly Report (in `_reusable.performance.yml`)

The `ci-runtime-benchmark` job:
1. Collects runtimes from CI artifacts (pytest durations JSON, Playwright report timing)
2. Compares against previous week's baseline
3. Flags regressions > 20% as warnings, > 50% as errors

### Ratchet Policy

- Runtime cannot increase more than 10% week-over-week without documented justification
- New tests adding > 5% to runtime require performance review
- `--durations=20` output reviewed weekly for optimization candidates

---

## Optimization Levers

### Backend
- `-n auto` for parallel execution (xdist)
- `--reuse-db` to skip migration overhead
- `-q` to reduce I/O
- `--dist worksteal` for unbalanced test distribution

### Frontend
- `--max-old-space-size=4096` for memory-intensive suites
- Split large test files (e.g., ProtectedRoute.test.tsx was split)
- `maxThreads: 2` for vitest parallel execution

### E2E
- Batch strategy (8 batches) isolates fast/slow tests
- `--workers=1` for auth-heavy batches (reduce rate-limit cascades)
- `storageState` caching avoids per-test login

---

## Related Documentation
- [e2e-batch-strategy.md](e2e-batch-strategy.md) — E2E batch definitions and rationale
- [xdist-parallelization-groups.md](xdist-parallelization-groups.md) — Parallel test execution groups
