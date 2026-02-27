#!/usr/bin/env bash
# Integration Tests Batched Execution — Run integration tests in batches
# Per TEST_EXECUTION_PLAN.md — Incremental approach: run batches, fix issues, then proceed
#
# Infrastructure: All batches run against the same test environment (docker-compose.test.yml).
# Prerequisites:
#   - Docker and Docker Compose
#   - From repo root: ./scripts/run_integration_tests_batched.sh [--batch=N] [--start-from=N]
#   To clean and restart: ./scripts/clean-test-stack.sh
#
# Requires bash.
if [ -z "${BASH_VERSION:-}" ]; then
  if command -v bash >/dev/null 2>&1; then
    exec bash "$0" "$@"
  fi
  echo "Error: This script requires bash." >&2
  exit 1
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

[[ -f .env.test ]] && set -a && source .env.test && set +a

COMPOSE_FILE=docker-compose.test.yml
export COMPOSE_FILE
API_SVC=api-service-test
COMPOSE_CMD="docker compose -f ${COMPOSE_FILE}"
[[ -f .env.test ]] && COMPOSE_CMD="${COMPOSE_CMD} --env-file .env.test"

export PYTEST_DOCKER_COMPOSE_RUNTIME=1

# Batches: Name|path1|path2|... (pipe-separated)
BATCHES=(
  # Batch 1: Auth, Users, Platform
  "Auth & Platform|tests/integration/test_auth_apis_comprehensive.py|tests/integration/test_users_apis_comprehensive.py|tests/integration/test_platform_apis_integration.py|tests/integration/test_tenant_config_api.py|tests/integration/test_tenant_isolation.py|tests/integration/test_tenant_onboarding_service_comprehensive_validation.py"

  # Batch 2: Assets, Contracts, Datasets
  "Assets & Contracts|tests/integration/test_asset_apis_comprehensive.py|tests/integration/test_simple_asset_creation.py|tests/integration/test_contract_apis_comprehensive.py|tests/integration/test_dataset_apis_comprehensive.py|tests/integration/contracts/"

  # Batch 3: Marketplace
  "Marketplace|tests/integration/test_marketplace_apis_comprehensive.py|tests/integration/test_marketplace_integration.py|tests/integration/test_marketplace_original_use_cases_comprehensive.py|tests/integration/test_advanced_marketplace_new_use_cases_comprehensive.py|tests/integration/test_trust_signals_config_api_comprehensive.py"

  # Batch 4: Jobs & Workers
  "Jobs & Workers|tests/integration/test_job_apis_comprehensive.py|tests/integration/test_worker_service.py|tests/integration/test_job_lifecycle_state_management_validation.py|tests/integration/test_job_monitoring_observability_validation.py|tests/integration/test_job_queue_dashboards.py|tests/integration/test_job_queue_operations_comprehensive.py|tests/integration/test_job_scheduling_queue_management_validation.py|tests/integration/jobs/"

  # Batch 5: Compliance, DQ, Audit
  "Compliance & DQ|tests/integration/test_compliance_apis_comprehensive.py|tests/integration/test_compliance_original_use_cases_comprehensive.py|tests/integration/test_dq_apis_comprehensive.py|tests/integration/test_data_quality_original_use_cases_comprehensive.py|tests/integration/test_audit_apis_comprehensive.py"

  # Batch 6: Files & Storage
  "Files & Storage|tests/integration/test_file_apis_comprehensive.py|tests/integration/test_files_service_comprehensive_validation.py|tests/integration/test_file_storage_operations_comprehensive.py|tests/integration/test_database_operations_comprehensive.py"

  # Batch 7: Monitoring & Observability
  "Monitoring & Observability|tests/integration/test_monitoring_integration.py|tests/integration/test_monitoring_infrastructure.py|tests/integration/test_monitoring_configurations.py|tests/integration/test_monitoring_observability_comprehensive_validation.py|tests/integration/test_prometheus_metrics.py|tests/integration/test_grafana_dashboards.py|tests/integration/test_alertmanager.py|tests/integration/test_metrics_export.py|tests/integration/test_tracing.py|tests/integration/test_jaeger_tracing.py|tests/integration/test_otel_metrics_integration.py|tests/integration/test_phase17_observability_validation.py|tests/integration/test_advanced_observability_new_use_cases_comprehensive.py"

  # Batch 8: Redis, Event Bus, Services
  "Redis & Event Bus|tests/integration/test_redis_service_configuration.py|tests/integration/test_redis_service_configuration_standalone.py|tests/integration/test_redis_separation.py|tests/integration/test_redis_monitoring_setup.py|tests/integration/test_redis_alerts.py|tests/integration/test_redis_backward_compatibility.py|tests/integration/test_redis_streams_comparison.py|tests/integration/test_event_bus_integration.py|tests/integration/test_event_bus_performance.py|tests/integration/test_event_bus_reliability.py|tests/integration/test_service_redis_connections.py|tests/integration/test_service_availability.py|tests/integration/test_service_availability_comprehensive.py|tests/integration/test_service_interactions.py|tests/integration/test_service_to_service_comprehensive.py"

  # Batch 9: API, REST, Middleware
  "API & REST|tests/integration/test_api_endpoints_comprehensive.py|tests/integration/test_api_edge_cases.py|tests/integration/test_api_error_handling.py|tests/integration/test_api_versioning.py|tests/integration/test_api_endpoint_discovery.py|tests/integration/test_api_inventory_verification.py|tests/integration/test_api_inventory_verification_comprehensive.py|tests/integration/test_middleware_integration.py|tests/integration/test_rest_business_rules_alignment.py|tests/integration/test_openapi_completeness.py"

  # Batch 10: Health, Search, Billing
  "Health Search Billing|tests/integration/test_health_integration.py|tests/integration/test_search_apis_comprehensive.py|tests/integration/test_billing_apis_comprehensive.py|tests/integration/test_rate_limiting_integration.py|tests/integration/test_rate_limiting_endpoints.py"

  # Batch 11: ODPS, Semantic, Lineage, Virtualization
  "ODPS Semantic Lineage|tests/integration/test_all_services_odps_integration_comprehensive.py|tests/integration/test_odps_cross_integration.py|tests/integration/test_odps_performance_validation.py|tests/integration/test_odps_semantic_layer_validation.py|tests/integration/test_lineage_service_comprehensive_validation.py|tests/integration/test_virtualization_service_comprehensive_validation.py|tests/integration/test_sparql_standard_vocabularies.py|tests/integration/test_jsonld_context.py|tests/integration/test_uri_resolution_enhanced.py|tests/integration/test_normalization_rdf_flow.py"

  # Batch 12: Docker, Kubernetes, Infra
  "Docker & Kubernetes|tests/integration/test_docker_compose.py|tests/integration/test_docker_compose_test.py|tests/integration/test_docker_compose_dev.py|tests/integration/test_docker_compose_production.py|tests/integration/test_docker_compose_staging.py|tests/integration/test_docker_compose_deployment.py|tests/integration/test_docker_compose_standalone.py|tests/integration/test_kubernetes_config.py|tests/integration/test_kubernetes_deployment.py|tests/integration/test_kubernetes_scaling.py|tests/integration/test_kubernetes_service_discovery.py|tests/integration/test_traefik_routing.py|tests/integration/test_gateway_configurations.py"

  # Batch 13: Scheduled, Workflow, Email, Notifications
  "Scheduled Workflow Notifications|tests/integration/test_scheduled_export_apis_comprehensive.py|tests/integration/test_workflow_integration.py|tests/integration/test_email_integration.py|tests/integration/test_notification_service_comprehensive_validation.py|tests/integration/test_webhook_payloads_and_events_search.py|tests/integration/run_webhook_payloads_tests.py|tests/integration/run_inter_service_communication_tests.py|tests/integration/test_inter_service_communication_search.py"

  # Batch 14: Use Cases, Ecosystem, Documentation
  "Use Cases & Documentation|tests/integration/test_asset_management_original_use_cases_comprehensive.py|tests/integration/test_contract_management_original_use_cases_comprehensive.py|tests/integration/test_data_mesh_new_use_cases_comprehensive.py|tests/integration/test_developer_experience_new_use_cases_comprehensive.py|tests/integration/test_integration_ecosystem_new_use_cases_comprehensive.py|tests/integration/test_transformation_new_use_cases_comprehensive.py|tests/integration/test_virtualization_new_use_cases_comprehensive.py|tests/integration/test_social_features_new_use_cases_comprehensive.py|tests/integration/test_ai_ml_new_use_cases_comprehensive.py|tests/integration/test_advanced_governance_new_use_cases_comprehensive.py|tests/integration/test_documentation_examples_integration.py|tests/integration/test_documentation_guides.py|tests/integration/test_runbook_accuracy.py"

  # Batch 15: Cross-service, Data Engineer, DPO, CLI, Misc
  "Cross-service & Misc|tests/integration/test_cross_service_integration.py|tests/integration/test_cross_service_integration_comprehensive.py|tests/integration/cross_service_test.py|tests/integration/test_data_engineer_api_endpoints.py|tests/integration/test_dpo_api_endpoints.py|tests/integration/test_cli_integration.py|tests/integration/test_client_interface_comprehensive_validation.py|tests/integration/test_service_integration_pattern_compliance.py|tests/integration/test_updated_service_integrations.py|tests/integration/test_external_services.py|tests/integration/test_third_party_apis.py|tests/integration/run_api_client_usage_tests.py|tests/integration/test_api_client_usage_search.py|tests/integration/test_consumer_impact_report.py|tests/integration/test_dual_write_optimization.py|tests/integration/test_dcs_removal_integration.py|tests/integration/test_erasure_workflow_integration.py|tests/integration/test_test_environment_setup.py|tests/integration/test_business_logic_integration_documentation.py|tests/integration/test_services_architecture_documentation.py|tests/integration/test_services_django6.py|tests/integration/test_proposal_implementation_overview.py|tests/integration/test_proposal_success_criteria.py|tests/integration/test_event_bus_architecture_decision_documentation.py|tests/integration/test_event_bus_metrics_exposure.py|tests/integration/test_redis_separation_design_documentation.py|tests/integration/test_redis_configuration_runner.py|tests/integration/test_kafka_rabbitmq_poc.py|tests/integration/test_minimal_timeout_debug.py|tests/integration/profile_contract_creation.py|tests/integration/test_backward_compatibility.py"
)

