# Test Script Audit — `scripts/` Directory

**Date:** 2026-05-21
**Scope:** 607 files in `scripts/` (`.py`, `.sh`); 200+ test-related scripts catalogued.
**Methodology:** Each script was checked for CI workflow references, Makefile references, pre-commit hook references, phase-specific naming, and relevance to current codebase.

## Summary

| Category | Count | % |
|---|---|---|
| **Active** (CI-referenced) | 48 | 24% |
| **Legacy** (phase-specific) | 30 | 15% |
| **Duplicate** (overlapping purpose) | 8 | 4% |
| **Dead** (unreferenced, no imports) | 52 | 26% |
| **Utility/Support** (not test-specific) | 62 | 31% |

---

## Categories

### 1. Active — CI-Referenced Scripts (48)

These scripts are directly invoked in `.github/workflows/*.yml`, `Makefile`, or `.pre-commit-config.yaml`.

**Top CI-referenced (used in 3+ workflows):**

| Script | CI Refs | Purpose |
|---|---|---|
| `scripts/_fitness_report.py` | 6 | Architecture fitness baseline report |
| `scripts/e2e_metrics.py` | 5 | E2E hidden-failure metrics extraction |
| `scripts/generate_openapi_yaml.py` | 3 | OpenAPI spec generation |
| `scripts/check_error_codes_catalogue.py` | 3 | Error code registry validation |
| `scripts/audit_pinned_cves.py` | 3 | Pinned CVE version audit |
| `scripts/check_phase232_production_flip_gate.py` | 3 | Phase 232 production flip gate check |
| `scripts/check_fitness_functions.py` | 4 | Architecture fitness function runner |

**Pre-commit hooks (5):**

| Script | Hook Stage |
|---|---|
| `scripts/validate_odps_schemas.py --strict` | pre-commit |
| `scripts/lint_odps.py --strict` | pre-commit |
| `scripts/format_odps.py` | pre-commit |
| `scripts/validate_url_patterns.py --strict` | pre-commit |
| `scripts/check_dq_log_extras.py` | pre-commit |

**Makefile targets (10):**

| Script | Makefile Line |
|---|---|
| `scripts/search_api_client_usage.py` | L124 |
| `scripts/search_webhook_payloads_and_events.py` | L134 |
| `scripts/search_inter_service_communication.py` | L144 |
| `scripts/start-services-for-tests.sh` | L153 |
| `scripts/validate_odps_schemas.py --strict` | L210 |
| `scripts/validate_odcs_schemas.py --strict` | L218 |

**CI-only scripts (25+ in `ci.yml`):**
`scripts/lint_rls_policies.py`, `scripts/detect_stale_feature_flags.py`, `scripts/check_ga_gate_scores.py`, `scripts/check_stale_defaults.py`, `scripts/check_asset_create_bypass.py`, `scripts/lint_no_client_tenant_id.py`, `scripts/lint_cli_sdk_openapi_parity.py`, `scripts/lint_openapi_completeness.py`, `scripts/lint_odps.py`, `scripts/contract_test_openapi.py`, `scripts/check_dq_log_extras.py`, `scripts/validate_odps_schemas.py`, `scripts/validate_odcs_schemas.py`, `scripts/format_odps.py`, `scripts/test_odps_export_ci.py`, `scripts/test_odps_version_ci.py`, `scripts/scan_odps_security.py`, `scripts/workflow_e2e_coverage_report.py`, `scripts/report_uc_journey_test_coverage.py`, `scripts/test_report_uc_journey_test_coverage.py`, `scripts/lint_tenant_context.py`, `scripts/lint-test-sleeps.sh`, `scripts/regenerate_typescript_sdk.sh`, `scripts/regenerate_python_sdk.sh`, `scripts/validate_doc_snippets.py`.

---

### 2. Legacy — Phase-Specific Scripts (30)

These scripts reference specific development phases (now complete) and are unlikely to be useful going forward. They remain in the repo for historical reference but are not invoked by any current CI workflow.

**Phase-specific shell scripts:**

