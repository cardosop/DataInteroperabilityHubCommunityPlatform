#!/bin/bash
# Comprehensive Test Evidence Collection Script
# Collects all test evidence (reports, coverage, logs, artifacts) in organized directory structure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

DATE=$(date +%Y%m%d_%H%M%S)
BASE_DIR="test_reports_comprehensive/${DATE}"

# Create directory structure
echo "Creating directory structure: ${BASE_DIR}"
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

# Function to collect unit test evidence
collect_unit_evidence() {
    echo "=========================================="
    echo "Collecting unit test evidence..."
    echo "=========================================="

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
      2>&1 | tee "${BASE_DIR}/unit/logs/test_execution.log" || true
}

# Function to collect integration test evidence
collect_integration_evidence() {
    echo "=========================================="
    echo "Collecting integration test evidence..."
    echo "=========================================="

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
      2>&1 | tee "${BASE_DIR}/integration/logs/test_execution.log" || true
}

# Function to collect E2E test evidence
collect_e2e_evidence() {
    echo "=========================================="
    echo "Collecting E2E test evidence..."
    echo "=========================================="

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
      2>&1 | tee "${BASE_DIR}/e2e/logs/test_execution.log" || true
}

# Function to collect security test evidence
collect_security_evidence() {
    echo "=========================================="
    echo "Collecting security test evidence..."
    echo "=========================================="

    pytest tests/security/ -v -m security \
      --html="${BASE_DIR}/security/scan-report.html" \
      --self-contained-html \
      --json-report \
      --json-report-file="${BASE_DIR}/security/results.json" \
      --junit-xml="${BASE_DIR}/security/junit.xml" \
      --tb=short \
      2>&1 | tee "${BASE_DIR}/security/logs/test_execution.log" || true
}

# Function to collect performance test evidence
collect_performance_evidence() {
    echo "=========================================="
    echo "Collecting performance test evidence..."
    echo "=========================================="

    # Check if API server is running
    if ! curl -f http://localhost:8000/health/ &> /dev/null; then
        echo "⚠️  API server not running. Skipping performance tests."
        return
    fi

    locust -f tests/performance/locustfile.py \
      --headless \
      -u 50 \
      -r 5 \
      -t 60s \
      --html="${BASE_DIR}/performance/report.html" \
      --csv="${BASE_DIR}/performance/metrics" \
      --loglevel INFO \
      --logfile="${BASE_DIR}/performance/logs/locust.log" || true
}