DATE="${DATE:-$(date +%Y-%m-%d)}"
[[ "$DATE" == "null" ]] || [[ -z "$DATE" ]] && DATE=$(date +%Y-%m-%d)
REPORT_BASE="test_reports_integration/${DATE}"
BATCH_REPORT_BASE="${REPORT_BASE}/batches"
mkdir -p "${BATCH_REPORT_BASE}"

run_batch() {
  local batch_num=$1
  local batch_def="$2"

  IFS='|' read -ra BATCH_PARTS <<< "$batch_def"
  local batch_name="${BATCH_PARTS[0]}"
  local batch_paths=("${BATCH_PARTS[@]:1}")

  local batch_dir="${BATCH_REPORT_BASE}/batch_${batch_num}"
  mkdir -p "$batch_dir"

  echo ""
  echo "=========================================="
  echo "Integration Batch ${batch_num}: ${batch_name}"
  echo "=========================================="
  echo "Paths: ${batch_paths[*]}"
  echo ""

  local batch_start=$(date +%s)
  local batch_log="${batch_dir}/batch_${batch_num}.log"
  local batch_junit="${batch_dir}/junit.xml"

  local path_args=""
  for p in "${batch_paths[@]}"; do
    path_args="${path_args} ${p}"
  done

  set +e
  # USE_PRODUCTION_DB_FOR_SDK_TESTS=1: SDK/CLI tests make HTTP requests to localhost; API server
  # uses hub_test. Tests must use same DB so API can see API keys, tenants, subscriptions.
  $COMPOSE_CMD exec -T "${API_SVC}" bash -c \
    "cd /app && USE_PRODUCTION_DB_FOR_SDK_TESTS=1 LOG_LEVEL=WARNING PYTHONUNBUFFERED=1 PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest \
    ${path_args} \
    -v --docker-compose-runtime --reuse-db --timeout=600 --tb=short \
    --junit-xml=/tmp/junit_integration_batch_${batch_num}.xml" 2>&1 | tee "$batch_log"
  local batch_exit=${PIPESTATUS[0]}
  set -e

  $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_integration_batch_${batch_num}.xml" "$batch_junit" 2>/dev/null || true

  local batch_end=$(date +%s)
  local batch_duration=$((batch_end - batch_start))

  local total=0 failed=0 errors=0 skipped=0
  local summary_lines
  summary_lines=$(grep -E ' in [0-9]+\.?[0-9]*s [\(=]' "$batch_log" 2>/dev/null || true)
  if [[ -n "$summary_lines" ]]; then
    while IFS= read -r summary_line; do
      [[ -z "$summary_line" ]] && continue
      total=$((total + $(echo "$summary_line" | grep -oP "\d+(?= passed)" | head -1 || echo "0")))
      failed=$((failed + $(echo "$summary_line" | grep -oP "\d+(?= failed)" | head -1 || echo "0")))
      errors=$((errors + $(echo "$summary_line" | grep -oP "\d+(?= error)" | head -1 || echo "0")))
      skipped=$((skipped + $(echo "$summary_line" | grep -oP "\d+(?= skipped)" | head -1 || echo "0")))
    done <<< "$summary_lines"
  fi

  _to_int() { printf '%s' "$1" | head -1 | tr -d '\n\r\t ' | grep -oE '[0-9]+' | head -1 || echo "0"; }
  total=$(( $( _to_int "$total" ) + 0 ))
  failed=$(( $( _to_int "$failed" ) + 0 ))
  errors=$(( $( _to_int "$errors" ) + 0 ))
  skipped=$(( $( _to_int "$skipped" ) + 0 ))

  echo ""
  echo "Batch ${batch_num} Summary:"
  echo "  Exit code: ${batch_exit}"
  echo "  Duration: ${batch_duration}s"
  echo "  Passed: ${total}"
  echo "  Failed: ${failed}"
  echo "  Errors: ${errors}"
  echo "  Skipped: ${skipped}"
  echo "  Log: ${batch_log}"
  echo ""

  if [[ "$failed" -eq 0 ]] && [[ "$errors" -eq 0 ]]; then
    return 0
  fi
  return "$batch_exit"
}

