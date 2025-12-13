#!/bin/bash
# Comprehensive test runner for fullcontract change
# Discovers all tests, runs them in parallel batches, and fixes failures

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

# Configuration
PARALLEL_WORKERS=${PARALLEL_WORKERS:-4}
MAX_FAILURES=${MAX_FAILURES:-100}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="test_reports_fullcontract_${TIMESTAMP}"
SUMMARY_FILE="${REPORT_DIR}/test_summary.txt"
FAILURES_FILE="${REPORT_DIR}/test_failures.txt"
ERRORS_FILE="${REPORT_DIR}/test_errors.txt"
SKIPS_FILE="${REPORT_DIR}/test_skips.txt"

# Change to project root
cd "$(dirname "$0")/.." || exit 1

# Check and activate virtual environment if it exists
if [ -d "venv-python312-test" ]; then
    echo "Activating virtual environment..."
    source venv-python312-test/bin/activate
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Set PYTHONPATH to include project root
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Set Django settings module
export DJANGO_SETTINGS_MODULE=hub.settings

# Create report directory
mkdir -p "$REPORT_DIR"

echo -e "${BOLD}${BLUE}Full Contract Test Suite - Comprehensive Execution${RESET}"
echo "=================================================="
echo "Timestamp: ${TIMESTAMP}"
echo "Parallel workers: ${PARALLEL_WORKERS}"
echo "Max failures: ${MAX_FAILURES}"
echo "Report directory: ${REPORT_DIR}"
echo ""

# Initialize summary file
cat > "$SUMMARY_FILE" << EOF
Full Contract Test Suite - Comprehensive Execution
==================================================
Timestamp: ${TIMESTAMP}
Python version: $(python3 --version)
Django version: $(python3 -c "import django; print(django.get_version())" 2>/dev/null || echo "Unknown")
Parallel workers: ${PARALLEL_WORKERS}
Max failures: ${MAX_FAILURES}

EOF

# Test discovery - find all test files related to fullcontract
echo -e "${BOLD}${BLUE}Discovering test files...${RESET}"

# Discover all test files dynamically
CONTRACTS_TESTS=($(find hub/apps/contracts/tests -name "test_*.py" -type f | sort))
REGRESSION_TESTS=($(find tests/regression -name "test_*.py" -type f 2>/dev/null | sort))
INTEGRATION_TESTS=($(find tests/integration -name "test_*.py" -type f 2>/dev/null | sort))
E2E_TESTS=($(find tests/e2e -name "test_*.py" -type f 2>/dev/null | sort))
SERVICE_TESTS=($(find services -name "test_*.py" -type f 2>/dev/null | sort))
OTHER_APP_TESTS=($(find hub/apps -name "test_*.py" -type f 2>/dev/null | grep -E "(datasets|dq|governance|observability|search|scheduled_ingestion|assets|versioning|api)" | sort))

# Organize into parallel batches for optimal execution
# Batch 1: Fast unit tests - Core normalization and foundation (Phase 0, 0a, 0b)
declare -a BATCH1_UNIT_TESTS=(
    "hub/apps/contracts/tests/test_versioning.py"
    "hub/apps/contracts/tests/test_spec_detection.py"
    "hub/apps/contracts/tests/test_context_fields.py"
    "hub/apps/contracts/tests/test_source_paths.py"
    "hub/apps/contracts/tests/test_coverage.py"
    "hub/apps/contracts/tests/test_normalizers.py"
    "hub/apps/contracts/tests/test_typed_models.py"
    "hub/apps/contracts/tests/test_validation.py"
    "hub/apps/contracts/tests/test_validation_enrichment.py"
    "hub/apps/contracts/tests/test_jsonfield_queries.py"
    "hub/apps/contracts/tests/test_dcs_rejection.py"
    "hub/apps/contracts/tests/test_migration.py"
)

# Batch 2: Object normalization tests (Phase 1, 2)
declare -a BATCH2_NORMALIZATION_TESTS=(
    "hub/apps/contracts/tests/test_normalization.py"
    "hub/apps/contracts/tests/test_definitions_normalization.py"
    "hub/apps/contracts/tests/test_models_complete_normalization.py"
    "hub/apps/contracts/tests/test_models.py"
    "hub/apps/contracts/tests/test_support_channels_normalization.py"
    "hub/apps/contracts/tests/test_integration_phase2_objects.py"
    "hub/apps/contracts/tests/test_integration_new_mappings.py"
)

