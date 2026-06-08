# CI Quality Scripts Audit

**Date:** 2026-05-21
**Scope:** 52 CI quality scripts (`scripts/check_*.py`, `scripts/lint_*.py`, `scripts/detect_*.py`, `scripts/verify_*.py`, `scripts/validate_*.py`).
**Methodology:** Each script was categorized by CI phase and functional category. References were cross-checked against `.github/workflows/*.yml`, `Makefile`, and `.pre-commit-config.yaml`.

---

## Summary

| CI Phase | Count | Scripts |
|---|---|---|
| Pre-commit | 5 | validate_odps_schemas, lint_odps, format_odps, validate_url_patterns, check_dq_log_extras |
| PR-check | 24 | lint_rls_policies, detect_stale_feature_flags, check_ga_gate_scores, check_stale_defaults, etc. |
| Merge-gate | 8 | check_migration_files, check_production_cors, check_error_codes_catalogue, etc. |
| Deploy-gate | 3 | check_phase232_production_flip_gate, check_fitness_functions, check_slo_burn |
| Weekly | 3 | check_doc_freshness, check_query_performance, lint_factory_coverage |
| Unreferenced (dead) | 9 | Several audit/check scripts with no CI, Makefile, or pre-commit references |

---

## 1. Complete Script Catalog

### 1.1 Pre-Commit Scripts (5)

Run before every commit via `.pre-commit-config.yaml`.

| Script | Category | Pre-Commit Hook |
|---|---|---|
| `scripts/validate_odps_schemas.py` | Architecture | `validate_odps_schemas.py --strict` |
| `scripts/lint_odps.py` | Architecture | `lint_odps.py --strict` |
| `scripts/format_odps.py` | Code quality | `format_odps.py` |
| `scripts/validate_url_patterns.py` | Code quality | `validate_url_patterns.py --strict` |
| `scripts/check_dq_log_extras.py` | Code quality | `check_dq_log_extras.py` |

### 1.2 PR-Check Scripts (24)

Run on every PR via `.github/workflows/ci.yml` and other PR-triggered workflows.

#### Migration Safety

| Script | CI Reference | Description |
|---|---|---|
| `scripts/lint_migrations.py` | ci.yml | Migration file integrity |
| `scripts/check_migration_count.py` | ci.yml | Migration count drift detection |
| `scripts/check_migration_files.py` | ci.yml | Missing/broken migration files |

#### RLS Enforcement

| Script | CI Reference | Description |
|---|---|---|
| `scripts/lint_rls_policies.py` | ci.yml (x2) | RLS policy completeness |
| `scripts/lint_no_client_tenant_id.py` | ci.yml | Client-provided tenant_id detection |

#### Tenant Isolation

| Script | CI Reference | Description |
|---|---|---|
| `scripts/lint_tenant_context.py` | ci.yml | Missing tenant_context() calls |
| `scripts/audit_tenant_isolation.py` | (dead) | One-shot tenant isolation audit |
| `scripts/audit_tenant_deletion_coverage.py` | (dead) | Tenant deletion coverage |

#### Feature Flags

| Script | CI Reference | Description |
|---|---|---|
| `scripts/detect_stale_feature_flags.py` | ci.yml (x2) | Stale flag detection (>180d) |
| `scripts/check_ga_gate_scores.py` | ci.yml | GA gate score threshold |
| `scripts/check_stale_defaults.py` | ci.yml | Stale default_new=False flags |

#### Business Rules

| Script | CI Reference | Description |
|---|---|---|
| `scripts/lint_business_rules_catalog.py` | (Makefile) | Business rules catalog integrity |
| `scripts/lint_e2e_backend_verification.py` | (Makefile) | E2E backend verification lint |

#### API Quality

| Script | CI Reference | Description |
|---|---|---|
| `scripts/lint_openapi_completeness.py` | ci.yml (x2) | OpenAPI completeness check |
| `scripts/lint_cli_sdk_openapi_parity.py` | ci.yml (x2) | CLI/SDK OpenAPI parity |
| `scripts/generate_openapi_yaml.py` | ci.yml (x3) | OpenAPI YAML generation |
| `scripts/contract_test_openapi.py` | ci.yml | Contract test against OpenAPI spec |
| `scripts/validate_api_naming_standards.py` | api-naming-validation.yml (x4) | API naming convention enforcement |

