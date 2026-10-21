# Existing Test Infrastructure Inventory

**Date:** 2026-05-21
**Scope:** Complete inventory of all test infrastructure components across backend, frontend, E2E, security, performance, and CI/CD.
**Methodology:** Directory scanning, grep for test patterns, CI workflow cross-referencing.

---

## 1. Backend Test Infrastructure

### 1.1 Unit & Integration Tests

| Component | Location | Approx. Count | Framework |
|---|---|---|---|
| Django unit/integration tests | `hub/apps/*/tests/` (14 apps) | ~5,000+ | pytest + pytest-django |
| Root-level tests | `tests/` | ~500+ | pytest |
| CLI tests | `cli/tests/` | ~200+ | pytest |
| SDK tests | `sdk/python/tests/` | ~100+ | pytest |

### 1.2 Production Guard Tests (~37)

Tests that verify production safety guards. Located in:
- `hub/test_runner.py` — Production DB guard (`SKIP_PROD_DB_GUARD`)
- `hub/tests/test_test_infrastructure.py` — Test infrastructure self-tests
- `tests/ci/` — CI-specific validation tests
- `tests/security/test_production_secrets.py` — Production secrets validation

### 1.3 AWS Secrets Manager Loader Tests

- `hub/aws_secrets_loader.py` — Production code with test coverage in `hub/tests/`
- Tests verify secret loading from AWS SM with proper error handling
- Gated behind `AWS_SECRETS_ENABLED` env var

### 1.4 PgBouncer Safety Tests

- Located in `tests/` — connection pooling safety verification
- Tests ensure PgBouncer transaction pooling doesn't break Django's connection state assumptions

### 1.5 Normalization Tests

- `tests/integration/test_normalization_rdf_flow.py` — RDF normalization flow
- `hub/apps/contracts/tests/` — Contract normalization (ODCS/ODPS formats)
- `scripts/lint_no_direct_http_in_normalizers.py` — Lint rule enforcing no HTTP calls in normalizers

### 1.6 N+1 Query Elimination Tests

- Widespread use of `assertNumQueries` / `assert_num_queries` across `hub/apps/*/tests/`
- `tests/performance/` — N+1 detection and regression tests
- `scripts/check_query_performance.py` — Weekly query performance regression check

### 1.7 Auth Security Tests

- `hub/apps/auth/tests/` — Authentication/authorization tests
- JWT tests (algorithm, expiry, rotation)
- API key tests
- Session security tests
- Rate limit isolation verification

### 1.8 SSRF Tests (3+ files)

| File | Description |
|---|---|
| `hub/tests/test_ref_resolver_ssrf.py` | Reference resolver SSRF prevention |
| `hub/tests/test_ssrf_delivery_integration.py` | SSRF delivery integration |
| `hub/tests/test_ssrf_single_source.py` | Single-source SSRF testing |
| `hub/tests/test_ssrf_guard.py` | SSRF guard validation |
| `tests/security/penetration_test_odps_ref_resolver.py` | ODPS ref resolver penetration test |
| `hub/tests/test_phase30_semantic_security.py` | Semantic security (includes SSRF) |

### 1.9 Data Migration Tests (8+ apps)

Tests for data migrations in:
- `hub/apps/assets/tests/`
- `hub/apps/contracts/tests/`
- `hub/apps/datasets/tests/`
- `hub/apps/files/tests/`
- `hub/apps/compliance/tests/`
- `hub/apps/governance/tests/`
- `hub/apps/marketplace/tests/`
- `hub/apps/scheduled_ingestion/tests/`
- `hub/apps/versioning/tests/`
- `hub/apps/audit/tests/`
- `hub/apps/mesh/tests/`

Migration safety is enforced by `scripts/lint_migrations.py`, `scripts/check_migration_files.py`, and `scripts/check_migration_count.py`.

### 1.10 Feature Flag Tests