# Parse args
START_FROM=1
RUN_ONLY=""
prev_arg=""
for arg in "$@"; do
  case $arg in
    --list-batches)
      for i in "${!BATCHES[@]}"; do
        num=$((i + 1))
        def="${BATCHES[$i]}"
        echo -e "${num}\t${def//|/$'\t'}"
      done
      exit 0
      ;;
    --start-from=*)
      START_FROM="${arg#*=}"
      ;;
    --start-from)
      prev_arg="start-from"
      ;;
    --batch=*)
      RUN_ONLY="${arg#*=}"
      ;;
    --batch)
      prev_arg="batch"
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --start-from=N    Start from batch N (default: 1)"
      echo "  --batch=N         Run only batch N"
      echo "  --list-batches    Print batch definitions and exit"
      echo ""
      echo "Examples:"
      echo "  $0                          # Run all batches"
      echo "  $0 --start-from=5            # Run batches 5 to end"
      echo "  $0 --start-from 5            # Same (space-separated)"
      echo "  $0 --batch=3                 # Run only batch 3"
      exit 0
      ;;
    *)
      if [[ "$prev_arg" == "start-from" ]] && [[ "$arg" =~ ^[0-9]+$ ]]; then
        START_FROM="$arg"
        prev_arg=""
      elif [[ "$prev_arg" == "batch" ]] && [[ "$arg" =~ ^[0-9]+$ ]]; then
        RUN_ONLY="$arg"
        prev_arg=""
      else
        prev_arg=""
      fi
      ;;
  esac
