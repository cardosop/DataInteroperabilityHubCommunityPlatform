#!/usr/bin/env bash
# E2E Tests Batched Execution — Run backend E2E tests in batches
# Prevents timeouts and resource exhaustion when running the full suite at once.
#
# Infrastructure: All batches run against the same test environment (docker-compose.test.yml).
# Prerequisites:
#   - Docker and Docker Compose
#   - From repo root: ./scripts/run_e2e_tests_batched.sh [--batch=N] [--start-from=N]
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

# Batches: Name|path1|path2|... (pipe-separated). Excludes test_docker_compose_e2e.py (runs outside container).
BATCHES=(
  # Batch 1: API, Docs, REST, OpenAPI
  "API & Docs|tests/e2e/test_api_documentation.py|tests/e2e/test_api_usability_comprehensive.py|tests/e2e/test_rest_api.py|tests/e2e/test_openapi_spec_comprehensive.py"

  # Batch 2: Auth (split from Errors to reduce memory pressure; exit 137 = OOM on constrained hosts)
  "Auth|tests/e2e/test_authentication.py|tests/e2e/test_auth_authorization_comprehensive.py"

  # Batch 3: Error handling
  "Errors|tests/e2e/test_error_handling.py|tests/e2e/test_error_handling_comprehensive.py"

  # Batch 4: Assets, Contracts (core)
  "Assets & Contracts|tests/e2e/test_asset_operations.py|tests/e2e/test_asset_recommendations_popularity_health_e2e.py|tests/e2e/test_contract_operations.py|tests/e2e/test_contract_first_flow.py|tests/e2e/test_contract_first_comprehensive.py|tests/e2e/test_contract_only_comprehensive.py"

  # Batch 5: Contract migration, normalization, schema
  "Contract Schema|tests/e2e/test_contract_migration.py|tests/e2e/test_contract_normalization_enhanced_e2e.py|tests/e2e/test_schema_inference.py|tests/e2e/test_schema_evolution_e2e.py"

  # Batch 6: Datasets, Files
  "Datasets & Files|tests/e2e/test_dataset_operations.py|tests/e2e/test_dataset_version_history.py|tests/e2e/test_file_operations.py"

  # Batch 7: DQ, Compliance, Audit
  "DQ Compliance Audit|tests/e2e/test_dq_service.py|tests/e2e/test_dq_alerting_scorecards_root_cause_e2e.py|tests/e2e/test_dq_anomaly_trend_e2e.py|tests/e2e/test_compliance_service.py|tests/e2e/test_audit_logging.py|tests/e2e/test_audit_compliance_journeys.py"

  # Batch 8: Jobs, Worker
  "Jobs & Worker|tests/e2e/test_job_orchestration.py|tests/e2e/test_worker_service.py|tests/e2e/test_worker_service_e2e.py"

  # Batch 9: Marketplace
  "Marketplace|tests/e2e/test_marketplace_comprehensive.py|tests/e2e/test_marketplace_listings.py|tests/e2e/test_marketplace_orders.py|tests/e2e/test_marketplace_purchase_flow.py|tests/e2e/test_marketplace_use_cases.py|tests/e2e/test_marketplace_integration.py|tests/e2e/test_entitlements.py"

  # Batch 10: Tenant, User, Multi-tenant
  "Tenant & User|tests/e2e/test_tenant_management.py|tests/e2e/test_tenant_config_e2e.py|tests/e2e/test_user_management.py|tests/e2e/test_multi_tenant_isolation.py"

  # Batch 11: Personas (DPO, DE, CPO, DC, TA, PA, Dev, Aud)
  "Personas Core|tests/e2e/test_persona_data_provider.py|tests/e2e/test_persona_data_consumer.py|tests/e2e/test_persona_auditor.py|tests/e2e/test_persona_platform_admin.py|tests/e2e/test_persona_tenant_admin.py|tests/e2e/test_persona_dpo_comprehensive.py|tests/e2e/test_persona_data_engineer_comprehensive.py|tests/e2e/test_persona_cpo_comprehensive.py|tests/e2e/test_persona_dc_comprehensive.py|tests/e2e/test_persona_dev_comprehensive.py|tests/e2e/test_persona_pa_comprehensive.py|tests/e2e/test_persona_ta_comprehensive.py|tests/e2e/test_persona_aud_comprehensive.py"

  # Batch 12: Personas (new journeys, failure paths, workflows)
  "Personas Journeys|tests/e2e/test_persona_failure_paths_comprehensive.py|tests/e2e/test_persona_workflows_odps_enhanced.py|tests/e2e/test_new_user_journeys_comprehensive.py"

  # Batch 13: User journeys, complete journeys
  "User Journeys|tests/e2e/test_user_journeys_comprehensive.py|tests/e2e/test_complete_user_journeys.py|tests/e2e/test_complete_journeys_enhanced.py"

  # Batch 14: Data first, contract first, business rules
  "Data Flows|tests/e2e/test_data_first_flow.py|tests/e2e/test_data_first_comprehensive.py|tests/e2e/test_business_rules_validation_real_scenarios_e2e.py"

  # Batch 15: ODPS, Enhanced journeys
  "ODPS & Enhanced|tests/e2e/test_odps_journeys_comprehensive.py|tests/e2e/test_enhanced_journeys_with_odps.py|tests/e2e/test_enhanced_use_cases_with_odps.py"

  # Batch 16: Semantic, GraphQL, Search
  "Semantic & GraphQL|tests/e2e/test_semantic_layer.py|tests/e2e/test_semantic_versioning_e2e.py|tests/e2e/test_graphql_api.py|tests/e2e/test_graphql_odps_fields.py|tests/e2e/test_graphql_odps_mutations.py|tests/e2e/test_search_e2e.py|tests/e2e/test_external_resource_semantic_discovery.py"

  # Batch 17: Monitoring, Observability, Health
  "Monitoring & Observability|tests/e2e/test_monitoring_e2e.py|tests/e2e/test_observability.py|tests/e2e/test_observability_e2e.py|tests/e2e/test_observability_event_publishing_e2e.py|tests/e2e/test_health_checks.py"

  # Batch 18: Scheduled, Email, Rate limit, Cross-capability
  "Scheduled & Services|tests/e2e/test_scheduled_ingestion.py|tests/e2e/test_scheduled_ingestion_use_cases.py|tests/e2e/test_scheduled_export.py|tests/e2e/test_email_service_e2e.py|tests/e2e/test_rate_limiting.py|tests/e2e/test_rate_limiting_e2e.py|tests/e2e/test_cross_capability_e2e.py"

  # Batch 19: Versioning, Lineage, Impact, Governance
  "Versioning & Governance|tests/e2e/test_versioning_use_cases.py|tests/e2e/test_version_impact_rollback_e2e.py|tests/e2e/test_lineage_use_cases_e2e.py|tests/e2e/test_impact_analysis_e2e.py|tests/e2e/test_governance_e2e.py"

  # Batch 20: Workflows, Security, Custom actions, Phase25, Django6
  "Workflows & Misc|tests/e2e/test_workflow_business_rules_e2e.py|tests/e2e/test_workflow_error_recovery_compensation_e2e.py|tests/e2e/test_workflow_observability_business_rules_e2e.py|tests/e2e/test_workflow_performance_business_rules_e2e.py|tests/e2e/test_workflow_security_business_rules_e2e.py|tests/e2e/test_workflow_use_case_integration_e2e.py|tests/e2e/test_workflow_user_journey_integration_e2e.py|tests/e2e/test_security_comprehensive.py|tests/e2e/test_custom_actions_error_handling.py|tests/e2e/test_phase25_billing_e2e.py|tests/e2e/test_phase25_gdpr_erasure_e2e.py|tests/e2e/test_phase25_tenant_onboarding_e2e.py|tests/e2e/test_django6_upgrade_critical_workflows.py"

  # Batch 21: CLI, SDK, Performance, Model serving
  "CLI SDK Performance|tests/e2e/test_cli_e2e.py|tests/e2e/test_sdk_python.py|tests/e2e/test_performance_comprehensive.py|tests/e2e/test_model_serving_cli_sdk_e2e.py|tests/e2e/test_odh_cli_sdk_e2e.py"
)