- `scripts/detect_stale_feature_flags.py` — CI gate for stale flags
- `scripts/check_ga_gate_scores.py` — GA gate score enforcement
- `scripts/check_stale_defaults.py` — Stale default detection
- Unit tests in `hub/tests/` verifying flag behavior

### 1.11 Management Command Tests

- Tests for Django management commands in `hub/apps/*/tests/`
- `tests/` contains management command integration tests
- Commands tested: `check_throttle_coverage`, tenant operations, data migrations, seed commands

---

## 2. E2E Test Infrastructure

### 2.1 E2E Test Suites

| Suite | Location | Trigger | Framework |
|---|---|---|---|
| Backend E2E | `tests/e2e/` | PR + nightly | pytest + docker-compose |
| E2E fixtures | `tests/e2e/conftest.py` | (shared) | pytest |
| Journey tests | `tests/e2e/` (journey-marked) | PR + nightly | pytest |
| E2E guards | `tests/e2e/_guards/` | (shared) | pytest |

### 2.2 Playwright E2E (Frontend)

| Config | File |
|---|---|
| Main Playwright config | `frontend/playwright.config.ts` |
| MVP Playwright config | `frontend/playwright.mvp.config.ts` |
| Accessibility config | `frontend/playwright.a11y.config.ts` |
| CI: `playwright-e2e.yml` | PR + scheduled |
| CI: `playwright-e2e-strict.yml` | PR (strict mode) + scheduled |

### 2.3 E2E Smoke Tests

- `tests/smoke/` — Deployment smoke tests
- `tests/smoke/conftest.py` — Smoke test fixtures
- `tests/smoke/test_deployment_smoke.py` — Post-deploy verification
- `e2e-pr-smoke.yml` — Critical path verification on every PR

### 2.4 E2E Metrics

- `scripts/e2e_metrics.py` — E2E hidden-failure metrics extraction
- `scripts/e2e_metrics_diff.py` — Metrics diff analysis
- `e2e-metrics.yml` — Metrics baseline on every PR
- Produces `e2e-metrics.json` artifact

---

## 3. Frontend Test Infrastructure

### 3.1 Unit & Component Tests

| Component | Location | Framework |
|---|---|---|
| Frontend unit tests | `frontend/src/**/*.test.{ts,tsx}` | Jest/Vitest |
| Frontend CI | `frontend-tests.yml` | PR-gated (path-filtered) |
| Bundle size check | `bundle-size-check.yml` | PR-gated |

### 3.2 Visual Regression

| Tool | Workflow | Trigger |
|---|---|---|
| Chromatic (Storybook) | `chromatic.yml` | Push to main |
| Playwright visual regression | `visual-regression-playwright.yml` | Scheduled + manual |

### 3.3 Accessibility (a11y) Suite (4 specs)

| Component | File |
|---|---|
| Playwright a11y config | `frontend/playwright.a11y.config.ts` |
| a11y specs | `frontend/src/**/*.a11y.spec.ts` (estimated 4 files) |
| Axe-core integration | `@axe-core/playwright` |

### 3.4 i18n Infrastructure

- `scripts/check_i18n_key_completeness.py` — Translation key completeness
- `scripts/audit_i18n_coverage.py` — i18n coverage audit
- `scripts/generate_translations.py` — Translation generation
- `i18n-check.yml` — CI i18n validation
- `i18n-hardcoded-check.yml` — Hardcoded string detection

### 3.5 Dark Mode Pre-Hydration

- `frontend/src/` — Dark mode implementation with pre-hydration state
- Tests ensure no flash of wrong theme on page load

### 3.6 Error Boundaries

- `frontend/src/` — React error boundary components
- Tests verify graceful degradation on render failures

### 3.7 Toast System

- `frontend/src/` — Toast notification system
- Tests verify toast display, dismissal, and queuing behavior

---

## 4. Security Test Infrastructure

### 4.1 Security Scanning