| Script | Phase | Status |
|---|---|---|
| `scripts/run_phase6_infrastructure_tests.sh` | Phase 6 | Legacy |
| `scripts/run_phase7_tests.sh` | Phase 7 | Legacy |
| `scripts/run_phase10_traefik_routing_tests.sh` | Phase 10 | Legacy |
| `scripts/run_phase11_tests.sh` | Phase 11 | Legacy |
| `scripts/run_phase12_tests.sh` | Phase 12 | Legacy |
| `scripts/run_phase13_tests.sh` | Phase 13 | Legacy |
| `scripts/run_phase14_tests.sh` | Phase 14 | Legacy |
| `scripts/run_phase15_tests.sh` | Phase 15 | Legacy |
| `scripts/run_phase16_tests.sh` | Phase 16 | Legacy |
| `scripts/run_phase18_tests.sh` | Phase 18 | Legacy |
| `scripts/run_phase25_tests.sh` | Phase 25 | Legacy |
| `scripts/run_phase25_odbc_tests.sh` | Phase 25 | Legacy |
| `scripts/run_workflow_tests_phase11.sh` | Phase 11 | Legacy |
| `scripts/run_phase66_workflow_security_e2e_tests.sh` | Phase 66 | Legacy |
| `scripts/run_phase67_workflow_error_recovery_e2e_tests.sh` | Phase 67 | Legacy |
| `scripts/run_phase68_workflow_user_journey_e2e_tests.sh` | Phase 68 | Legacy |
| `scripts/run_phase69_workflow_use_case_e2e_tests.sh` | Phase 69 | Legacy |
| `scripts/run_phase75e_asset_tests.sh` | Phase 75 | Legacy |

**Additional legacy scripts:**
- `scripts/run_full_test_suite.py` — replaced by CI matrix
- `scripts/run_comprehensive_test_execution.py` — replaced by `run_comprehensive_test_execution_docker.py`
- `scripts/run_comprehensive_test_suite.py` — superseded by CI batching
- `scripts/review_unit_tests_comprehensive.py` — one-shot review script
- `scripts/report_phase278_test_coverage.py` — phase-specific report
- `scripts/run_security_tests.sh` — generic, unused wrapper
- `scripts/run_tenant_switch_tests.sh` — one-shot
- `scripts/run_tenant_membership_tests.sh` — one-shot
- `scripts/run_resource_picker_tests.sh` — one-shot
- `scripts/run_integration_tests_batched.sh` — superseded
- `scripts/run_validation_29_7.sh` — stale
- `scripts/run_fullcontract_tests_comprehensive.sh` — superseded

---

### 3. Duplicate / Overlapping Scripts (8)

| Scripts | Overlap | Recommendation |
|---|---|---|
| `scripts/run_comprehensive_test_execution.py` + `scripts/run_comprehensive_test_execution_docker.py` | Docker version is newer; both do same thing | Keep docker version, delete py |
| `scripts/run_all_migrated_tests.sh` + `scripts/run_migrated_tests_incremental.sh` + `scripts/run_migrated_tests_sequential.sh` + `scripts/run_migrated_app_tests_cycle.sh` + `scripts/run_migrated_app_tests_final.sh` | 5 scripts for same migrated-test pattern | Consolidate into one parameterized script |
| `scripts/e2e_metrics.py` + `scripts/e2e_metrics_diff.py` | Metrics collection + diff; diff could be a flag | Merge diff into main script with `--diff` flag |
| `scripts/check_skip_usage.py` + `scripts/check_skip_counter.py` | Both audit skip/pytest.skip usage | Consolidate |

---

### 4. Dead — Unreferenced Scripts (52)

These scripts have no CI references, no Makefile entries, no pre-commit hook configuration, and no documentation references. Many are one-shot audits or tooling experiments.

