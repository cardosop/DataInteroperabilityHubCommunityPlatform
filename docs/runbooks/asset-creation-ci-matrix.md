# Phase 250.0.22 — CI matrix additions for asset-creation

**Status**: Authoritative
**Phase**: 250.0.22
**Owners**: SRE / Platform Engineering

## Required CI checks for Phase 250 PRs

Every PR that modifies `hub/apps/{assets,orchestration,compliance,dq}/` OR the OpenSpec change `preprod01` MUST pass these gates before merge.

### Static analysis (existing, verify scope)

| Gate | Tool | Scope | Phase reference |
|---|---|---|---|
| Type check | `mypy --strict` | `hub/apps/{assets,orchestration}/**/*.py` | (existing) |
| Lint (Python) | `ruff check` | `hub/apps/**/*.py` | (existing) |
| Lint (TypeScript) | `tsc --strict` | `frontend/src/**/*.{ts,tsx}` | (existing) |
| Lint (TypeScript style) | `eslint` | `frontend/src/**/*.{ts,tsx}` | (existing) |
| Accessibility | `axe-core` (in Playwright) | `frontend/e2e/**/*.spec.ts` | (existing) |
| Visual regression | `chromatic` | Storybook stories for AssetCreatePage / AssetDetailPage | (existing) |
| Bundle size | `size-limit` (Phase 230.13.10) | `frontend/dist` | (existing) |

### Phase 250-specific gates (NEW)

| Gate | Tool / Script | Scope | Behaviour |
|---|---|---|---|
| Migration safety | `strong-migrations` (Django) | `hub/apps/*/migrations/*.py` | Block PR if migration is non-additive without explicit `RunPython` reverse OR `atomic=False` declaration. |
| OpenAPI delta | `openapi-diff` | `hub/api/openapi.json` | Block PR on breaking changes to public API; warn on additive. |
| Python supply chain | `pip-audit` + `safety check` | `requirements.txt` + `requirements-dev.txt` | Block PR on CRITICAL CVE; warn on HIGH; pinned `.trivyignore` allowance reviewed quarterly. |
| Frontend supply chain | `npm audit` (CI threshold) | `frontend/package.json` | Block PR on CRITICAL/HIGH from npm audit. |
| Static security | `bandit` | `hub/apps/**/*.py` | Block PR on `bandit -ll` (HIGH severity) findings. |
| Pattern security | `semgrep` (custom rules) | `hub/apps/**/*.py` | Block PR on rules: SQL-injection, secret-leak, SSRF-bypass per Phase 240.5.G + Phase 250.5.B. |
| Direct Asset.objects.create() guard | `scripts/check_asset_create_bypass.py` (Phase 250.1.G NEW) | `hub/apps/**/*.py` | Block PR on new direct `Asset.objects.create()` callers outside `hub/apps/assets/services.py` and `migrations/`. Allow-list captures the 9 existing sites pending migration per [b2-13 audit](../audit-reports/b2-13-direct-asset-create-callers-2026-05-03.md). |
| Error-codes catalogue | `scripts/check_error_codes_catalogue.py` (Phase 250.0.13 NEW) | `hub/apps/**/*.py` ↔ `docs/api/error-codes.md` | Block PR on emitted code missing from catalogue. |
| PII redaction (DQ logs) | `scripts/check_dq_log_extras.py` (Phase 240.5.F.4 existing) | `hub/apps/dq/**/*.py` | Already in CI; extend `_DEFAULT_PATHS` if Phase 250 adds DQ-adjacent code paths. |
| Stale feature flags | `scripts/detect_stale_feature_flags.py` (Phase 250.0.15 NEW) | `hub/apps/tenants/feature_flag_registry.py` | Informational; warn on flags >180 days post-GA. NEVER blocks PRs (per the policy). |
| Workflow version invariants | `python manage.py audit_workflow_version_invariants` | `hub/apps/orchestration/**` | Run nightly; alert on violations (single active version, in-flight runs in soak). |
| Cross-service version check (in CI test envs) | `python manage.py validate_cross_service_versions` | `hub/apps/core/cross_service_version_check.py` | Verify the check itself works against staging dq-service / compliance-service before deploy. |