| Scan | Workflow | Trigger |
|---|---|---|
| Dependency review | `dependency-review.yml` | PR-gated |
| License scan | `license-scan.yml` | PR-gated |
| Security scan (SAST) | `security-scan.yml` | Scheduled |
| CSP violation endpoint | `hub/` — CSP report endpoint | Runtime |
| Production CORS check | `scripts/check_production_cors.py` | Merge-gate |

### 4.2 Penetration Testing

- `tests/security/penetration_test_odps_ref_resolver.py` — ODPS reference resolver security
- `hub/tests/test_phase30_semantic_security.py` — Semantic endpoint security
- `hub/tests/test_security_docs_phase_250_5_e.py` — Security documentation verification

---

## 5. Performance Test Infrastructure

### 5.1 Performance Benchmarks

| Benchmark | Workflow | Trigger |
|---|---|---|
| Contracts perf benchmark | `contracts-perf-benchmark.yml` | PR (path-filtered) |
| Perf nightly | `perf-nightly.yml` | Scheduled + release |
| K6 load test gate | `k6-load-test-gate.yml` | Deploy-gate |
| Lineage history growth | `tests/load/lineage_history_growth.py` | Scheduled (soak) |
| Notification storm | `tests/load/notification_storm.py` | Manual |

### 5.2 Performance Test Files

- `tests/performance/test_performance.py`
- `tests/performance/test_performance_django6.py`
- `tests/performance/setup_test_users.py` — Performance test data setup

---

## 6. Specialized Test Infrastructure

### 6.1 GraphQL Tests (10+ files)

| Area | Files |
|---|---|
| GraphQL ODPS queries | `hub/apps/graphql_graphene/tests/test_odps_queries_unit.py` |
| GraphQL ODPS integration | `hub/apps/graphql_graphene/tests/test_odps_queries_integration.py` |
| GraphQL comprehensive | `hub/apps/graphql_graphene/tests/test_odps_graphql_integration_comprehensive.py` |
| E2E GraphQL API | `tests/e2e/test_graphql_api.py` |
| E2E GraphQL ODPS fields | `tests/e2e/test_graphql_odps_fields.py` |
| E2E GraphQL ODPS mutations | `tests/e2e/test_graphql_odps_mutations.py` |

### 6.2 Microservice Tests (7 services)

| Service | Test Directory | File Count |
|---|---|---|
| `compliance-service` | `services/compliance-service/tests/` | ~10+ |
| `datacontract-service` | `services/datacontract-service/tests/` | ~8+ |
| `dq-service` | `services/dq-service/tests/` | ~5+ |
| `odh-integration` | `services/odh-integration/tests/` | ~5+ |
| `prefect-integration` | `services/prefect-integration/tests/` | ~10+ |
| `semantic-service` | `services/semantic-service/tests/` | ~8+ |
| `worker` | `services/worker/tests/` | ~15+ |

### 6.3 Helm Chart Tests

- `scripts/lint_helm_charts.py` — Helm chart linting
- `helm/` directory contains test values files
- `helm-rollback.yml` — Helm rollback testing

### 6.4 Contract/Pact Tests

- `tests/pact/conftest.py` — Pact contract test fixtures
- Consumer-driven contract tests for inter-service communication

---

## 7. Test Execution Infrastructure

### 7.1 Test Runners

| Runner | File | Purpose |
|---|---|---|
| Custom Django test runner | `hub/test_runner.py` | Migration skip, prod DB guard |
| pytest configuration | `pytest.ini` | Markers, timeouts, asyncio mode |
| Batch runner | `scripts/run_phase_12a_backend_suites.sh` | CI batch test execution |
| Docker compose runner | `tests/integration/test_docker_compose.py` | Docker Compose runtime tests |

### 7.2 Flaky Test Quarantine

- `pytest.ini` `--strict-markers` prevents unregistered markers
- `@pytest.mark.xfail` used for known-flaky tests (1 occurrence)
- `@pytest.mark.flaky` not found — no formal flaky quarantine mechanism
- No `flaky` marker registered in `pytest.ini`