# Batch 3: Lineage tests (Phase 3)
declare -a BATCH3_LINEAGE_TESTS=(
    "hub/apps/contracts/tests/test_lineage_extraction.py"
    "hub/apps/contracts/tests/test_lineage_traversal.py"
    "hub/apps/contracts/tests/test_lineage_reference_resolution.py"
    "hub/apps/contracts/tests/test_lineage_visualization.py"
    "hub/apps/contracts/tests/test_integration_lineage.py"
    "hub/apps/contracts/tests/test_impact_analysis.py"
    "hub/apps/contracts/tests/test_impact_visualization.py"
    "hub/apps/contracts/tests/test_impact_api.py"
)

# Batch 4: API and integration tests (Phase 4, 15)
declare -a BATCH4_API_TESTS=(
    "hub/apps/contracts/tests/test_api_filtering_phase15.py"
    "hub/apps/contracts/tests/test_views_filtering_sorting.py"
    "hub/apps/contracts/tests/test_views_validation.py"
    "hub/apps/contracts/tests/test_serializers.py"
    "hub/apps/contracts/tests/test_contract_crud.py"
    "hub/apps/contracts/tests/test_contract_status_rules.py"
    "hub/apps/contracts/tests/test_integration.py"
    "hub/apps/contracts/tests/test_integration_onboarding.py"
    "hub/apps/contracts/tests/test_integration_versioning.py"
    "hub/apps/contracts/tests/test_integration_metrics_phase15.py"
)

# Batch 5: Phase 15 tests (metrics, edge cases, performance)
declare -a BATCH5_PHASE15_TESTS=(
    "hub/apps/contracts/tests/test_normalization_metrics.py"
    "hub/apps/contracts/tests/test_edge_cases_phase15.py"
    "hub/apps/contracts/tests/test_index_performance_phase15.py"
    "hub/apps/contracts/tests/test_performance.py"
    "hub/apps/contracts/tests/test_error_reporting.py"
    "hub/apps/contracts/tests/test_cli_client.py"
)

# Batch 6: Regression tests (Django 6 upgrade)
declare -a BATCH6_REGRESSION_TESTS=(
    "tests/regression/test_api_endpoints.py"
    "tests/regression/test_workflows.py"
    "tests/regression/test_integrations.py"
    "tests/regression/test_middleware.py"
    "tests/regression/test_database_operations.py"
    "tests/regression/test_auth_authorization.py"
    "tests/regression/test_file_storage.py"
    "tests/regression/test_job_queue.py"
    "tests/regression/test_tenant_isolation.py"
)

# Batch 7: Integration tests
declare -a BATCH7_INTEGRATION_TESTS=(
    "tests/integration/test_dcs_removal_integration.py"
    "tests/integration/test_normalization_rdf_flow.py"
    "tests/integration/test_cross_service_integration.py"
    "tests/integration/test_cross_service_integration_comprehensive.py"
    "tests/integration/test_api_endpoints_comprehensive.py"
    "tests/integration/test_api_edge_cases.py"
    "tests/integration/test_services_django6.py"
    "tests/integration/test_otel_metrics_integration.py"
    "tests/integration/test_monitoring_integration.py"
    "tests/integration/test_worker_service.py"
    "tests/integration/test_middleware_integration.py"
    "tests/integration/test_rate_limiting_integration.py"
    "tests/integration/test_jsonld_context.py"
    "tests/integration/test_sparql_standard_vocabularies.py"
    "tests/integration/test_uri_resolution_enhanced.py"
    "tests/integration/test_cli_integration.py"
    "tests/integration/test_email_integration.py"
    "tests/integration/test_tenant_config_api.py"
    "tests/integration/test_tracing.py"
    "tests/integration/test_metrics_export.py"
    "tests/integration/test_monitoring_infrastructure.py"
    "tests/integration/test_database_operations_comprehensive.py"
    "tests/integration/test_file_storage_operations_comprehensive.py"
    "tests/integration/test_job_queue_operations_comprehensive.py"
)

# Batch 8: Service tests
declare -a BATCH8_SERVICE_TESTS=(
    "services/datacontract-service/tests/test_normalization.py"
    "services/datacontract-service/tests/test_integration.py"
    "services/datacontract-service/tests/test_cli_integration.py"
    "services/semantic-service/tests/test_rdf_jsonld_smoke.py"
    "services/semantic-service/tests/test_integration_normalization_rdf.py"
    "services/semantic-service/tests/test_integration_jsonld_context.py"
    "services/semantic-service/tests/test_integration_sparql_vocabularies.py"
    "services/semantic-service/tests/test_mapping.py"
    "services/semantic-service/tests/test_fuseki_integration.py"
    "services/semantic-service/tests/test_standard_vocabularies.py"
    "services/semantic-service/tests/test_uri_resolution.py"
    "services/compliance-service/tests/test_compliance_report.py"
    "services/compliance-service/tests/test_pii_detection.py"
    "services/compliance-service/tests/test_policy_engine.py"
    "services/compliance-service/tests/test_regulatory_mapping.py"
    "services/compliance-service/tests/test_risk_calculation.py"
    "services/dq-service/tests/test_dq_execution.py"
    "services/prefect-integration/tests/test_connectors.py"
    "services/prefect-integration/tests/test_deployment_sync.py"
    "services/prefect-integration/tests/test_e2e.py"
    "services/prefect-integration/tests/test_integration.py"
    "services/worker/tests/test_health.py"
)

