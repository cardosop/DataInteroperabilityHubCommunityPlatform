.PHONY: help setup install test test-ci test-ci-backend test-ci-frontend test-ci-lint lint format clean docker-up docker-down docker-logs migrate createsuperuser runserver dev-env test-helm test-helm-lint test-helm-unit test-infra-secrets test-staging-post-deploy test-verify-k8s-rollouts test-infra-staging-pipeline test-stack-up test-stack-down test-batch-6-1 test-batch-6-2 test-batch-6-3 test-batch-6-4 test-batch-6-5 test-batch-6-6 test-batch-7-1 test-batch-7-2 test-batch-7-3 test-batch-7-4 test-batch-7-5 test-batch-7-6 test-batch-7 test-batch-8 test-batch-8-1 test-batch-8-2 test-batch-8-3 test-batch-all

help: ## Show this help message
	@echo "Interoperable Data Hub MVP - Makefile Commands"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev-env: ## Generate .env.dev from .env.dev.template with random per-developer passwords
	@if [ -f .env.dev ]; then \
		cp .env.dev .env.dev.bak && echo "Backed up existing .env.dev to .env.dev.bak"; \
	fi
	@cp .env.dev.template .env.dev
	@sed -i "s/__POSTGRES_PASSWORD__/$$(openssl rand -hex 8)/g" .env.dev
	@sed -i "s/__MINIO_ROOT_PASSWORD__/$$(openssl rand -hex 8)/g" .env.dev
	@sed -i "s/__FUSEKI_ADMIN_PASSWORD__/$$(openssl rand -hex 8)/g" .env.dev
	@sed -i "s/__SECRET_KEY__/$$(openssl rand -hex 32)/g" .env.dev
	@sed -i "s/__JWT_SECRET_KEY__/$$(openssl rand -hex 32)/g" .env.dev
	@echo "Generated .env.dev with random passwords. Review before running docker compose."

setup: ## Initial setup (install dependencies, create venv)
	@./setup.sh

install: ## Install Python dependencies
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

docker-up: ## Start all Docker services (infrastructure only)
	docker compose up -d postgres redis minio fuseki

docker-up-services: ## Start all Docker services including microservices
	docker compose up -d postgres redis minio fuseki \
		datacontract-service dq-service compliance-service semantic-service

docker-up-all: ## Start all Docker services (infrastructure + microservices + API)
	docker compose up -d postgres redis minio fuseki \
		datacontract-service dq-service compliance-service semantic-service \
		api-service worker-service

mvp-up: ## Start core stack with MVP_MODE (compose overlay; build frontend for VITE_MVP_MODE)
	docker compose -f docker-compose.yml -f docker-compose.mvp.yml up -d --build \
		postgres redis-cache redis-queue redis-events redis-channels minio fuseki \
		datacontract-service dq-service compliance-service semantic-service jaeger \
		api-service worker-service frontend traefik

docker-down: ## Stop all Docker services
	docker compose down

docker-logs: ## View Docker logs
	docker compose logs -f

docker-ps: ## Show running Docker containers
	docker compose ps

migrate: ## Run database migrations
	python manage.py migrate

makemigrations: ## Create database migrations
	python manage.py makemigrations

createsuperuser: ## Create Django superuser
	python manage.py createsuperuser

runserver: ## Run Django development server
	python manage.py runserver

test: ## Run tests
	pytest

# ── CI-parity targets ────────────────────────────────────────────────
# Mirror the exact commands from .github/workflows/ci.yml so
# "make test-ci" locally produces the same result as CI.

test-ci: test-ci-lint test-ci-backend test-ci-frontend ## Run full CI suite locally (lint + backend + frontend)

test-ci-lint: ## Run linters (same as CI lint job)
	ruff check . --output-format=github
	ruff format --check .

test-ci-backend: ## Run backend tests in Docker (same as CI test-backend job)
	docker compose -f docker-compose.test.yml up -d --build --wait
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest hub/apps/ hub/tests/test_mvp_mode.py --reuse-db -x -q --timeout=300; \
	rc=$$?; \
	docker compose -f docker-compose.test.yml down -v --remove-orphans; \
	exit $$rc

test-ci-frontend: ## Run frontend unit tests (same as CI test-frontend-unit job)
	cd frontend && npm ci && npx vitest --run

# ── Helm & Infrastructure validation ────────────────────────────────
# Fast local checks (<10s total). No Docker required.
# Prerequisites: helm, helm-unittest plugin, jq

test-helm-lint: ## Helm chart lint + template rendering (mirrors CI helm-lint job)
	@command -v helm >/dev/null 2>&1 || { echo "Error: helm not found. Install from https://helm.sh/docs/intro/install/"; exit 1; }
	helm lint helm/
	helm template hub helm/ --values helm/values.yaml > /dev/null
	helm template hub helm/ --values helm/values.yaml --values helm/values.staging.yaml > /dev/null

