# Evidence Collection Plan

**Document Version**: 1.0.0
**Last Updated**: 2026-02-05
**Status**: ✅ Active
**Task**: Phase 1.4 - Evidence Collection Plan Documentation

---

## Table of Contents

1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [Evidence Collection Tools](#evidence-collection-tools)
4. [Evidence Collection Commands](#evidence-collection-commands)
5. [Automated Evidence Collection](#automated-evidence-collection)
6. [CI/CD Integration](#cicd-integration)
7. [Best Practices](#best-practices)

---

## Overview

This document provides comprehensive, engineering-grade evidence collection plan for test execution results, coverage reports, performance metrics, security scans, and other test artifacts. All evidence collection follows best practices and uses real services (no mocks/stubs except at external boundaries).

### Key Principles

1. **Comprehensive Evidence**: Collect all test artifacts, reports, logs, and metrics
2. **Organized Storage**: Use date-based directory structure for easy retrieval
3. **Automated Collection**: Integrate evidence collection into test execution
4. **CI/CD Integration**: Support CI/CD pipeline evidence collection
5. **Engineering-Grade**: Follow TDD, DRY, SOLID, clean code, and Django best practices

### Evidence Types

- **Test Results**: JSON, HTML, JUnit XML reports
- **Coverage Reports**: HTML, XML, JSON, terminal reports
- **Performance Metrics**: CSV, HTML, charts
- **Security Scans**: HTML reports, JSON results
- **E2E Artifacts**: Screenshots, videos, traces
- **Logs**: Test execution logs, error logs, debug logs

---

## Prerequisites

### Required Tools Installation

**Install Evidence Collection Tools**:
```bash
# Install pytest reporting plugins
pip install pytest-html>=4.0.0
pip install pytest-json-report>=1.5.0
pip install allure-pytest>=2.13.0

# Install performance testing tool
pip install locust>=2.17.0

# Or add to requirements-dev.txt:
# pytest-html>=4.0.0
# pytest-json-report>=1.5.0
# allure-pytest>=2.13.0
```

**Note**: These tools are optional but recommended for comprehensive evidence collection. The script will warn if tools are missing but will continue execution. Core pytest functionality (coverage, JUnit XML) works without these plugins.

### Environment Setup

1. **Python Environment**: Python 3.12+ with virtual environment activated
2. **Django Settings**: `DJANGO_SETTINGS_MODULE=hub.settings` must be set
3. **Database**: PostgreSQL database accessible (test database created automatically)
4. **Redis**: Redis server running (for rate limiting and job queue tests)
5. **Docker Compose**: For integration and E2E tests requiring services
6. **Node.js**: Node.js 18+ for frontend tests

---

## Directory Structure

### Evidence Storage Structure

**Layout creation**: The directory structure is produced by one of the following:

- **Phase 12A full run** (recommended): `./scripts/run_phase_12a_full_suites.sh` creates `test_reports_comprehensive/{date}/` with subdirs `unit/`, `integration/`, `e2e/`, `security/`, `performance/`, `concurrency/`, `regression/`, `frontend-unit/`, `frontend-e2e/` and writes summary artifacts `phase_12a_1_summary.json` (backend), `phase_12a_3_summary.json` (security/performance/concurrency/regression). Date default: `YYYY-MM-DD` (set `DATE` to override). Backend-only: `./scripts/run_phase_12a_backend_suites.sh` creates unit, integration, e2e and `phase_12a_1_summary.json`.
- **Layout only (no test run)**: `./scripts/collect_test_evidence.sh` creates the same top-level subdirs plus nested dirs (e.g. `unit/logs`, `e2e/screenshots`, `performance/charts`). Date format: `YYYYmmdd_HHMMSS`. See [RUNBOOKS.md](RUNBOOKS.md#full-test-suite-phase-12a-style).

Report contents are not committed: `test_reports_comprehensive/` is listed in `.gitignore`.

```
test_reports_comprehensive/
├── {date}/                    # Date: YYYY-MM-DD (Phase 12A scripts) or YYYYMMDD_HHMMSS (collect_test_evidence.sh)
│   ├── unit/
│   │   ├── results.json       # pytest-json-report output
│   │   ├── results.html       # pytest-html output
│   │   ├── coverage.html      # pytest-cov HTML report
│   │   ├── coverage.xml       # pytest-cov XML report (for Codecov)
│   │   ├── coverage.json      # pytest-cov JSON report
│   │   ├── junit.xml          # JUnit XML report
│   │   └── logs/              # Test execution logs
│   │       ├── test_execution.log
│   │       └── errors.log
│   ├── integration/
│   │   ├── results.json
│   │   ├── results.html
│   │   ├── coverage.html
│   │   ├── coverage.xml
│   │   ├── coverage.json
│   │   ├── junit.xml
│   │   └── logs/
│   ├── e2e/
│   │   ├── results.json
│   │   ├── results.html
│   │   ├── coverage.html
│   │   ├── coverage.xml
│   │   ├── coverage.json
│   │   ├── junit.xml
│   │   ├── screenshots/       # Playwright screenshots
│   │   │   └── {test_name}/
│   │   ├── videos/             # Playwright videos
│   │   │   └── {test_name}.webm
│   │   ├── traces/            # Playwright traces
│   │   │   └── {test_name}.zip
│   │   └── logs/
│   ├── security/
│   │   ├── results.json
│   │   ├── scan-report.html   # Security scan HTML report
│   │   ├── junit.xml
│   │   └── logs/
│   ├── performance/
│   │   ├── results.json
│   │   ├── metrics.csv        # Locust CSV metrics
│   │   ├── metrics_stats.csv  # Locust stats CSV
│   │   ├── metrics_failures.csv # Locust failures CSV
│   │   ├── report.html        # Locust HTML report
│   │   ├── charts/            # Performance charts
│   │   │   ├── response_time.png
│   │   │   ├── throughput.png
│   │   │   └── rps.png
│   │   └── logs/
│   ├── concurrency/
│   │   ├── results.json
│   │   ├── results.html
│   │   ├── junit.xml
│   │   └── logs/
│   ├── regression/
│   │   ├── results.json
│   │   ├── results.html
│   │   ├── junit.xml
│   │   └── logs/
│   ├── frontend-unit/
│   │   ├── results.json       # Vitest JSON report
│   │   ├── coverage/          # Vitest coverage
│   │   │   ├── lcov.info
│   │   │   └── index.html
│   │   └── logs/
│   ├── frontend-e2e/
│   │   ├── results.json       # Playwright JSON report
│   │   ├── screenshots/
│   │   ├── videos/
│   │   ├── traces/
│   │   └── logs/
│   ├── allure-results/        # Allure test results
│   │   └── {allure_files}
│   ├── summary.json           # Combined test summary (optional)
│   ├── phase_12a_1_summary.json   # Phase 12A backend summary (unit, integration, e2e)
│   ├── phase_12a_3_summary.json   # Phase 12A security/performance/concurrency/regression summary
│   └── README.md              # Execution summary and notes
└── (root test_reports_comprehensive/ is in .gitignore; contents are not committed)
```

When using Phase 12A scripts (`run_phase_12a_full_suites.sh` / `run_phase_12a_backend_suites.sh`), summary artifacts are `phase_12a_1_summary.json` and (for full suite) `phase_12a_3_summary.json`; the test summary report is generated separately via `./scripts/generate_test_summary_report.sh`.

**Test summary report script** (`scripts/generate_test_summary_report.sh` and `scripts/generate_test_summary_report.py`): Accepts a date (e.g. `./scripts/generate_test_summary_report.sh YYYY-MM-DD`) or omits it to use the latest date directory under `test_reports_comprehensive/`. When Phase 12A evidence is present, the script reads `phase_12a_1_summary.json`, `phase_12a_3_summary.json`, and JUnit XML (`{category}/junit.xml`) per category to produce execution summary (date, suite, total/passed/failed/skipped, duration), results by category (unit, integration, E2E, security, performance, concurrency, regression, frontend-unit, frontend-e2e), and **evidence links** to each category directory. Output is markdown (from `docs/TEST_SUMMARY_REPORT_TEMPLATE.md`) written under `test_reports_comprehensive/{date}/TEST_SUMMARY_REPORT_{timestamp}.md`. Documented in RUNBOOKS (Full test suite, Gap remediation validation) and in this plan.

**Canonical layout (Phase 12A)** — the required subdirs and summary artifacts so integration/E2E and evidence collection are consistent:

- **Subdirs**: `unit/`, `integration/`, `e2e/`, `security/`, `performance/`, `concurrency/`, `regression/`, `frontend-unit/`, `frontend-e2e/`
- **Summary artifacts**: `phase_12a_1_summary.json` (backend: unit, integration, e2e), `phase_12a_3_summary.json` (security, performance, concurrency, regression)
- **Backend-only** (`run_phase_12a_backend_suites.sh`): creates `unit/`, `integration/`, `e2e/` and `phase_12a_1_summary.json`
- **Full suite** (`run_phase_12a_full_suites.sh`): creates all subdirs above and both summary JSON files

### Directory Creation Script

**Create Directory Structure**:
```bash
#!/bin/bash
# Create evidence collection directory structure

DATE=$(date +%Y%m%d_%H%M%S)
BASE_DIR="test_reports_comprehensive/${DATE}"

mkdir -p "${BASE_DIR}/unit/logs"
mkdir -p "${BASE_DIR}/integration/logs"
mkdir -p "${BASE_DIR}/e2e/screenshots"
mkdir -p "${BASE_DIR}/e2e/videos"
mkdir -p "${BASE_DIR}/e2e/traces"
mkdir -p "${BASE_DIR}/e2e/logs"
mkdir -p "${BASE_DIR}/security/logs"
mkdir -p "${BASE_DIR}/performance/charts"
mkdir -p "${BASE_DIR}/performance/logs"
mkdir -p "${BASE_DIR}/concurrency/logs"
mkdir -p "${BASE_DIR}/regression/logs"
mkdir -p "${BASE_DIR}/frontend-unit/coverage"
mkdir -p "${BASE_DIR}/frontend-unit/logs"
mkdir -p "${BASE_DIR}/frontend-e2e/screenshots"
mkdir -p "${BASE_DIR}/frontend-e2e/videos"
mkdir -p "${BASE_DIR}/frontend-e2e/traces"
mkdir -p "${BASE_DIR}/frontend-e2e/logs"
mkdir -p "${BASE_DIR}/allure-results"

echo "Created directory structure: ${BASE_DIR}"
```

---

## Evidence Collection Tools

### pytest-html

**Purpose**: Generate HTML test reports with detailed test results

**Installation**:
```bash
pip install pytest-html
```

**Note**: Add to `requirements-dev.txt` if not already present:
```bash
pytest-html>=4.0.0
```

**Features**:
- Self-contained HTML reports (no external dependencies)
- Test result summary with pass/fail/skip counts
- Detailed test execution information
- Error tracebacks and logs
- Test duration information

**Usage**:
```bash
pytest tests/ --html=test_reports_comprehensive/{date}/results.html --self-contained-html
```

**Options**:
- `--self-contained-html`: Embed CSS and JavaScript in HTML file
- `--html=path`: Specify output HTML file path

---

### pytest-cov

**Purpose**: Generate code coverage reports

**Installation**:
```bash
pip install pytest-cov
```

**Features**:
- HTML coverage reports with line-by-line coverage
- XML coverage reports for CI/CD integration (Codecov)
- JSON coverage reports for programmatic analysis
- Terminal coverage reports with missing lines
- Coverage threshold checking

**Usage**:
```bash
pytest tests/ --cov=hub --cov-report=html --cov-report=xml --cov-report=json --cov-report=term-missing
```

**Options**:
- `--cov=package`: Specify package/module to measure coverage
- `--cov-report=html`: Generate HTML coverage report
- `--cov-report=xml`: Generate XML coverage report (for Codecov)
- `--cov-report=json`: Generate JSON coverage report
- `--cov-report=term`: Generate terminal coverage report
- `--cov-report=term-missing`: Show missing lines in terminal
- `--cov-append`: Append to existing coverage file
- `--cov-fail-under=PERCENT`: Fail if coverage below threshold

---

### pytest-json-report

**Purpose**: Generate JSON test reports for programmatic analysis

**Installation**:
```bash
pip install pytest-json-report
```

**Note**: Add to `requirements-dev.txt` if not already present:
```bash
pytest-json-report>=1.5.0
```

**Features**:
- Machine-readable JSON test reports
- Test result summary with statistics
- Detailed test information (name, status, duration, error)
- Integration with CI/CD pipelines
- Test result aggregation

**Usage**:
```bash
pytest tests/ --json-report --json-report-file=test_reports_comprehensive/{date}/results.json
```

**Options**:
- `--json-report`: Enable JSON report generation
- `--json-report-file=path`: Specify output JSON file path
- `--json-report-summary`: Include summary in JSON report
- `--json-report-pretty`: Pretty-print JSON output

---

### pytest-xdist (JUnit XML)

**Purpose**: Generate JUnit XML reports for CI/CD integration

**Installation**:
```bash
pip install pytest-xdist  # Includes junitxml plugin
```

**Features**:
- JUnit XML format for CI/CD tools (Jenkins, GitLab CI, GitHub Actions)
- Test suite and test case information
- Test duration and status
- Error messages and stack traces

**Usage**:
```bash
pytest tests/ --junit-xml=test_reports_comprehensive/{date}/junit.xml
```

**Options**:
- `--junit-xml=path`: Generate JUnit XML report

---

### Playwright

**Purpose**: Screenshots, videos, and traces for E2E tests

**Installation**:
```bash
cd frontend && npm install -D @playwright/test
npx playwright install
```

**Features**:
- Automatic screenshot capture on failure
- Video recording of test execution
- Trace files for debugging (time-travel debugging)
- Screenshot comparison for visual regression
- Network and console logs

**Configuration** (in `playwright.config.ts`):
```typescript
export default defineConfig({
  use: {
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
  outputDir: 'test_reports_comprehensive/{date}/frontend-e2e',
});
```

**Usage**:
```bash
cd frontend && npm run test:e2e
```

---

### Locust

**Purpose**: Performance metrics and load test reports

**Installation**:
```bash
pip install locust
```

**Features**:
- CSV metrics export (response times, RPS, failures)
- HTML performance reports
- Real-time performance charts
- Statistical analysis (min, max, median, p95, p99)
- Failure analysis

**Usage**:
```bash
locust -f tests/performance/locustfile.py \
  --headless \
  -u 100 \
  -r 10 \
  -t 60s \
  --html=test_reports_comprehensive/{date}/performance/report.html \
  --csv=test_reports_comprehensive/{date}/performance/metrics
```

**Options**:
- `--headless`: Run without web UI
- `-u USERS`: Number of concurrent users
- `-r SPAWN_RATE`: Users spawned per second
- `-t DURATION`: Test duration (e.g., 60s, 5m)
- `--html=path`: Generate HTML report
- `--csv=path`: Generate CSV metrics files

---

### Allure

**Purpose**: Advanced test reporting with rich visualizations

**Installation**:
```bash
pip install allure-pytest
# Install Allure command-line tool
# macOS: brew install allure
# Linux: Download from https://github.com/allure-framework/allure2/releases
```

**Note**: Add to `requirements-dev.txt` if not already present:
```bash
allure-pytest>=2.13.0
```

**Features**:
- Rich HTML test reports
- Test history and trends
- Test categories and tags
- Screenshots and attachments
- Test execution timeline
- Environment information

**Usage**:
```bash
# Generate Allure results
pytest tests/ --alluredir=test_reports_comprehensive/{date}/allure-results

# Generate and serve Allure report
allure generate test_reports_comprehensive/{date}/allure-results -o test_reports_comprehensive/{date}/allure-report
allure open test_reports_comprehensive/{date}/allure-report

# Or serve directly
allure serve test_reports_comprehensive/{date}/allure-results
```

**Options**:
- `--alluredir=path`: Directory for Allure results
- `allure generate`: Generate HTML report from results
- `allure serve`: Generate and serve report (temporary)
- `allure open`: Open existing report

---

## Evidence Collection Commands

### Unit Tests

**HTML Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest hub/apps/*/tests/test_*.py -v \
  --html=test_reports_comprehensive/${DATE}/unit/results.html \
  --self-contained-html
```

**JSON Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest hub/apps/*/tests/test_*.py -v \
  --json-report \
  --json-report-file=test_reports_comprehensive/${DATE}/unit/results.json
```

**Coverage Reports**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest hub/apps/*/tests/test_*.py -v \
  --cov=hub \
  --cov-report=html:test_reports_comprehensive/${DATE}/unit/coverage.html \
  --cov-report=xml:test_reports_comprehensive/${DATE}/unit/coverage.xml \
  --cov-report=json:test_reports_comprehensive/${DATE}/unit/coverage.json \
  --cov-report=term-missing
```

**JUnit XML Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest hub/apps/*/tests/test_*.py -v \
  --junit-xml=test_reports_comprehensive/${DATE}/unit/junit.xml
```

**All Reports Combined**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest hub/apps/*/tests/test_*.py -v \
  --html=test_reports_comprehensive/${DATE}/unit/results.html \
  --self-contained-html \
  --json-report \
  --json-report-file=test_reports_comprehensive/${DATE}/unit/results.json \
  --cov=hub \
  --cov-report=html:test_reports_comprehensive/${DATE}/unit/coverage.html \
  --cov-report=xml:test_reports_comprehensive/${DATE}/unit/coverage.xml \
  --cov-report=json:test_reports_comprehensive/${DATE}/unit/coverage.json \
  --junit-xml=test_reports_comprehensive/${DATE}/unit/junit.xml \
  --tb=short
```

---

### Integration Tests

**All Reports Combined**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v \
  --docker-compose-runtime \
  --html=test_reports_comprehensive/${DATE}/integration/results.html \
  --self-contained-html \
  --json-report \
  --json-report-file=test_reports_comprehensive/${DATE}/integration/results.json \
  --cov=hub \
  --cov-report=html:test_reports_comprehensive/${DATE}/integration/coverage.html \
  --cov-report=xml:test_reports_comprehensive/${DATE}/integration/coverage.xml \
  --cov-report=json:test_reports_comprehensive/${DATE}/integration/coverage.json \
  --cov-append \
  --junit-xml=test_reports_comprehensive/${DATE}/integration/junit.xml \
  --tb=short
```

---

### E2E Tests

**All Reports Combined**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/e2e/ -v \
  --docker-compose-runtime \
  --html=test_reports_comprehensive/${DATE}/e2e/results.html \
  --self-contained-html \
  --json-report \
  --json-report-file=test_reports_comprehensive/${DATE}/e2e/results.json \
  --cov=hub \
  --cov-report=html:test_reports_comprehensive/${DATE}/e2e/coverage.html \
  --cov-report=xml:test_reports_comprehensive/${DATE}/e2e/coverage.xml \
  --cov-report=json:test_reports_comprehensive/${DATE}/e2e/coverage.json \
  --cov-append \
  --junit-xml=test_reports_comprehensive/${DATE}/e2e/junit.xml \
  --tb=short
```

**Note**: Playwright screenshots, videos, and traces are automatically collected based on `playwright.config.ts` configuration.

---

### Security Tests

**Security Scan Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest tests/security/ -v -m security \
  --html=test_reports_comprehensive/${DATE}/security/scan-report.html \
  --self-contained-html \
  --json-report \
  --json-report-file=test_reports_comprehensive/${DATE}/security/results.json \
  --junit-xml=test_reports_comprehensive/${DATE}/security/junit.xml \
  --tb=short
```

---

### Performance Tests

**Locust Performance Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
locust -f tests/performance/locustfile.py \
  --headless \
  -u 100 \
  -r 10 \
  -t 60s \
  --html=test_reports_comprehensive/${DATE}/performance/report.html \
  --csv=test_reports_comprehensive/${DATE}/performance/metrics \
  --loglevel INFO \
  --logfile=test_reports_comprehensive/${DATE}/performance/logs/locust.log
```

**Pytest Performance Tests**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest tests/performance/ -v -m performance \
  --html=test_reports_comprehensive/${DATE}/performance/results.html \
  --self-contained-html \
  --json-report \
  --json-report-file=test_reports_comprehensive/${DATE}/performance/results.json \
  --junit-xml=test_reports_comprehensive/${DATE}/performance/junit.xml \
  --tb=short
```

---

### Concurrency Tests

**Concurrency Test Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest hub/apps/*/tests/test_*.py tests/integration/ -v -m concurrency \
  --html=test_reports_comprehensive/${DATE}/concurrency/results.html \
  --self-contained-html \
  --json-report \
  --json-report-file=test_reports_comprehensive/${DATE}/concurrency/results.json \
  --junit-xml=test_reports_comprehensive/${DATE}/concurrency/junit.xml \
  --tb=short
```

---

### Regression Tests

**Regression Test Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest tests/regression/ -v -m regression \
  --html=test_reports_comprehensive/${DATE}/regression/results.html \
  --self-contained-html \
  --json-report \
  --json-report-file=test_reports_comprehensive/${DATE}/regression/results.json \
  --junit-xml=test_reports_comprehensive/${DATE}/regression/junit.xml \
  --tb=short
```

---

### Frontend Unit Tests

**Vitest Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
cd frontend && npm test -- \
  --reporter=json \
  --outputFile=../test_reports_comprehensive/${DATE}/frontend-unit/results.json \
  --coverage \
  --coverage.reporter=html \
  --coverage.reporter=lcov \
  --coverage.reportDir=../test_reports_comprehensive/${DATE}/frontend-unit/coverage
```

---

### Frontend E2E Tests

**Playwright Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
cd frontend && npm run test:e2e -- \
  --reporter=html \
  --output-dir=../test_reports_comprehensive/${DATE}/frontend-e2e \
  --reporter=json \
  --output-file=../test_reports_comprehensive/${DATE}/frontend-e2e/results.json
```

**Note**: Screenshots, videos, and traces are automatically collected based on `playwright.config.ts` configuration.

---

### Allure Report (All Test Types)

**Generate Allure Results**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
pytest tests/ -v \
  --alluredir=test_reports_comprehensive/${DATE}/allure-results
```

**Generate and Serve Allure Report**:
```bash
DATE=$(date +%Y%m%d_%H%M%S)
allure generate test_reports_comprehensive/${DATE}/allure-results \
  -o test_reports_comprehensive/${DATE}/allure-report \
  --clean
allure open test_reports_comprehensive/${DATE}/allure-report
```

---

## Automated Evidence Collection

### Comprehensive Test Execution Script

**Script**: `scripts/collect_test_evidence.sh`

```bash
#!/bin/bash
# Comprehensive Test Evidence Collection Script

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

DATE=$(date +%Y%m%d_%H%M%S)
BASE_DIR="test_reports_comprehensive/${DATE}"

# Create directory structure
mkdir -p "${BASE_DIR}/unit/logs"
mkdir -p "${BASE_DIR}/integration/logs"
mkdir -p "${BASE_DIR}/e2e/screenshots"
mkdir -p "${BASE_DIR}/e2e/videos"
mkdir -p "${BASE_DIR}/e2e/traces"
mkdir -p "${BASE_DIR}/e2e/logs"
mkdir -p "${BASE_DIR}/security/logs"
mkdir -p "${BASE_DIR}/performance/charts"
mkdir -p "${BASE_DIR}/performance/logs"
mkdir -p "${BASE_DIR}/concurrency/logs"
mkdir -p "${BASE_DIR}/regression/logs"
mkdir -p "${BASE_DIR}/frontend-unit/coverage"
mkdir -p "${BASE_DIR}/frontend-unit/logs"
mkdir -p "${BASE_DIR}/frontend-e2e/screenshots"
mkdir -p "${BASE_DIR}/frontend-e2e/videos"
mkdir -p "${BASE_DIR}/frontend-e2e/traces"
mkdir -p "${BASE_DIR}/frontend-e2e/logs"
mkdir -p "${BASE_DIR}/allure-results"

echo "Created directory structure: ${BASE_DIR}"

# Function to collect unit test evidence
collect_unit_evidence() {
    echo "Collecting unit test evidence..."
    pytest hub/apps/*/tests/test_*.py -v \
      --html="${BASE_DIR}/unit/results.html" \
      --self-contained-html \
      --json-report \
      --json-report-file="${BASE_DIR}/unit/results.json" \
      --cov=hub \
      --cov-report=html:"${BASE_DIR}/unit/coverage.html" \
      --cov-report=xml:"${BASE_DIR}/unit/coverage.xml" \
      --cov-report=json:"${BASE_DIR}/unit/coverage.json" \
      --junit-xml="${BASE_DIR}/unit/junit.xml" \
      --tb=short \
      2>&1 | tee "${BASE_DIR}/unit/logs/test_execution.log"
}

# Function to collect integration test evidence
collect_integration_evidence() {
    echo "Collecting integration test evidence..."
    PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/integration/ -v \
      --docker-compose-runtime \
      --html="${BASE_DIR}/integration/results.html" \
      --self-contained-html \
      --json-report \
      --json-report-file="${BASE_DIR}/integration/results.json" \
      --cov=hub \
      --cov-report=html:"${BASE_DIR}/integration/coverage.html" \
      --cov-report=xml:"${BASE_DIR}/integration/coverage.xml" \
      --cov-report=json:"${BASE_DIR}/integration/coverage.json" \
      --cov-append \
      --junit-xml="${BASE_DIR}/integration/junit.xml" \
      --tb=short \
      2>&1 | tee "${BASE_DIR}/integration/logs/test_execution.log"
}

# Function to collect E2E test evidence
collect_e2e_evidence() {
    echo "Collecting E2E test evidence..."
    PYTEST_DOCKER_COMPOSE_RUNTIME=1 pytest tests/e2e/ -v \
      --docker-compose-runtime \
      --html="${BASE_DIR}/e2e/results.html" \
      --self-contained-html \
      --json-report \
      --json-report-file="${BASE_DIR}/e2e/results.json" \
      --cov=hub \
      --cov-report=html:"${BASE_DIR}/e2e/coverage.html" \
      --cov-report=xml:"${BASE_DIR}/e2e/coverage.xml" \
      --cov-report=json:"${BASE_DIR}/e2e/coverage.json" \
      --cov-append \
      --junit-xml="${BASE_DIR}/e2e/junit.xml" \
      --tb=short \
      2>&1 | tee "${BASE_DIR}/e2e/logs/test_execution.log"
}

# Function to collect security test evidence
collect_security_evidence() {
    echo "Collecting security test evidence..."
    pytest tests/security/ -v -m security \
      --html="${BASE_DIR}/security/scan-report.html" \
      --self-contained-html \
      --json-report \
      --json-report-file="${BASE_DIR}/security/results.json" \
      --junit-xml="${BASE_DIR}/security/junit.xml" \
      --tb=short \
      2>&1 | tee "${BASE_DIR}/security/logs/test_execution.log"
}

# Function to collect performance test evidence
collect_performance_evidence() {
    echo "Collecting performance test evidence..."
    locust -f tests/performance/locustfile.py \
      --headless \
      -u 100 \
      -r 10 \
      -t 60s \
      --html="${BASE_DIR}/performance/report.html" \
      --csv="${BASE_DIR}/performance/metrics" \
      --loglevel INFO \
      --logfile="${BASE_DIR}/performance/logs/locust.log" || true
}

# Function to generate summary
generate_summary() {
    echo "Generating test summary..."
    python3 << EOF
import json
import os
from pathlib import Path

summary = {
    "date": "${DATE}",
    "test_types": {}
}

base_dir = Path("${BASE_DIR}")

# Collect results from each test type
for test_type in ["unit", "integration", "e2e", "security", "performance"]:
    json_file = base_dir / test_type / "results.json"
    if json_file.exists():
        with open(json_file) as f:
            data = json.load(f)
            summary["test_types"][test_type] = {
                "total": data.get("summary", {}).get("total", 0),
                "passed": data.get("summary", {}).get("passed", 0),
                "failed": data.get("summary", {}).get("failed", 0),
                "skipped": data.get("summary", {}).get("skipped", 0),
                "duration": data.get("duration", 0)
            }

# Write summary
with open(base_dir / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"Summary generated: {base_dir / 'summary.json'}")
EOF
}

# Main execution
main() {
    # Check tool availability
    check_tool_availability

    collect_unit_evidence || true
    collect_integration_evidence || true
    collect_e2e_evidence || true
    collect_security_evidence || true
    collect_performance_evidence || true
    collect_concurrency_evidence || true
    collect_regression_evidence || true
    collect_frontend_unit_evidence || true
    collect_frontend_e2e_evidence || true
    collect_allure_results || true
    generate_summary

    echo "Evidence collection complete: ${BASE_DIR}"
}

main "$@"
```

---

## CI/CD Integration

Dependency and vulnerability scans (Safety, pip-audit, Bandit, Trivy) run in CI and are documented in [RUNBOOKS.md — Dependency and vulnerability scans](RUNBOOKS.md#dependency-and-vulnerability-scans). Scan results are uploaded as workflow artifacts; they are separate from `test_reports_comprehensive/` but part of the project’s test/evidence and release posture.

### GitHub Actions

**Example Workflow**:
```yaml
name: Test Evidence Collection

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  collect-evidence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Collect test evidence
        run: |
          DATE=$(date +%Y%m%d_%H%M%S)
          BASE_DIR="test_reports_comprehensive/${DATE}"
          mkdir -p "${BASE_DIR}"

          pytest tests/ -v \
            --html="${BASE_DIR}/results.html" \
            --self-contained-html \
            --json-report \
            --json-report-file="${BASE_DIR}/results.json" \
            --cov=hub \
            --cov-report=xml:"${BASE_DIR}/coverage.xml" \
            --junit-xml="${BASE_DIR}/junit.xml"

      - name: Upload test evidence
        uses: actions/upload-artifact@v3
        with:
          name: test-evidence
          path: test_reports_comprehensive/
          retention-days: 30

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: test_reports_comprehensive/${DATE}/coverage.xml
```

---

## Best Practices

### Evidence Collection Best Practices

1. **Use Date-Based Directories**: Organize evidence by execution date for easy retrieval
2. **Collect All Report Formats**: Generate HTML, JSON, XML, and coverage reports
3. **Automate Collection**: Integrate evidence collection into test execution
4. **Store Logs**: Capture all test execution logs for debugging
5. **Preserve Artifacts**: Keep E2E screenshots, videos, and traces
6. **Generate Summaries**: Create summary JSON files for quick status checks
7. **CI/CD Integration**: Upload evidence as artifacts in CI/CD pipelines
8. **Retention Policy**: Define retention periods for test evidence
9. **Version Control**: Don't commit large binary files (videos, screenshots) to git
10. **Documentation**: Include README.md in each date directory with execution notes

### Storage Best Practices

1. **Separate by Test Type**: Organize evidence by test type (unit, integration, E2E)
2. **Include Metadata**: Store test execution metadata (date, version, environment)
3. **Compress Old Reports**: Compress or archive old test evidence
4. **Clean Up**: Regularly clean up old test evidence directories
5. **Backup Important Reports**: Backup critical test evidence

---

## Related Documents

- **[TEST_EXECUTION_PLAN.md](TEST_EXECUTION_PLAN.md)** - Test execution commands and strategies
- **[COMPREHENSIVE_TEST_PLAN.md](COMPREHENSIVE_TEST_PLAN.md)** - Complete test plan documentation
- **[TEST_COVERAGE_MATRIX.md](TEST_COVERAGE_MATRIX.md)** - Test coverage matrix

---

**Document Created**: 2026-02-05
**Last Updated**: 2026-02-05
**Version**: 1.0.0
**Status**: ✅ Active