done

echo "=========================================="
echo "Integration Tests Batched Execution"
echo "=========================================="
echo "Date: ${DATE}"
echo "Report base: ${REPORT_BASE}"
echo "Batches: ${#BATCHES[@]}"
echo ""

# Ensure stack is up
echo "Ensuring test stack is up..."
if ! $COMPOSE_CMD ps -q "${API_SVC}" 2>/dev/null | grep -q .; then
  echo "Bringing up test stack..."
  $COMPOSE_CMD up -d --wait 2>&1 || true
fi

TOTAL_BATCHES=${#BATCHES[@]}
FAILED_BATCHES=()

if [[ -n "$RUN_ONLY" ]]; then
  if [[ ! "$RUN_ONLY" =~ ^[0-9]+$ ]] || [[ "$RUN_ONLY" -lt 1 ]] || [[ "$RUN_ONLY" -gt "$TOTAL_BATCHES" ]]; then
    echo "Error: --batch must be 1-${TOTAL_BATCHES}"
    exit 1
  fi
  START_FROM="$RUN_ONLY"
fi

for i in "${!BATCHES[@]}"; do
  CURRENT_BATCH=$((i + 1))
  [[ $CURRENT_BATCH -lt $START_FROM ]] && continue
  [[ -n "$RUN_ONLY" ]] && [[ $CURRENT_BATCH -ne $RUN_ONLY ]] && continue

  run_batch "$CURRENT_BATCH" "${BATCHES[$i]}"
  batch_ret=$?
  if [[ $batch_ret -eq 0 ]]; then
    echo "[PASS] Batch ${CURRENT_BATCH}"
  else
    echo "[FAIL] Batch ${CURRENT_BATCH}"
    FAILED_BATCHES+=("$CURRENT_BATCH")
    echo ""
    echo "Fix failures, then re-run:"
    echo "  ./scripts/run_integration_tests_batched.sh --start-from ${CURRENT_BATCH}"
    echo ""
    exit 1
  fi

  [[ -n "$RUN_ONLY" ]] && [[ $CURRENT_BATCH -eq $RUN_ONLY ]] && break
done

echo "=========================================="
echo "All Integration Batches Complete"
echo "=========================================="
echo "Total batches: ${TOTAL_BATCHES}"
echo "Failed: ${#FAILED_BATCHES[@]}"
if [[ ${#FAILED_BATCHES[@]} -gt 0 ]]; then
  exit 1
fi
exit 0