test-helm-unit: ## Run Helm unit tests (54 tests, ~1s)
	@helm unittest --help >/dev/null 2>&1 || { echo "Error: helm-unittest plugin not found. Install: helm plugin install https://github.com/helm-unittest/helm-unittest.git --verify=false"; exit 1; }
	helm unittest helm/

test-helm: test-helm-lint test-helm-unit ## Run all Helm tests (lint + template + unit, ~2s)

test-infra-secrets: ## Run secrets manager population tests (76 assertions, ~2s)
	bash infrastructure/scripts/tests/test_populate_secrets_manager.sh

test-staging-post-deploy: ## Staging post-deploy script dry-run tests (210.23–210.26)
	bash infrastructure/scripts/tests/test_staging_post_deploy.sh

test-verify-k8s-rollouts: ## K8s rollout verification script dry-run tests (210.22)
	bash infrastructure/scripts/tests/test_verify_k8s_rollouts.sh

test-infra-staging-pipeline: test-staging-post-deploy test-verify-k8s-rollouts ## Post-deploy + rollout verify script tests

test-api-client-usage: ## Run API client usage search tests (validates JSON report structure)
	@echo "Running API client usage search tests..."
	@python3 tests/integration/run_api_client_usage_tests.py

test-api-client-usage-generate: ## Generate API client usage report and run tests
	@echo "Generating API client usage report..."
	@python3 scripts/search_api_client_usage.py
	@echo "Running tests..."
	@python3 tests/integration/run_api_client_usage_tests.py

test-webhook-payloads: ## Run webhook payloads and events search tests (validates JSON report structure)
	@echo "Running webhook payloads and events search tests..."
	@python3 tests/integration/run_webhook_payloads_tests.py

test-webhook-payloads-generate: ## Generate webhook payloads and events report and run tests
	@echo "Generating webhook payloads and events report..."
	@python3 scripts/search_webhook_payloads_and_events.py
	@echo "Running tests..."
	@python3 tests/integration/run_webhook_payloads_tests.py

test-inter-service-communication: ## Run inter-service communication search tests (validates JSON report structure)
	@echo "Running inter-service communication search tests..."
	@python3 tests/integration/run_inter_service_communication_tests.py

test-inter-service-communication-generate: ## Generate inter-service communication report and run tests
	@echo "Generating inter-service communication report..."
	@python3 scripts/search_inter_service_communication.py
	@echo "Running tests..."
	@python3 tests/integration/run_inter_service_communication_tests.py

test-integration: ## Run integration tests (requires services to be running)
	pytest -m integration

test-integration-with-services: ## Start services and run integration tests
	@echo "Starting services for integration tests..."
	@./scripts/start-services-for-tests.sh || (echo "Failed to start services. Make sure Docker is running." && exit 1)
	@echo "Running integration tests..."
	pytest -m integration
	@echo "Tests completed. Services are still running. Use 'make docker-down' to stop them."

test-with-services: ## Run tests with real services (requires services to be running)
	@echo "Running tests with real services..."
	@echo "Make sure services are running: make docker-up-services"
	USE_REAL_SERVICES=true pytest

test-e2e-with-services: ## Run E2E tests with real services
	@echo "Running E2E tests with real services..."
	@echo "Make sure services are running: make docker-up-services"
	USE_REAL_SERVICES=true cd hub && python manage.py test tests.e2e

test-connectors-e2e: ## Run Connector E2E tests (requires credentials)
	@echo "=========================================="
	@echo "Connector E2E Testing"
	@echo "=========================================="
	@echo ""
	@echo "This command runs end-to-end tests for marketplace connectors."
	@echo "Tests use real marketplace instances and real connections - no mocks or stubs."
	@echo ""
	@echo "Prerequisites:"
	@echo "  - Services must be running: make docker-up-all"
	@echo "  - Database migrations applied: make migrate"
	@echo ""
	@echo "Required Environment Variables:"
	@echo "  - DADOS_GOV_BR_API_KEY: JWT token for dados.gov.br API (optional)"
	@echo "  - SNOWFLAKE_ACCOUNT: Snowflake account identifier (optional)"
	@echo "  - SNOWFLAKE_USER: Snowflake username (optional)"
	@echo "  - SNOWFLAKE_TOKEN: Snowflake PAT token (optional)"
	@echo "  - SNOWFLAKE_WAREHOUSE: Snowflake warehouse (optional)"
	@echo "  - SNOWFLAKE_ROLE: Snowflake role (optional)"
	@echo "  - SNOWFLAKE_DATABASE: Snowflake database (optional)"
	@echo ""
	@echo "Note: Tests skip gracefully if credentials are not available."
	@echo ""
	@echo "Running tests..."
	@docker compose exec api-service python -m pytest \
		hub/apps/integrations/tests/test_connectors_e2e.py \
		-v \
		--tb=short \
		-m integration || echo "⚠️ Some tests may have been skipped due to missing credentials"