# Batch 9: E2E tests - Contract operations
declare -a BATCH9_E2E_CONTRACTS=(
    "tests/e2e/test_contract_operations.py"
    "tests/e2e/test_contract_first_comprehensive.py"
    "tests/e2e/test_contract_only_comprehensive.py"
    "tests/e2e/test_contract_normalization_enhanced_e2e.py"
    "tests/e2e/test_contract_first_flow.py"
    "tests/e2e/test_contract_migration.py"
    "tests/e2e/test_django6_upgrade_critical_workflows.py"
)

# Batch 10: E2E tests - Data and assets
declare -a BATCH10_E2E_DATA=(
    "tests/e2e/test_data_first_comprehensive.py"
    "tests/e2e/test_data_first_flow.py"
    "tests/e2e/test_dataset_operations.py"
    "tests/e2e/test_dataset_version_history.py"
    "tests/e2e/test_asset_operations.py"
    "tests/e2e/test_asset_recommendations_popularity_health_e2e.py"
    "tests/e2e/test_file_operations.py"
    "tests/e2e/test_schema_inference.py"
    "tests/e2e/test_schema_evolution_e2e.py"
    "tests/e2e/test_semantic_versioning_e2e.py"
    "tests/e2e/test_version_impact_rollback_e2e.py"
)

# Batch 11: E2E tests - Services and workflows
declare -a BATCH11_E2E_SERVICES=(
    "tests/e2e/test_dq_service.py"
    "tests/e2e/test_dq_alerting_scorecards_root_cause_e2e.py"
    "tests/e2e/test_dq_anomaly_trend_e2e.py"
    "tests/e2e/test_compliance_service.py"
    "tests/e2e/test_worker_service.py"
    "tests/e2e/test_worker_service_e2e.py"
    "tests/e2e/test_job_orchestration.py"
    "tests/e2e/test_scheduled_ingestion.py"
    "tests/e2e/test_observability_e2e.py"
    "tests/e2e/test_observability.py"
    "tests/e2e/test_search_e2e.py"
    "tests/e2e/test_impact_analysis_e2e.py"
)

# Batch 12: E2E tests - Governance and access
declare -a BATCH12_E2E_GOVERNANCE=(
    "tests/e2e/test_governance_e2e.py"
    "tests/e2e/test_audit_logging.py"
    "tests/e2e/test_audit_compliance_journeys.py"
    "tests/e2e/test_entitlements.py"
    "tests/e2e/test_authentication.py"
    "tests/e2e/test_multi_tenant_isolation.py"
    "tests/e2e/test_tenant_management.py"
    "tests/e2e/test_tenant_config_e2e.py"
    "tests/e2e/test_user_management.py"
)

# Batch 13: E2E tests - Personas
declare -a BATCH13_E2E_PERSONAS=(
    "tests/e2e/test_persona_auditor.py"
    "tests/e2e/test_persona_data_consumer.py"
    "tests/e2e/test_persona_data_provider.py"
    "tests/e2e/test_persona_platform_admin.py"
    "tests/e2e/test_persona_tenant_admin.py"
)

# Batch 14: E2E tests - Marketplace and API
declare -a BATCH14_E2E_MARKETPLACE=(
    "tests/e2e/test_marketplace_comprehensive.py"
    "tests/e2e/test_marketplace_listings.py"
    "tests/e2e/test_marketplace_orders.py"
    "tests/e2e/test_marketplace_purchase_flow.py"
    "tests/e2e/test_rest_api.py"
    "tests/e2e/test_api_documentation.py"
    "tests/e2e/test_graphql_api.py"
    "tests/e2e/test_semantic_layer.py"
    "tests/e2e/test_sdk_python.py"
)

