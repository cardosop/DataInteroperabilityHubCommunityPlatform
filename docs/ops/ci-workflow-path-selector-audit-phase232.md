# CI workflow path-selector audit — Phase 232.8.18

This document records **high-signal** GitHub Actions workflows and their `paths` / `paths-ignore` selectors so changes to compliance-programme code trigger the right checks.

| Workflow | Primary paths | Notes |
| --- | --- | --- |
| `ci.yml` | Repo-wide (push/PR to protected branches) | Backend tests, ruff, OpenSpec `preprod01`, promtool on `monitoring/prometheus/alerts.yml` |
| `frontend-ci.yml` | `frontend/**`, `openspec/**`, workflow file | Should include `frontend/vite.config.ts` when bundle splits change |
| `bundle-size-check.yml` | `frontend/**`, `scripts/bundle_size_check.mjs` | Phase 232 programme chunk gate shares baseline |
| `openapi-validation.yml` | `hub/apps/**/views.py`, `serializers.py`, `urls.py` | Regenerate `docs/api/openapi-baseline.json` after URL or schema changes |
| `playwright-e2e.yml` / `e2e.yml` | Varies | Public DSAR journeys touch `frontend/e2e/**` |

## Maintenance rule

When adding a **new** top-level Django app or API prefix:

1. Extend `openapi-validation.yml` paths if new `urls.py` lives outside existing globs.
2. Add promtool / dashboard coverage under `monitoring/` when new metrics are introduced.
3. Update this audit file in the same PR.