test-unit: ## Run unit tests only
	pytest -m "not integration"

test-cov: ## Run tests with coverage
	pytest --cov=. --cov-report=html

# ── Batch test targets ────────────────────────────────────────────────
# Split test-ci-backend into 6 batches (~600–950 tests each) to avoid
# I/O contention and OOM kills during parallel runs.
# Requires the test stack to be running:
#   make test-stack-up          # start full stack
#   make test-batch-6-4         # run a single batch
#   make test-stack-down        # tear down
#
# Connector env vars (DATABRICKS_HOST, DATABRICKS_TOKEN) are sourced
# from .env.test at runtime so batches work regardless of whether the
# stack was restarted after credential changes.

test-stack-up: ## Start the test stack (postgres, redis, minio, fuseki, microservices, api, worker)
	docker compose -f docker-compose.test.yml --env-file .env.test up -d --build --wait

test-stack-down: ## Stop the test stack and remove volumes
	docker compose -f docker-compose.test.yml down -v --remove-orphans

test-batch-6-1: ## Run test batch 6-1: CKAN + AWS + Dados + Connectors E2E + Snowflake (~600 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_ckan_*.py \
		hub/apps/integrations/tests/test_aws_data_exchange_*.py \
		hub/apps/integrations/tests/test_dados_gov_br_*.py \
		hub/apps/integrations/tests/test_connectors_e2e.py \
		hub/apps/integrations/tests/test_snowflake_*.py \
		--reuse-db -q --timeout=300'

test-batch-6-2: ## Run test batch 6-2: GCP Marketplace + Marketplace + Federated + Event Publishers + Connection Validation (~650 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_gcp_marketplace_*.py \
		hub/apps/integrations/tests/test_marketplace_*.py \
		hub/apps/integrations/tests/test_federated_*.py \
		hub/apps/integrations/tests/test_event_publishers*.py \
		hub/apps/integrations/tests/test_connection_validation_*.py \
		hub/apps/integrations/tests/integration/ \
		--reuse-db -q --timeout=300'

test-batch-6-3: ## Run test batch 6-3: Encryption + Core + Views + Sync/Mapping + Remaining (~730 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_encryption_*.py \
		hub/apps/integrations/tests/test_credential_encryption_*.py \
		hub/apps/integrations/tests/test_base.py \
		hub/apps/integrations/tests/test_business_rules.py \
		hub/apps/integrations/tests/test_error_classification.py \
		hub/apps/integrations/tests/test_models.py \
		hub/apps/integrations/tests/test_serializers.py \
		hub/apps/integrations/tests/test_signals.py \
		hub/apps/integrations/tests/test_views.py \
		hub/apps/integrations/tests/test_urls.py \
		hub/apps/integrations/tests/test_utils.py \
		hub/apps/integrations/tests/test_tasks.py \
		hub/apps/integrations/tests/test_connector_capabilities.py \
		hub/apps/integrations/tests/test_connector_development_documentation.py \
		hub/apps/integrations/tests/test_connector_pattern.py \
		hub/apps/integrations/tests/test_factory*.py \
		hub/apps/integrations/tests/test_init_exports.py \
		hub/apps/integrations/tests/test_metadata_first_architecture.py \
		hub/apps/integrations/tests/test_migrations.py \
		hub/apps/integrations/tests/test_scheduled_sync.py \
		hub/apps/integrations/tests/test_service*.py \
		hub/apps/integrations/tests/test_sync_job_*.py \
		hub/apps/integrations/tests/test_mapping_*.py \
		hub/apps/integrations/tests/test_integrations_tenant_context.py \
		hub/apps/integrations/tests/security/ \
		--reuse-db -q --timeout=300'

test-batch-6-4: ## Run test batch 6-4: Virtualization + Integrations Connectors + OpenLineage (~860 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/virtualization/ \
		hub/apps/integrations/connectors/ \
		hub/apps/integrations/openlineage/ \
		--reuse-db -q --timeout=300

test-batch-6-5: ## Run test batch 6-5: Orchestration + Workflows (~900 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/orchestration/ \
		--reuse-db -q --timeout=300

test-batch-6-6: ## Run test batch 6-6: Jobs + Webhooks + Websocket (~950 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/jobs/ \
		hub/apps/webhooks/ \
		hub/apps/websocket/ \
		--reuse-db -q --timeout=300

test-batch-7-1: ## Run test batch 7-1: ML + AI (~550 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/ml/ \
		hub/apps/ai/ \
		--reuse-db -q --timeout=300

test-batch-7-2: ## Run test batch 7-2: BaaS + Transformation (~710 tests)
	docker compose -f docker-compose.test.yml exec -T -e STRICT_TEST_TEARDOWN=1 api-service-test \
		python -u -m pytest \
		hub/apps/baas/ \
		hub/apps/transformation/ \
		--reuse-db -q --timeout=300