DATE="${DATE:-$(date +%Y-%m-%d)}"
[[ "$DATE" == "null" ]] || [[ -z "$DATE" ]] && DATE=$(date +%Y-%m-%d)
REPORT_BASE="test_reports_e2e/${DATE}"
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
  echo "E2E Batch ${batch_num}: ${batch_name}"
  echo "=========================================="
  echo "Paths: ${batch_paths[*]}"
  echo ""

  local batch_start=$(date +%s)
  local batch_log="${batch_dir}/batch_${batch_num}.log"
  local batch_junit="${batch_dir}/junit.xml"

  local path_args=""
  for p in "${batch_paths[@]}"; do
    [[ -f "$p" ]] && path_args="${path_args} ${p}"
  done

  if [[ -z "${path_args// }" ]]; then
    echo "No valid paths in batch ${batch_num}, skipping."
    return 0
  fi

  set +e
  $COMPOSE_CMD exec -T "${API_SVC}" bash -c \
    "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings PYTHONDONTWRITEBYTECODE=1 python -m pytest \
    ${path_args} \
    -v --docker-compose-runtime --reuse-db --timeout=900 --tb=short --no-cov \
    --junit-xml=/tmp/junit_e2e_batch_${batch_num}.xml" 2>&1 | tee "$batch_log"
  local batch_exit=${PIPESTATUS[0]}
  set -e

  $COMPOSE_CMD cp "${API_SVC}:/tmp/junit_e2e_batch_${batch_num}.xml" "$batch_junit" 2>/dev/null || true

  local batch_end=$(date +%s)
  local batch_duration=$((batch_end - batch_start))

  echo ""
  echo "Batch ${batch_num} Summary:"
  echo "  Exit code: ${batch_exit}"
  echo "  Duration: ${batch_duration}s"
  echo "  Log: ${batch_log}"
  echo ""

  if [[ "$batch_exit" -eq 0 ]]; then
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
      echo "Run backend E2E tests in batches to prevent timeouts and resource exhaustion."
      echo ""
      echo "Options:"
      echo "  --start-from=N    Start from batch N (default: 1)"
      echo "  --batch=N         Run only batch N"
      echo "  --list-batches    Print batch definitions and exit"
      echo ""
      echo "Examples:"
      echo "  $0                          # Run all batches"
      echo "  $0 --start-from=5            # Run batches 5 to end"
      echo "  $0 --batch=3                 # Run only batch 3"
      echo ""
      echo "Reports: test_reports_e2e/<date>/batches/"
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
echo "E2E Tests Batched Execution"
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

  # Batch 17 (Monitoring) needs Grafana; ensure it's up before running
  if [[ "$CURRENT_BATCH" -eq 17 ]]; then
    echo "Ensuring Grafana is up for monitoring tests..."
    $COMPOSE_CMD up -d grafana-test 2>&1 || true
    sleep 20
  fi

  # Batch 18 (Scheduled export) needs Prefect + HUB_WORKER_API_KEY; ensure services are up
  if [[ "$CURRENT_BATCH" -eq 18 ]]; then
    echo "Ensuring Prefect integration and worker are up for scheduled export tests..."
    $COMPOSE_CMD up -d api-service-test prefect-integration-service-test prefect-worker-test 2>&1 || true
    sleep 120
  fi

  run_batch "$CURRENT_BATCH" "${BATCHES[$i]}"
  batch_ret=$?
  if [[ $batch_ret -eq 0 ]]; then
    echo "[PASS] Batch ${CURRENT_BATCH}"
  else
    echo "[FAIL] Batch ${CURRENT_BATCH}"
    FAILED_BATCHES+=("$CURRENT_BATCH")
    echo ""
    echo "Fix failures, then re-run:"
    echo "  ./scripts/run_e2e_tests_batched.sh --start-from ${CURRENT_BATCH}"
    echo ""
    exit 1
  fi

  [[ -n "$RUN_ONLY" ]] && [[ $CURRENT_BATCH -eq $RUN_ONLY ]] && break
done

echo "=========================================="
echo "All E2E Batches Complete"
echo "=========================================="
echo "Total batches: ${TOTAL_BATCHES}"
echo "Failed: ${#FAILED_BATCHES[@]}"
if [[ ${#FAILED_BATCHES[@]} -gt 0 ]]; then
  exit 1
fi
exit 0