**One-shot audit scripts (likely run once, now dead):**
- `scripts/access_review.py`
- `scripts/add_e2e_batch_markers.py`
- `scripts/add-error-responses-to-openapi.py`
- `scripts/add-security-requirements-to-openapi.py`
- `scripts/adr-freshness-check.sh`
- `scripts/analyze_and_fix_transformation_failures.sh`
- `scripts/analyze_baas_test_results.sh`
- `scripts/analyze_foreign_keys.py`
- `scripts/analyze_reverse_lookups.py`
- `scripts/analyze_workflow_test_matrix.py`
- `scripts/append_260b_ledger_row.py`
- `scripts/audit-api-endpoints.py`
- `scripts/audit_app_overlaps.py`
- `scripts/audit_batch_sizes.sh`
- `scripts/audit_cli_vs_api.py`
- `scripts/audit_dead_code.py`
- `scripts/audit_dependency_compatibility.py`
- `scripts/audit_deployment_log.py`
- `scripts/audit_django6_dependencies.py`
- `scripts/audit_documentation_endpoints.py`
- `scripts/audit_encryption_coverage.py`
- `scripts/audit_env_drift.py`
- `scripts/audit_i18n_coverage.py`
- `scripts/audit_i18n_strings.py`
- `scripts/audit_jsonfield_django6.py`
- `scripts/audit_jsonfield_usage.py`
- `scripts/audit_plan_limit_enforcement.py`
- `scripts/audit_service_integrations.py`
- `scripts/audit_tenant_deletion_coverage.py`
- `scripts/audit_tenant_isolation.py`
- `scripts/audit-test-endpoints.py`
- `scripts/categorize-api-inventory.py`
- `scripts/comprehensive_dependency_audit.py`
- `scripts/diagnose_odh_availability.py`
- `scripts/generate_audit_reports.py`
- `scripts/generate-test-impact-report.py`
- `scripts/generate_translations.py`
- `scripts/monitor_deployment_errors.py`
- `scripts/optimize_jsonfield_queries.py`
- `scripts/regenerate-openapi-spec.py`
- `scripts/review_api_inventory.py`
- `scripts/review_gateway_configs.py`
- `scripts/review_rate_limiting_configs.py`

---

### 5. Utility / Support Scripts (62)

These are operational scripts not specific to testing: migrations, documentation, deployment helpers, code generation.

**Key active utilities:**
- `scripts/lint_helm_charts.py` — Helm chart linting
- `scripts/lint_k8s_manifests.py` — Kubernetes manifest validation
- `scripts/lint_env_file.py` — .env file validation
- `scripts/lint_migrations.py` — Migration file linting
- `scripts/lint_debug_output.py` — Debug output detection
- `scripts/lint_test_dir_markdown.py` — Test dir markdown linting
- `scripts/check_doc_freshness.py` — Documentation staleness
- `scripts/check_doc_links.py` — Broken link checking
- `scripts/check_migration_files.py` — Migration integrity
- `scripts/check_migration_count.py` — Migration count validation
- `scripts/check_query_performance.py` — Query performance audit
- `scripts/check_slo_burn.py` — SLO burn rate monitoring
- `scripts/check_production_cors.py` — Production CORS validation
- `scripts/check_mvp_doc_boundary.py` — MVP documentation boundary
- `scripts/check_mvp_marker_coverage.py` — MVP marker coverage
- `scripts/check_postman_collections.py` — Postman collection validation
- `scripts/documentation_qa.py` — Documentation quality checks
- `scripts/review_cicd_workflows.py` — CI/CD workflow review
- `scripts/lint_e2e_backend_verification.py` — E2E backend verification lint
- `scripts/lint_journey_marker_coverage.py` — Journey marker coverage
- `scripts/lint_factory_coverage.py` — Factory coverage lint
- `scripts/lint_business_rules_catalog.py` — Business rules catalog lint
- `scripts/check_test_fixtures_and_factories.py` — Fixture/factory check

---

## Recommendations

1. **Delete 30 phase-specific legacy scripts** — they reference completed development phases and are never invoked. Archive to a `scripts/_legacy/` directory if preservation is desired.
2. **Delete 52 dead audit/one-shot scripts** — one-shot audits that were run once and never again.
3. **Consolidate 8 duplicate scripts** — merge overlapping test runners and metrics scripts.
4. **Document the 48 active scripts** in `docs/test-infrastructure/ci-scripts-audit.md` (312.2.9).
5. **Add CI check** that warns when a script in `scripts/` has no CI/Makefile/pre-commit reference and no docstring explaining its purpose.