### 7.3 Test Isolation

| Mechanism | Location |
|---|---|
| `tests/isolation/conftest.py` | Isolation test fixtures |
| `tests/concurrency/conftest.py` | Concurrency test isolation |
| `@pytest.mark.isolation` (6 uses) | Isolation marker |
| `TEST_DB_SUFFIX` | Shared DB isolation |
| Rate limit isolation | Tenant-scoped throttle cache keys |

### 7.4 Resilience/Chaos Tests

- `tests/resilience/conftest.py` — Resilience test fixtures
- `tests/chaos/` — Chaos engineering tests
- `tests/disaster_recovery/` — DR test scenarios
- `tests/dr/` — Disaster recovery tests

---

## 8. CI/CD Test Gates

### 8.1 Quality Gates (CI Scripts)

| Category | Count | Enforcement |
|---|---|---|
| Migration safety | 3 | PR-check |
| RLS enforcement | 2 | PR-check |
| Feature flags | 3 | PR-check |
| API quality | 5 | PR-check + merge-gate |
| Code quality | 5 | Pre-commit + PR-check |
| i18n | 2 | PR-check |
| Documentation | 4 | Merge-gate + weekly |
| Architecture | 3 | Pre-commit + merge-gate |
| Security | 2 | Merge-gate |

### 8.2 Test Results Reporting

- `test-results-reporting.yml` — Meta-aggregator for test results
- `scripts/generate-test-summary-report.sh` — Summary report generation
- `scripts/_fitness_report.py` — Architecture fitness report (6 CI references)
- `scripts/workflow_e2e_coverage_report.py` — E2E coverage reporting

---

## 9. Test Data & Fixtures

### 9.1 Test Data Files

| Directory | Contents |
|---|---|
| `tests/fixtures/odps/` | ODPS schema fixtures (v1.x, v2.x, v3.x, v4.0) |
| `tests/fixtures/contracts/` | Contract fixture files |
| `tests/fixtures/marketplace/ckan/` | CKAN marketplace fixtures |
| `tests/fixtures/odps/security/malicious/` | Security test fixtures (malicious payloads) |

### 9.2 Factory Coverage

- Central `tests/factories.py`: 54 factory classes, 645 lines
- App-level factories: 8 files, ~1,247 lines total
- `scripts/lint_factory_coverage.py`: CI check for model coverage

---

## 10. Mutation Testing

| Workflow | Target |
|---|---|
| `mutmut-asset-saga.yml` | Asset creation saga mutation testing |
| `mutmut-lineage-validator.yml` | Lineage validator mutation testing |
| `mutmut-magic-bytes.yml` | File magic-byte validation mutation testing |

All scheduled nightly + manual dispatch. No PR gating.

---

## Summary Statistics

| Component | Count |
|---|---|
| Backend test files | ~800+ Python test files |
| Frontend test files | ~200+ TS/TSX test files |
| E2E test files | ~50+ |
| Microservice test files | ~60+ |
| CI workflows (test-related) | 25 |
| CI quality scripts | 52 |
| conftest files (project) | 47 |
| Factory files | 9 |
| Pytest markers registered | 58 |
| Test-referenced env vars | 14+ |
| Docker Compose test services | 63 |

---

## Recommendations

1. **Add formal flaky quarantine** — register `flaky` marker in `pytest.ini`, track flaky tests in `docs/test-infrastructure/flaky-tests.md`.
2. **Document test data fixtures** — the `tests/fixtures/` directory needs a README explaining each fixture's purpose.
3. **Add test infrastructure health dashboard** — a `GET /api/v1/health/test-infrastructure` endpoint reporting conftest health, CI script status, and marker coverage.
4. **Create `docs/test-infrastructure/` index** — this audit serves as the comprehensive inventory; the README (312.2.11) will index all 11 audit documents.