## Wiring (.github/workflows/ci.yml additions)

The CI workflow gains the following jobs (path-filtered per Phase 240.5.F precedent):

```yaml
  # Phase 250.0.13 — error-codes catalogue gate
  error-codes-catalogue-check:
    name: 250.0.13 — Error codes documented in docs/api/error-codes.md
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Detect relevant changes
        id: filter
        uses: dorny/paths-filter@v3
        with:
          filters: |
            changed:
              - 'hub/apps/**/*.py'
              - 'docs/api/error-codes.md'
              - 'scripts/check_error_codes_catalogue.py'
              - '.github/workflows/ci.yml'
      - uses: actions/setup-python@v5
        if: steps.filter.outputs.changed == 'true'
        with: { python-version: '3.12' }
      - name: Run error-codes catalogue check
        if: steps.filter.outputs.changed == 'true'
        run: python scripts/check_error_codes_catalogue.py
      - name: No-op (keeps job registered as a required check)
        if: steps.filter.outputs.changed != 'true'
        run: echo "no-op; PR did not touch error-code-relevant paths"

  # Phase 250.0.14 — cross-service version-check unit tests + integration smoke
  cross-service-version-check:
    name: 250.0.14 — Cross-service version-compatibility tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Detect relevant changes
        id: filter
        uses: dorny/paths-filter@v3
        with:
          filters: |
            changed:
              - 'hub/apps/core/cross_service_version_check.py'
              - 'hub/apps/core/tests/test_cross_service_version_check.py'
              - 'hub/apps/core/apps.py'
              - '.github/workflows/ci.yml'
      - uses: actions/setup-python@v5
        if: steps.filter.outputs.changed == 'true'
        with: { python-version: '3.12' }
      - name: Run focused tests
        if: steps.filter.outputs.changed == 'true'
        run: |
          pip install -r requirements-dev.txt
          pytest hub/apps/core/tests/test_cross_service_version_check.py -v

  # Phase 250.1.G — direct Asset.objects.create() bypass guard
  asset-create-bypass-check:
    name: 250.1.G — Asset.objects.create() bypass guard
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run check_asset_create_bypass.py
        run: python scripts/check_asset_create_bypass.py
      # NOTE: ships in Phase 250.1.G; until then, this job is a stub.

  # Phase 250.0.15 — stale feature-flag detector (INFO only)
  stale-feature-flag-detector:
    name: 250.0.15 — Stale feature flags (informational)
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - name: Detect stale flags
        run: python scripts/detect_stale_feature_flags.py || true  # never blocks
```

## Required-checks branch protection

Add the following to `main` branch protection (in repo settings):

- `error-codes-catalogue-check`
- `cross-service-version-check`
- `asset-create-bypass-check`
- `lint-dq-log-extras` (existing Phase 240.5.F)
- `mypy-strict-asset-creation`
- `bandit-security-scan`
- `semgrep-rules`
- `pip-audit`
- `npm-audit`
- `strong-migrations`
- `openapi-diff`

## Path-filter rationale

Path-filtering is mandatory for Phase 250 jobs to avoid CI runtime regressions. Each job uses `dorny/paths-filter@v3` mirroring Phase 240.5.D's deploy-workflow contract test. The no-op fallback keeps the job registered as a required check on every PR for branch-protection compatibility.

## Monitoring

The CI matrix's effectiveness is monitored via:

- **GitHub Actions usage report** (per-job runtime + PR pass-rate).
- **Internal CI dashboard**: percentage of PRs that fail per gate, time-to-merge median per phase.
- **Quarterly review**: Tech Debt review meeting evaluates which gates produce signal vs noise.
