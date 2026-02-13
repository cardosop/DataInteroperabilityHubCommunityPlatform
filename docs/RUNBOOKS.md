# Operational Runbooks

Complete troubleshooting and operational procedures for the Data Interoperability Hub.

## Table of Contents

1. [Full test suite (Phase 12A-style)](#full-test-suite-phase-12a-style)
2. [Batch execution (Phase 12A path-based batches)](#batch-execution-phase-12a-path-based-batches)
3. [Gap remediation validation](#gap-remediation-validation)
4. [Security suite (Phase 12A.3)](#security-suite-phase-12a3)
5. [Dependency and vulnerability scans](#dependency-and-vulnerability-scans)
6. [Deployment and rollback](#deployment-and-rollback)
7. [Normalization Failures](#normalization-failures)
8. [Lineage Issues](#lineage-issues)
9. [Scheduled Ingestion Failures](#scheduled-ingestion-failures)
10. [Prefect Server Issues](#prefect-server-issues)
11. [Prefect Workers Issues](#prefect-workers-issues)
12. [Search Service Issues](#search-service-issues)
13. [Observability Service Issues](#observability-service-issues)
14. [Webhook Service Issues](#webhook-service-issues)
15. [Marketplace Connector Pattern Violations](#marketplace-connector-pattern-violations)
16. [BaaS Platform Troubleshooting](#baas-platform-troubleshooting)
17. [ODH Integration Troubleshooting](#odh-integration-troubleshooting)
18. [Disaster Recovery](#disaster-recovery)
19. [Backup and Recovery](#backup-and-recovery)

---

## Full test suite (Phase 12A-style)

**When to run**: Pre-release, after major changes, or when validating the full test suite per [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) and [openspec/changes/gapfix1](../openspec/changes/gapfix1).

### Commands

**Prerequisites**: (1) Scripts must be executable. If `./scripts/run_phase_12a_...` fails with "Permission denied", run: `chmod +x scripts/run_phase_12a_backend_suites.sh scripts/run_phase_12a_full_suites.sh scripts/generate_test_summary_report.sh scripts/generate_sign_off_snippet.sh`. (2) The test stack must be up so backend and smoke tests can run: `docker compose -f docker-compose.test.yml up -d` (wait until `api-service-test` is healthy). Same as [Batch execution](#batch-execution-phase-12a-path-based-batches) start step.

1. **Backend only** (unit, integration, E2E):
   ```bash
   ./scripts/run_phase_12a_backend_suites.sh
   ```
2. **Full suite** (backend + frontend unit/E2E + security + performance + concurrency + regression):
   ```bash
   ./scripts/run_phase_12a_full_suites.sh
   ```
3. **Where artifacts are stored**: `test_reports_comprehensive/YYYY-MM-DD/` with subdirs `unit/`, `integration/`, `e2e/`, `smoke/`, `security/`, `performance/`, `concurrency/`, `regression/`, `frontend-unit/`, `frontend-e2e/`. Summary artifacts: `phase_12a_1_summary.json` (backend), `phase_12a_3_summary.json` (security/performance/concurrency/regression). Canonical layout is defined in [EVIDENCE_COLLECTION_PLAN.md — Directory structure](EVIDENCE_COLLECTION_PLAN.md#directory-structure).

4. **Layout only (no test run)**: To create the directory structure without running tests, use `./scripts/collect_test_evidence.sh` (date format `YYYYmmdd_HHMMSS`). Phase 12A scripts create the layout automatically when they run.

5. **Git**: `test_reports_comprehensive/` is in `.gitignore`; report contents are not committed.

6. **Canonical definition**: Run order, commands per step, and CI vs nightly/manual are defined in [FULL_TEST_SUITE_DEFINITION.md](FULL_TEST_SUITE_DEFINITION.md). Batched execution and full-suite commands are aligned with [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md). Performance, regression, and concurrency are optional for the PR gate and run in **nightly** or **release** (see phase-12a-nightly.yml, phase-12a-release.yml); regression can also be the last batch in batched runs.

### Use case and journey test coverage report (Phase 5.5)

To report which use cases ([USE_CASES.md](USE_CASES.md)) and user journeys ([USER_JOURNEYS.md](USER_JOURNEYS.md)) have at least one test:

```bash
python scripts/report_uc_journey_test_coverage.py
```

Options: `--json` (output JSON), `--fail-if-zero` (exit 1 if any UC or journey has no tests), `--audit-traceability` (check [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) file paths exist and report broken links). Use in nightly or release to produce the report (e.g. artifact) or to fail the run when coverage is required (`--fail-if-zero`).

### Generate test summary report

After the run, generate the report from evidence:

```bash
./scripts/generate_test_summary_report.sh YYYY-MM-DD
```

Or omit the date to use the latest date directory under `test_reports_comprehensive/`.

### How to read the report

The report includes test execution summary (date, suite, total/passed/failed/skipped, duration), results by category, and evidence links to the artifact subdirs. See [EVIDENCE_COLLECTION_PLAN.md](EVIDENCE_COLLECTION_PLAN.md) and [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md#gap-implementation-plan-gapfix1--full-test-run-and-sign-off).

---

## Batch execution (Phase 12A path-based batches)

**When to run**: Incremental full-suite validation per [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md) — run batches in order, fix failures at root cause, then proceed. Target ≤200 tests per batch.

### Start the test stack

From repo root, using the test compose file:

```bash
docker compose -f docker-compose.test.yml up -d
```

Wait until core services (including `api-service-test`) are running and healthy. The batched script brings up the stack automatically if you run it without `--no-up`.

### Run batches

| Goal | Command |
|------|--------|
| **Run all batches** | `./scripts/run_phase_12a_batched.sh` |
| **Run one batch** | `./scripts/run_phase_12a_batched.sh --batch=N` (e.g. `--batch=5`) |
| **Run from batch N to end** | `./scripts/run_phase_12a_batched.sh --start-from=N` |
| **List batch definitions** | `./scripts/run_phase_12a_batched.sh --list-batches` |

All runs use `docker-compose.test.yml` and `api-service-test`; evidence is written under `test_reports_comprehensive/{DATE}/batches/`.

### Where logs and JUnit are

- **Base path**: `test_reports_comprehensive/YYYY-MM-DD/batches/`
- **Per batch**: `batch_N/batch_N.log`, `batch_N/junit.xml`, `batch_N/summary.json` (and `coverage.xml` when coverage is enabled for that batch).
- **Date**: Default is today (`YYYY-MM-DD`); override with `DATE=2026-02-12 ./scripts/run_phase_12a_batched.sh` if needed.

### Audit batch sizes (≤200 per batch)

To see current test count per batch and which exceed 200:

```bash
./scripts/audit_batch_sizes.sh
```

If you get "Permission denied", run `chmod +x scripts/audit_batch_sizes.sh` from the repo root. Use `--no-up` to skip bringing up the stack (stack must already be up). Output is a Markdown table; batches over 200 are marked **SPLIT**. To generate a batch list with every batch ≤200, run (with stack up; may take 30+ minutes):

```bash
python3 scripts/split_batches_to_cap.py --max 200 --output scripts/batch_definitions.txt
```

Then run the batched script as above; it will load `scripts/batch_definitions.txt` when present. When using a generated batch file, special handling (no-coverage for ODPS/ODCS/Files, Prefect wait for Scheduled, DQ/MinIO wait for Data Quality, STRIPE note for Billing) is applied by batch **name**, so split batches still get the correct behavior.

### Batch status and fix cycle (Phase 3)

After each batch (and at the end of a run), the script writes:

- **`batches/batch_status.json`** — Machine-readable: date, generated_at, and per batch: batch_num, name, status (pass/fail/deferred/not_run), last_run, log path, junit path, optional deferred_reason.
- **`batches/README.md`** — Table: Batch | Name | Status | Last run | Log | JUnit.

**Fix cycle (no mocks/stubs):** When a batch fails, the script stops. Fix the root cause (application, test, or environment), then re-run from that batch:

```bash
./scripts/run_phase_12a_batched.sh --start-from N
```

**Defer and continue:** If you must defer a failure (e.g. external dependency, ticket created), mark the batch deferred and continue to the next:

```bash
./scripts/run_phase_12a_batched.sh --start-from N --defer=N --defer-reason=TICKET-123
```

The script writes `batches/batch_N/deferred` with the reason; `generate_batch_status.sh` then reports that batch as **deferred** in batch_status.json and README.md. Before sign-off, address or accept all deferred items (see GAP_FIX plan §6.3).

To regenerate batch_status.json and README.md only (e.g. after editing deferred reasons):

```bash
./scripts/generate_batch_status.sh test_reports_comprehensive/YYYY-MM-DD/batches
```

### References

- [GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md](GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md) §5 (Batch strategy), §11 (splitting batches).
- [TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md) (Phase 12A, evidence layout).

---

## Gap remediation validation

**When to run**: After completing gap implementation phases (e.g. [gapfix1](../openspec/changes/gapfix1) or [testreview1](../openspec/changes/testreview1)); required for release when gap remediation applies. See [GAP_REMEDIATION_PLAN.md §11](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md) and Phase 16 in [testreview1/tasks.md](../openspec/changes/testreview1/tasks.md).

### Steps

1. **Run full 12A suite**: Execute `./scripts/run_phase_12a_full_suites.sh` (or backend-only `./scripts/run_phase_12a_backend_suites.sh` if frontend/other suites are not needed). Ensure all critical suites are green; fix failures at root cause before proceeding.
2. **Generate test summary report**: `./scripts/generate_test_summary_report.sh YYYY-MM-DD` (use the date of the run). Evidence is stored under `test_reports_comprehensive/{DATE}/`. Verify report contains execution summary and evidence links.
3. **Sign-off**: Product/tech lead confirms documentation and implementation choices; gap items resolved or deferred as planned; record evidence and report location (e.g. in release notes or audit).

Release MUST NOT proceed until sign-off is obtained when gap remediation applies.

### Full suite sign-off record (Phase 4.3)

When documenting a full suite run sign-off, record:

| Field | Description |
|-------|-------------|
| **Date** | Date of the full run (YYYY-MM-DD). |
| **Commit / branch** | Git commit hash and branch (e.g. `main` or `feature/xyz`). |
| **Outcome** | "Full suite run passed" or "Passed with deferred failures" (see below). |
| **Evidence path** | `test_reports_comprehensive/{DATE}/` (and summary report path if generated). |
| **Deferred failures** | If any batch or suite was deferred: list batch/suite, reason, and ticket reference. |

Optional: generate a sign-off snippet (date, branch, commit, evidence path, deferred from batch status) with:

```bash
./scripts/generate_sign_off_snippet.sh [YYYY-MM-DD]
```

Omit the date to use the latest date directory under `test_reports_comprehensive/`. The script reads `test_reports_comprehensive/{DATE}/batches/batch_status.json` for deferred batches when present.

---

## Security suite (Phase 12A.3)

**When to run**: As part of the full Phase 12A run (nightly, release, or manual); or alone when validating security after changes. Security tests are **part of the full run and sign-off** per [TEST_EXECUTION_PLAN.md — Phase 12A.3](TEST_EXECUTION_PLAN.md#phase-12a3--security-performance-concurrency-regression-runnable) and gapfix1/testreview1.

### As part of full run

The security suite runs automatically in **Phase 12A.3** when you execute:

```bash
./scripts/run_phase_12a_full_suites.sh
```

It runs after backend (12A.1) and frontend (12A.2), inside the `api-service` container. Artifacts: `test_reports_comprehensive/{date}/security/` (`security.log`, `junit.xml`). Exit code is recorded in `phase_12a_3_summary.json`; the script exits 1 if the security suite (or any 12A.3 suite) failed (no masking).

### Run security suite alone

With the stack up (`docker compose up -d` or equivalent):

```bash
docker compose exec -T api-service bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/security/ -v --tb=short"
```

Or with JUnit XML for CI:

```bash
docker compose exec -T api-service bash -c "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/security/ -v --junit-xml=/tmp/junit_security.xml --tb=short"
```

### Fixing failures

- **Do not mask or skip**: Fix any failure at **root cause** (no mocks/stubs; no "skip if flaky").
- Inspect `test_reports_comprehensive/{date}/security/security.log` and `junit.xml` for failures.
- Re-run the security suite (or full Phase 12A) after fixes; ensure green before sign-off.

### CI

Security tests are included in **Phase 12A Nightly** (`phase-12a-nightly.yml`) and **Phase 12A Release** (`phase-12a-release.yml`). They run as step 12A.3.1 in the full suite; evidence is uploaded with the rest of `test_reports_comprehensive/`. Sign-off requires the full run (including security) to be green; see [Gap remediation validation](#gap-remediation-validation).

---

## Dependency and vulnerability scans

**When to use**: To understand or verify dependency and vulnerability scanning in CI; part of test/evidence and release posture (gapfix1 6.2.2).

Dependency and vulnerability scans run in CI and are **kept in place**; results are uploaded as workflow artifacts. No mocks or stubs; scans run against real dependencies and code.

### CI workflow: `security-scan.yml`

The [security-scan.yml](../.github/workflows/security-scan.yml) workflow runs on push/PR to `main` and `develop`, weekly (Monday 00:00 UTC), and on `workflow_dispatch`:

| Job | What runs | Artifacts | Retention |
|-----|------------|-----------|-----------|
| **dependency-scan** | [Safety](https://pyup.io/safety/) (Python vulns), [pip-audit](https://pypi.org/project/pip-audit/) (known vulns in installed packages) | `dependency-scan-results`: `safety-report.json`, `pip-audit-report.json` | 30 days |
| **code-scan** | [Bandit](https://bandit.readthedocs.io/) (security issues in `hub/`, `services/`) with `.bandit` config | `bandit-report`: `bandit-report.json`, `bandit-report.txt` | 30 days |
| **container-scan** | [Trivy](https://trivy.dev/) (container image vulns; CRITICAL/HIGH) | SARIF uploaded to GitHub Security tab | — |

### Where to find results

- **GitHub Actions**: Run the **Security Scan** workflow; open the run and download **Artifacts** (`dependency-scan-results`, `bandit-report`).
- **Trivy**: Container scan results appear under the repository’s **Security** → **Code security and analysis** (SARIF).

### Relation to test evidence and sign-off

- Dependency and code scans are **separate** from Phase 12A test evidence (`test_reports_comprehensive/`). They are part of the project’s security posture and should be reviewed (e.g. before release or when adding dependencies).
- Fix findings at **root cause** (upgrade or replace vulnerable deps; fix or suppress Bandit findings with justification). Document in runbooks or release notes if a finding is deferred.

See also [.github/workflows/README.md](../.github/workflows/README.md) (Security Scan Workflow) and [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) (logging, observability).

---

## Deployment and rollback

**When to use**: Before any staging or production deployment, and when a release fails and rollback is needed.

### Release criteria (gate before release)

The release gate is explicit: **Green Phase 12A + test summary report + sign-off**. Do not release (staging or production) until all three are satisfied.

| Criterion | Description |
|-----------|-------------|
| **Green Phase 12A** | Full test suite run (`./scripts/run_phase_12a_full_suites.sh`) with all critical suites green. Fix any failure at root cause; re-run until green. |
| **Test summary report** | Generate report from evidence: `./scripts/generate_test_summary_report.sh YYYY-MM-DD`. Evidence under `test_reports_comprehensive/{date}/`. |
| **Sign-off** | When gap remediation applies: complete [Gap remediation validation](#gap-remediation-validation); product/tech lead sign-off; record evidence and report location. Release MUST NOT proceed until sign-off is obtained. |

Canonical document: [RELEASE.md — Release criteria and gate](RELEASE.md).

### Deploy only after green Phase 12A + sign-off

- **Same suite**: Run Phase 12A full suite (`./scripts/run_phase_12a_full_suites.sh`) so "deploy after green tests" uses the same suite every time. See [Full test suite (Phase 12A-style)](#full-test-suite-phase-12a-style).
- **Same evidence location**: Artifacts go to `test_reports_comprehensive/{date}/`; generate the test summary report with `./scripts/generate_test_summary_report.sh YYYY-MM-DD`. When gap remediation applies, complete [Gap remediation validation](#gap-remediation-validation) and obtain sign-off before release.
- **Deployment steps**: Follow [DOCKER_COMPOSE_DEPLOYMENT.md](DOCKER_COMPOSE_DEPLOYMENT.md) (Docker Compose); for K8s-based flows (e.g. Prefect workers), see [DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md](DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md).

### Rollback when a release fails

If a release fails after deployment (e.g. critical errors, failed health checks, misconfiguration), roll back **application** (previous image/version) or **configuration** (restore previous config). No new tooling required.

- **Procedures**: See [DOCKER_COMPOSE_DEPLOYMENT.md — Rollback Procedures](DOCKER_COMPOSE_DEPLOYMENT.md#rollback-procedures): Failed Deployment (Scenario 1), Database Migration Failure (Scenario 2), Configuration Error (Scenario 3), Partial Rollback (Scenario 4).
- **After rollback**: Fix root cause, re-run Phase 12A, generate report, obtain sign-off again, then re-release.

---

## Normalization Failures

### Symptoms
- Contracts fail to normalize
- Normalization status is `NORMALIZATION_FAILED`
- Normalization errors in contract record

### Diagnosis

1. **Check Normalization Errors**:
```python
from hub.apps.contracts.models import Contract

contract = Contract.objects.get(id='<contract-id>')
print(contract.normalization_errors)
print(contract.normalization_warnings)
```

2. **Check Contract JSON Size**:
```python
import json

size_bytes = len(json.dumps(contract.hub_contract_json).encode('utf-8'))
print(f"Contract JSON size: {size_bytes} bytes")
```

3. **Check Prometheus Metrics**:
```bash
curl http://localhost:8000/metrics | grep normalization
```

### Common Issues

#### Issue: Large Contract JSON Size (>1MB)
**Symptoms**: Alert `LargeContractJSONSize` triggered
**Resolution**:
1. Review contract structure for unnecessary data
2. Move large data to external storage
3. Consider splitting contract into multiple contracts

#### Issue: Missing Objects
**Symptoms**: Alert `HighMissingObjectsRate` triggered
**Resolution**:
1. Check ODCS contract structure
2. Verify normalization logic for missing objects
3. Review normalization coverage metrics

#### Issue: Broken Lineage Links
**Symptoms**: Alert `BrokenLineageLinksDetected` triggered
**Resolution**:
1. Check referenced contracts exist
2. Verify contract names/IDs in lineage references
3. Review lineage reference resolution logic

### Resolution Steps

1. **Review Normalization Logs**:
```bash
docker-compose logs api-service | grep -i normalization
```

2. **Test Normalization Manually**:
```python
from hub.apps.contracts.normalization import normalize_contract

result = normalize_contract(raw_contract, format='JSON')
print(result)
```

3. **Fix Contract Data**:
- Update ODCS contract to fix errors
- Re-normalize contract
- Verify normalization status

---

## Lineage Issues

### Symptoms
- Lineage queries timeout
- Broken lineage links detected
- Lineage visualization fails

### Diagnosis

1. **Check Lineage Query Performance**:
```sql
EXPLAIN ANALYZE
SELECT id FROM contracts_contract
WHERE hub_contract_json->'lineage' IS NOT NULL;
```

2. **Check Broken Links**:
```python
from hub.apps.contracts.lineage import LineageReference, resolve_lineage_reference

ref = LineageReference(namespace='ns', name='contract1', model_name='model1')
result = resolve_lineage_reference(ref)
print(result)
```

3. **Check Lineage Indexes**:
```sql
SELECT indexname, idx_scan
FROM pg_stat_user_indexes
WHERE indexname LIKE '%lineage%';
```

### Common Issues

#### Issue: Slow Lineage Queries
**Symptoms**: Lineage queries take >1 second
**Resolution**:
1. Verify GIN indexes exist on lineage JSONB paths
2. Run `VACUUM ANALYZE contracts_contract`
3. Check for missing indexes (see `docs/DATABASE_INDEXES.md`)

#### Issue: Broken Lineage Links
**Symptoms**: Lineage references point to non-existent contracts
**Resolution**:
1. Identify broken links using `contract_broken_lineage_links_total` metric
2. Update lineage references to point to existing contracts
3. Re-normalize affected contracts

### Resolution Steps

1. **Rebuild Lineage Indexes**:
```sql
REINDEX INDEX contracts_hub_contract_json_lineage_gin;
REINDEX INDEX contracts_hub_contract_json_models_lineage_gin;
REINDEX INDEX contracts_hub_contract_json_models_fields_lineage_gin;
```

2. **Fix Broken Links**:
```python
# Update lineage references in contracts
from hub.apps.contracts.models import Contract

contract = Contract.objects.get(id='<contract-id>')
# Update hub_contract_json['lineage'] references
contract.save()
```

---

## Scheduled Ingestion Failures

### Symptoms
- Scheduled ingestion runs fail
- No datasets created
- Prefect workflows fail

### Diagnosis

1. **Check Prefect UI**:
- Navigate to `http://localhost:4200`
- Check workflow runs for failures

2. **Check Scheduled Ingestion Status**:
```python
from hub.apps.scheduled_ingestion.models import ScheduledIngestion, ScheduledIngestionRun

ingestion = ScheduledIngestion.objects.get(id='<id>')
runs = ScheduledIngestionRun.objects.filter(scheduled_ingestion=ingestion).order_by('-created_at')[:10]
for run in runs:
    print(f"{run.status}: {run.error_message}")
```

3. **Check Prometheus Metrics**:
```bash
curl http://localhost:8000/metrics | grep scheduled_ingestion
```

### Common Issues

#### Issue: Prefect Server Connection Failure
**Symptoms**: `PREFECT_API_URL` connection error
**Resolution**:
1. Verify Prefect Server is running: `docker-compose ps prefect-server`
2. Check `PREFECT_API_URL` environment variable
3. Verify network connectivity

#### Issue: Source Connector Failure
**Symptoms**: File discovery or download fails
**Resolution**:
1. Check source credentials
2. Verify source path/URL is accessible
3. Check network connectivity to source

#### Worker API and config/secrets
- **Internal Worker API**: Prefect worker calls hub at `/api/v1/scheduled-ingestions/internal/` (run lifecycle, process-file, config). See `docs/SCHEDULED_INGESTION_WORKER_API.md`.
- **Auth**: Worker uses `HUB_WORKER_API_KEY` (env) or an API key with scope `scheduled_ingestion:internal`; must send `X-Tenant-ID` when using env key.
- **Config response and logs MUST NOT contain raw credentials**: The config endpoint (`GET .../internal/config/{id}/`) returns masked `source_config` (credentials masked via CredentialManager). Hub MUST NOT log full config; worker MUST NOT log full config. Documented in runbooks and API doc.

### Resolution Steps

1. **Restart Prefect Integration Service**:
```bash
docker-compose restart prefect-integration-service
```

2. **Manually Trigger Ingestion**:
```python
from hub.apps.scheduled_ingestion.models import ScheduledIngestion

ingestion = ScheduledIngestion.objects.get(id='<id>')
# Trigger manually via API or Prefect UI
```

---

## Prefect Server Issues

### Symptoms
- Prefect Server not responding
- Workflows not executing
- API connection errors

### Diagnosis

1. **Check Prefect Server Health**:
```bash
curl http://localhost:4200/api/health
```

2. **Check Prefect Server Logs**:
```bash
docker-compose logs prefect-server
```

3. **Check Database Connection**:
```bash
docker-compose exec prefect-server psql -U prefect -d prefect -c "SELECT 1;"
```

### Resolution Steps

1. **Restart Prefect Server**:
```bash
docker-compose restart prefect-server
```

2. **Check Database**:
```bash
docker-compose exec postgres psql -U prefect -d prefect -c "\dt"
```

3. **Reset Prefect Server** (if needed):
```bash
docker-compose down prefect-server
docker-compose up -d prefect-server
```

---

## Prefect Workers Issues

### Symptoms
- Workers not processing jobs
- Workflows stuck in "Running" state
- Worker connection errors
- Scheduled ingestion flows failing with hub API errors

### Diagnosis

1. **Check Worker Status**:
```bash
docker-compose ps prefect-worker
```

2. **Check Worker Logs**:
```bash
docker-compose logs prefect-worker
```

3. **Check Worker Connection**:
```bash
docker-compose exec prefect-worker prefect worker status
```

4. **Verify Hub API Configuration** (for scheduled ingestion):
```bash
# Check environment variables
docker-compose exec prefect-worker env | grep HUB_

# Expected:
# HUB_BASE_URL=http://api-service:8000
# HUB_WORKER_API_KEY=<api-key-value>
```

5. **Test Hub API Connectivity**:
```bash
# From prefect-worker container
docker-compose exec prefect-worker curl -f http://api-service:8000/health
```

### Common Issues

#### Issue: Hub API Connection Failure
**Symptoms**:
- `HUB_BASE_URL must be set` errors in worker logs
- `HUB_WORKER_API_KEY must be set` errors
- 401/403 errors when calling hub internal endpoints

**Resolution**:
1. Verify `HUB_BASE_URL` is set correctly:
   - Docker Compose: `http://api-service:8000` (or `http://api-service-test:8000` for test)
   - Kubernetes: `http://api-service.default.svc.cluster.local:8000` (adjust namespace if needed)
2. Verify `HUB_WORKER_API_KEY` is set and valid:
   - Generate API key: `python hub/manage.py create_api_key --scopes scheduled_ingestion:internal`
   - Set in `.env.dev` / `.env.staging` / `.env.production` or Kubernetes secrets
3. Verify network connectivity between prefect-worker and api-service
4. Verify API key has correct scope (`scheduled_ingestion:internal`)

#### Issue: Worker Cannot Reach Hub API
**Symptoms**: Connection timeout or DNS resolution errors

**Resolution**:
1. Verify both services are on the same Docker network
2. Check service names match (e.g., `api-service` vs `api-service-test`)
3. Verify api-service is healthy: `docker-compose ps api-service`
4. Test connectivity: `docker-compose exec prefect-worker ping api-service`

### Resolution Steps

1. **Restart Workers**:
```bash
docker-compose restart prefect-worker
```

2. **Scale Workers**:
```bash
docker-compose up -d --scale prefect-worker=3
```

3. **Update Hub API Configuration**:
```bash
# Update .env file with correct values
HUB_BASE_URL=http://api-service:8000
HUB_WORKER_API_KEY=<your-api-key>

# Restart worker to pick up changes
docker-compose restart prefect-worker
```

4. **Verify Configuration**:
```bash
# Check worker can reach hub API
docker-compose exec prefect-worker curl -H "Authorization: ApiKey $HUB_WORKER_API_KEY" \
  -H "X-Tenant-ID: <tenant-id>" \
  http://api-service:8000/api/v1/scheduled-ingestions/internal/config/<scheduled-ingestion-id>/
```

---

## Search Service Issues

### Symptoms
- Search queries fail
- Search index not updating
- Search results incorrect

### Diagnosis

1. **Check Search Index Status**:
```python
from hub.apps.search.models import SearchIndex

indices = SearchIndex.objects.filter(tenant_id='<tenant-id>')[:10]
for idx in indices:
    print(f"{idx.resource_type} {idx.resource_id}: {idx.indexed_at}")
```

2. **Check Search Query Performance**:
```sql
EXPLAIN ANALYZE
SELECT * FROM search_index
WHERE tenant_id = '<tenant-id>' AND search_vector @@ to_tsquery('english', 'test');
```

### Resolution Steps

1. **Rebuild Search Index**:
```python
from hub.apps.search.tasks import update_search_index

update_search_index.delay(resource_type='CONTRACT', resource_id='<id>')
```

2. **Reindex All Resources**:
```python
from hub.apps.search.tasks import reindex_all_resources

reindex_all_resources.delay()
```

---

## Observability Service Issues

### Symptoms
- Observability metrics not updating
- Dashboards show no data
- Alerts not triggering

### Diagnosis

1. **Check Metrics Endpoint**:
```bash
curl http://localhost:8000/metrics | head -20
```

2. **Check Observability Models**:
```python
from hub.apps.observability.models import DataObservabilityMetric

metrics = DataObservabilityMetric.objects.filter(tenant_id='<tenant-id>')[:10]
for metric in metrics:
    print(f"{metric.recorded_at}: {metric.is_stale}")
```

### Resolution Steps

1. **Restart Observability Service**:
```bash
docker-compose restart observability-service
```

2. **Check Prometheus Scraping**:
```bash
curl http://localhost:9090/api/v1/targets
```

---

## Webhook Service Issues

### Symptoms
- Webhooks not delivering
- Webhook delivery failures
- Webhook retries exhausted

### Diagnosis

1. **Check Webhook Deliveries**:
```python
from hub.apps.webhooks.models import Webhook, WebhookDelivery

webhook = Webhook.objects.get(id='<id>')
deliveries = WebhookDelivery.objects.filter(webhook=webhook).order_by('-created_at')[:10]
for delivery in deliveries:
    print(f"{delivery.status}: {delivery.error_message}")
```

2. **Check Webhook Service Logs**:
```bash
docker-compose logs webhook-service
```

### Resolution Steps

1. **Retry Failed Deliveries**:
```python
from hub.apps.webhooks.tasks import retry_failed_deliveries

retry_failed_deliveries.delay()
```

2. **Restart Webhook Service**:
```bash
docker-compose restart webhook-service
```

---

## Marketplace Connector Pattern Violations

### Symptoms

- Connectors create assets directly instead of returning mappings
- `sync_pull()` downloads data instead of mapping listings only
- `sync_pull()` performs marketplace-specific operations (database creation, subscriptions, snapshots)
- `map_to_hub_asset()` accesses external data sources instead of storing references
- Assets are created during sync instead of being created by workflow
- Slow sync performance (hours instead of seconds)
- High storage usage during initial sync

### Diagnosis

#### 1. Check if Connector Creates Assets in `sync_pull()`

```python
from hub.apps.integrations.models import MarketplaceSyncJob
from hub.apps.assets.models import Asset
from django.utils import timezone
from datetime import timedelta

# Get recent sync job
sync_job = MarketplaceSyncJob.objects.filter(
    direction="PULL",
    created_at__gte=timezone.now() - timedelta(hours=1)
).first()

if sync_job:
    # Count assets created during sync window
    assets_created_during_sync = Asset.objects.filter(
        created_at__gte=sync_job.created_at,
        created_at__lte=sync_job.completed_at if sync_job.completed_at else timezone.now()
    ).count()

    print(f"Assets created during sync: {assets_created_during_sync}")
    print(f"Sync job successful items: {sync_job.successful_items}")

    # If assets created > successful items, connector may be creating assets directly
    if assets_created_during_sync > sync_job.successful_items:
        print("⚠️  WARNING: Connector may be creating assets directly in sync_pull()")
```

#### 2. Check if `sync_pull()` Returns Mappings Only

```python
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection

# Get connector
connection = MarketplaceConnection.objects.get(id="<connection-id>")
connector = MarketplaceConnectorFactory.create_connector(connection)

# Execute sync_pull
result = connector.sync_pull(options={"limit": 10, "dry_run": True})

# Verify result structure
print(f"Result type: {type(result)}")
print(f"Has metadata: {'metadata' in result.metadata if hasattr(result, 'metadata') else False}")
print(f"Has mappings: {'mappings' in result.metadata if hasattr(result, 'metadata') else False}")

if hasattr(result, 'metadata') and 'mappings' in result.metadata:
    mappings = result.metadata['mappings']
    print(f"Number of mappings: {len(mappings)}")
    if mappings:
        print(f"First mapping type: {type(mappings[0])}")
        print(f"First mapping keys: {mappings[0].keys() if isinstance(mappings[0], dict) else 'Not a dict'}")

    # Check for asset IDs (should NOT be present)
    if 'asset_ids' in result.metadata:
        print("❌ ERROR: sync_pull() returns asset_ids (should return mappings only)")

    # Check for contract IDs (should NOT be present)
    if 'contract_ids' in result.metadata:
        print("❌ ERROR: sync_pull() returns contract_ids (should return mappings only)")
else:
    print("❌ ERROR: sync_pull() does not return mappings in metadata")
```

#### 3. Check if `sync_pull()` Downloads Data

```python
import os
import tempfile
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection

# Get connector
connection = MarketplaceConnection.objects.get(id="<connection-id>")
connector = MarketplaceConnectorFactory.create_connector(connection)

# Track file creation during sync_pull
initial_files = set()
temp_dir = tempfile.gettempdir()
for root, dirs, files in os.walk(temp_dir):
    for file in files:
        initial_files.add(os.path.join(root, file))

# Execute sync_pull
result = connector.sync_pull(options={"limit": 10, "dry_run": True})

# Check for new files
new_files = set()
for root, dirs, files in os.walk(temp_dir):
    for file in files:
        file_path = os.path.join(root, file)
        if file_path not in initial_files:
            new_files.add(file_path)

if new_files:
    print(f"⚠️  WARNING: {len(new_files)} files created during sync_pull()")
    print("Files created:")
    for file_path in list(new_files)[:10]:  # Show first 10
        print(f"  - {file_path}")
    print("❌ ERROR: sync_pull() should not download data")
else:
    print("✅ OK: sync_pull() does not download data")
```

#### 4. Check if `map_to_hub_asset()` Accesses External Data Sources

```python
import httpx
from unittest.mock import patch
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceListing
from hub.apps.integrations.base import MarketplaceType

# Get connector
connection = MarketplaceConnection.objects.get(id="<connection-id>")
connector = MarketplaceConnectorFactory.create_connector(connection)

# Create test listing
listing = MarketplaceListing(
    marketplace_id="test-listing",
    marketplace_type=MarketplaceType.CKAN_INSTANCE,
    title="Test Listing"
)

# Track HTTP requests
http_requests = []

def track_request(*args, **kwargs):
    http_requests.append((args, kwargs))
    return httpx.get(*args, **kwargs)

# Execute map_to_hub_asset with HTTP tracking
with patch('httpx.get', side_effect=track_request):
    mapping = connector.map_to_hub_asset(listing)

if http_requests:
    print(f"⚠️  WARNING: {len(http_requests)} HTTP requests made during map_to_hub_asset()")
    print("HTTP requests:")
    for args, kwargs in http_requests[:5]:  # Show first 5
        print(f"  - {args[0] if args else 'N/A'}")
    print("❌ ERROR: map_to_hub_asset() should not access external data sources")
else:
    print("✅ OK: map_to_hub_asset() does not access external data sources")
```

#### 5. Run Pattern Verification Tests

```bash
# Run pattern verification tests for all connectors
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connector_pattern.py \
  -v \
  --tb=short

# Run tests for specific connector
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullDoesNotCreateAssets::test_ckan_sync_pull_does_not_create_assets \
  -v \
  --tb=short
```

### Common Issues

#### Issue: Connector Creates Assets in `sync_pull()`

**Symptoms**:
- Assets are created during sync instead of after workflow execution
- `sync_pull()` returns asset IDs instead of mappings
- Sync performance is slow (assets created synchronously)

**Root Cause**:
Connector is calling `create_federated_asset_with_contracts()` or `Asset.objects.create()` directly in `sync_pull()`.

**Resolution**:
1. Refactor `sync_pull()` to return mappings only:
   ```python
   # Wrong
   def sync_pull(self, ...):
       for listing in listings:
           asset = create_federated_asset_with_contracts(...)  # ❌

   # Correct
   def sync_pull(self, ...):
       mappings = []
       for listing in listings:
           mapping = self.map_to_hub_asset(listing)  # ✅
           mappings.append(mapping)
       return SyncResult(metadata={"mappings": [m.__dict__ for m in mappings]})
   ```

2. Verify workflow handles asset creation:
   - Check `hub/apps/orchestration/workflows/marketplace_sync.py`
   - Verify `create_federated_assets_task` calls `create_federated_asset_with_contracts()`

#### Issue: Connector Downloads Data in `sync_pull()`

**Symptoms**:
- Files are created during sync
- High storage usage during initial sync
- Slow sync performance (downloading data synchronously)

**Root Cause**:
Connector is calling `download_resource()` or file download methods in `sync_pull()`.

**Resolution**:
1. Remove data download logic from `sync_pull()`:
   ```python
   # Wrong
   def sync_pull(self, ...):
       for listing in listings:
           for resource in listing.resources:
               download_path = self.download_resource(resource.id, "/tmp/data.csv")  # ❌

   # Correct
   def sync_pull(self, ...):
       mappings = []
       for listing in listings:
           mapping = self.map_to_hub_asset(listing)  # ✅ Maps resources with external references
           mappings.append(mapping)
       return SyncResult(metadata={"mappings": [m.__dict__ for m in mappings]})
   ```

2. Ensure `map_to_hub_asset()` includes external resource references:
   ```python
   def map_to_hub_asset(self, listing):
       resources = [
           MarketplaceResource(
               resource_id=resource.id,
               url=resource.external_url,  # ✅ Store reference
               metadata={"external": True, "download_url": resource.external_url}
           )
           for resource in listing.resources
       ]
       return MarketplaceAssetMapping(resources=resources, ...)
   ```

#### Issue: Connector Performs Marketplace-Specific Operations in `sync_pull()`

**Symptoms**:
- Database creation happens during sync (Snowflake)
- Subscriptions happen during sync (AWS Data Exchange)
- Snapshots are triggered during sync (Azure Data Share)
- Slow sync performance

**Root Cause**:
Connector is performing marketplace-specific operations in `sync_pull()` instead of deferring them to `download_resource()`.

**Resolution**:
1. Move marketplace-specific operations to `download_resource()`:
   ```python
   # Wrong (Snowflake example)
   def sync_pull(self, ...):
       for listing in listings:
           self._create_database_from_listing(listing.id)  # ❌
           schema = self._extract_schema_metadata(listing.database_name)  # ❌

   # Correct
   def sync_pull(self, ...):
       mappings = []
       for listing in listings:
           mapping = self.map_to_hub_asset(listing)  # ✅ Maps only
           mappings.append(mapping)
       return SyncResult(metadata={"mappings": [m.__dict__ for m in mappings]})

   def download_resource(self, resource_id, destination_path):
       # ✅ Marketplace-specific operations happen here
       if len(resource_id.split(".")) == 1:  # Listing ID
           self._create_database_from_listing(resource_id)
           schema = self._extract_schema_metadata(resource_id)
           # ... download data
   ```

#### Issue: `map_to_hub_asset()` Accesses External Data Sources

**Symptoms**:
- HTTP requests are made during mapping
- Schema extraction happens during mapping
- Slow mapping performance

**Root Cause**:
Connector is accessing external data sources in `map_to_hub_asset()` instead of storing references.

**Resolution**:
1. Remove external data access from `map_to_hub_asset()`:
   ```python
   # Wrong
   def map_to_hub_asset(self, listing):
       data = httpx.get(listing.resource_url).content  # ❌
       schema = extract_schema_from_data(data)  # ❌

   # Correct
   def map_to_hub_asset(self, listing):
       resources = [
           MarketplaceResource(
               resource_id=resource.id,
               url=resource.external_url,  # ✅ Store reference
               metadata={"external": True, "download_url": resource.external_url}
           )
           for resource in listing.resources
       ]
       return MarketplaceAssetMapping(resources=resources, ...)
   ```

### Diagnostic Commands

#### Verify Connector Pattern Compliance

```bash
# Run all pattern verification tests
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connector_pattern.py \
  -v \
  --tb=short

# Check specific connector
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_connector_pattern.py::TestSyncPullDoesNotCreateAssets::test_ckan_sync_pull_does_not_create_assets \
  -v \
  --tb=short
```

#### Check Sync Job Results

```python
from hub.apps.integrations.models import MarketplaceSyncJob
from django.utils import timezone
from datetime import timedelta

# Get recent sync jobs
sync_jobs = MarketplaceSyncJob.objects.filter(
    direction="PULL",
    created_at__gte=timezone.now() - timedelta(hours=24)
).order_by('-created_at')[:10]

for job in sync_jobs:
    print(f"Sync Job: {job.id}")
    print(f"  Status: {job.status}")
    print(f"  Successful Items: {job.successful_items}")
    print(f"  Failed Items: {job.failed_items}")
    print(f"  Metadata Keys: {list(job.metadata.keys()) if job.metadata else 'None'}")
    if job.metadata and 'mappings' in job.metadata:
        print(f"  Mappings Count: {len(job.metadata['mappings'])}")
    print()
```

#### Check Asset Creation Timing

```python
from hub.apps.assets.models import Asset
from hub.apps.integrations.models import MarketplaceSyncJob
from django.utils import timezone
from datetime import timedelta

# Get recent sync job
sync_job = MarketplaceSyncJob.objects.filter(
    direction="PULL",
    created_at__gte=timezone.now() - timedelta(hours=1)
).first()

if sync_job:
    # Count assets created during sync window
    assets_created = Asset.objects.filter(
        created_at__gte=sync_job.created_at,
        created_at__lte=sync_job.completed_at if sync_job.completed_at else timezone.now(),
        source_type="FEDERATED"
    ).count()

    print(f"Sync Job: {sync_job.id}")
    print(f"  Created At: {sync_job.created_at}")
    print(f"  Completed At: {sync_job.completed_at}")
    print(f"  Successful Items: {sync_job.successful_items}")
    print(f"  Assets Created During Sync: {assets_created}")

    if assets_created > sync_job.successful_items:
        print("⚠️  WARNING: More assets created than successful items (connector may be creating assets directly)")
```

### Resolution Steps

1. **Identify the Violation**:
   - Run pattern verification tests
   - Check sync job results
   - Review connector code

2. **Refactor Connector**:
   - Move asset creation logic out of `sync_pull()`
   - Move data download logic to `download_resource()`
   - Move marketplace-specific operations to `download_resource()`
   - Ensure `map_to_hub_asset()` only stores references

3. **Verify Fix**:
   - Run pattern verification tests
   - Test sync with dry_run=True
   - Verify workflow handles asset creation

4. **Monitor**:
   - Check sync performance (should be fast for metadata-only)
   - Check storage usage (should be low for metadata-only)
   - Verify assets are created by workflow, not connector

### Prevention

- Always follow the metadata-first architecture pattern
- Use pattern verification tests during development
- Review connector code before deployment
- Monitor sync performance and storage usage
- See [Connector Development Guide](./connectors/DEVELOPMENT.md) for detailed implementation guidelines

---

## Disaster Recovery

### Recovery Procedures

1. **Database Recovery**:
```bash
# Restore from backup
pg_restore -d hub_db backup.dump
```

2. **Service Recovery**:
```bash
# Restart all services
docker-compose down
docker-compose up -d
```

3. **Data Recovery**:
```bash
# Restore from S3/MinIO backup
aws s3 cp s3://backup-bucket/backup.tar.gz .
tar -xzf backup.tar.gz
```

---

## Backup and Recovery

### Backup Procedures

1. **Database Backup**:
```bash
pg_dump -Fc hub_db > backup_$(date +%Y%m%d).dump
```

2. **File Storage Backup**:
```bash
# Backup MinIO data
mc mirror minio/backup-bucket s3://backup-bucket/
```

3. **Configuration Backup**:
```bash
# Backup configuration files
tar -czf config_backup_$(date +%Y%m%d).tar.gz config/
```

### Recovery Procedures

1. **Database Recovery**:
```bash
pg_restore -d hub_db backup_20250115.dump
```

2. **File Storage Recovery**:
```bash
mc mirror s3://backup-bucket/ minio/backup-bucket/
```

---

## CKAN Connector Issues

### Symptoms
- CKAN connector connection failures
- Harvest operations failing
- Circuit breaker open
- API key authentication errors

### Diagnosis

1. **Check Connector Configuration**:
```python
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config

config = get_marketplace_instance_config('dados.gov.br')
print(f"Base URL: {config.base_url}")
print(f"Connector Type: {config.connector_type}")  # "swagger" for dados.gov.br
print(f"API Key Set: {config.get_api_key() is not None}")
```

2. **Test Connection**:
```python
from hub.apps.integrations.factory import MarketplaceConnectorFactory

# Use new method name (recommended)
connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance('dados.gov.br')
# Or use backward-compatible method (deprecated):
# connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance('dados.gov.br')
result = connector.test_connection()
print(f"Connection test: {result}")
```

3. **Check Circuit Breaker State**:
```bash
docker compose exec api-service python -c "
from hub.apps.core.services.redis import get_redis_client
redis = get_redis_client()
state = redis.get('circuit_breaker:ckan-connector:state')
print(f'Circuit Breaker State: {state}')
"
```

### Common Issues

#### Issue: Connection Errors
**Symptoms**: `ConnectionError` when accessing marketplace instances

**Resolution**:
1. Verify network connectivity:
   - For Swagger API (dados.gov.br): `curl https://dados.gov.br/v3/api-docs`
   - For CKAN API (demo.ckan.org, data.gov): `curl https://demo.ckan.org/api/3/action/status_show`
2. Check firewall rules allow outbound HTTPS
3. Verify DNS resolution
4. Check marketplace instance status

#### Issue: API Key Not Working
**Symptoms**: Permission errors even with API key set

**Resolution**:
1. Verify API key format:
   - For Swagger API (dados.gov.br): JWT Bearer token format (`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`)
   - For CKAN API (demo.ckan.org, data.gov): Standard API key string
2. Check environment variable name:
   - For dados.gov.br: Use `DADOS_GOV_BR_API_KEY` (primary) or `CKAN_DADOS_GOV_BR_API_KEY` (deprecated)
   - For CKAN instances: Use `CKAN_TEST_API_KEY`
3. Check API key permissions in marketplace instance
4. Regenerate API key if needed
5. Verify environment variable is loaded correctly

#### Issue: Circuit Breaker Open
**Symptoms**: Requests fail immediately without attempting connection

**Resolution**:
1. Reset circuit breaker: Delete Redis key `circuit_breaker:ckan-connector:state`
2. Wait for automatic recovery (60 seconds timeout)
3. Check underlying connectivity issues
4. Verify Redis is healthy

### Resolution Steps

1. **Check Logs**:
```bash
docker compose logs api-service | grep -i ckan
```

2. **Verify Environment Variables**:
```bash
# Check all marketplace-related environment variables
docker compose exec api-service env | grep -E "DADOS_GOV_BR_API_KEY|CKAN"
```

3. **Test Connector**:
```bash
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_marketplace_instances_config.py \
  -v
```

4. **Reset Circuit Breaker** (if needed):
```bash
docker compose exec api-service python -c "
from hub.apps.core.services.redis import get_redis_client
redis = get_redis_client()
redis.delete('circuit_breaker:ckan-connector:state')
print('Circuit breaker reset')
"
```

For detailed troubleshooting, see [Marketplace Connector Deployment Runbook](./runbooks/marketplace-connector-deployment.md).

---

## BaaS Platform Troubleshooting

### Symptoms
- API key creation/validation failures
- Rate limiting not working correctly
- Usage tracking not recording requests
- Developer portal endpoints returning errors
- Quota exhaustion errors

### Diagnosis

1. **Check API Gateway Status**:
```bash
# Check API Gateway service health
curl http://localhost:8000/health
docker compose logs api-gateway | tail -50
```

2. **Check API Key Status**:
```python
from hub.apps.baas.models import APIKey

# Check API keys
api_keys = APIKey.objects.filter(tenant_id='...')
for key in api_keys:
    print(f"{key.name}: {key.tier}, revoked={key.is_revoked}, expired={key.is_expired()}")
```

3. **Check Usage Tracking**:
```python
from hub.apps.baas.models import APIUsage

# Check usage records
usage = APIUsage.objects.filter(api_key_id='...').order_by('-timestamp')[:10]
for u in usage:
    print(f"{u.endpoint}: {u.status_code}, {u.response_time_ms}ms")
```

4. **Check Rate Limiting**:
```bash
# Check Redis for rate limit counters
docker compose exec redis redis-cli
> KEYS rate_limit:*
> GET rate_limit:api_key:*
```

### Common Issues

#### Issue: API Key Validation Failures
**Symptoms**: `BAAS_API_KEY_INVALID` errors, authentication failures
**Resolution**:
1. Verify API key exists: `APIKey.objects.get(id='...')`
2. Check API key is not revoked: `api_key.is_revoked == False`
3. Check API key is not expired: `api_key.is_expired() == False`
4. Verify API key hash matches: Check hashing algorithm
5. Review API Gateway logs for validation errors

#### Issue: Rate Limiting Not Working
**Symptoms**: Requests not being rate limited, quota not enforced
**Resolution**:
1. Check API Gateway service is running: `docker compose ps api-gateway`
2. Verify tier configuration: `APITier.objects.all()`
3. Check Redis connectivity: `docker compose exec redis redis-cli ping`
4. Review rate limiting middleware configuration
5. Check rate limit counters in Redis: `KEYS rate_limit:*`

#### Issue: Usage Tracking Not Recording
**Symptoms**: Usage statistics not updating, missing usage records
**Resolution**:
1. Verify UsageTrackingService is called: Check middleware configuration
2. Check database connectivity: `python manage.py dbshell`
3. Review APIUsage model: `APIUsage.objects.count()`
4. Check for database transaction issues
5. Review usage tracking service logs

#### Issue: Developer Portal Errors
**Symptoms**: `/api/v1/baas/docs/` endpoints returning errors
**Resolution**:
1. Check DeveloperDocumentationViewSet: Verify view configuration
2. Check OpenAPI schema generation: `python manage.py spectacular --file schema.yaml`
3. Verify SDK download links: Check static file serving
4. Review developer portal service logs

### Resolution Steps

1. **Restart API Gateway**:
```bash
docker compose restart api-gateway
```

2. **Clear Rate Limit Counters**:
```bash
docker compose exec redis redis-cli
> KEYS rate_limit:*
> DEL rate_limit:*
```

3. **Reset API Key**:
```python
from hub.apps.baas.models import APIKey

api_key = APIKey.objects.get(id='...')
# Regenerate API key (if needed)
# Note: This invalidates the old key
```

4. **Recalculate Usage Statistics**:
```python
from hub.apps.baas.services import UsageTrackingService

service = UsageTrackingService()
stats = service.get_usage_statistics(api_key_id='...')
```

### Performance Tuning

1. **Optimize Rate Limiting**: Use Redis for distributed rate limiting
2. **Batch Usage Tracking**: Batch usage records for better performance
3. **Cache Tier Information**: Cache tier limits to reduce database queries
4. **Optimize Quota Checks**: Use Redis counters for quota tracking

---

## ODH Integration Troubleshooting

### Symptoms
- ML model operations failing
- Training jobs not starting or completing
- Inference predictions failing
- ODH service connection errors
- Model registry sync failures

### Diagnosis

1. **Check ODH Service Status**:
```bash
# Check ODH Model Registry
curl http://odh-model-registry:8080/health

# Check ODH Training Operator
curl http://odh-training-operator:8080/health

# Check ODH Inference Scheduler
curl http://odh-inference-scheduler:8080/health
```

2. **Check ML Model Status**:
```python
from hub.apps.ml.models import MLModel, TrainingJob, InferenceDeployment

# Check models
models = MLModel.objects.filter(status='FAILED')
for model in models:
    print(f"{model.odh_model_id}: {model.status}")

# Check training jobs
jobs = TrainingJob.objects.filter(status='FAILED')
for job in jobs:
    print(f"{job.id}: {job.status}, {job.error_message}")

# Check inference deployments
deployments = InferenceDeployment.objects.filter(status='FAILED')
for dep in deployments:
    print(f"{dep.id}: {dep.status}, {dep.error_message}")
```

3. **Check ODH Client Configuration**:
```python
# Check ODH client availability
from services.odh_integration.model_registry_client import ODHModelRegistryClient

try:
    client = ODHModelRegistryClient()
    models = client.list_models()
    print(f"ODH connection successful: {len(models)} models")
except Exception as e:
    print(f"ODH connection failed: {e}")
```

4. **Check Training Job Logs**:
```bash
# Get training job logs
curl http://localhost:8000/api/v1/ml/training/jobs/{job_id}/logs/
```

### Common Issues

#### Issue: ODH Service Connection Failed
**Symptoms**: `ODH_CONNECTION_FAILED` errors, model operations timing out
**Resolution**:
1. Verify ODH services are running: `docker compose ps | grep odh`
2. Check ODH service URLs: `ODH_MODEL_REGISTRY_URL` environment variable
3. Test ODH service connectivity: `curl http://odh-service:8080/health`
4. Review ODH client configuration: Check connection timeout settings
5. Check network connectivity: Verify service-to-service communication

#### Issue: Training Job Not Starting
**Symptoms**: Training jobs stuck in `PENDING` or `RUNNING` status
**Resolution**:
1. Check training job configuration: Verify dataset and model IDs
2. Verify dataset accessibility: Check dataset exists and is accessible
3. Check DQ and compliance checks: Review validation results
4. Review ODH Training Operator logs: `docker compose logs odh-training-operator`
5. Check resource availability: Verify Kubernetes resources for training

#### Issue: Training Job Failing
**Symptoms**: Training jobs failing with errors, `ODH_TRAINING_JOB_FAILED`
**Resolution**:
1. Review training job logs: `GET /api/v1/ml/training/jobs/{id}/logs/`
2. Check dataset validation: Verify dataset format and quality
3. Review training configuration: Check epochs, batch_size, learning_rate
4. Check ODH Training Operator status: Verify operator is healthy
5. Review resource constraints: Check CPU/memory limits

#### Issue: Inference Predictions Failing
**Symptoms**: Inference requests returning errors, validation failures
**Resolution**:
1. Check inference deployment status: `InferenceDeployment.objects.get(id='...')`
2. Verify input contract validation: Check input data format
3. Check ODH Inference Scheduler: Verify scheduler is running
4. Review inference logs: Check inference service logs
5. Verify model is deployed: Check model status is `DEPLOYED`

#### Issue: Model Registry Sync Failures
**Symptoms**: Model metadata not syncing from ODH, sync errors
**Resolution**:
1. Check ODH Model Registry connection: Test client connectivity
2. Verify model exists in ODH: `ODHModelRegistryClient().get_model('...')`
3. Review sync workflow: Check ModelRegistryBridgeService logs
4. Check tenant permissions: Verify tenant has access to ODH models
5. Review sync error messages: Check model sync error logs

### Resolution Steps

1. **Restart ODH Services**:
```bash
docker compose restart odh-model-registry odh-training-operator odh-inference-scheduler
```

2. **Retry Failed Operations**:
```python
from hub.apps.ml.services import ModelRegistryBridgeService

service = ModelRegistryBridgeService()
# Retry model sync
service.sync_from_odh(model_id='...')
```

3. **Cancel Stuck Training Jobs**:
```bash
curl -X POST http://localhost:8000/api/v1/ml/training/jobs/{job_id}/cancel/
```

4. **Redeploy Inference Deployment**:
```bash
# Undeploy
curl -X DELETE http://localhost:8000/api/v1/ml/inference/deployments/{id}/

# Redeploy
curl -X POST http://localhost:8000/api/v1/ml/inference/deployments/ \
  -H "Content-Type: application/json" \
  -d '{"model_id": "...", "config": {...}}'
```

### Performance Tuning

1. **Optimize Model Registry Queries**: Use database indexes for model lookups
2. **Batch Training Job Submissions**: Batch multiple training jobs
3. **Cache ODH Model Metadata**: Cache model metadata to reduce ODH API calls
4. **Optimize Inference Latency**: Use model caching and request batching
5. **Monitor Resource Usage**: Track CPU/memory usage for training and inference

---

## Frontend / SPA

### Overview

The frontend is a React + TypeScript Single Page Application (SPA) built with Vite and served via Nginx in production. It communicates with the backend API service through REST endpoints and WebSocket connections.

**Architecture**:
- **Development**: Vite dev server (port 5173) with hot module replacement
- **Production**: Nginx serving static files built by Vite
- **Container**: Docker multi-stage build (Node.js builder + Nginx runtime)
- **Deployment**: Docker Compose (dev/staging) or Kubernetes (production)

### Symptoms

- Frontend not loading or showing blank page
- API calls failing (CORS, 404, 502 errors)
- WebSocket connections failing
- Build failures
- Environment variable issues
- Health check failures

### Diagnosis

#### 1. Check Frontend Container Status

```bash
# Check container status
docker compose ps frontend

# Check container logs
docker compose logs frontend --tail=100

# Check container health
docker inspect hub-frontend | grep -A 10 Health
```

#### 2. Check Frontend Health Endpoint

```bash
# Direct container check (from host)
curl http://localhost:3000/

# Health check (Nginx serves index.html)
curl -I http://localhost:3000/

# Check if Nginx is responding
docker compose exec frontend wget -q -O /dev/null http://127.0.0.1/ && echo "✅ Nginx healthy"
```

#### 3. Check API Connectivity

```bash
# Check API proxy through frontend
curl http://localhost:3000/api/v1/health/

# Check direct API service
curl http://localhost:8000/health/

# Check WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:3000/ws/events/
```

#### 4. Check Environment Variables

```bash
# Check environment variables in container
docker compose exec frontend env | grep VITE_

# Verify build-time variables (check built files)
docker compose exec frontend cat /usr/share/nginx/html/index.html | grep -o 'VITE_[^"]*' | head -5
```

#### 5. Check Build Output

```bash
# Check if build files exist
docker compose exec frontend ls -la /usr/share/nginx/html/

# Check build artifacts
docker compose exec frontend ls -la /usr/share/nginx/html/assets/
```

### Common Issues

#### Issue: Frontend Shows Blank Page

**Symptoms**: Browser shows blank page, console errors about missing files or API errors

**Root Causes**:
1. Build failed or incomplete
2. Environment variables not set correctly
3. API base URL incorrect
4. Nginx configuration issue

**Resolution**:

1. **Check Build Logs**:
   ```bash
   docker compose logs frontend | grep -i "build\|error\|failed"
   ```

2. **Rebuild Frontend**:
   ```bash
   docker compose build frontend --no-cache
   docker compose up -d frontend
   ```

3. **Verify Environment Variables**:
   ```bash
   # Check docker-compose.yml
   grep -A 10 "frontend:" docker-compose.yml | grep VITE_

   # Verify in container
   docker compose exec frontend env | grep VITE_API_BASE_URL
   ```

4. **Check Browser Console**:
   - Open browser DevTools (F12)
   - Check Console tab for JavaScript errors
   - Check Network tab for failed API requests
   - Verify `VITE_API_BASE_URL` is correctly set in built files

5. **Verify API Service is Running**:
   ```bash
   docker compose ps api-service
   curl http://localhost:8000/health/
   ```

#### Issue: API Calls Failing (CORS, 404, 502)

**Symptoms**: Network errors in browser console, API requests returning errors

**Root Causes**:
1. API service not running or unhealthy
2. Incorrect `VITE_API_BASE_URL` configuration
3. Nginx proxy misconfiguration
4. CORS issues (if using direct API access)

**Resolution**:

1. **Verify API Service Health**:
   ```bash
   docker compose ps api-service
   docker compose logs api-service --tail=50
   curl http://localhost:8000/health/
   ```

2. **Check API Base URL Configuration**:
   ```bash
   # Development (Vite dev server)
   # Check .env file or environment
   echo $VITE_API_BASE_URL

   # Production (Nginx)
   docker compose exec frontend env | grep VITE_API_BASE_URL
   ```

3. **Verify Nginx Proxy Configuration**:
   ```bash
   # Check nginx.conf
   docker compose exec frontend cat /etc/nginx/conf.d/default.conf | grep -A 10 "location /api"

   # Test proxy manually
   curl -H "Host: localhost" http://localhost:3000/api/v1/health/
   ```

4. **Check CORS Configuration** (if accessing API directly):
   ```bash
   # Check Django CORS settings
   docker compose exec api-service python -c "from django.conf import settings; print(settings.CORS_ALLOWED_ORIGINS)"
   ```

#### Issue: WebSocket Connections Failing

**Symptoms**: WebSocket connection errors, real-time features not working

**Root Causes**:
1. WebSocket proxy misconfiguration
2. API service WebSocket endpoint not available
3. Network/firewall issues

**Resolution**:

1. **Check WebSocket Proxy Configuration**:
   ```bash
   docker compose exec frontend cat /etc/nginx/conf.d/default.conf | grep -A 10 "location /ws"
   ```

2. **Test WebSocket Endpoint**:
   ```bash
   # Test WebSocket connection
   curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: test" -H "Sec-WebSocket-Version: 13" \
     http://localhost:3000/ws/events/
   ```

3. **Verify API Service WebSocket Support**:
   ```bash
   # Check Django channels/WebSocket configuration
   docker compose logs api-service | grep -i "websocket\|channels"
   ```

#### Issue: Build Failures

**Symptoms**: Docker build fails, TypeScript errors, missing dependencies

**Root Causes**:
1. TypeScript compilation errors
2. Missing dependencies
3. Node.js version mismatch
4. Build cache issues

**Resolution**:

1. **Check Build Logs**:
   ```bash
   docker compose build frontend 2>&1 | tee build.log
   grep -i "error\|failed" build.log
   ```

2. **Fix TypeScript Errors**:
   ```bash
   # Run typecheck locally
   cd frontend
   npm run typecheck
   ```

3. **Clear Build Cache**:
   ```bash
   docker compose build frontend --no-cache
   ```

4. **Verify Node.js Version**:
   ```bash
   # Check Dockerfile
   grep "FROM node" frontend/Dockerfile

   # Should match local Node.js version (if building locally)
   node --version
   ```

#### Issue: Environment Variables Not Applied

**Symptoms**: Frontend uses wrong API URL, features not working as expected

**Root Causes**:
1. Environment variables not set in docker-compose.yml
2. Variables set at runtime instead of build time
3. Vite build-time variables not included

**Resolution**:

1. **Check docker-compose.yml Configuration**:
   ```bash
   grep -A 15 "frontend:" docker-compose.yml | grep -E "VITE_|environment:"
   ```

2. **Verify Build-Time Variables**:
   ```bash
   # Vite variables must be prefixed with VITE_ and available at build time
   # Check Dockerfile build stage
   grep -A 5 "RUN npm run build" frontend/Dockerfile
   ```

3. **Rebuild with Correct Variables**:
   ```bash
   # Set variables before build
   export VITE_API_BASE_URL=http://api-service:8000/api/v1
   export VITE_WS_BASE_URL=ws://api-service:8000
   docker compose build frontend
   docker compose up -d frontend
   ```

### Deployment Procedures

#### Development Deployment (Docker Compose)

**Prerequisites**:
- Docker and Docker Compose installed
- Backend services (api-service, postgres, redis) running

**Steps**:

1. **Set Environment Variables**:
   ```bash
   # Create .env file or set in docker-compose.yml
   export VITE_API_BASE_URL=http://api-service:8000/api/v1
   export VITE_WS_BASE_URL=ws://api-service:8000
   export VITE_ENV=development
   ```

2. **Build and Start Frontend**:
   ```bash
   # Build frontend image
   docker compose build frontend

   # Start frontend service
   docker compose up -d frontend

   # Check status
   docker compose ps frontend
   ```

3. **Verify Deployment**:
   ```bash
   # Wait for health check
   sleep 10

   # Check health
   curl http://localhost:3000/

   # Check logs
   docker compose logs frontend --tail=50
   ```

#### Production Deployment (Docker Compose)

**Prerequisites**:
- Production environment variables configured
- Backend services healthy
- SSL certificates (if using HTTPS)

**Steps**:

1. **Configure Production Environment**:
   ```bash
   # Set production variables
   export VITE_API_BASE_URL=https://api.example.com/api/v1
   export VITE_WS_BASE_URL=wss://api.example.com
   export VITE_ENV=production
   ```

2. **Build Production Image**:
   ```bash
   docker compose -f docker-compose.production.yml build frontend
   ```

3. **Deploy**:
   ```bash
   # Start with production config
   docker compose -f docker-compose.production.yml up -d frontend

   # Verify
   curl https://frontend.example.com/
   ```

#### Rollback Procedures

**Rollback to Previous Version**:

1. **Identify Previous Image**:
   ```bash
   # List available images
   docker images | grep hub-frontend

   # Tag of previous version (e.g., hub-frontend:20250129-120000)
   ```

2. **Stop Current Container**:
   ```bash
   docker compose stop frontend
   ```

3. **Start Previous Version**:
   ```bash
   # Update docker-compose.yml to use previous image tag
   # Or pull and tag previous image
   docker tag hub-frontend:previous-tag hub-frontend:latest
   docker compose up -d frontend
   ```

4. **Verify Rollback**:
   ```bash
   # Check version in UI (if version endpoint exists)
   curl http://localhost:3000/

   # Check logs
   docker compose logs frontend --tail=50
   ```

**Quick Rollback (Docker Compose)**:

```bash
# Stop and remove current container
docker compose stop frontend
docker compose rm -f frontend

# Use previous image
docker compose up -d frontend --no-build
```

### Health Checks

#### Container Health Check

The frontend container uses Nginx health check:

```bash
# Health check command (from docker-compose.yml)
wget -q -O /dev/null http://127.0.0.1/ || exit 1

# Manual health check
docker compose exec frontend wget -q -O /dev/null http://127.0.0.1/ && echo "✅ Healthy"
```

#### Application Health Check

**Check Frontend Accessibility**:
```bash
# Check HTTP response
curl -I http://localhost:3000/

# Check API proxy
curl http://localhost:3000/api/v1/health/

# Check WebSocket (if configured)
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:3000/ws/events/
```

**Check Build Integrity**:
```bash
# Verify index.html exists
docker compose exec frontend test -f /usr/share/nginx/html/index.html && echo "✅ index.html exists"

# Verify assets directory
docker compose exec frontend test -d /usr/share/nginx/html/assets && echo "✅ Assets directory exists"

# Check for JavaScript files
docker compose exec frontend ls -la /usr/share/nginx/html/assets/*.js | head -5
```

### Environment Variables

#### Required Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` | `http://api-service:8000/api/v1` |
| `VITE_WS_BASE_URL` | WebSocket base URL | `ws://localhost:8000` | `ws://api-service:8000` |
| `VITE_ENV` | Environment name | `development` | `production` |

#### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_USE_TRAEFIK_ENTRYPOINT` | Use Traefik as entrypoint | unset/false |

#### Configuration Notes

- **Build-Time Variables**: All `VITE_*` variables are embedded at build time. Changes require rebuild.
- **Runtime Variables**: Nginx proxy configuration can be adjusted without rebuild (via nginx.conf).
- **Docker Compose**: Variables set in `docker-compose.yml` `environment:` section are available at build time if passed correctly.

### Troubleshooting Commands

```bash
# Check frontend container status
docker compose ps frontend

# View logs
docker compose logs frontend --tail=100 --follow

# Check environment variables
docker compose exec frontend env | grep VITE_

# Test API connectivity from container
docker compose exec frontend wget -q -O - http://api-service:8000/health/

# Check Nginx configuration
docker compose exec frontend cat /etc/nginx/conf.d/default.conf

# Test Nginx configuration
docker compose exec frontend nginx -t

# Restart frontend
docker compose restart frontend

# Rebuild and restart
docker compose build frontend && docker compose up -d frontend

# Check build artifacts
docker compose exec frontend ls -la /usr/share/nginx/html/

# Check for JavaScript errors (browser console)
# Open http://localhost:3000/ in browser and check DevTools Console
```

### Performance Tuning

1. **Enable Gzip Compression**: Already configured in nginx.conf
2. **Cache Static Assets**: Already configured (1 year cache for static files)
3. **Optimize Build**: Use production build (`npm run build`)
4. **CDN for Static Assets**: Consider CDN for production deployments

### Monitoring

- **Container Health**: Docker health check status
- **Nginx Access Logs**: `docker compose logs frontend | grep "GET\|POST"`
- **Error Logs**: `docker compose logs frontend | grep -i error`
- **API Proxy Errors**: Check Nginx error logs for proxy failures

---

## References

- [Database Indexes Documentation](./DATABASE_INDEXES.md)
- [Monitoring & Observability](./MONITORING.md)
- [Marketplace Connector Deployment Runbook](./runbooks/marketplace-connector-deployment.md)
- [Marketplace Connector Development Guide](./connectors/DEVELOPMENT.md)
- [Marketplace Test Documentation](../hub/apps/integrations/tests/README_MARKETPLACE_TESTS.md)
- [BaaS Platform CLI Usage Guide](../cli/docs/BAAS_USAGE.md) - BaaS troubleshooting commands
- [BaaS Platform SDK Usage Guide](../sdk/python/docs/BAAS_USAGE.md) - BaaS SDK error handling
- [ODH Integration CLI Usage Guide](../cli/docs/ODH_USAGE.md) - ODH troubleshooting commands
- [ODH Integration SDK Usage Guide](../sdk/python/docs/ODH_USAGE.md) - ODH SDK error handling
- [Frontend Architecture Documentation](./UI/FRONTEND_ARCHITECTURE.md)
- [Frontend Deployment Guide](./UI/DEPLOYMENT.md)