# Batch 15: E2E tests - Infrastructure and monitoring
declare -a BATCH15_E2E_INFRA=(
    "tests/e2e/test_health_checks.py"
    "tests/e2e/test_monitoring_e2e.py"
    "tests/e2e/test_rate_limiting.py"
    "tests/e2e/test_rate_limiting_e2e.py"
    "tests/e2e/test_email_service_e2e.py"
    "tests/e2e/test_cli_e2e.py"
    "tests/e2e/test_error_handling.py"
    "tests/e2e/test_custom_actions_error_handling.py"
    "tests/e2e/test_complete_user_journeys.py"
    "tests/e2e/test_complete_journeys_enhanced.py"
    "tests/e2e/test_cross_capability_e2e.py"
)

# Batch 16: Other app tests (datasets, assets, etc.)
declare -a BATCH16_OTHER_APPS=(
    "hub/apps/datasets/tests/test_version_history.py"
    "hub/apps/datasets/tests/test_version_integration.py"
    "hub/apps/datasets/tests/test_schema_evolution.py"
    "hub/apps/datasets/tests/test_schema_evolution_integration.py"
    "hub/apps/datasets/tests/test_time_travel.py"
    "hub/apps/datasets/tests/test_version_comparison.py"
    "hub/apps/datasets/tests/test_semantic_versioning_enhanced.py"
    "hub/apps/datasets/tests/test_semantic_versioning_integration.py"
    "hub/apps/datasets/tests/test_version_impact.py"
    "hub/apps/datasets/tests/test_version_impact_integration.py"
    "hub/apps/datasets/tests/test_rollback.py"
    "hub/apps/datasets/tests/test_models.py"
    "hub/apps/datasets/tests/test_schema_inference.py"
    "hub/apps/datasets/tests/test_sample_data_extraction.py"
    "hub/apps/assets/tests/test_asset_crud.py"
    "hub/apps/assets/tests/test_asset_activation.py"
    "hub/apps/assets/tests/test_asset_relationships.py"
    "hub/apps/assets/tests/test_dependencies.py"
    "hub/apps/assets/tests/test_health_score.py"
    "hub/apps/assets/tests/test_health_score_integration.py"
    "hub/apps/assets/tests/test_popularity.py"
    "hub/apps/assets/tests/test_popularity_integration.py"
    "hub/apps/assets/tests/test_recommendations.py"
    "hub/apps/assets/tests/test_recommendations_integration.py"
    "hub/apps/assets/tests/test_activation_integration.py"
    "hub/apps/assets/tests/test_models.py"
    "hub/apps/assets/tests/test_serializers.py"
    "hub/apps/api/tests/test_versioning.py"
)