test-batch-7-3: ## Run test batch 7-3: Mesh (~607 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/mesh/ \
		--reuse-db -q --timeout=300

test-batch-7-4: ## Run test batch 7-4: API (~563 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/api/ \
		--reuse-db -q --timeout=300

test-batch-7-5: ## Run test batch 7-5: Audit + Observability (~824 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/audit/ \
		hub/apps/observability/ \
		--reuse-db -q --timeout=300

test-batch-7-6: ## Run test batch 7-6: Core (~1,027 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/core/ \
		--reuse-db -q --timeout=300

test-batch-7: ## Run all batch 7 sub-batches sequentially
	-$(MAKE) test-batch-7-1
	-$(MAKE) test-batch-7-2
	-$(MAKE) test-batch-7-3
	-$(MAKE) test-batch-7-4
	-$(MAKE) test-batch-7-5
	-$(MAKE) test-batch-7-6

test-batch-8-1: ## Run test batch 8-1: GraphQL + Developer + Health + Platform + Versioning + Security (~362 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/graphql/ \
		hub/apps/graphql_graphene/ \
		hub/apps/graphql_ld/ \
		hub/apps/developer/ \
		hub/apps/health/ \
		hub/apps/platform/ \
		hub/apps/versioning/ \
		hub/apps/security/ \
		--reuse-db -q --timeout=300

test-batch-8-2: ## Run test batch 8-2: Datasets + Data Movement (~840 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/datasets/ \
		hub/data_movement/ \
		--reuse-db -q --timeout=300

test-batch-8-3: ## Run test batch 8-3: Breach + RoPA + Warehouses + GDPR + DSAR + DPIA + Consent + Processor Agreements + Regulation Policies (~373 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/breach/ \
		hub/apps/ropa/ \
		hub/apps/warehouses/ \
		hub/apps/gdpr/ \
		hub/apps/dsar/ \
		hub/apps/dpia/ \
		hub/apps/consent/ \
		hub/apps/processor_agreements/ \
		hub/apps/regulation_policies/ \
		--reuse-db -q --timeout=300

test-batch-8: ## Run all batch 8 sub-batches sequentially
	-$(MAKE) test-batch-8-1
	-$(MAKE) test-batch-8-2
	-$(MAKE) test-batch-8-3

# ── Batch 9: hub/tests + SDK + CLI (~813 tests) ─────────────────────

test-batch-9-1: ## Run test batch 9-1: hub/tests/ (~56 files, ~300 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/tests/ \
		--reuse-db -q --timeout=300

test-batch-9-3a: ## Sub-batch 9-3a: meta/guard tests (~200 tests, ~5s, no API)
	@echo "=== 9-3a: Meta & Guard ==="
	@cd cli && python3 -m pytest -q \
		tests/test_persona_provisioning_sync.py \
		tests/test_mvp_gates_drift_sync.py \
		tests/test_parse_bool_env_drift.py \
		tests/test_post_mvp_help_markers.py \
		tests/test_static_id_guard.py \
		tests/test_mvp_detection.py \
		tests/test_mvp_gated_404_handling.py \
		tests/test_cli_118e.py

test-batch-9-3b: ## Sub-batch 9-3b: fixtures + unit config (~200 tests, ~10s, no API)
	@echo "=== 9-3b: Fixtures & Config ==="
	@cd cli && python3 -m pytest -q \
		tests/fixtures/ \
		tests/unit/test_api_client.py \
		tests/unit/test_auth.py \
		tests/unit/test_config.py \
		tests/unit/test_configuration.py \
		tests/unit/test_documentation.py \
		tests/unit/test_error_handling.py \
		tests/unit/test_errors.py \
		tests/unit/test_installation.py \
		tests/unit/test_marketplace_errors.py \
		tests/unit/test_odps_errors.py \
		tests/unit/test_output_formatting.py \
		-m "not slow"

test-batch-9-3c: ## Sub-batch 9-3c: CLI command unit tests (~400 tests, ~30s, no API)
	@echo "=== 9-3c: CLI Commands ==="
	@cd cli && python3 -m pytest -q \
		tests/unit/test_commands_*.py \
		-m "not slow"

test-batch-9-3d: ## Sub-batch 9-3d: unit auth + token + persona (~100 tests, ~5s, no API)
	@echo "=== 9-3d: Auth & Persona ==="
	@cd cli && python3 -m pytest -q \
		tests/unit/test_authentication_comprehensive.py \
		tests/unit/test_ml_training_commands.py \
		tests/unit/test_phase118a_endpoint_param_fixes.py \
		tests/test_persona_provisioning_unit.py

