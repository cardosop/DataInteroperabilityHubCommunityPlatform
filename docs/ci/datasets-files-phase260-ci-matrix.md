# Phase 260.0.23 — CI matrix (incremental rollout)

Baseline repo already invokes **ruff**, **black**, **mypy** (informational lane),
`scripts/check_error_codes_catalogue.py`, OpenSpec `validate`, and Playwright
subsets.

## Phase additions

| Capability | Scope | Merge gate |
|------------|-------|------------|
| Stale feature flags CRITICAL | `detect_stale_feature_flags.py --fail-on-critical` | Yes (`stale-feature-flag-critical-gate` job). |
| EICAR fixture | `tests/fixtures/eicar.txt`; pytest `hub/apps/files/tests/test_virus_scan_e2e.py` (`RUN_FILE_VIRUS_SCAN_E2E=1`, `--profile clamav-test`); Playwright `frontend/e2e/features/file-virus-scan.spec.ts` | Optional nightly / manual (default merge gate stays green without ClamAV). Host AV must exclude fixture paths — see `docs/onboarding/datasets-files-feature.md`. |
| ClamAV compose image | `clamav/clamav:1.5` in `docker-compose.yml` / `docker-compose.test.yml` | Legacy `1.3` tags were removed from Docker Hub; keeps profile pulls reproducible (Helm already pins `1.5`). |
| Distributed-lock unit tests | `fakeredis[lua]` (**`lupa`** enables `EVAL`; matches production Lua release) | Default pytest corpus (`hub/apps/core/tests/test_distributed_lock.py`). |

## Deferred tightening (260.23b — owners backlog)

Strict **mypy**, **eslint** zero-warnings, **`tsc --strict`**, **chromatic**, **openapi-diff**, **strong-migrations** — schedule once existing debt trackers close.