# Function to collect concurrency test evidence
collect_concurrency_evidence() {
    echo "=========================================="
    echo "Collecting concurrency test evidence..."
    echo "=========================================="

    pytest hub/apps/*/tests/test_*.py tests/integration/ -v -m concurrency \
      --html="${BASE_DIR}/concurrency/results.html" \
      --self-contained-html \
      --json-report \
      --json-report-file="${BASE_DIR}/concurrency/results.json" \
      --junit-xml="${BASE_DIR}/concurrency/junit.xml" \
      --tb=short \
      2>&1 | tee "${BASE_DIR}/concurrency/logs/test_execution.log" || true
}

# Function to collect regression test evidence
collect_regression_evidence() {
    echo "=========================================="
    echo "Collecting regression test evidence..."
    echo "=========================================="

    pytest tests/regression/ -v -m regression \
      --html="${BASE_DIR}/regression/results.html" \
      --self-contained-html \
      --json-report \
      --json-report-file="${BASE_DIR}/regression/results.json" \
      --junit-xml="${BASE_DIR}/regression/junit.xml" \
      --tb=short \
      2>&1 | tee "${BASE_DIR}/regression/logs/test_execution.log" || true
}

# Function to collect frontend unit test evidence
collect_frontend_unit_evidence() {
    echo "=========================================="
    echo "Collecting frontend unit test evidence..."
    echo "=========================================="

    if [ ! -d "frontend" ]; then
        echo "⚠️  Frontend directory not found. Skipping frontend unit tests."
        return
    fi

    cd frontend && npm test -- \
      --reporter=json \
      --outputFile="../${BASE_DIR}/frontend-unit/results.json" \
      --coverage \
      --coverage.reporter=html \
      --coverage.reporter=lcov \
      --coverage.reportDir="../${BASE_DIR}/frontend-unit/coverage" \
      2>&1 | tee "../${BASE_DIR}/frontend-unit/logs/test_execution.log" || true

    cd ..
}

# Function to collect frontend E2E test evidence
collect_frontend_e2e_evidence() {
    echo "=========================================="
    echo "Collecting frontend E2E test evidence..."
    echo "=========================================="

    if [ ! -d "frontend" ]; then
        echo "⚠️  Frontend directory not found. Skipping frontend E2E tests."
        return
    fi

    # Check if backend services are running
    if ! curl -f http://localhost:8000/health/ &> /dev/null; then
        echo "⚠️  Backend services not running. Skipping frontend E2E tests."
        return
    fi

    cd frontend && npm run test:e2e -- \
      --reporter=html \
      --output-dir="../${BASE_DIR}/frontend-e2e" \
      --reporter=json \
      --output-file="../${BASE_DIR}/frontend-e2e/results.json" \
      2>&1 | tee "../${BASE_DIR}/frontend-e2e/logs/test_execution.log" || true

    cd ..
}

# Function to collect Allure results
collect_allure_results() {
    echo "=========================================="
    echo "Collecting Allure test results..."
    echo "=========================================="

    pytest tests/ -v \
      --alluredir="${BASE_DIR}/allure-results" \
      2>&1 | tee "${BASE_DIR}/allure-results/collection.log" || true
}

# Function to check tool availability
check_tool_availability() {
    echo "=========================================="
    echo "Checking tool availability..."
    echo "=========================================="

    local missing_tools=()

    # Check pytest-html
    if ! python3 -c "import pytest_html" 2>/dev/null; then
        missing_tools+=("pytest-html")
        echo "⚠️  pytest-html not installed (optional for HTML reports)"
    fi

    # Check pytest-json-report
    if ! python3 -c "import pytest_jsonreport" 2>/dev/null; then
        missing_tools+=("pytest-json-report")
        echo "⚠️  pytest-json-report not installed (optional for JSON reports)"
    fi

    # Check allure-pytest
    if ! python3 -c "import allure" 2>/dev/null; then
        missing_tools+=("allure-pytest")
        echo "⚠️  allure-pytest not installed (optional for Allure reports)"
    fi

    # Check locust
    if ! command -v locust &> /dev/null; then
        missing_tools+=("locust")
        echo "⚠️  locust not installed (optional for performance tests)"
    fi

    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo ""
        echo "Note: Some optional tools are missing. Install with:"
        echo "  pip install pytest-html pytest-json-report allure-pytest"
        echo "  pip install locust  # For performance tests"
        echo ""
    else
        echo "✅ All tools available"
    fi

    echo ""
}

# Function to generate summary
generate_summary() {
    echo "=========================================="
    echo "Generating test summary..."
    echo "=========================================="

    python3 << EOF
import json
import os
from pathlib import Path
from datetime import datetime

summary = {
    "date": "${DATE}",
    "timestamp": datetime.now().isoformat(),
    "test_types": {}
}

base_dir = Path("${BASE_DIR}")

# Collect results from each test type
for test_type in ["unit", "integration", "e2e", "security", "performance", "concurrency", "regression"]:
    json_file = base_dir / test_type / "results.json"
    if json_file.exists():
        try:
            with open(json_file) as f:
                data = json.load(f)
                summary["test_types"][test_type] = {
                    "total": data.get("summary", {}).get("total", 0),
                    "passed": data.get("summary", {}).get("passed", 0),
                    "failed": data.get("summary", {}).get("failed", 0),
                    "skipped": data.get("summary", {}).get("skipped", 0),
                    "duration": data.get("duration", 0)
                }
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            summary["test_types"][test_type] = {"error": str(e)}

# Calculate totals
total_tests = sum(t.get("total", 0) for t in summary["test_types"].values())
total_passed = sum(t.get("passed", 0) for t in summary["test_types"].values())
total_failed = sum(t.get("failed", 0) for t in summary["test_types"].values())
total_skipped = sum(t.get("skipped", 0) for t in summary["test_types"].values())

summary["totals"] = {
    "total": total_tests,
    "passed": total_passed,
    "failed": total_failed,
    "skipped": total_skipped
}

# Write summary
with open(base_dir / "summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"✅ Summary generated: {base_dir / 'summary.json'}")
print(f"   Total Tests: {total_tests}")
print(f"   Passed: {total_passed}")
print(f"   Failed: {total_failed}")
print(f"   Skipped: {total_skipped}")
EOF
}

# Function to create README
create_readme() {
    cat > "${BASE_DIR}/README.md" << EOF
# Test Execution Evidence - ${DATE}

## Execution Summary

**Date**: ${DATE}
**Directory**: \`${BASE_DIR}\`

## Test Types

- **Unit Tests**: \`unit/\`
- **Integration Tests**: \`integration/\`
- **E2E Tests**: \`e2e/\`
- **Security Tests**: \`security/\`
- **Performance Tests**: \`performance/\`
- **Concurrency Tests**: \`concurrency/\`
- **Regression Tests**: \`regression/\`
- **Frontend Unit Tests**: \`frontend-unit/\`
- **Frontend E2E Tests**: \`frontend-e2e/\`
- **Allure Results**: \`allure-results/\`

## Reports

- **HTML Reports**: \`{test_type}/results.html\`
- **JSON Reports**: \`{test_type}/results.json\`
- **Coverage Reports**: \`{test_type}/coverage.html\`
- **JUnit XML**: \`{test_type}/junit.xml\`
- **Summary**: \`summary.json\`

## Viewing Reports

\`\`\`bash
# View HTML report
open ${BASE_DIR}/unit/results.html

# View coverage report
open ${BASE_DIR}/unit/coverage.html

# View summary
cat ${BASE_DIR}/summary.json | jq
\`\`\`

## Notes

Add execution notes here...
EOF
}

# Main execution
main() {
    echo "=========================================="
    echo "Comprehensive Test Evidence Collection"
    echo "=========================================="
    echo "Date: ${DATE}"
    echo "Base Directory: ${BASE_DIR}"
    echo ""

    # Check tool availability
    check_tool_availability

    # Collect evidence (continue on failure)
    collect_unit_evidence
    collect_integration_evidence
    collect_e2e_evidence
    collect_security_evidence
    collect_performance_evidence
    collect_concurrency_evidence
    collect_regression_evidence
    collect_frontend_unit_evidence
    collect_frontend_e2e_evidence
    collect_allure_results

    # Generate summary and README
    generate_summary
    create_readme

    echo ""
    echo "=========================================="
    echo "Evidence collection complete!"
    echo "=========================================="
    echo "Evidence directory: ${BASE_DIR}"
    echo "Summary: ${BASE_DIR}/summary.json"
    echo ""
}

main "$@"