#### Code Quality

| Script | CI Reference | Description |
|---|---|---|
| `scripts/lint_debug_output.py` | (Makefile) | Debug output in production code |
| `scripts/check_django_deprecations.py` | (Makefile) | Django deprecation detection |
| `scripts/check_skip_usage.py` | (unreferenced) | pytest.skip usage audit |
| `scripts/check_skip_counter.py` | (unreferenced) | Skip counter |
| `scripts/lint_no_direct_http_in_normalizers.py` | (unreferenced) | HTTP in normalizers |

### 1.3 Merge-Gate Scripts (8)

Must pass before merge to main/staging.

| Script | Category | Description |
|---|---|---|
| `scripts/check_error_codes_catalogue.py` | API quality | Error code registry validation (ci.yml x3) |
| `scripts/check_production_cors.py` | Security | Production CORS configuration |
| `scripts/check_asset_create_bypass.py` | Security | Asset creation bypass detection (ci.yml x2) |
| `scripts/check_arch_fitness.py` | Architecture | Architecture fitness check |
| `scripts/check_fitness_functions.py` | Architecture | Fitness function runner (x4 in CI) |
| `scripts/check_doc_links.py` | Documentation | Broken documentation links |
| `scripts/check_mvp_doc_boundary.py` | Documentation | MVP documentation boundary (x2) |
| `scripts/check_mvp_marker_coverage.py` | Testing | MVP marker coverage |

### 1.4 Deploy-Gate Scripts (3)

Run before deploy to staging/production.

| Script | Category | Description |
|---|---|---|
| `scripts/check_phase232_production_flip_gate.py` | Operations | Production flip gate (x3) |
| `scripts/check_slo_burn.py` | Operations | SLO burn rate check |
| `scripts/lint_env_file.py` | Operations | .env file validation |

### 1.5 Weekly Scheduled Scripts (3)

Run on schedule (weekly cron).

| Script | Category | Description |
|---|---|---|
| `scripts/check_doc_freshness.py` | Documentation | Documentation staleness (x2) |
| `scripts/check_query_performance.py` | Testing | Query performance regression |
| `scripts/lint_factory_coverage.py` | Testing | Factory model coverage |

### 1.6 i18n Scripts (2)

| Script | Category | Description |
|---|---|---|
| `scripts/check_i18n_key_completeness.py` | i18n | Translation key completeness |
| `scripts/audit_i18n_coverage.py` | i18n | i18n coverage audit (dead) |

### 1.7 Dead/Unreferenced Scripts (9)

Scripts with no CI workflow, Makefile, or pre-commit reference:

| Script | Last Known Purpose |
|---|---|
| `scripts/audit_tenant_isolation.py` | One-shot tenant isolation audit |
| `scripts/audit_tenant_deletion_coverage.py` | Tenant deletion coverage |
| `scripts/audit_jsonfield_django6.py` | Django 6 JSONField migration audit |
| `scripts/audit_jsonfield_usage.py` | JSONField usage patterns |
| `scripts/audit_django6_dependencies.py` | Django 6 dependency audit |
| `scripts/audit_dependency_compatibility.py` | Dependency compatibility |
| `scripts/audit_encryption_coverage.py` | Encryption coverage |
| `scripts/audit_dead_code.py` | Dead code detection |
| `scripts/check_dead_code.py` | Dead code check |

---

## 2. Categorization by Functional Area