test-batch-9-3e: ## Sub-batch 9-3e: security E2E (~70 tests, needs API on port 8001)
	@echo "=== 9-3e: Security E2E ==="
	@rm -rf ~/.cache/datahub-test-provisioning/ 2>/dev/null || true
	@curl -s -X POST http://localhost:8001/api/v1/test/reset-e2e-auth-rate-limits/ \
		-H "X-E2E-Token: $${E2E_TEST_SECRET:-e2e-test-secret-for-local-dev}" > /dev/null 2>&1 || true
	export API_TEST_PORT=8001; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	cd cli && python3 -m pytest tests/security/ -q

test-batch-9-3f: ## Sub-batch 9-3f: use cases E2E (~200 tests, needs API on port 8001)
	@echo "=== 9-3f: Use Cases E2E ==="
	@rm -rf ~/.cache/datahub-test-provisioning/ 2>/dev/null || true
	@curl -s -X POST http://localhost:8001/api/v1/test/reset-e2e-auth-rate-limits/ \
		-H "X-E2E-Token: $${E2E_TEST_SECRET:-e2e-test-secret-for-local-dev}" > /dev/null 2>&1 || true
	export API_TEST_PORT=8001; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	cd cli && python3 -m pytest tests/use_cases/ -q

test-batch-9-3: ## Run test batch 9-3: all sub-batches (unit + E2E when API is up)
	@echo "Running CLI tests..."
	@rm -rf ~/.cache/datahub-test-provisioning/ 2>/dev/null || true
	@curl -s -X POST http://localhost:8001/api/v1/test/reset-e2e-auth-rate-limits/ \
		-H "X-E2E-Token: $${E2E_TEST_SECRET:-e2e-test-secret-for-local-dev}" > /dev/null 2>&1 || true
	export API_TEST_PORT=8001; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	export API_BASE_URL="$${API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_API_TOKEN="$${DATAHUB_API_TOKEN:-}"; \
	cd cli && python3 -m pytest -q \
		--ignore=tests/e2e \
		--ignore=tests/integration \
		--ignore=tests/performance \
		-m "not slow"
	@echo ""
	@if [ -z "$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/health/live/ 2>/dev/null)" ] || \
	    [ "$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/health/live/ 2>/dev/null)" != "200" ]; then \
		echo "[notice] API not reachable on port 8001 — security/use_cases tests were skipped."; \
		echo "[notice] To run them: make test-stack-up && make test-batch-9-3"; \
	fi

test-batch-9-2: ## Run all batch 9-2 sub-batches (~94 files, ~1400 tests)
	-$(MAKE) test-batch-9-2-a
	-$(MAKE) test-batch-9-2-b
	-$(MAKE) test-batch-9-2-c
	-$(MAKE) test-batch-9-2-d
	-$(MAKE) test-batch-9-2-e
	-$(MAKE) test-batch-9-2-f