# Function to run test suite
run_test_suite() {
    local suite_name=$1
    shift
    local test_files=("$@")
    
    if [ ${#test_files[@]} -eq 0 ]; then
        echo -e "${YELLOW}⚠️  ${suite_name}: No test files found${RESET}"
        return 0
    fi
    
    echo -e "${BOLD}${BLUE}Running ${suite_name} (${#test_files[@]} files, ${PARALLEL_WORKERS} workers)...${RESET}"
    echo "" >> "$SUMMARY_FILE"
    echo "=== ${suite_name} ===" >> "$SUMMARY_FILE"
    echo "Files: ${#test_files[@]}" >> "$SUMMARY_FILE"
    
    local report_file="${REPORT_DIR}/${suite_name// /_}_${TIMESTAMP}.txt"
    local exit_code=0
    local start_time=$(date +%s)
    
    # Run tests in parallel
    pytest "${test_files[@]}" \
        -v \
        --tb=short \
        -n "${PARALLEL_WORKERS}" \
        --dist=worksteal \
        --maxfail="${MAX_FAILURES}" \
        --junitxml="${REPORT_DIR}/${suite_name// /_}_junit.xml" \
        > "$report_file" 2>&1 || exit_code=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Extract test results
    local total=$(grep -E "collected" "$report_file" | grep -oE "[0-9]+" | head -1 || echo "0")
    local passed=$(grep -E "passed" "$report_file" | tail -1 | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
    local failed=$(grep -E "failed" "$report_file" | tail -1 | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
    local skipped=$(grep -E "skipped" "$report_file" | tail -1 | grep -oE "[0-9]+ skipped" | grep -oE "[0-9]+" || echo "0")
    local errors=$(grep -E "error" "$report_file" | tail -1 | grep -oE "[0-9]+ error" | grep -oE "[0-9]+" || echo "0")
    
    # Extract failures
    if [ "$failed" -gt 0 ] || [ "$errors" -gt 0 ]; then
        echo "" >> "$FAILURES_FILE"
        echo "=== ${suite_name} ===" >> "$FAILURES_FILE"
        grep -E "(FAILED|ERROR)" "$report_file" >> "$FAILURES_FILE" || true
    fi
    
    # Extract skips
    if [ "$skipped" -gt 0 ]; then
        echo "" >> "$SKIPS_FILE"
        echo "=== ${suite_name} ===" >> "$SKIPS_FILE"
        grep -E "SKIPPED" "$report_file" >> "$SKIPS_FILE" || true
    fi
    
    # Update summary
    echo "Total: ${total}, Passed: ${passed}, Failed: ${failed}, Errors: ${errors}, Skipped: ${skipped}, Duration: ${duration}s" >> "$SUMMARY_FILE"
    
    if [ "$exit_code" -eq 0 ]; then
        echo -e "${GREEN}✅ ${suite_name}: ${passed} passed, ${skipped} skipped (${duration}s)${RESET}"
    else
        echo -e "${RED}❌ ${suite_name}: ${failed} failed, ${errors} errors, ${passed} passed, ${skipped} skipped (${duration}s)${RESET}"
    fi
    
    return $exit_code
}

# Initialize failure tracking
echo "Test Failures - $(date)" > "$FAILURES_FILE"
echo "======================" >> "$FAILURES_FILE"
echo "" > "$ERRORS_FILE"
echo "Test Skips - $(date)" > "$SKIPS_FILE"
echo "======================" >> "$SKIPS_FILE"

# Run test suites in parallel batches
TOTAL_FAILURES=0
TOTAL_ERRORS=0

echo "" >> "$SUMMARY_FILE"
echo "=== Test Execution (16 Parallel Batches) ===" >> "$SUMMARY_FILE"
echo "Total test files discovered:" >> "$SUMMARY_FILE"
echo "  - Contracts tests: ${#CONTRACTS_TESTS[@]}" >> "$SUMMARY_FILE"
echo "  - Regression tests: ${#REGRESSION_TESTS[@]}" >> "$SUMMARY_FILE"
echo "  - Integration tests: ${#INTEGRATION_TESTS[@]}" >> "$SUMMARY_FILE"
echo "  - E2E tests: ${#E2E_TESTS[@]}" >> "$SUMMARY_FILE"
echo "  - Service tests: ${#SERVICE_TESTS[@]}" >> "$SUMMARY_FILE"
echo "  - Other app tests: ${#OTHER_APP_TESTS[@]}" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

# Run all batches
run_test_suite "Batch 1: Foundation Unit Tests" "${BATCH1_UNIT_TESTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 2: Object Normalization Tests" "${BATCH2_NORMALIZATION_TESTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 3: Lineage Tests" "${BATCH3_LINEAGE_TESTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 4: API and Integration Tests" "${BATCH4_API_TESTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 5: Phase 15 Tests" "${BATCH5_PHASE15_TESTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 6: Regression Tests" "${BATCH6_REGRESSION_TESTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 7: Integration Tests" "${BATCH7_INTEGRATION_TESTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 8: Service Tests" "${BATCH8_SERVICE_TESTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 9: E2E Contract Tests" "${BATCH9_E2E_CONTRACTS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 10: E2E Data Tests" "${BATCH10_E2E_DATA[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 11: E2E Service Tests" "${BATCH11_E2E_SERVICES[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 12: E2E Governance Tests" "${BATCH12_E2E_GOVERNANCE[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 13: E2E Persona Tests" "${BATCH13_E2E_PERSONAS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 14: E2E Marketplace Tests" "${BATCH14_E2E_MARKETPLACE[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 15: E2E Infrastructure Tests" "${BATCH15_E2E_INFRA[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
run_test_suite "Batch 16: Other App Tests" "${BATCH16_OTHER_APPS[@]}" || TOTAL_FAILURES=$((TOTAL_FAILURES + 1))

# Final summary
echo "" >> "$SUMMARY_FILE"
echo "=== Final Summary ===" >> "$SUMMARY_FILE"
echo "Total failures: ${TOTAL_FAILURES}" >> "$SUMMARY_FILE"
echo "Report directory: ${REPORT_DIR}" >> "$SUMMARY_FILE"

echo ""
echo -e "${BOLD}${BLUE}Test Execution Complete${RESET}"
echo "=================================================="
echo "Summary: ${SUMMARY_FILE}"
echo "Failures: ${FAILURES_FILE}"
echo "Skips: ${SKIPS_FILE}"
echo ""

if [ "$TOTAL_FAILURES" -eq 0 ]; then
    echo -e "${GREEN}✅ All test suites passed!${RESET}"
    exit 0
else
    echo -e "${RED}❌ Some test suites failed. Check ${FAILURES_FILE} for details.${RESET}"
    exit 1
fi