| Category | Count | Scripts |
|---|---|---|
| Migration safety | 3 | `lint_migrations`, `check_migration_count`, `check_migration_files` |
| RLS enforcement | 2 | `lint_rls_policies`, `lint_no_client_tenant_id` |
| Tenant isolation | 3 | `lint_tenant_context`, `audit_tenant_isolation`, `audit_tenant_deletion_coverage` |
| Feature flags | 3 | `detect_stale_feature_flags`, `check_ga_gate_scores`, `check_stale_defaults` |
| Business rules | 2 | `lint_business_rules_catalog`, `lint_e2e_backend_verification` |
| API quality | 5 | `lint_openapi_completeness`, `lint_cli_sdk_openapi_parity`, `generate_openapi_yaml`, `contract_test_openapi`, `validate_api_naming_standards` |
| Code quality | 5 | `lint_debug_output`, `check_django_deprecations`, `check_skip_usage`, `check_skip_counter`, `lint_no_direct_http_in_normalizers` |
| i18n | 2 | `check_i18n_key_completeness`, `audit_i18n_coverage` |
| Documentation | 4 | `check_doc_links`, `check_doc_freshness`, `check_mvp_doc_boundary`, `check_mvp_marker_coverage` |
| Architecture | 3 | `validate_odps_schemas`, `lint_odps`, `check_fitness_functions` |
| Testing | 3 | `lint_factory_coverage`, `check_query_performance`, `check_test_fixtures_and_factories` |
| Operations | 3 | `check_phase232_production_flip_gate`, `check_slo_burn`, `lint_env_file` |
| Security | 2 | `check_production_cors`, `check_asset_create_bypass` |
| Other (dead audits) | 9 | Various one-shot audit scripts |
| **Total** | **52** | |

---

## 3. CI Phase vs Category Matrix

| Category | Pre-commit | PR-check | Merge-gate | Deploy-gate | Weekly | Dead |
|---|---|---|---|---|---|---|
| Migration safety | — | 3 | — | — | — | — |
| RLS enforcement | — | 2 | — | — | — | — |
| Tenant isolation | — | 1 | — | — | — | 2 |
| Feature flags | — | 3 | — | — | — | — |
| Business rules | — | 2 | — | — | — | — |
| API quality | — | 4 | 1 | — | — | — |
| Code quality | 1 | 2 | — | — | — | 2 |
| i18n | — | — | — | — | — | 1 (dead) |
| Documentation | — | — | 2 | — | 1 | — |
| Architecture | 4 | 1 | 2 | — | — | — |
| Testing | — | 1 | 1 | — | 2 | — |
| Operations | — | — | — | 3 | — | — |
| Security | — | 1 | 1 | — | — | — |
| Other | — | — | — | — | — | 9 |

---

## 4. Script Quality Observations

### 4.1 Naming Inconsistency

- `audit_tenant_isolation.py` vs `lint_tenant_context.py` — both check tenant isolation, different verb prefixes
- `check_dead_code.py` vs `audit_dead_code.py` — two scripts with similar names, both dead
- `check_skip_usage.py` vs `check_skip_counter.py` — overlapping purpose, neither referenced

### 4.2 Redundant Pairs

| Script A | Script B | Issue |
|---|---|---|
| `audit_tenant_isolation.py` | `lint_tenant_context.py` | Same domain, different scripts |
| `audit_dead_code.py` | `check_dead_code.py` | Both dead AND overlapping |
| `check_skip_usage.py` | `check_skip_counter.py` | Both audit pytest.skip |

### 4.3 Format Consistency

- All scripts are `.py` (Python) — consistent ✅
- Mixed verb prefixes: `check_`, `lint_`, `detect_`, `audit_`, `validate_`, `verify_`, `generate_`, `format_`, `contract_test_`
- Most scripts use argparse for CLI — consistent ✅

---

## Recommendations

1. **Delete 9 dead scripts** — one-shot audits with no CI references. Archive to `scripts/_legacy/` if preservation desired.
2. **Consolidate redundant pairs** — merge `audit_tenant_isolation.py` into `lint_tenant_context.py`; merge `check_skip_usage.py` + `check_skip_counter.py`.
3. **Standardize verb prefixes** — adopt a convention: `lint_` for style/pattern checks, `check_` for pass/fail gates, `validate_` for schema validation, `audit_` for one-shot reports.
4. **Move pre-commit scripts to dedicated directory** — `scripts/pre_commit/` would make it obvious which scripts block commits.
5. **Add `--help` to all unreferenced scripts** — if kept, ensure they document their purpose in argparse.
6. **Run CI check for script staleness** — a meta-script that verifies every `scripts/check_*.py` / `scripts/lint_*.py` is referenced in at least one CI workflow.