test-batch-9-2-a: ## Run test batch 9-2-a: fast unit — fixtures, core, SDK, MVP (~29 files, ~300 tests, ~5s)
	@echo "Running test-batch-9-2-a..."
	export API_TEST_PORT=8001; \
	export MESHANT_API_URL="$${MESHANT_API_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	export API_BASE_URL="$${API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_API_TOKEN="$${DATAHUB_API_TOKEN:-}"; \
	test -n "$${TEST_API_KEY}" && export TEST_API_KEY="$${TEST_API_KEY}" || true; \
	test -n "$${DATAHUB_API_KEY}" && export DATAHUB_API_KEY="$${DATAHUB_API_KEY}" || true; \
	cd sdk/python && python3 -m pytest tests/fixtures/ tests/test_client.py tests/test_client_retry.py tests/test_client_token_refresh.py tests/test_error_handling.py tests/test_errors.py tests/test_retry.py tests/test_download_checksum_verify.py tests/test_federated_import.py tests/test_idempotency.py tests/test_parse_bool_env_drift.py tests/test_persona_provisioning_unit.py tests/test_semantic_graphql_ld.py tests/test_wait_for_helpers.py tests/test_phase5_modules.py tests/test_phase232_programme_surface.py tests/test_platform.py tests/test_mvp_detection.py tests/test_mvp_gated_404_async.py tests/test_mvp_gates_drift_sync.py tests/test_readme_mvp_section.py tests/test_static_id_guard.py tests/test_sdk_118f.py tests/test_phase118b_endpoint_fixes.py tests/test_scheduled_ingestion_api.py tests/test_lineage_api.py -q

test-batch-9-2-b: ## Run test batch 9-2-b: API unit — baas, contracts, marketplace, ml, model-serving, virtualization (~9 files, ~200 tests, ~10s)
	@echo "Running test-batch-9-2-b..."
	export API_TEST_PORT=8001; \
	export MESHANT_API_URL="$${MESHANT_API_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	export API_BASE_URL="$${API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_API_TOKEN="$${DATAHUB_API_TOKEN:-}"; \
	export VIRTUALIZATION_TEST_DB_HOST="$${VIRTUALIZATION_TEST_DB_HOST:-hub-test-postgres}"; \
	test -n "$${TEST_API_KEY}" && export TEST_API_KEY="$${TEST_API_KEY}" || true; \
	test -n "$${DATAHUB_API_KEY}" && export DATAHUB_API_KEY="$${DATAHUB_API_KEY}" || true; \
	cd sdk/python && python3 -m pytest tests/test_baas_api.py tests/test_contracts_api.py tests/test_marketplace_api.py tests/test_ml_api.py tests/test_model_serving_api.py tests/test_odcs_export.py tests/test_odcs_export_integration.py tests/test_virtualization_api.py -q

test-batch-9-2-c: ## Run test batch 9-2-c: security (~12 files, ~75 tests, ~30s)
	@echo "Running test-batch-9-2-c..."
	export API_TEST_PORT=8001; \
	export MESHANT_API_URL="$${MESHANT_API_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	export API_BASE_URL="$${API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_API_TOKEN="$${DATAHUB_API_TOKEN:-}"; \
	test -n "$${TEST_API_KEY}" && export TEST_API_KEY="$${TEST_API_KEY}" || true; \
	test -n "$${DATAHUB_API_KEY}" && export DATAHUB_API_KEY="$${DATAHUB_API_KEY}" || true; \
	cd sdk/python && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/security/ -q

test-batch-9-2-d: ## Run test batch 9-2-d: mesh API + performance + integration (~11 files, ~100 tests, ~30s)
	@echo "Running test-batch-9-2-d..."
	export API_TEST_PORT=8001; \
	export MESHANT_API_URL="$${MESHANT_API_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	export API_BASE_URL="$${API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export TEST_API_URL="$${TEST_API_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_API_TOKEN="$${DATAHUB_API_TOKEN:-}"; \
	test -n "$${TEST_API_KEY}" && export TEST_API_KEY="$${TEST_API_KEY}" || true; \
	test -n "$${DATAHUB_API_KEY}" && export DATAHUB_API_KEY="$${DATAHUB_API_KEY}" || true; \
	cd sdk/python && python3 -m pytest tests/test_mesh_api.py tests/test_mesh_compliance_api.py tests/test_mesh_domains_api.py tests/test_mesh_policies_api.py tests/test_mesh_topology_api.py tests/performance/ tests/integration/test_de1_full_flow.py tests/test_integration.py -q

test-batch-9-2-e: ## Run test batch 9-2-e: use-case + journey (~17 files, ~100 tests, ~5min)
	@echo "Running test-batch-9-2-e..."
	export API_TEST_PORT=8001; \
	export MESHANT_API_URL="$${MESHANT_API_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	export API_BASE_URL="$${API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_API_TOKEN="$${DATAHUB_API_TOKEN:-}"; \
	test -n "$${TEST_API_KEY}" && export TEST_API_KEY="$${TEST_API_KEY}" || true; \
	test -n "$${DATAHUB_API_KEY}" && export DATAHUB_API_KEY="$${DATAHUB_API_KEY}" || true; \
	cd sdk/python && python3 -m pytest tests/use_cases/ -q

test-batch-9-2-f: ## Run test batch 9-2-f: comprehensive integration — ODPS, BaaS, ODH (~15 files, ~200 tests, ~40min)
	@echo "Running test-batch-9-2-f..."
	export API_TEST_PORT=8001; \
	export MESHANT_API_URL="$${MESHANT_API_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_BASE_URL="$${DATAHUB_BASE_URL:-http://localhost:8001/api/v1}"; \
	export API_BASE_URL="$${API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export TEST_API_BASE_URL="$${TEST_API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export TEST_API_URL="$${TEST_API_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_API_BASE_URL="$${DATAHUB_API_BASE_URL:-http://localhost:8001/api/v1}"; \
	export DATAHUB_API_TOKEN="$${DATAHUB_API_TOKEN:-}"; \
	test -n "$${TEST_API_KEY}" && export TEST_API_KEY="$${TEST_API_KEY}" || true; \
	test -n "$${DATAHUB_API_KEY}" && export DATAHUB_API_KEY="$${DATAHUB_API_KEY}" || true; \
	cd sdk/python && python3 -m pytest tests/test_all_apis_odps_integration.py tests/test_baas_api_integration.py tests/test_baas_sdk_comprehensive.py tests/test_contracts_api_odps_comprehensive.py tests/test_marketplace_api_integration.py tests/test_marketplace_sdk_comprehensive_validation.py tests/test_ml_api_e2e.py tests/test_ml_api_integration.py tests/test_model_serving_sdk_comprehensive.py tests/test_odh_sdk_comprehensive_validation.py tests/test_odps_filtering_integration.py tests/test_odps_helpers_integration.py tests/test_odps_workflows_integration.py tests/test_phase26_sdk_integration.py tests/test_python_js_odps_consistency.py -q

test-batch-9: ## Run all batch 9 sub-batches sequentially
	-$(MAKE) test-batch-9-1
	-$(MAKE) test-batch-9-2
	-$(MAKE) test-batch-9-3

# ── Batch 10: tests/ root — subdivided for CI timeouts (~6,853 tests) ─

test-batch-10-1: ## Run test batch 10-1: tests/unit/ + tests/integration/ (~244 files, ~2,500 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		tests/unit/ \
		tests/integration/ \
		--reuse-db -q --timeout=600

test-batch-10-2: ## Run test batch 10-2: tests/e2e/ (~122 files, ~800 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		tests/e2e/ \
		--reuse-db -q --timeout=600

test-batch-10-3: ## Run test batch 10-3: tests/security/ + tests/performance/ (~104 files, ~600 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		tests/security/ \
		tests/performance/ \
		--reuse-db -q --timeout=600

test-batch-10-4: ## Run test batch 10-4: tests/regression/ + tests/smoke/ + tests/resilience/ + tests/uat/ (~54 files, ~400 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		tests/regression/ \
		tests/smoke/ \
		tests/resilience/ \
		tests/uat/ \
		--reuse-db -q --timeout=600

test-batch-10-5: ## Run test batch 10-5: tests/concurrency/ + tests/pact/ + tests/contract/ + tests/property/ + tests/load/ + tests/chaos/ + tests/migration/ (~49 files, ~500 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		tests/concurrency/ \
		tests/pact/ \
		tests/contract/ \
		tests/property/ \
		tests/load/ \
		tests/chaos/ \
		tests/migrations/ \
		--reuse-db -q --timeout=600

test-batch-10-6: ## Run test batch 10-6: tests/infrastructure/ + tests/observability/ + tests/benchmarks/ + tests/prefect/ + tests/chains/ + tests/ci/ + tests/dr/ + tests/disaster_recovery/ + tests/docs/ + tests/i18n/ + tests/isolation/ + tests/preprod01/ + tests/schema/ + tests/scripts/ + tests/sdk_python/ + tests/fixtures/ + tests/gdpr/ + tests/utils/ (~46 files, ~2,000 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		tests/infrastructure/ \
		tests/observability/ \
		tests/benchmarks/ \
		tests/prefect/ \
		tests/chains/ \
		tests/ci/ \
		tests/dr/ \
		tests/disaster_recovery/ \
		tests/docs/ \
		tests/i18n/ \
		tests/isolation/ \
		tests/preprod01/ \
		tests/schema/ \
		tests/scripts/ \
		tests/sdk_python/ \
		tests/fixtures/ \
		tests/gdpr/ \
		tests/utils/ \
		--reuse-db -q --timeout=600

test-batch-10: ## Run all batch 10 sub-batches sequentially
	-$(MAKE) test-batch-10-1
	-$(MAKE) test-batch-10-2
	-$(MAKE) test-batch-10-3
	-$(MAKE) test-batch-10-4
	-$(MAKE) test-batch-10-5
	-$(MAKE) test-batch-10-6

test-batch-all: ## Run all 8 test batches sequentially (continues on failure)
	-$(MAKE) test-batch-6-1
	-$(MAKE) test-batch-6-2
	-$(MAKE) test-batch-6-3
	-$(MAKE) test-batch-6-4
	-$(MAKE) test-batch-6-5
	-$(MAKE) test-batch-6-6
	-$(MAKE) test-batch-7-1
	-$(MAKE) test-batch-7-2
	-$(MAKE) test-batch-7-3
	-$(MAKE) test-batch-7-4
	-$(MAKE) test-batch-7-5
	-$(MAKE) test-batch-7-6
	-$(MAKE) test-batch-8-1
	-$(MAKE) test-batch-8-2
	-$(MAKE) test-batch-8-3
	-$(MAKE) test-batch-9-1
	-$(MAKE) test-batch-9-2
	-$(MAKE) test-batch-9-3
	-$(MAKE) test-batch-10-1
	-$(MAKE) test-batch-10-2
	-$(MAKE) test-batch-10-3
	-$(MAKE) test-batch-10-4
	-$(MAKE) test-batch-10-5
	-$(MAKE) test-batch-10-6

test-odps-validation: ## Run ODPS schema CI validation tests
	@echo "Running ODPS schema CI validation tests..."
	cd hub && python manage.py test apps.contracts.tests.test_odps_ci_validation --verbosity=2

validate-odps-schemas: ## Validate ODPS schema files (JSON Schema validation)
	@echo "Validating ODPS schema files..."
	@python scripts/validate_odps_schemas.py --strict || (echo "❌ ODPS schema validation failed!" && exit 1)
	@echo "✅ All ODPS schema files are valid!"

ci-odps-validation: validate-odps-schemas test-odps-validation ## Run all ODPS validation checks (CI pipeline)
	@echo "✅ All ODPS validation checks passed!"

validate-odcs-schemas: ## Validate ODCS contract files (all versions: 3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2)
	@echo "Validating ODCS contract files..."
	@python scripts/validate_odcs_schemas.py --strict || (echo "❌ ODCS contract validation failed!" && exit 1)
	@echo "✅ All ODCS contract files are valid!"

test-odcs-validation: ## Run ODCS validation tests (all versions)
	@echo "Running ODCS validation tests..."
	cd services/datacontract-service && pytest tests/test_odcs_ci_validation.py -v --tb=short || (echo "❌ ODCS validation tests failed!" && exit 1)
	@echo "✅ All ODCS validation tests passed!"

test-odcs-backward-compatibility: ## Test ODCS backward compatibility across versions
	@echo "Testing ODCS backward compatibility..."
	cd services/datacontract-service && pytest tests/test_odcs_ci_validation.py::TestODCSBackwardCompatibility -v --tb=short || (echo "❌ ODCS backward compatibility tests failed!" && exit 1)
	@echo "✅ ODCS backward compatibility tests passed!"

test-odcs-normalizers: ## Test ODCS version-specific normalizers
	@echo "Testing ODCS version-specific normalizers..."
	cd services/datacontract-service && pytest tests/test_odcs_ci_validation.py::TestODCSVersionSpecificNormalizers -v --tb=short || (echo "❌ ODCS normalizer tests failed!" && exit 1)
	@echo "✅ ODCS normalizer tests passed!"

ci-odcs-validation: validate-odcs-schemas test-odcs-validation test-odcs-backward-compatibility test-odcs-normalizers ## Run all ODCS validation checks (CI pipeline)
	@echo "✅ All ODCS validation checks passed!"

test-backward-compatibility: ## Run comprehensive backward compatibility tests (ODPS and ODCS)
	@echo "Running comprehensive backward compatibility tests..."
	cd hub && python manage.py test hub.apps.contracts.tests.test_comprehensive_backward_compatibility_ci --verbosity=2 || (echo "❌ Backward compatibility tests failed!" && exit 1)
	@echo "✅ All backward compatibility tests passed!"

ci-backward-compatibility: test-backward-compatibility ## Run all backward compatibility checks (CI pipeline)
	@echo "✅ All backward compatibility checks passed!"

lint: ## Run linters
	@echo "Running ruff..."
	@ruff check . || true
	@echo "Running mypy..."
	@mypy hub/ || true
	@echo "Linting complete!"

format: ## Format code
	black .
	ruff check --fix .

clean: ## Clean temporary files
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name ".mypy_cache" -exec rm -r {} +
	find . -type d -name ".ruff_cache" -exec rm -r {} +
	rm -rf htmlcov/
	rm -rf .coverage

verify-deps: ## Verify all external dependencies
	@echo "Verifying dependencies..."
	@python3 --version | grep -q "3.1[2-9]" && echo "✅ Python 3.12+" || echo "❌ Python 3.12+ required"
	@docker --version > /dev/null 2>&1 && echo "✅ Docker" || echo "❌ Docker required"
	@docker ps | grep -q postgres && echo "✅ PostgreSQL running" || echo "⚠️  PostgreSQL not running"
	@docker ps | grep -q redis && echo "✅ Redis running" || echo "⚠️  Redis not running"
	@docker ps | grep -q minio && echo "✅ MinIO running" || echo "⚠️  MinIO not running"
	@docker ps | grep -q fuseki && echo "✅ Fuseki running" || echo "⚠️  Fuseki not running"
	@docker ps | grep -q datacontract && echo "✅ DataContract service running" || echo "⚠️  DataContract service not running"
	@docker ps | grep -q dq-service && echo "✅ DQ service running" || echo "⚠️  DQ service not running"
	@docker ps | grep -q compliance && echo "✅ Compliance service running" || echo "⚠️  Compliance service not running"
	@docker ps | grep -q semantic && echo "✅ Semantic service running" || echo "⚠️  Semantic service not running"

wait-for-services: ## Wait for all services to be healthy
	@echo "Waiting for services to be healthy..."
	@timeout=60; \
	for service in datacontract-service:8080 dq-service:8083 compliance-service:8082 semantic-service:8081; do \
		name=$${service%%:*}; port=$${service##*:}; \
		echo "Waiting for $$name..."; \
		for i in $$(seq 1 $$timeout); do \
			if docker compose exec -T $$name curl -f http://localhost:$$port/health > /dev/null 2>&1 || \
			   curl -f http://localhost:$$port/health > /dev/null 2>&1; then \
				echo "✅ $$name is healthy"; \
				break; \
			fi; \
			if [ $$i -eq $$timeout ]; then \
				echo "❌ $$name failed to become healthy after $$timeout seconds"; \
				exit 1; \
			fi; \
			sleep 1; \
		done; \
	done
	@echo "✅ All services are healthy"

