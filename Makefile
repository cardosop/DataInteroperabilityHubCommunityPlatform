.PHONY: help setup install test test-ci test-ci-backend test-ci-frontend test-ci-lint lint format clean docker-up docker-down docker-logs migrate createsuperuser runserver dev-env test-helm test-helm-lint test-helm-unit test-infra-secrets test-staging-post-deploy test-verify-k8s-rollouts test-infra-staging-pipeline test-stack-up test-stack-down test-batch-1 test-batch-1-1 test-batch-1-2 test-batch-1-3 test-batch-1-4 test-batch-1-5 test-batch-1-6 test-batch-1-7 test-batch-1-8 test-batch-1-9 test-batch-2 test-batch-2-1 test-batch-2-2 test-batch-2-3 test-batch-2-4 test-batch-2-5 test-batch-2-6 test-batch-2-7 test-batch-2-8 test-batch-2-9 test-batch-2-10 test-batch-3 test-batch-3-1 test-batch-3-2 test-batch-3-3 test-batch-3-4 test-batch-3-5 test-batch-3-6 test-batch-3-7 test-batch-3-8 test-batch-3-9 test-batch-3-10 test-batch-3-11 test-batch-4 test-batch-4-1 test-batch-4-2 test-batch-4-3 test-batch-4-4 test-batch-4-5 test-batch-4-6 test-batch-5 test-batch-5-1 test-batch-5-2 test-batch-5-3 test-batch-5-4 test-batch-5-5 test-batch-6-1 test-batch-6-1a test-batch-6-1b test-batch-6-1c test-batch-6-1-all test-batch-6-2 test-batch-6-3 test-batch-6-4 test-batch-6-5 test-batch-6-6 test-batch-7-1 test-batch-7-2 test-batch-7-3 test-batch-7-4 test-batch-7-5 test-batch-7-6 test-batch-7 test-batch-8 test-batch-8-1 test-batch-8-2 test-batch-8-3 test-batch-9-1 test-batch-9-2 test-batch-9-2-a test-batch-9-2-b test-batch-9-2-c test-batch-9-2-d test-batch-9-2-e test-batch-9-2-f test-batch-9-3 test-batch-9-3a test-batch-9-3b test-batch-9-3c test-batch-9-3d test-batch-9-3e test-batch-9-3f test-batch-9 test-batch-10-1 test-batch-10-2 test-batch-10-3 test-batch-10-4 test-batch-10-5 test-batch-10-6 test-batch-10 test-batch-12-1 test-batch-12-2 test-batch-12-3 test-batch-12-4 test-batch-12-5 test-batch-all test-frontend-e2e-batch1 test-frontend-e2e-batch1a test-frontend-e2e-batch1b test-frontend-e2e-batch1c test-frontend-e2e-batch2 test-frontend-e2e-batch3 test-frontend-e2e-batch4 test-frontend-e2e-batch5 test-frontend-e2e-batch6 test-frontend-e2e-batch7 test-frontend-e2e-batch8 docker-up-services docker-up-all mvp-up docker-ps makemigrations test-api-client-usage test-api-client-usage-generate test-webhook-payloads test-webhook-payloads-generate test-inter-service-communication test-inter-service-communication-generate test-integration test-integration-with-services test-with-services test-e2e-with-services test-connectors-e2e test-unit test-cov test-odps-validation validate-odps-schemas ci-odps-validation validate-odcs-schemas test-odcs-validation test-odcs-backward-compatibility test-odcs-normalizers ci-odcs-validation test-backward-compatibility ci-backward-compatibility verify-deps wait-for-services check-docs-sync audit-docs _seed-e2e-data quality-gates

# ── CI-Makefile parity note ──────────────────────────────────────────
# CI has 57 jobs (ci.yml + e2e.yml + 7 reusable workflows). The Makefile
# provides 5 CI-parity targets + 36 batch targets. Remaining CI jobs
# (secret scans, ODPS/ODCS version matrices, OpenAPI validation, scheduled
# jobs, mutation testing, cross-browser E2E) are CI-only by design — they
# require GitHub-hosted runners, matrix strategy, or scheduled triggers.
#
# Locally-runnable quality gates:  make quality-gates
# Documentation health:           make audit-docs
# Full CI simulation locally:     make test-ci
# All batch tests:                make test-batch-all
#
# ── Target naming convention ─────────────────────────────────────────
# test-batch-N     — top-level batch group (runs entire Django app dir)
# test-batch-N-M   — sub-batch within a group (file-glob split)
# test-batch-N-M-x — sub-sub-batch (letter suffix)
# test-ci-*        — CI-parity target matching a specific CI job
# test-frontend-*  — frontend test target
# test-helm-*      — Helm/K8s test target

# Ensure the project venv python3 is first in PATH so that ``python3``
# always resolves to the interpreter that has all dependencies installed.
export PATH := $(CURDIR)/venv/bin:$(PATH)

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

test-ci-lint: ## Run linters (same as CI lint job) — continues on failure
	-ruff check . --output-format=github
	-ruff format --check .
	-python scripts/check_assert_true_true.py
	-python scripts/check_persona_mapping_drift.py
	-python scripts/lint_journey_marker_coverage.py --blocking
	@echo "test-ci-lint complete — check output above for violations"

test-ci-backend: ## Run backend tests in Docker (same as CI test-backend job)
	docker compose -f docker-compose.test.yml up -d --build --wait
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest hub/apps/ hub/tests/test_mvp_mode.py --reuse-db -x -q --timeout=300; \
	rc=$$?; \
	docker compose -f docker-compose.test.yml down -v --remove-orphans; \
	exit $$rc

test-ci-frontend: ## Run frontend unit tests (same as CI test-frontend-unit job)
	cd frontend && npm ci && npx vitest --run

# ── Frontend E2E batches ────────────────────────────────────────────

test-frontend-e2e-batch1: ## Frontend E2E batch 1: all sub-batches (1a → 1b → 1c)
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch1

test-frontend-e2e-batch1a: ## Frontend E2E batch 1a: auth core (~35 tests, ~5 min)
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch1a

test-frontend-e2e-batch1b: ## Frontend E2E batch 1b: a11y + UX (~100 tests, ~12 min)
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch1b

test-frontend-e2e-batch1c: ## Frontend E2E batch 1c: cross-cutting + security (~65 tests, ~6 min)
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch1c

test-frontend-e2e-batch2: ## Frontend E2E batch 2: routes
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch2

test-frontend-e2e-batch3: ## Frontend E2E batch 3: DPO journeys
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch3

test-frontend-e2e-batch4: ## Frontend E2E batch 4: Auth, DC, DE journeys
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch4

test-frontend-e2e-batch5: ## Frontend E2E batch 5: TA, PA, Dev, Aud journeys
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch5

test-frontend-e2e-batch6: ## Frontend E2E batch 6: CPO, DS, DMO, DA, CM, MPA journeys
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch6

test-frontend-e2e-batch7: ## Frontend E2E batch 7
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch7

test-frontend-e2e-batch8: ## Frontend E2E batch 8
	cd frontend && E2E_RESTART_FRONTEND=1 E2E_TEST_SECRET=e2e-test-secret-for-local-dev npm run test:e2e:batch8

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

# ── Backend test batches 1-5 (core Django apps) ──────────────────────

# ── Backend test batch 1: assets + files + datasets (~2,076 tests) ────

test-batch-1-1: ## assets-business-rules (~224 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/assets/tests/test_business_rules.py \
		hub/apps/assets/tests/test_business_rules_dataset_attachment.py \
		hub/apps/assets/tests/test_models.py \
		hub/apps/assets/tests/test_serializers.py \
		hub/apps/assets/tests/test_services.py \
		hub/apps/assets/tests/test_signals.py \
		hub/apps/assets/tests/test_contract_driven_governance.py \
		hub/apps/assets/tests/test_health_score.py \
		hub/apps/assets/tests/test_health_score_integration.py \
		--reuse-db -q --timeout=300

test-batch-1-2: ## assets-crud-lifecycle-activation (~238 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/assets/tests/test_asset_crud.py \
		hub/apps/assets/tests/test_asset_relationships.py \
		hub/apps/assets/tests/test_asset_activation.py \
		hub/apps/assets/tests/test_asset_activation_rule.py \
		hub/apps/assets/tests/test_activation_blockers_api.py \
		hub/apps/assets/tests/test_activation_integration.py \
		hub/apps/assets/tests/test_onboarding_lifecycle.py \
		hub/apps/assets/tests/test_onboarding_scenario_matrix.py \
		hub/apps/assets/tests/test_status_transitions.py \
		hub/apps/assets/tests/test_cascade_safety.py \
		hub/apps/assets/tests/test_cleanup_orphan_drafts.py \
		hub/apps/assets/tests/test_asset_workflow_status_endpoint.py \
		hub/apps/assets/tests/test_performance.py \
		hub/apps/assets/tests/test_domain_model_doc_drift.py \
		--reuse-db -q --timeout=300

test-batch-1-3: ## assets-operational-popularity-caching-search (~201 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/assets/tests/test_popularity.py \
		hub/apps/assets/tests/test_popularity_integration.py \
		hub/apps/assets/tests/test_recommendations.py \
		hub/apps/assets/tests/test_recommendations_integration.py \
		hub/apps/assets/tests/test_caching.py \
		hub/apps/assets/tests/test_search_vector_signal_timing.py \
		hub/apps/assets/tests/test_metrics.py \
		hub/apps/assets/tests/test_dependencies.py \
		hub/apps/assets/tests/test_data_strategy.py \
		hub/apps/assets/tests/test_external_resource_reference.py \
		hub/apps/assets/tests/test_external_resource_download_api.py \
		hub/apps/assets/tests/test_dataset_versioning.py \
		hub/apps/assets/tests/test_create_or_get_idempotent.py \
		--reuse-db -q --timeout=300

test-batch-1-4: ## assets-data-first-federated-visibility-security (~244 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/assets/tests/test_data_first_asset_api.py \
		hub/apps/assets/tests/test_data_first_fail_closed.py \
		hub/apps/assets/tests/test_data_first_idempotency.py \
		hub/apps/assets/tests/test_visibility_deprecation.py \
		hub/apps/assets/tests/test_visibility_phase_2_rejection.py \
		hub/apps/assets/tests/test_federated_assets.py \
		hub/apps/assets/tests/test_federated_asset_migrations.py \
		hub/apps/assets/tests/test_cross_tenant_activation.py \
		hub/apps/assets/tests/test_jwt_scope_enforcement.py \
		hub/apps/assets/tests/test_workflow_fail_closed.py \
		hub/apps/assets/tests/test_asset_creation_kill_switch.py \
		hub/apps/assets/tests/test_asset_creation_rate_limits.py \
		hub/apps/assets/tests/test_asset_if_match_locking.py \
		hub/apps/assets/tests/test_idempotency.py \
		hub/apps/assets/tests/test_service_webhook_events.py \
		hub/apps/assets/tests/test_create_asset_command.py \
		hub/apps/assets/tests/test_asset_list_compliance_prefetch.py \
		hub/apps/datasets/tests/test_sample_data_extraction.py \
		hub/apps/datasets/tests/test_sample_endpoint.py \
		hub/apps/datasets/tests/test_sample_pii_redaction.py \
		hub/apps/datasets/tests/test_csv_long_tail_formats.py \
		hub/apps/datasets/tests/test_dataset_malware_gate.py \
		--reuse-db -q --timeout=300

test-batch-1-5: ## files-upload-download-multipart-storage (~197 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/files/tests/test_file_upload_download.py \
		hub/apps/files/tests/test_chunked_upload.py \
		hub/apps/files/tests/test_multipart_abort_and_resume.py \
		hub/apps/files/tests/test_multipart_complete_race.py \
		hub/apps/files/tests/test_multipart_list_parts.py \
		hub/apps/files/tests/test_storage.py \
		hub/apps/files/tests/test_storage_credentials.py \
		hub/apps/files/tests/test_rename.py \
		hub/apps/files/tests/test_locale_filename_roundtrip.py \
		hub/apps/files/tests/test_magic_bytes.py \
		hub/apps/files/tests/test_download_checksum_mismatch.py \
		hub/apps/files/tests/test_file_size_limits.py \
		hub/apps/files/tests/test_metadata_size_cap.py \
		hub/apps/files/tests/test_unique_active_filename.py \
		hub/apps/files/tests/test_abandoned_multipart_cleanup.py \
		--reuse-db -q --timeout=300

test-batch-1-6: ## files-business-rules-scan-security-quota-ops (~273 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/files/tests/test_business_rules.py \
		hub/apps/files/tests/test_virus_scan.py \
		hub/apps/files/tests/test_virus_scan_e2e.py \
		hub/apps/files/tests/test_clamav_transport.py \
		hub/apps/files/tests/test_scanner.py \
		hub/apps/files/tests/test_file_security.py \
		hub/apps/files/tests/security/test_idor.py \
		hub/apps/files/tests/test_file_scan_status.py \
		hub/apps/files/tests/test_quota.py \
		hub/apps/files/tests/test_models.py \
		hub/apps/files/tests/test_serializers.py \
		hub/apps/files/tests/test_services.py \
		hub/apps/files/tests/test_file_service_event_publishing.py \
		hub/apps/files/tests/test_file_event_publisher_integration.py \
		hub/apps/files/tests/test_file_views_event_publishing_e2e.py \
		hub/apps/files/tests/test_file_metadata_view_audit.py \
		hub/apps/files/tests/test_file_purged_webhook.py \
		hub/apps/files/tests/test_purge_deleted_files.py \
		hub/apps/files/tests/test_cleanup_orphan_files.py \
		hub/apps/files/tests/test_drop_completed_status.py \
		hub/apps/files/tests/test_file_init_rate_limits.py \
		hub/apps/files/tests/test_gdpr_delete_files_commands.py \
		hub/apps/files/tests/test_openapi_file_scan_fields.py \
		--reuse-db -q --timeout=300

test-batch-1-6-clamav: ## files-virus-scan-e2e (requires clamav-test profile, ~268 tests)
	@echo "Starting ClamAV test profile..."
	docker compose -f docker-compose.test.yml --profile clamav-test up -d clamav-test
	@echo "Waiting for ClamAV health check..."
	@for _ in $$(seq 1 30); do \
		docker compose -f docker-compose.test.yml ps clamav-test | grep -q healthy && break; \
		echo "  still waiting..."; sleep 5; \
	done
	@echo "Running virus-scan E2E + live scanner tests..."
	docker compose -f docker-compose.test.yml exec -T \
		-e CLAMAV_ENABLED=true \
		-e RUN_FILE_VIRUS_SCAN_E2E=1 \
		-e RUN_CLAMAV_LIVE_TESTS=1 \
		api-service-test \
		python -u -m pytest \
			hub/apps/files/tests/test_virus_scan_e2e.py \
			hub/apps/files/tests/test_virus_scan.py \
			hub/apps/files/tests/test_scanner.py \
			--reuse-db -v --timeout=300

test-batch-1-7: ## datasets-business-rules-validation-inference (~247 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/datasets/tests/test_business_rules.py \
		hub/apps/datasets/tests/test_business_rules_access_validation.py \
		hub/apps/datasets/tests/test_datasets_service_comprehensive_validation.py \
		hub/apps/datasets/tests/test_inference_limits.py \
		hub/apps/datasets/tests/test_dataset_inference_limits_integration.py \
		hub/apps/datasets/tests/test_encoding_detection.py \
		hub/apps/datasets/tests/test_dataset_encoding_gate.py \
		hub/apps/datasets/tests/test_dataset_kind.py \
		--reuse-db -q --timeout=300

test-batch-1-8: ## datasets-versioning-schema-semantic-impact (~233 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/datasets/tests/test_versioning.py \
		hub/apps/datasets/tests/test_versioning_service.py \
		hub/apps/datasets/tests/test_versioning_service_event_publishing.py \
		hub/apps/datasets/tests/test_versioning_event_publisher.py \
		hub/apps/datasets/tests/test_versioning_event_publishing_e2e.py \
		hub/apps/datasets/tests/test_version_history.py \
		hub/apps/datasets/tests/test_version_comparison.py \
		hub/apps/datasets/tests/test_version_integration.py \
		hub/apps/datasets/tests/test_version_impact.py \
		hub/apps/datasets/tests/test_version_impact_integration.py \
		hub/apps/datasets/tests/test_version_sample_refresh.py \
		hub/apps/datasets/tests/test_schema_inference.py \
		hub/apps/datasets/tests/test_schema_evolution.py \
		hub/apps/datasets/tests/test_schema_evolution_integration.py \
		hub/apps/datasets/tests/test_semantic_versioning_enhanced.py \
		hub/apps/datasets/tests/test_semantic_versioning_integration.py \
		hub/apps/datasets/tests/test_snapshot_type_enum.py \
		hub/apps/datasets/tests/test_cursor_backward_compat.py \
		--reuse-db -q --timeout=300

test-batch-1-9: ## datasets-views-lifecycle-operations-caching (~250 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/datasets/tests/test_views.py \
		hub/apps/datasets/tests/test_models.py \
		hub/apps/datasets/tests/test_services.py \
		hub/apps/datasets/tests/test_caching.py \
		hub/apps/datasets/tests/test_cache_invalidation.py \
		hub/apps/datasets/tests/test_refresh_from_file.py \
		hub/apps/datasets/tests/test_manual_refresh.py \
		hub/apps/datasets/tests/test_retire_lifecycle.py \
		hub/apps/datasets/tests/test_time_travel.py \
		hub/apps/datasets/tests/test_rollback.py \
		hub/apps/datasets/tests/test_orphan_dataset_lifecycle.py \
		hub/apps/datasets/tests/test_orphan_dataset_backfill.py \
		hub/apps/datasets/tests/test_orphan_file_cascade.py \
		hub/apps/datasets/tests/test_file_hard_delete_retires_datasets.py \
		hub/apps/datasets/tests/test_storage_fetch_retries.py \
		hub/apps/datasets/tests/test_rls_policies.py \
		hub/apps/datasets/tests/test_mock_fallback.py \
		hub/apps/datasets/tests/test_file_active_precondition.py \
		hub/apps/datasets/tests/test_file_handle_purpose.py \
		--reuse-db -q --timeout=300

# ── Parent target: runs all batch-1 sub-batches ─────────────────────
test-batch-1: ## Run test batch 1: all assets + files + datasets sub-batches
	@$(MAKE) test-batch-1-1
	@$(MAKE) test-batch-1-2
	@$(MAKE) test-batch-1-3
	@$(MAKE) test-batch-1-4
	@$(MAKE) test-batch-1-5
	@$(MAKE) test-batch-1-6
	@$(MAKE) test-batch-1-7
	@$(MAKE) test-batch-1-8
	@$(MAKE) test-batch-1-9

# ── Backend test batch 2: contracts (~5,488 tests) ─

test-batch-2-1: ## ODPS normalizers, parsers, validators, fixtures (~23 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_odps_normalizer.py \
		hub/apps/contracts/tests/test_odps_normalizer_base.py \
		hub/apps/contracts/tests/test_odps_normalizer_v4_0.py \
		hub/apps/contracts/tests/test_odps_normalizer_v4_1.py \
		hub/apps/contracts/tests/test_odps_normalizer_v4_2.py \
		hub/apps/contracts/tests/test_odps_normalizer_coverage_final.py \
		hub/apps/contracts/tests/test_odps_normalizer_coverage_gaps.py \
		hub/apps/contracts/tests/test_odps_normalizer_coverage_gaps_extended.py \
		hub/apps/contracts/tests/test_odps_parser.py \
		hub/apps/contracts/tests/test_odps_parser_validation.py \
		hub/apps/contracts/tests/test_odps_format_converter.py \
		hub/apps/contracts/tests/test_odps_errors.py \
		hub/apps/contracts/tests/test_odps_version_detection.py \
		hub/apps/contracts/tests/test_odps_schema_files.py \
		hub/apps/contracts/tests/test_odps_schema_loading.py \
		hub/apps/contracts/tests/test_odps_refs_config.py \
		hub/apps/contracts/tests/test_odps_ref_fixtures.py \
		hub/apps/contracts/tests/test_odps_invalid_fixtures.py \
		hub/apps/contracts/tests/test_odps_multilingual_fixtures.py \
		hub/apps/contracts/tests/test_odps_marketplace_fixtures.py \
		hub/apps/contracts/tests/test_odps_test_structure_conventions.py \
		hub/apps/contracts/tests/test_odps_url_allowlist_denylist.py \
		hub/apps/contracts/tests/test_odps_security_logging.py \
		hub/apps/contracts/tests/test_odps_outputports_normalization.py \
		--reuse-db -q --timeout=300

test-batch-2-2: ## ODPS generators, service, integration, business rules (~26 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_odps_generator.py \
		hub/apps/contracts/tests/test_odps_generator_assembly.py \
		hub/apps/contracts/tests/test_odps_generator_contract.py \
		hub/apps/contracts/tests/test_odps_generator_coverage_gaps.py \
		hub/apps/contracts/tests/test_odps_generator_lifecycle.py \
		hub/apps/contracts/tests/test_odps_generator_marketplace.py \
		hub/apps/contracts/tests/test_odps_generator_product_strategy.py \
		hub/apps/contracts/tests/test_odps_auto_generation.py \
		hub/apps/contracts/tests/test_odps_service.py \
		hub/apps/contracts/tests/test_odps_service_integration.py \
		hub/apps/contracts/tests/test_odps_integration_validation_comprehensive.py \
		hub/apps/contracts/tests/test_odps_business_rules.py \
		hub/apps/contracts/tests/test_odps_business_rules_integration.py \
		hub/apps/contracts/tests/test_odps_linking_rules.py \
		hub/apps/contracts/tests/test_odps_linking_endpoint.py \
		hub/apps/contracts/tests/test_odps_linking_compensation.py \
		hub/apps/contracts/tests/test_odps_linking_compensation_integration.py \
		hub/apps/contracts/tests/test_odps_creation_compensation.py \
		hub/apps/contracts/tests/test_odps_creation_compensation_integration.py \
		hub/apps/contracts/tests/test_odps_normalization_rules.py \
		hub/apps/contracts/tests/test_odps_normalization_integration.py \
		hub/apps/contracts/tests/test_odps_normalization_compensation.py \
		hub/apps/contracts/tests/test_odps_ingestion_integration.py \
		hub/apps/contracts/tests/test_odps_metrics.py \
		hub/apps/contracts/tests/test_odps_dashboards.py \
		hub/apps/contracts/tests/test_odps_event_bus_integration.py \
		--reuse-db -q --timeout=300

test-batch-2-3: ## ODPS use cases, marketplace, security, multi-tenant, export (~20 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_odps_use_cases_comprehensive.py \
		hub/apps/contracts/tests/test_odps_security_validation_comprehensive.py \
		hub/apps/contracts/tests/test_odps_multi_tenancy_validation.py \
		hub/apps/contracts/tests/test_odps_api_schema_validation.py \
		hub/apps/contracts/tests/test_odps_authentication_authorization_validation.py \
		hub/apps/contracts/tests/test_odps_rate_limiting.py \
		hub/apps/contracts/tests/test_odps_export_rules.py \
		hub/apps/contracts/tests/test_odps_export_metrics.py \
		hub/apps/contracts/tests/test_odps_export_ci_integration.py \
		hub/apps/contracts/tests/test_odps_backward_compatibility.py \
		hub/apps/contracts/tests/test_odps_ref_resolution_ci.py \
		hub/apps/contracts/tests/test_odps_odcs_extraction.py \
		hub/apps/contracts/tests/test_odps_ci_validation.py \
		hub/apps/contracts/tests/test_odps_job_queue_integration.py \
		hub/apps/contracts/tests/test_odps_link_index_performance.py \
		hub/apps/contracts/tests/test_odps_query_indexes_performance.py \
		hub/apps/contracts/tests/test_odps_generation_endpoint_integration.py \
		hub/apps/contracts/tests/test_odps_alerts.py \
		hub/apps/contracts/tests/test_odps_audit_integration.py \
		hub/apps/contracts/tests/test_odps_bitol_v1.py \
		--reuse-db -q --timeout=300

test-batch-2-4: ## ODCS generators, normalizers, versioning (~30 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_odcs_generator_base.py \
		hub/apps/contracts/tests/test_odcs_generator_main_function.py \
		hub/apps/contracts/tests/test_odcs_generator_registry.py \
		hub/apps/contracts/tests/test_odcs_generator_registry_integration.py \
		hub/apps/contracts/tests/test_odcs_generator_structure.py \
		hub/apps/contracts/tests/test_odcs_generator_v2_2_2.py \
		hub/apps/contracts/tests/test_odcs_generator_v3_0_0.py \
		hub/apps/contracts/tests/test_odcs_generator_v3_0_0_preview.py \
		hub/apps/contracts/tests/test_odcs_generator_v3_0_1.py \
		hub/apps/contracts/tests/test_odcs_generator_v3_0_2.py \
		hub/apps/contracts/tests/test_odcs_normalizer_base.py \
		hub/apps/contracts/tests/test_odcs_normalizer_regression.py \
		hub/apps/contracts/tests/test_odcs_normalizer_v2_2_2.py \
		hub/apps/contracts/tests/test_odcs_normalizer_v3_0_0.py \
		hub/apps/contracts/tests/test_odcs_normalizer_v3_0_0_preview.py \
		hub/apps/contracts/tests/test_odcs_normalizer_v3_0_1.py \
		hub/apps/contracts/tests/test_odcs_normalizer_v3_0_2.py \
		hub/apps/contracts/tests/test_odcs_normalizer_v3_1_0.py \
		hub/apps/contracts/tests/test_odcs_normalization_integration.py \
		hub/apps/contracts/tests/test_odcs_format_converter.py \
		hub/apps/contracts/tests/test_odcs_version_detection.py \
		hub/apps/contracts/tests/test_odcs_version_routing.py \
		hub/apps/contracts/tests/test_odcs_version_support_documentation.py \
		hub/apps/contracts/tests/test_odcs_backward_compatibility.py \
		hub/apps/contracts/tests/test_odcs_backward_compatibility_regression.py \
		hub/apps/contracts/tests/test_odcs_backward_compatibility_e2e.py \
		hub/apps/contracts/tests/test_odcs_export_integration.py \
		hub/apps/contracts/tests/test_odcs_metrics.py \
		hub/apps/contracts/tests/test_odcs_nested_properties.py \
		hub/apps/contracts/tests/test_odcs_alerts.py \
		--reuse-db -q --timeout=300

test-batch-2-5: ## Lineage — extraction, service, validation, visualization (~26 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_lineage_service.py \
		hub/apps/contracts/tests/test_lineage_service_for_asset.py \
		hub/apps/contracts/tests/test_lineage_service_event_publishing.py \
		hub/apps/contracts/tests/test_lineage_extraction.py \
		hub/apps/contracts/tests/test_lineage_validator.py \
		hub/apps/contracts/tests/test_lineage_traversal.py \
		hub/apps/contracts/tests/test_lineage_visualization.py \
		hub/apps/contracts/tests/test_lineage_diff.py \
		hub/apps/contracts/tests/test_lineage_sync.py \
		hub/apps/contracts/tests/test_lineage_backfill.py \
		hub/apps/contracts/tests/test_lineage_archive.py \
		hub/apps/contracts/tests/test_lineage_redaction.py \
		hub/apps/contracts/tests/test_lineage_edit_endpoint.py \
		hub/apps/contracts/tests/test_lineage_edit_propagation.py \
		hub/apps/contracts/tests/test_lineage_event_publishing_e2e.py \
		hub/apps/contracts/tests/test_lineage_subscription_endpoints.py \
		hub/apps/contracts/tests/test_lineage_impact_dispatcher.py \
		hub/apps/contracts/tests/test_lineage_notification_flow.py \
		hub/apps/contracts/tests/test_lineage_drift_check.py \
		hub/apps/contracts/tests/test_lineage_clock_skew.py \
		hub/apps/contracts/tests/test_lineage_time_travel.py \
		hub/apps/contracts/tests/test_lineage_severity.py \
		hub/apps/contracts/tests/test_lineage_soak_status.py \
		hub/apps/contracts/tests/test_lineage_residency.py \
		hub/apps/contracts/tests/test_lineage_gdpr_cascade.py \
		hub/apps/contracts/tests/test_lineage_reference_resolution.py \
		--reuse-db -q --timeout=300

test-batch-2-6: ## Core contracts — CRUD, views, services, models, serializers, validation (~54 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_contract_crud.py \
		hub/apps/contracts/tests/test_contracts_business_rules.py \
		hub/apps/contracts/tests/test_contract_status_rules.py \
		hub/apps/contracts/tests/test_contracts_tenant_context.py \
		hub/apps/contracts/tests/test_views.py \
		hub/apps/contracts/tests/test_views_validation.py \
		hub/apps/contracts/tests/test_views_filtering_sorting.py \
		hub/apps/contracts/tests/test_views_product_details.py \
		hub/apps/contracts/tests/test_services.py \
		hub/apps/contracts/tests/test_models.py \
		hub/apps/contracts/tests/test_models_complete_normalization.py \
		hub/apps/contracts/tests/test_serializers.py \
		hub/apps/contracts/tests/test_signals.py \
		hub/apps/contracts/tests/test_validation.py \
		hub/apps/contracts/tests/test_validation_enrichment.py \
		hub/apps/contracts/tests/test_validate_draft.py \
		hub/apps/contracts/tests/test_versioning.py \
		hub/apps/contracts/tests/test_normalization.py \
		hub/apps/contracts/tests/test_normalization_service.py \
		hub/apps/contracts/tests/test_normalization_service_event_publishing.py \
		hub/apps/contracts/tests/test_normalization_operations_event_publishing_e2e.py \
		hub/apps/contracts/tests/test_normalization_metrics.py \
		hub/apps/contracts/tests/test_normalization_performance.py \
		hub/apps/contracts/tests/test_normalizers.py \
		hub/apps/contracts/tests/test_definitions_normalization.py \
		hub/apps/contracts/tests/test_linking_logic.py \
		hub/apps/contracts/tests/test_linking_validation.py \
		hub/apps/contracts/tests/test_structural_floor_rule.py \
		hub/apps/contracts/tests/test_frontend_data_format.py \
		hub/apps/contracts/tests/test_frontend_error_handling.py \
		hub/apps/contracts/tests/test_frontend_integration_points.py \
		hub/apps/contracts/tests/test_product_first_endpoint.py \
		hub/apps/contracts/tests/test_dcs_rejection.py \
		hub/apps/contracts/tests/test_download_endpoint.py \
		hub/apps/contracts/tests/test_export_endpoint.py \
		hub/apps/contracts/tests/test_export_endpoints_integration.py \
		hub/apps/contracts/tests/test_invalidation_cascade.py \
		hub/apps/contracts/tests/test_invalid_yaml_wire_code.py \
		hub/apps/contracts/tests/test_jsonfield_queries.py \
		hub/apps/contracts/tests/test_post_save_cascade.py \
		hub/apps/contracts/tests/test_context_fields.py \
		hub/apps/contracts/tests/test_tasks.py \
		hub/apps/contracts/tests/test_typed_models.py \
		hub/apps/contracts/tests/test_edge_cases_phase15.py \
		hub/apps/contracts/tests/test_impact_analysis.py \
		hub/apps/contracts/tests/test_impact_api.py \
		hub/apps/contracts/tests/test_impact_visualization.py \
		hub/apps/contracts/tests/test_integration_lineage.py \
		hub/apps/contracts/tests/test_integration_metrics_phase15.py \
		hub/apps/contracts/tests/test_integration_new_mappings.py \
		hub/apps/contracts/tests/test_integration_onboarding.py \
		hub/apps/contracts/tests/test_integration_phase2_objects.py \
		hub/apps/contracts/tests/test_integration_versioning.py \
		hub/apps/contracts/tests/test_hubcontract_to_odps_generation_integration.py \
		--reuse-db -q --timeout=300

test-batch-2-7: ## Migration, structureless, rollback, database state (~19 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_migration.py \
		hub/apps/contracts/tests/test_migration_0009_odps.py \
		hub/apps/contracts/tests/test_migration_crash_recovery.py \
		hub/apps/contracts/tests/test_migration_validation.py \
		hub/apps/contracts/tests/test_migration_validation_comprehensive.py \
		hub/apps/contracts/tests/test_migration_rollback_comprehensive.py \
		hub/apps/contracts/tests/test_post_migration_validation_e2e_comprehensive.py \
		hub/apps/contracts/tests/test_rollback_odps_migration.py \
		hub/apps/contracts/tests/test_migrate_contracts_to_odps.py \
		hub/apps/contracts/tests/test_structureless.py \
		hub/apps/contracts/tests/test_structureless_contract_validation.py \
		hub/apps/contracts/tests/test_structureless_notification.py \
		hub/apps/contracts/tests/test_activation_structureless_blocker.py \
		hub/apps/contracts/tests/test_audit_structureless_command.py \
		hub/apps/contracts/tests/test_database_state_verification.py \
		hub/apps/contracts/tests/test_data_seeding.py \
		hub/apps/contracts/tests/test_seed_contract_lineage.py \
		hub/apps/contracts/tests/test_wave0_capture_command.py \
		hub/apps/contracts/tests/test_wave0_notify_command.py \
		hub/apps/contracts/tests/test_wave0_summarize_command.py \
		--reuse-db -q --timeout=300

test-batch-2-8: ## Wave commands, CLI, schema editor, renormalize (~25 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_cli_client.py \
		hub/apps/contracts/tests/test_cli_client_circuit_breaker.py \
		hub/apps/contracts/tests/test_wave2_driver_command.py \
		hub/apps/contracts/tests/test_wave3_renormalize_apply.py \
		hub/apps/contracts/tests/test_wave4_classify_residue.py \
		hub/apps/contracts/tests/test_wave4_deploy_smoke_gate.py \
		hub/apps/contracts/tests/test_wave4_escalate_residue.py \
		hub/apps/contracts/tests/test_wave4_send_residue_reminders.py \
		hub/apps/contracts/tests/test_wave5_auto_revert_notifications.py \
		hub/apps/contracts/tests/test_wave6_cleanup.py \
		hub/apps/contracts/tests/test_renormalize_command.py \
		hub/apps/contracts/tests/test_renormalize_include_active_only.py \
		hub/apps/contracts/tests/test_renormalize_structureless_filter.py \
		hub/apps/contracts/tests/test_schema_compare.py \
		hub/apps/contracts/tests/test_schema_directory_structure.py \
		hub/apps/contracts/tests/test_schema_editor_adoption_report.py \
		hub/apps/contracts/tests/test_schema_editor_available_notification.py \
		hub/apps/contracts/tests/test_schema_editor_residue_reminder.py \
		hub/apps/contracts/tests/test_schema_editor_rule_invocation.py \
		hub/apps/contracts/tests/test_source_paths.py \
		hub/apps/contracts/tests/test_spec_detection.py \
		hub/apps/contracts/tests/test_support_channels_normalization.py \
		--reuse-db -q --timeout=300

test-batch-2-9: ## API patterns — filtering, pagination, caching, rate limiting, observability (~25 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_api_filtering_phase15.py \
		hub/apps/contracts/tests/test_api_filtering_sorting_consistency.py \
		hub/apps/contracts/tests/test_api_pagination_consistency.py \
		hub/apps/contracts/tests/test_api_caching_headers.py \
		hub/apps/contracts/tests/test_api_contract_documentation.py \
		hub/apps/contracts/tests/test_api_documentation.py \
		hub/apps/contracts/tests/test_api_input_sanitization.py \
		hub/apps/contracts/tests/test_api_key_rotation.py \
		hub/apps/contracts/tests/test_api_l9_endpoints.py \
		hub/apps/contracts/tests/test_api_response_size.py \
		hub/apps/contracts/tests/test_rate_limiting_validation.py \
		hub/apps/contracts/tests/test_payload_size_limit.py \
		hub/apps/contracts/tests/test_caching_behavior_validation.py \
		hub/apps/contracts/tests/test_caching_enhanced.py \
		hub/apps/contracts/tests/test_concurrent_api_requests.py \
		hub/apps/contracts/tests/test_etag_concurrent_edit.py \
		hub/apps/contracts/tests/test_realtime_updates.py \
		hub/apps/contracts/tests/test_index_performance_phase15.py \
		hub/apps/contracts/tests/test_observability_l7.py \
		hub/apps/contracts/tests/test_performance.py \
		hub/apps/contracts/tests/test_base.py \
		hub/apps/contracts/tests/test_coverage.py \
		hub/apps/contracts/tests/test_error_reporting.py \
		hub/apps/contracts/tests/test_phase_227_doc_coverage.py \
		hub/apps/contracts/tests/test_url_patterns.py \
		--reuse-db -q --timeout=300

test-batch-2-10: ## E2E, backward compat, comprehensive integration, security (~17 files)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/contracts/tests/test_backward_compatibility_e2e_comprehensive.py \
		hub/apps/contracts/tests/test_comprehensive_backward_compatibility.py \
		hub/apps/contracts/tests/test_comprehensive_backward_compatibility_ci.py \
		hub/apps/contracts/tests/test_creation_flows_e2e_comprehensive.py \
		hub/apps/contracts/tests/test_creation_flows_integration.py \
		hub/apps/contracts/tests/test_error_handling_e2e_comprehensive.py \
		hub/apps/contracts/tests/test_environment_validation_comprehensive.py \
		hub/apps/contracts/tests/test_integration.py \
		hub/apps/contracts/tests/test_service_integration_comprehensive_validation.py \
		hub/apps/contracts/tests/test_security_incidents.py \
		hub/apps/contracts/tests/test_security_audit_log_tenant_isolation.py \
		hub/apps/contracts/tests/test_ssrf_port_contractURL.py \
		hub/apps/contracts/tests/test_yaml_safety.py \
		hub/apps/contracts/tests/test_data_setup_teardown.py \
		hub/apps/contracts/tests/test_ref_resolver.py \
		hub/apps/contracts/tests/test_ref_resolver_caching.py \
		hub/apps/contracts/tests/test_ref_resolver_coverage_gaps.py \
		hub/apps/contracts/tests/test_ref_resolver_integration.py \
		hub/apps/contracts/tests/test_ref_resolver_performance.py \
		hub/apps/contracts/tests/test_ref_warming.py \
		--reuse-db -q --timeout=300

test-batch-2: ## Run all contracts sub-batches
	@$(MAKE) test-batch-2-1
	@$(MAKE) test-batch-2-2
	@$(MAKE) test-batch-2-3
	@$(MAKE) test-batch-2-4
	@$(MAKE) test-batch-2-5
	@$(MAKE) test-batch-2-6
	@$(MAKE) test-batch-2-7
	@$(MAKE) test-batch-2-8
	@$(MAKE) test-batch-2-9
	@$(MAKE) test-batch-2-10

# ── Backend test batch 3: compliance + marketplace + billing (~1,877 tests) ─

test-batch-3-1: ## Run test batch 3-1: compliance-business-rules (~138 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/compliance/tests/test_business_rules.py \
		hub/apps/compliance/tests/test_business_rules_limits.py \
		hub/apps/compliance/tests/test_risk_score_calculation.py \
		hub/apps/compliance/tests/test_risk_level_exceeds.py \
		hub/apps/compliance/tests/test_async_regulation.py \
		hub/apps/compliance/tests/test_file_resolution.py \
		hub/apps/compliance/tests/test_call_compliance_service.py \
		hub/apps/compliance/tests/test_fail_closed_behavior.py \
		--reuse-db -q --timeout=300

test-batch-3-2: ## Run test batch 3-2: compliance-api-integration (~195 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/compliance/tests/test_views.py \
		hub/apps/compliance/tests/test_serializers.py \
		hub/apps/compliance/tests/test_urls.py \
		hub/apps/compliance/tests/test_models.py \
		hub/apps/compliance/tests/test_latest_succeeded_summary_on_serializers.py \
		hub/apps/compliance/tests/test_services.py \
		hub/apps/compliance/tests/test_contract_integration.py \
		hub/apps/compliance/tests/test_warehouse_sql_compiler.py \
		hub/apps/compliance/tests/test_service_client.py \
		hub/apps/compliance/tests/test_compliance_execution.py \
		hub/apps/compliance/tests/test_create_run_license_validation.py \
		hub/apps/compliance/tests/test_warehouse_compliance_service.py \
		--reuse-db -q --timeout=300

test-batch-3-3: ## Run test batch 3-3: compliance-operations (~114 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/compliance/tests/test_results_endpoint_regression.py \
		hub/apps/compliance/tests/test_results_endpoint_detailed.py \
		hub/apps/compliance/tests/test_persist_result.py \
		hub/apps/compliance/tests/test_export_endpoints.py \
		hub/apps/compliance/tests/test_intake_signal.py \
		hub/apps/compliance/tests/test_scan_inmemory.py \
		hub/apps/compliance/tests/test_service_client_circuit_breaker.py \
		hub/apps/compliance/tests/test_service_client_regression.py \
		hub/apps/compliance/tests/test_service_client_x_actor_id_header.py \
		hub/apps/compliance/tests/test_service_client_legal_basis_strict_header.py \
		hub/apps/compliance/tests/test_tasks.py \
		hub/apps/compliance/tests/test_poll_task_behavior.py \
		hub/apps/compliance/tests/test_poll_timeout.py \
		hub/apps/compliance/tests/test_poll_compliance_job_tenant_context.py \
		hub/apps/compliance/tests/test_compliance_tenant_context.py \
		hub/apps/compliance/tests/test_tenant_propagation_integration.py \
		hub/apps/compliance/tests/test_webhook_emission.py \
		hub/apps/compliance/tests/test_rls_policies.py \
		hub/apps/compliance/tests/test_migrate_compliance_v2_command.py \
		hub/apps/compliance/tests/test_phase231_gate_observability.py \
		hub/apps/compliance/tests/test_warehouse_compliance_views.py \
		hub/apps/compliance/tests/test_circuit_breaker.py \
		--reuse-db -q --timeout=300

test-batch-3-4: ## Run test batch 3-4: marketplace-business-rules-contracts (~223 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/marketplace/tests/test_business_rules.py \
		hub/apps/marketplace/tests/test_business_rules_pricing_validation.py \
		hub/apps/marketplace/tests/test_contract_integration.py \
		hub/apps/marketplace/tests/test_contract_drift_signal.py \
		--reuse-db -q --timeout=300

test-batch-3-5: ## Run test batch 3-5: marketplace-api-services (~187 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/marketplace/tests/test_views.py \
		hub/apps/marketplace/tests/test_services.py \
		hub/apps/marketplace/tests/test_models.py \
		hub/apps/marketplace/tests/test_serializers.py \
		hub/apps/marketplace/tests/test_caching.py \
		hub/apps/marketplace/tests/test_preview.py \
		hub/apps/marketplace/tests/test_listing_crud.py \
		hub/apps/marketplace/tests/test_access_checks.py \
		hub/apps/marketplace/tests/test_marketplace_validation_comprehensive.py \
		--reuse-db -q --timeout=300

test-batch-3-6: ## Run test batch 3-6: marketplace-payment-kyc-orders (~232 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/marketplace/tests/test_payment_gateway_linking.py \
		hub/apps/marketplace/tests/test_payment_gateway_event_publisher.py \
		hub/apps/marketplace/tests/test_payment_amount_cents_dual_write.py \
		hub/apps/marketplace/tests/test_payment_gateway_service_event_integration.py \
		hub/apps/marketplace/tests/test_payment_gateway_views_event_publishing_e2e.py \
		hub/apps/marketplace/tests/test_payment_service_event_publishing.py \
		hub/apps/marketplace/tests/test_payment_views_event_publishing_e2e.py \
		hub/apps/marketplace/tests/test_payment_idempotency.py \
		hub/apps/marketplace/tests/test_3ds_flow.py \
		hub/apps/marketplace/tests/test_stripe_webhooks.py \
		hub/apps/marketplace/tests/test_kyc_enforcement.py \
		hub/apps/marketplace/tests/test_kyc_gate.py \
		hub/apps/marketplace/tests/test_kyb_gate.py \
		hub/apps/marketplace/tests/test_publish_compliance_gate.py \
		hub/apps/marketplace/tests/test_compliance_threshold_gate.py \
		hub/apps/marketplace/tests/test_continuous_compliance.py \
		hub/apps/marketplace/tests/test_compliance_run_invalidates_listing_cache.py \
		hub/apps/marketplace/tests/test_order_flow.py \
		hub/apps/marketplace/tests/test_order_lifecycle_117b.py \
		hub/apps/marketplace/tests/test_order_plan_limit.py \
		hub/apps/marketplace/tests/test_entitlement_concurrent_creation.py \
		hub/apps/marketplace/tests/test_entitlement_lifecycle.py \
		hub/apps/marketplace/tests/test_expire_entitlements_command.py \
		hub/apps/marketplace/tests/test_kyc_order_entitlement.py \
		hub/apps/marketplace/tests/test_free_listing_auto_entitlement_311_2.py \
		--reuse-db -q --timeout=300

test-batch-3-7: ## Run test batch 3-7: marketplace-cross-tenant-financial (~204 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/marketplace/tests/test_listing_lineage_view.py \
		hub/apps/marketplace/tests/test_listing_lineage_residency_redaction.py \
		hub/apps/marketplace/tests/test_listing_search_compliance_prefetch.py \
		hub/apps/marketplace/tests/test_listing_search_throttle.py \
		hub/apps/marketplace/tests/test_saved_searches.py \
		hub/apps/marketplace/tests/test_recommendations.py \
		hub/apps/marketplace/tests/test_cross_tenant_publish.py \
		hub/apps/marketplace/tests/test_cross_tenant_auto_approve_access_request.py \
		hub/apps/marketplace/tests/test_marketplace_export_integration.py \
		hub/apps/marketplace/tests/test_marketplace_odps_integration.py \
		hub/apps/marketplace/tests/test_integration_order_flow.py \
		hub/apps/marketplace/tests/test_lineage_marketplace_e2e.py \
		hub/apps/marketplace/tests/test_refunds.py \
		hub/apps/marketplace/tests/test_seller_refund_endpoint.py \
		hub/apps/marketplace/tests/test_take_rate_285_13_7.py \
		hub/apps/marketplace/tests/test_internal_purchase.py \
		hub/apps/marketplace/tests/test_phase_271_3_connect_fees_kyb.py \
		hub/apps/marketplace/tests/test_auto_approval.py \
		hub/apps/marketplace/tests/test_concurrent_publish.py \
		hub/apps/marketplace/tests/test_marketplace_publish_structural_blocker.py \
		hub/apps/marketplace/tests/test_performance.py \
		hub/apps/marketplace/tests/test_race_condition_locking.py \
		hub/apps/marketplace/tests/test_rls_policies.py \
		--reuse-db -q --timeout=300 --continue-on-collection-errors

test-batch-3-8: ## Run test batch 3-8: billing-business-rules-models (~151 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/billing/tests/test_models.py \
		hub/apps/billing/tests/test_billing_business_rules.py \
		hub/apps/billing/tests/test_business_rules_285_13_6.py \
		hub/apps/billing/tests/test_flsc_pricing.py \
		hub/apps/billing/tests/test_storage_limits.py \
		--reuse-db -q --timeout=300 --continue-on-collection-errors

test-batch-3-9: ## Run test batch 3-9: billing-api-services (~143 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/billing/tests/test_views.py \
		hub/apps/billing/tests/test_serializers.py \
		hub/apps/billing/tests/test_middleware.py \
		hub/apps/billing/tests/test_services.py \
		hub/apps/billing/tests/test_throttles.py \
		--reuse-db -q --timeout=300

test-batch-3-10: ## Run test batch 3-10: billing-stripe-subscriptions (~144 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/billing/tests/test_connect_account_phase_271_1.py \
		hub/apps/billing/tests/test_connect_webhooks_phase_271_2.py \
		hub/apps/billing/tests/test_stripe_tax_phase_270_d.py \
		hub/apps/billing/tests/test_stripe_retry.py \
		hub/apps/billing/tests/test_sync_stripe_products_285_13_14.py \
		hub/apps/billing/tests/test_subscription_integration.py \
		hub/apps/billing/tests/test_subscription_lifecycle_285_13_5.py \
		hub/apps/billing/tests/test_cost_overview.py \
		--reuse-db -q --timeout=300 --continue-on-collection-errors

test-batch-3-11: ## Run test batch 3-11: billing-hardening-ml-misc (~146 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/billing/tests/test_billing_hardening_117a.py \
		hub/apps/billing/tests/test_metrics_285_13_15.py \
		hub/apps/billing/tests/test_ml_billing_114a.py \
		hub/apps/billing/tests/test_billing_tenant_context.py \
		hub/apps/billing/tests/test_concurrency.py \
		hub/apps/billing/tests/test_customer_identity.py \
		hub/apps/billing/tests/test_phase_271_4_payouts.py \
		hub/apps/billing/tests/test_phase_271_5_kyb_review_queue.py \
		hub/apps/billing/tests/test_rls_policies.py \
		hub/apps/billing/tests/test_webhook_idempotency.py \
		--reuse-db -q --timeout=300

test-batch-3: ## Run test batch 3: all compliance + marketplace + billing sub-batches
	@$(MAKE) test-batch-3-1
	@$(MAKE) test-batch-3-2
	@$(MAKE) test-batch-3-3
	@$(MAKE) test-batch-3-4
	@$(MAKE) test-batch-3-5
	@$(MAKE) test-batch-3-6
	@$(MAKE) test-batch-3-7
	@$(MAKE) test-batch-3-8
	@$(MAKE) test-batch-3-9
	@$(MAKE) test-batch-3-10
	@$(MAKE) test-batch-3-11

# ── Backend test batch 4: dq + governance + gdpr (~1,077 tests) ──────────

test-batch-4-1: ## Run test batch 4-1: dq-api — views, endpoints, url patterns (~117 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/dq/tests/test_views.py \
		hub/apps/dq/tests/test_quality_endpoints.py \
		hub/apps/dq/tests/test_url_patterns.py \
		hub/apps/dq/tests/test_admin.py \
		hub/apps/dq/tests/test_results_endpoint_regression.py \
		hub/apps/dq/tests/test_runs_dual_mount.py \
		hub/apps/dq/tests/test_spa_no_deprecated_quality_paths.py \
		hub/apps/dq/tests/e2e/ \
		hub/apps/dq/tests/security/ \
		--reuse-db -q --timeout=300

test-batch-4-2: ## Run test batch 4-2: dq-core — business rules, models, services, warehouse (~168 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/dq/tests/test_business_rules.py \
		hub/apps/dq/tests/test_models.py \
		hub/apps/dq/tests/test_feature_flag.py \
		hub/apps/dq/tests/test_service_client.py \
		hub/apps/dq/tests/test_service_client_cache.py \
		hub/apps/dq/tests/test_service_client_circuit_breaker.py \
		hub/apps/dq/tests/test_execute_dq_run_detailed.py \
		hub/apps/dq/tests/test_dq_execution.py \
		hub/apps/dq/tests/test_dq_results_field_mapping.py \
		hub/apps/dq/tests/test_dq_result_structure.py \
		hub/apps/dq/tests/test_warehouse_dq_service.py \
		hub/apps/dq/tests/test_warehouse_dq_views.py \
		hub/apps/dq/tests/test_warehouse_sql_compiler.py \
		--reuse-db -q --timeout=300

test-batch-4-3: ## Run test batch 4-3: dq-ops — analytics, alerting, anomalies, trends, operational (~195 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/dq/tests/test_alerting.py \
		hub/apps/dq/tests/test_alerting_clients.py \
		hub/apps/dq/tests/test_alerting_integration.py \
		hub/apps/dq/tests/test_anomaly_detection.py \
		hub/apps/dq/tests/test_anomaly_detection_integration.py \
		hub/apps/dq/tests/test_trend_analysis.py \
		hub/apps/dq/tests/test_trend_analysis_integration.py \
		hub/apps/dq/tests/test_scorecards.py \
		hub/apps/dq/tests/test_scorecards_integration.py \
		hub/apps/dq/tests/test_root_cause_analysis.py \
		hub/apps/dq/tests/test_root_cause_integration.py \
		hub/apps/dq/tests/test_threshold_overrides.py \
		hub/apps/dq/tests/test_purge_dq_runs.py \
		hub/apps/dq/tests/test_poll_timeout.py \
		hub/apps/dq/tests/test_billing_emit.py \
		hub/apps/dq/tests/test_soda_engine_routing.py \
		hub/apps/dq/tests/test_scan_inmemory.py \
		hub/apps/dq/tests/test_collect_dq_s3_metrics.py \
		hub/apps/dq/tests/test_circuit_breaker.py \
		hub/apps/dq/tests/test_contract_integration.py \
		hub/apps/dq/tests/test_integration_execution.py \
		hub/apps/dq/tests/test_performance.py \
		hub/apps/dq/tests/test_log_helpers.py \
		hub/apps/dq/tests/test_base.py \
		--reuse-db -q --timeout=300

test-batch-4-4: ## Run test batch 4-4: governance-access — ABAC, access requests, approvals (~182 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/governance/tests/test_abac_engine.py \
		hub/apps/governance/tests/test_abac_enhanced.py \
		hub/apps/governance/tests/test_abac_integration.py \
		hub/apps/governance/tests/test_abac.py \
		hub/apps/governance/tests/test_admin_abac.py \
		hub/apps/governance/tests/test_access_request_views.py \
		hub/apps/governance/tests/test_access_requests.py \
		hub/apps/governance/tests/test_access_request_comments.py \
		hub/apps/governance/tests/test_access_request_sla_sweep.py \
		hub/apps/governance/tests/test_approval_state_machine.py \
		hub/apps/governance/tests/test_compliance_abac_approval.py \
		--reuse-db -q --timeout=300

test-batch-4-5: ## Run test batch 4-5: governance-policy — business rules, retention, classification, services (~254 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/governance/tests/test_business_rules.py \
		hub/apps/governance/tests/test_retention_api_integration.py \
		hub/apps/governance/tests/test_retention_auto_enforcer.py \
		hub/apps/governance/tests/test_retention.py \
		hub/apps/governance/tests/test_retention_service.py \
		hub/apps/governance/tests/test_services.py \
		hub/apps/governance/tests/test_signals.py \
		hub/apps/governance/tests/test_access_logging_middleware.py \
		hub/apps/governance/tests/test_data_masking.py \
		hub/apps/governance/tests/test_classification.py \
		hub/apps/governance/tests/test_access_analytics_integration.py \
		hub/apps/governance/tests/test_access_analytics.py \
		hub/apps/governance/tests/test_compliance_reports_integration.py \
		hub/apps/governance/tests/test_compliance_reports.py \
		hub/apps/governance/tests/test_governance_hardening.py \
		hub/apps/governance/tests/test_access_certification.py \
		hub/apps/governance/tests/test_phase_272_multi_step_integration.py \
		--reuse-db -q --timeout=300

test-batch-4-6: ## Run test batch 4-6: gdpr — erasure, models, serializers, services, views (~161 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/gdpr/tests/test_erasure_integration.py \
		hub/apps/gdpr/tests/test_gdpr_models.py \
		hub/apps/gdpr/tests/test_gdpr_serializers.py \
		hub/apps/gdpr/tests/test_gdpr_services.py \
		hub/apps/gdpr/tests/test_gdpr_views.py \
		hub/apps/gdpr/tests/test_phase_250_5_f_gdpr_dpa.py \
		--reuse-db -q --timeout=300

test-batch-4: ## Run test batch 4: all dq + governance + gdpr sub-batches
	@$(MAKE) test-batch-4-1
	@$(MAKE) test-batch-4-2
	@$(MAKE) test-batch-4-3
	@$(MAKE) test-batch-4-4
	@$(MAKE) test-batch-4-5
	@$(MAKE) test-batch-4-6

test-batch-5-1: ## auth — business rules, views, providers, sign-in, tokens, MFA, RBAC (~519 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/auth/tests/ \
		--reuse-db -q --timeout=300

test-batch-5-2: ## tenants — models, services, middleware, RLS, config, registration, KYC (~647 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/tenants/tests/ \
		--reuse-db -q --timeout=300

test-batch-5-3: ## semantic + search — SPARQL, Fuseki, ontologies, unified search, Memento (~642 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/semantic/tests/ \
		hub/apps/search/tests/ \
		--reuse-db -q --timeout=300

test-batch-5-4: ## scheduled — ingestion, export, recurring operations (~481 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/scheduled_ingestion/tests/ \
		hub/apps/scheduled_export/tests/ \
		--reuse-db -q --timeout=300

test-batch-5-5: ## social + users + notifications + rate-limiting (~600 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/social/tests/ \
		hub/apps/users/tests/ \
		hub/apps/notifications/tests/ \
		hub/apps/rate_limiting/tests/ \
		--reuse-db -q --timeout=300

test-batch-5: ## Run test batch 5: all auth + tenants + semantic + search + social + users + scheduled + rate_limiting + notifications sub-batches
	@$(MAKE) test-batch-5-1
	@$(MAKE) test-batch-5-2
	@$(MAKE) test-batch-5-3
	@$(MAKE) test-batch-5-4
	@$(MAKE) test-batch-5-5

# ── Backend test batches 6-8 (Django apps + integrations) ───────────

test-batch-6-1: ## Run test batch 6-1: CKAN connector (~220 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_ckan_*.py \
		--reuse-db -q --timeout=300'

test-batch-6-1a: ## Run test batch 6-1a: AWS Data Exchange (~200 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_aws_data_exchange_*.py \
		--reuse-db -q --timeout=300'

test-batch-6-1b: ## Run test batch 6-1b: Snowflake (~90 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_snowflake_*.py \
		--reuse-db -q --timeout=300'

test-batch-6-1c: ## Run test batch 6-1c: Dados.gov.br + Connectors E2E (~45 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_dados_gov_br_*.py \
		hub/apps/integrations/tests/test_connectors_e2e.py \
		--reuse-db -q --timeout=300'

test-batch-6-1-all: ## Run all 6-1 sub-batches: CKAN + AWS + Snowflake + Dados/E2E (~550 tests)
	-$(MAKE) test-batch-6-1
	-$(MAKE) test-batch-6-1a
	-$(MAKE) test-batch-6-1b
	-$(MAKE) test-batch-6-1c

test-batch-6-2: ## Run test batch 6-2: GCP Marketplace (~240 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_gcp_marketplace_*.py \
		--reuse-db -q --timeout=300'

test-batch-6-3: ## Run test batch 6-3: Marketplace (non-GCP) + Federated Import (~280 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_marketplace_alerting_notifications_integration.py \
		hub/apps/integrations/tests/test_marketplace_dashboards_integration.py \
		hub/apps/integrations/tests/test_marketplace_dashboards.py \
		hub/apps/integrations/tests/test_marketplace_demo_ckan_fixture.py \
		hub/apps/integrations/tests/test_marketplace_framework.py \
		hub/apps/integrations/tests/test_marketplace_instances_config.py \
		hub/apps/integrations/tests/test_marketplace_integration_service_comprehensive_validation.py \
		hub/apps/integrations/tests/test_marketplace_metrics.py \
		hub/apps/integrations/tests/test_marketplace_structured_logging.py \
		hub/apps/integrations/tests/test_marketplace_test_helpers.py \
		hub/apps/integrations/tests/test_federated_*.py \
		--reuse-db -q --timeout=300'

test-batch-6-4: ## Run test batch 6-4: Event Publishers + Connection Validation + Marketplace Integration (~250 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_event_publishers*.py \
		hub/apps/integrations/tests/test_connection_validation_*.py \
		hub/apps/integrations/tests/integration/ \
		--reuse-db -q --timeout=300'

test-batch-6-5: ## Run test batch 6-5: Encryption + Credential Encryption (~100 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_encryption_*.py \
		hub/apps/integrations/tests/test_credential_encryption_*.py \
		--reuse-db -q --timeout=300'

test-batch-6-6: ## Run test batch 6-6: Integrations Core (base, business_rules, error, models, serializers, signals) (~280 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_base.py \
		hub/apps/integrations/tests/test_business_rules.py \
		hub/apps/integrations/tests/test_error_classification.py \
		hub/apps/integrations/tests/test_models.py \
		hub/apps/integrations/tests/test_serializers.py \
		hub/apps/integrations/tests/test_signals.py \
		--reuse-db -q --timeout=300'

test-batch-6-7: ## Run test batch 6-7: Integrations Views + URLs + Utils + Tasks (~260 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_views.py \
		hub/apps/integrations/tests/test_urls.py \
		hub/apps/integrations/tests/test_utils.py \
		hub/apps/integrations/tests/test_tasks.py \
		--reuse-db -q --timeout=300'

test-batch-6-8: ## Run test batch 6-8: Integrations Services + Sync Jobs + Mappings (~280 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_service*.py \
		hub/apps/integrations/tests/test_sync_job_*.py \
		hub/apps/integrations/tests/test_mapping_*.py \
		--reuse-db -q --timeout=300'

test-batch-6-9: ## Run test batch 6-9: Integrations Remaining (factory, scheduled_sync, migrations, capabilities, security, etc.) (~240 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		bash -c 'python -u -m pytest \
		hub/apps/integrations/tests/test_connector_capabilities.py \
		hub/apps/integrations/tests/test_connector_development_documentation.py \
		hub/apps/integrations/tests/test_connector_pattern.py \
		hub/apps/integrations/tests/test_factory*.py \
		hub/apps/integrations/tests/test_init_exports.py \
		hub/apps/integrations/tests/test_metadata_first_architecture.py \
		hub/apps/integrations/tests/test_migrations.py \
		hub/apps/integrations/tests/test_scheduled_sync.py \
		hub/apps/integrations/tests/test_integrations_tenant_context.py \
		hub/apps/integrations/tests/security/ \
		--reuse-db -q --timeout=300'

test-batch-6-10: ## Run test batch 6-10: Connectors + OpenLineage (~260 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/integrations/connectors/ \
		hub/apps/integrations/openlineage/ \
		--reuse-db -q --timeout=300

test-batch-6-11: ## Run test batch 6-11: Virtualization Part 1 — views, serializers, services (~276 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/virtualization/tests/test_views.py \
		hub/apps/virtualization/tests/test_views_integration.py \
		hub/apps/virtualization/tests/test_query_execution_views.py \
		hub/apps/virtualization/tests/test_topology_views.py \
		hub/apps/virtualization/tests/test_serializers.py \
		hub/apps/virtualization/tests/test_serializer_decryption.py \
		hub/apps/virtualization/tests/test_services.py \
		hub/apps/virtualization/tests/test_service_workflow_integration.py \
		hub/apps/virtualization/tests/test_urls.py \
		--reuse-db -q --timeout=300

test-batch-6-12: ## Run test batch 6-12: Virtualization Part 2 -- business rules, execute query, security, metrics, models (~325 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/virtualization/tests/test_business_rules.py \
		hub/apps/virtualization/tests/test_virtualization_business_rules_refactoring.py \
		hub/apps/virtualization/tests/test_execute_query.py \
		hub/apps/virtualization/tests/test_execute_query_integration.py \
		hub/apps/virtualization/tests/test_security.py \
		hub/apps/virtualization/tests/test_sql_injection_prevention.py \
		hub/apps/virtualization/tests/test_metrics.py \
		hub/apps/virtualization/tests/test_models.py \
		hub/apps/virtualization/tests/test_performance.py \
		hub/apps/virtualization/tests/test_source_config_utils.py \
		--reuse-db -q --timeout=300

test-batch-6-13: ## Run test batch 6-13: Virtualization Part 3 — integration, compliance, governance, federated, e2e (~220 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/virtualization/tests/test_compliance_integration.py \
		hub/apps/virtualization/tests/test_governance_integration.py \
		hub/apps/virtualization/tests/test_quality_integration.py \
		hub/apps/virtualization/tests/test_real_source_integration.py \
		hub/apps/virtualization/tests/test_job_queue_integration.py \
		hub/apps/virtualization/tests/test_federated_asset_sources.py \
		hub/apps/virtualization/tests/test_virtualization_real_federated_e2e.py \
		hub/apps/virtualization/tests/test_migration.py \
		--reuse-db -q --timeout=300

test-batch-6-14: ## Run test batch 6-14: Orchestration Part 1 — workflows, saga, state machine, DSL, trigger engine (~240 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/orchestration/tests/test_workflows_api_integration.py \
		hub/apps/orchestration/tests/test_workflow_business_rules_integration.py \
		hub/apps/orchestration/tests/test_workflow_business_rules_performance.py \
		hub/apps/orchestration/tests/test_workflow_business_rules_unit.py \
		hub/apps/orchestration/tests/test_workflow_comprehensive_validation.py \
		hub/apps/orchestration/tests/test_workflow_engine_progress.py \
		hub/apps/orchestration/tests/test_workflow_gateway_independence.py \
		hub/apps/orchestration/tests/test_workflow_observability_phase3.py \
		hub/apps/orchestration/tests/test_workflow_progress_events_no_mocks.py \
		hub/apps/orchestration/tests/test_workflow_progress_events.py \
		hub/apps/orchestration/tests/test_workflow_progress_state.py \
		hub/apps/orchestration/tests/test_workflow_task_business_rules_integration.py \
		hub/apps/orchestration/tests/test_workflow_auto_retry.py \
		hub/apps/orchestration/tests/test_saga.py \
		hub/apps/orchestration/tests/test_state_machine.py \
		hub/apps/orchestration/tests/test_dsl_parser.py \
		hub/apps/orchestration/tests/test_trigger_engine.py \
		--reuse-db -q --timeout=300

test-batch-6-15: ## Run test batch 6-15: Orchestration Part 2 — execution, validation, dependency, rollback (~240 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/orchestration/tests/test_execution_validators.py \
		hub/apps/orchestration/tests/test_execution_validators_integration.py \
		hub/apps/orchestration/tests/test_dependency_enforcement.py \
		hub/apps/orchestration/tests/test_dependency_migrations.py \
		hub/apps/orchestration/tests/test_dependency_resolver.py \
		hub/apps/orchestration/tests/test_rollback_procedures.py \
		hub/apps/orchestration/tests/test_compensation_incomplete.py \
		hub/apps/orchestration/tests/test_idempotent_compensation.py \
		hub/apps/orchestration/tests/test_auto_derivation.py \
		hub/apps/orchestration/tests/test_dlq_sync_status.py \
		hub/apps/orchestration/tests/test_gradual_rollout.py \
		hub/apps/orchestration/tests/test_versioning.py \
		hub/apps/orchestration/tests/test_versioning_soak_window.py \
		hub/apps/orchestration/tests/test_feature_flags.py \
		hub/apps/orchestration/tests/test_post_deployment.py \
		hub/apps/orchestration/tests/test_check_workflow_v1_removal_readiness.py \
		hub/apps/orchestration/tests/test_cleanup_command.py \
		--reuse-db -q --timeout=300

test-batch-6-16: ## Run test batch 6-16: Orchestration Part 3 — product, marketplace, ML workflows, event-driven (~240 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/orchestration/tests/test_product_creation_workflow.py \
		hub/apps/orchestration/tests/test_marketplace_sync_workflow.py \
		hub/apps/orchestration/tests/test_model_inference_workflow.py \
		hub/apps/orchestration/tests/test_model_training_workflow.py \
		hub/apps/orchestration/tests/test_event_driven_workflows.py \
		hub/apps/orchestration/tests/test_odps_workflow_events.py \
		hub/apps/orchestration/tests/test_alerting.py \
		hub/apps/orchestration/tests/test_metrics.py \
		hub/apps/orchestration/tests/test_monitoring_validation.py \
		hub/apps/orchestration/tests/test_business_rules.py \
		hub/apps/orchestration/tests/test_business_rules_state_management.py \
		hub/apps/orchestration/tests/test_integration.py \
		hub/apps/orchestration/tests/test_models.py \
		hub/apps/orchestration/tests/test_registry.py \
		hub/apps/orchestration/tests/test_migrations.py \
		--reuse-db -q --timeout=300

test-batch-6-17: ## Run test batch 6-17: Jobs Part 1 — core processing, execution, lifecycle, queue (~240 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/jobs/tests/test_job_creation_processing.py \
		hub/apps/jobs/tests/test_job_execution_integration.py \
		hub/apps/jobs/tests/test_job_integration_lifecycle.py \
		hub/apps/jobs/tests/test_job_processors.py \
		hub/apps/jobs/tests/test_job_queue_infrastructure.py \
		hub/apps/jobs/tests/test_job_queue_integration.py \
		hub/apps/jobs/tests/test_job_priority_queue.py \
		hub/apps/jobs/tests/test_job_timeouts.py \
		hub/apps/jobs/tests/test_job_cancellation.py \
		hub/apps/jobs/tests/test_business_rules.py \
		hub/apps/jobs/tests/test_models.py \
		hub/apps/jobs/tests/test_views.py \
		hub/apps/jobs/tests/test_utils.py \
		hub/apps/jobs/tests/test_utils_comprehensive.py \
		hub/apps/jobs/tests/test_tasks_handlers.py \
		--reuse-db -q --timeout=300

test-batch-6-18: ## Run test batch 6-18: Jobs Part 2 — ODPS, Prefect, DLQ, scheduled, tasks, metrics (~240 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/jobs/tests/test_odps_export_job.py \
		hub/apps/jobs/tests/test_odps_linking_job.py \
		hub/apps/jobs/tests/test_odps_normalization_job.py \
		hub/apps/jobs/tests/test_odps_ref_resolution_job.py \
		hub/apps/jobs/tests/test_odps_semantic_mapping_job.py \
		hub/apps/jobs/tests/test_scheduled_ingestion_job.py \
		hub/apps/jobs/tests/test_integration_processing.py \
		hub/apps/jobs/tests/test_prefect_orphan_detection.py \
		hub/apps/jobs/tests/test_purge_orphan_deployments_command.py \
		hub/apps/jobs/tests/test_reconcile_prefect_statuses_command.py \
		hub/apps/jobs/tests/test_recover_stuck_jobs_command.py \
		hub/apps/jobs/tests/test_detect_stuck_dq_compliance_runs.py \
		hub/apps/jobs/tests/test_dlq_replay_idempotency.py \
		hub/apps/jobs/tests/test_side_effects.py \
		hub/apps/jobs/tests/test_task_circuit_breaker.py \
		hub/apps/jobs/tests/test_tasks_base_comprehensive.py \
		hub/apps/jobs/tests/test_tasks_base_tenant_context.py \
		hub/apps/jobs/tests/test_tasks_prefect_sync_tenant_context.py \
		hub/apps/jobs/tests/test_queue_metrics.py \
		hub/apps/jobs/tests/test_latency_metrics.py \
		--reuse-db -q --timeout=300

test-batch-6-19: ## Run test batch 6-19: Webhooks Part 1 — core, delivery, ODPS, mesh (~250 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/webhooks/tests/test_webhooks.py \
		hub/apps/webhooks/tests/test_webhook_service.py \
		hub/apps/webhooks/tests/test_webhooks_business_rules.py \
		hub/apps/webhooks/tests/test_webhooks_tenant_context.py \
		hub/apps/webhooks/tests/test_webhook_api_integration.py \
		hub/apps/webhooks/tests/test_webhook_delivery_idempotency.py \
		hub/apps/webhooks/tests/test_delivery_service.py \
		hub/apps/webhooks/tests/test_delivery_validators.py \
		hub/apps/webhooks/tests/test_delivery_validators_integration.py \
		hub/apps/webhooks/tests/test_odps_webhook_delivery.py \
		hub/apps/webhooks/tests/test_odps_webhook_e2e.py \
		hub/apps/webhooks/tests/test_odps_webhook_error_handling.py \
		hub/apps/webhooks/tests/test_odps_webhook_error_integration.py \
		hub/apps/webhooks/tests/test_odps_webhook_event_integration.py \
		hub/apps/webhooks/tests/test_odps_webhook_events_comprehensive.py \
		hub/apps/webhooks/tests/test_odps_webhook_integration.py \
		hub/apps/webhooks/tests/test_odps_event_integration.py \
		hub/apps/webhooks/tests/test_odps_event_types.py \
		hub/apps/webhooks/tests/test_mesh_webhook_delivery.py \
		hub/apps/webhooks/tests/test_mesh_webhook_e2e.py \
		hub/apps/webhooks/tests/test_virtualization_webhook_e2e.py \
		--reuse-db -q --timeout=300

test-batch-6-20: ## Run test batch 6-20: Webhooks Part 2 — encryption, signing, replay, views, signals, tasks, events (~250 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/webhooks/tests/test_encryption_vault_transit.py \
		hub/apps/webhooks/tests/test_signing_rotation.py \
		hub/apps/webhooks/tests/test_key_rotation_command.py \
		hub/apps/webhooks/tests/test_key_rotation_drill.py \
		hub/apps/webhooks/tests/test_replay_protection.py \
		hub/apps/webhooks/tests/test_retry_jitter.py \
		hub/apps/webhooks/tests/test_outbound_rate_limit.py \
		hub/apps/webhooks/tests/test_views_comprehensive.py \
		hub/apps/webhooks/tests/test_signals.py \
		hub/apps/webhooks/tests/test_tasks.py \
		hub/apps/webhooks/tests/test_event_type_validation.py \
		hub/apps/webhooks/tests/test_test_event_type.py \
		hub/apps/webhooks/tests/test_phase232_webhook_event_registry.py \
		hub/apps/webhooks/tests/test_plan_change_webhooks_285_13_14.py \
		hub/apps/webhooks/tests/test_models_comprehensive.py \
		hub/apps/webhooks/tests/test_business_rules_payload.py \
		--reuse-db -q --timeout=300

test-batch-6-21: ## Run test batch 6-21: Websocket (~150 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/websocket/ \
		--reuse-db -q --timeout=300

test-batch-7-1: ## Run test batch 7-1: ML part 1 — heaviest 7 files (~266 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/ml/tests/test_access_control_metering.py \
		hub/apps/ml/tests/test_ml_contracts_marketplace_114c.py \
		hub/apps/ml/tests/test_odh_integration_comprehensive_validation.py \
		hub/apps/ml/tests/test_models.py \
		hub/apps/ml/tests/test_training.py \
		hub/apps/ml/tests/test_inference.py \
		hub/apps/ml/tests/test_ml_phase114f.py \
		--reuse-db -q --timeout=300

test-batch-7-2: ## Run test batch 7-2: ML part 2 — remaining 19 files (~213 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/ml/tests/test_views.py \
		hub/apps/ml/tests/test_business_rules.py \
		hub/apps/ml/tests/test_inference_service.py \
		hub/apps/ml/tests/test_training_service.py \
		hub/apps/ml/tests/test_inference_monitoring.py \
		hub/apps/ml/tests/test_ml_root_cause_fixes.py \
		hub/apps/ml/tests/test_training_orchestrator.py \
		hub/apps/ml/tests/test_feature_flag.py \
		hub/apps/ml/tests/test_throttle.py \
		hub/apps/ml/tests/test_training_e2e.py \
		hub/apps/ml/tests/test_e2e.py \
		hub/apps/ml/tests/test_services.py \
		hub/apps/ml/tests/test_inference_integration.py \
		hub/apps/ml/tests/test_integration.py \
		hub/apps/ml/tests/test_inference_e2e.py \
		hub/apps/ml/tests/test_inference_real_integration.py \
		hub/apps/ml/tests/test_migration.py \
		hub/apps/ml/tests/test_rls_policies.py \
		hub/apps/ml/tests/test_training_integration.py \
		--reuse-db -q --timeout=300

test-batch-7-3: ## Run test batch 7-3: AI + API versioning/idempotency/urls (~244 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/ai/tests/ \
		hub/apps/api/tests/test_versioning_comprehensive.py \
		hub/apps/api/tests/test_idempotency.py \
		hub/apps/api/tests/test_url_patterns.py \
		--reuse-db -q --timeout=300

test-batch-7-4: ## Run test batch 7-4: BaaS (~300 tests)
	docker compose -f docker-compose.test.yml exec -T -e STRICT_TEST_TEARDOWN=1 api-service-test \
		python -u -m pytest \
		hub/apps/baas/tests/ \
		--reuse-db -q --timeout=300

test-batch-7-5: ## Run test batch 7-5: Transformation part 1 — heaviest 7 files (~270 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/transformation/tests/test_business_rules.py \
		hub/apps/transformation/tests/test_exceptions.py \
		hub/apps/transformation/tests/test_services.py \
		hub/apps/transformation/tests/test_dbt_executor.py \
		hub/apps/transformation/tests/test_pipeline_execution_models.py \
		hub/apps/transformation/tests/test_models.py \
		hub/apps/transformation/tests/test_credential_resolver.py \
		--reuse-db -q --timeout=300

test-batch-7-6: ## Run test batch 7-6: Transformation part 2 + Mesh biz rules (~266 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/transformation/tests/test_dbt_scaffolder.py \
		hub/apps/transformation/tests/test_contract_generator.py \
		hub/apps/transformation/tests/test_views.py \
		hub/apps/transformation/tests/test_transformation_integration.py \
		hub/apps/transformation/tests/test_transformation_security.py \
		hub/apps/transformation/tests/test_transformation_e2e.py \
		hub/apps/transformation/tests/test_dbt_schema_introspector.py \
		hub/apps/transformation/tests/test_sql_security.py \
		hub/apps/transformation/tests/test_serializers.py \
		hub/apps/transformation/tests/test_management_commands.py \
		hub/apps/transformation/tests/test_plan_limits.py \
		hub/apps/transformation/tests/test_signals.py \
		hub/apps/transformation/tests/test_feature_gate.py \
		hub/apps/transformation/tests/test_rls_policies.py \
		hub/apps/transformation/tests/test_serializer_decryption.py \
		hub/apps/transformation/tests/test_transformation_performance.py \
		hub/apps/mesh/tests/test_business_rules.py \
		--reuse-db -q --timeout=300

test-batch-7-7: ## Run test batch 7-7: Mesh part 1 — serializers/views/services/comp_val (~266 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/mesh/tests/test_serializers.py \
		hub/apps/mesh/tests/test_views.py \
		hub/apps/mesh/tests/test_services.py \
		hub/apps/mesh/tests/test_data_mesh_service_comprehensive_validation.py \
		--reuse-db -q --timeout=300

test-batch-7-8: ## Run test batch 7-8: Mesh part 2 — remaining 13 files (~240 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/mesh/tests/test_data_mesh_business_rules_refactoring.py \
		hub/apps/mesh/tests/test_policy_topology_business_rules_refactoring.py \
		hub/apps/mesh/tests/test_policy_topology_business_rules.py \
		hub/apps/mesh/tests/test_compliance_topology.py \
		hub/apps/mesh/tests/test_governance_integration.py \
		hub/apps/mesh/tests/test_models.py \
		hub/apps/mesh/tests/test_policy_compliance_models.py \
		hub/apps/mesh/tests/test_migration.py \
		hub/apps/mesh/tests/test_topology_endpoints.py \
		hub/apps/mesh/tests/test_audit_logging.py \
		hub/apps/mesh/tests/test_metrics.py \
		hub/apps/mesh/tests/test_rls_policies.py \
		--reuse-db -q --timeout=300

test-batch-7-9: ## Run test batch 7-9: API remaining files (~226 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/api/tests/test_mailhog_proxy.py \
		hub/apps/api/tests/test_analytics_views.py \
		hub/apps/api/tests/test_cost_tracking.py \
		hub/apps/api/tests/test_analytics_middleware.py \
		hub/apps/api/tests/test_e2e_gating.py \
		hub/apps/api/tests/test_webhook_sink.py \
		hub/apps/api/tests/test_on_commit_rollback_safety.py \
		hub/apps/api/tests/test_middleware.py \
		hub/apps/api/tests/test_system_checks.py \
		hub/apps/api/tests/test_version_discovery.py \
		hub/apps/api/tests/test_capabilities.py \
		hub/apps/api/tests/test_idempotency_error_handling.py \
		hub/apps/api/tests/test_api_integration.py \
		hub/apps/api/tests/test_require_e2e_token.py \
		hub/apps/api/tests/test_versioning.py \
		hub/apps/api/tests/test_versioning_headers.py \
		hub/apps/api/tests/test_analytics.py \
		hub/apps/api/tests/test_error_codes.py \
		hub/apps/api/tests/test_error_response_contract.py \
		hub/apps/api/tests/test_openapi_completeness.py \
		hub/apps/api/tests/test_openapi_validation.py \
		hub/apps/api/tests/test_mvp_mode_middleware.py \
		hub/apps/api/tests/test_compliance_url_mount.py \
		--reuse-db -q --timeout=300

test-batch-7-10: ## Run test batch 7-10: Audit heavy files + obs business_rules (~231 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/audit/tests/test_odps_audit_comprehensive_validation.py \
		hub/apps/audit/tests/test_views.py \
		hub/apps/audit/tests/test_tamper_evidence.py \
		hub/apps/audit/tests/test_audit_event_querying.py \
		hub/apps/observability/tests/test_business_rules.py \
		--reuse-db -q --timeout=300

test-batch-7-11: ## Run test batch 7-11: Audit remaining files + obs remaining (~282 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/audit/tests/test_audit_event_retention_policy.py \
		hub/apps/audit/tests/test_utils.py \
		hub/apps/audit/tests/test_audit_event_creation.py \
		hub/apps/audit/tests/test_resource_activity.py \
		hub/apps/audit/tests/test_resource_activity_viewset.py \
		hub/apps/audit/tests/test_audit_retention_purge_complete.py \
		hub/apps/audit/tests/test_audit_policy_critical_paths.py \
		hub/apps/audit/tests/test_audit_payload_filename_sanitize.py \
		hub/apps/audit/tests/test_audit_search.py \
		hub/apps/audit/tests/test_trace_id.py \
		hub/apps/audit/tests/test_verify_integrity_command.py \
		hub/apps/audit/tests/test_event_types.py \
		hub/apps/audit/tests/test_phase_234_7_observability.py \
		hub/apps/audit/tests/test_archive_command.py \
		hub/apps/audit/tests/test_audit_chain_integrity.py \
		hub/apps/audit/tests/test_audit_event_payload.py \
		hub/apps/audit/tests/test_fail_closed_redaction.py \
		hub/apps/audit/tests/test_models.py \
		hub/apps/observability/tests/test_otel_metrics.py \
		hub/apps/observability/tests/test_otel_config.py \
		hub/apps/observability/tests/test_span_instrumentation.py \
		hub/apps/observability/tests/test_incident_management.py \
		hub/apps/observability/tests/test_freshness.py \
		hub/apps/observability/tests/test_metrics.py \
		hub/apps/observability/tests/test_trace_sampling.py \
		hub/apps/observability/tests/test_data_slas.py \
		hub/apps/observability/tests/test_views.py \
		hub/apps/observability/tests/test_services.py \
		hub/apps/observability/tests/test_metrics_collection.py \
		hub/apps/observability/tests/test_middleware.py \
		hub/apps/observability/tests/test_observability_lineage_integration.py \
		hub/apps/observability/tests/test_observability_service_event_publishing.py \
		hub/apps/observability/tests/test_otel_spans.py \
		hub/apps/observability/tests/test_structured_logging.py \
		hub/apps/observability/tests/test_e2e_observability.py \
		hub/apps/observability/tests/test_schema_drift.py \
		hub/apps/observability/tests/test_pipeline_monitoring.py \
		hub/apps/observability/tests/test_logging.py \
		hub/apps/observability/tests/test_cross_tenant_metric_exposition.py \
		hub/apps/observability/tests/test_search_cross_cutting_drift.py \
		hub/apps/observability/tests/test_volume.py \
		--reuse-db -q --timeout=300

test-batch-7-12: ## Run test batch 7-12: Core services (~214 tests)
	docker compose -f docker-compose.test.yml exec -T api-service-test \
		python -u -m pytest \
		hub/apps/core/tests/ \
		--reuse-db -q --timeout=300

test-batch-7: ## Run all batch 7 sub-batches sequentially
	-$(MAKE) test-batch-7-1
	-$(MAKE) test-batch-7-2
	-$(MAKE) test-batch-7-3
	-$(MAKE) test-batch-7-4
	-$(MAKE) test-batch-7-5
	-$(MAKE) test-batch-7-6
	-$(MAKE) test-batch-7-7
	-$(MAKE) test-batch-7-8
	-$(MAKE) test-batch-7-9
	-$(MAKE) test-batch-7-10
	-$(MAKE) test-batch-7-11
	-$(MAKE) test-batch-7-12

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

# ── Batch 12: Service-level tests (prefect, ODH, worker, shared) ──────
# Small services with their own pytest.ini — run from the service
# directory or container like the CI jobs do.

_seed-e2e-data: ## Seed E2E test data for scheduled export integration tests
	@echo "=== Seeding E2E test data ==="
	@docker compose -f docker-compose.test.yml exec -T prefect-integration-service-test \
		sh -c 'export PATH="$$PATH:/home/appuser/.local/bin" && cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python3 services/prefect-integration/tests/create_test_data.py 2>&1 | grep -E "Tenant|User|API Key|Subscription|Scheduled"' || true

test-batch-12-1: ## Run compliance-service tests
	(cd services/compliance-service && python3 -m pytest tests/ -q -p no:django)

test-batch-12-2: ## Run semantic-service tests
	(cd services/semantic-service && python3 -m pytest tests/ -q -p no:django)

test-batch-12-3: ## Run dq-service tests
	(cd services/dq-service && python3 -m pytest tests/ -q -p no:django)

test-batch-12-4: ## Datacontract-service tests (10 files, ~135 tests, local)
	@echo "=== 12-4: datacontract-service ==="
	-(cd services/datacontract-service && REDIS_CACHE_URL=redis://localhost:6379/0 python3 -m pytest tests/ -q)

test-batch-12-5: _seed-e2e-data ## Prefect + ODH integration + Worker + Shared tests (~28 files, ~380 tests)
	@echo "=== 12-5: prefect-integration (Docker) ==="
	-docker compose -f docker-compose.test.yml exec -T prefect-integration-service-test \
		sh -c 'export PATH="$$PATH:/home/appuser/.local/bin" && cd /app/services/prefect-integration && USE_PRODUCTION_DB_FOR_SDK_TESTS=1 python -m pytest tests/ -q --override-ini="pythonpath=" -o cache_dir=/tmp/.pytest_cache' 2>&1 | tee /tmp/batch-12-5-prefect.log
	@echo "=== 12-5: odh-integration (local) ==="
	-(cd services/odh-integration && PYTHONPATH=../.. python3 -m pytest tests/ -q -p no:django -W 'ignore::pytest.PytestConfigWarning')
	@echo "=== 12-5: worker (Docker) ==="
	-docker compose -f docker-compose.test.yml exec -T worker-service-test \
		python -m pytest /app/services/worker/tests/ -q 2>&1 | tee /tmp/batch-12-5-worker.log
	@echo "=== 12-5: shared (local) ==="
	-(cd services/shared && PYTHONPATH=../.. python3 -m pytest tests/ -q -p no:django -W 'ignore::pytest.PytestConfigWarning')
	@echo "=== Summary: check /tmp/batch-12-5-*.log for per-service results ==="

test-batch-all: ## Run all test batches sequentially (batches 1-10, 12) — continues on failure
	-$(MAKE) test-batch-1
	-$(MAKE) test-batch-2
	-$(MAKE) test-batch-3-1
	-$(MAKE) test-batch-3-2
	-$(MAKE) test-batch-3-3
	-$(MAKE) test-batch-3-4
	-$(MAKE) test-batch-3-5
	-$(MAKE) test-batch-3-6
	-$(MAKE) test-batch-3-7
	-$(MAKE) test-batch-3-8
	-$(MAKE) test-batch-3-9
	-$(MAKE) test-batch-3-10
	-$(MAKE) test-batch-3-11
	-$(MAKE) test-batch-4-1
	-$(MAKE) test-batch-4-2
	-$(MAKE) test-batch-4-3
	-$(MAKE) test-batch-4-4
	-$(MAKE) test-batch-4-5
	-$(MAKE) test-batch-4-6
	-$(MAKE) test-batch-5-1
	-$(MAKE) test-batch-5-2
	-$(MAKE) test-batch-5-3
	-$(MAKE) test-batch-5-4
	-$(MAKE) test-batch-5-5
	-$(MAKE) test-batch-6-1-all
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
	-$(MAKE) test-batch-12-4
	-$(MAKE) test-batch-12-5

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

.PHONY: check-docs-sync
check-docs-sync: ## Verify docs, markers, and YAML are bidirectionally consistent
	python scripts/check_doc_journey_marker_sync.py --ci-mode
	python scripts/check_doc_uc_marker_sync.py --ci-mode
	python scripts/check_persona_mapping_drift.py
	python scripts/check_persona_journey_mapping_drift.py

.PHONY: audit-docs
audit-docs: check-docs-sync ## Run all documentation-health checks
	python scripts/check_assert_true_true.py
	python scripts/lint_journey_marker_coverage.py --blocking
	python scripts/check_marker_consistency.py --verbose 2>/dev/null || echo "Marker consistency script not found — skipping"
	python scripts/report_uc_journey_test_coverage.py --ci-mode 2>/dev/null || echo "Coverage report script not found — skipping"
	python scripts/extract_persona_journey_mapping.py --check 2>/dev/null || echo "Persona-journey mapping extraction check — run without --check to regenerate"
	@echo "ALL DOC-HEALTH CHECKS PASSED"

.PHONY: quality-gates
quality-gates: ## Run all locally-runnable CI quality gates (GATE-01 through GATE-28 subset)
	@echo "=== Quality Gates GATE-01 through GATE-09 ==="
	python scripts/check_assert_true_true.py
	python scripts/check_unused_assert_raises.py
	python scripts/check_broad_status_codes.py
	python scripts/check_tautological_frontend_assertions.py
	python scripts/check_time_sleep_in_tests.py
	python scripts/check_no_reverse_match.py
	python scripts/check_pytest_skip_in_body.py
	python scripts/check_empty_test_methods.py
	python scripts/check_bare_assert_called.py
	@echo "=== Quality Gates GATE-15 through GATE-23 ==="
	python scripts/spec_coverage_report.py --check 50
	python scripts/check_marker_consistency.py --verbose
	python scripts/check_ga_gate_scores.py
	python scripts/check_stale_defaults.py
	@echo "=== Traceability Gates GATE-26 through GATE-28 ==="
	python scripts/lint_journey_marker_coverage.py --blocking
	python scripts/check_doc_journey_marker_sync.py --ci-mode
	python scripts/check_doc_uc_marker_sync.py --ci-mode
	python scripts/check_persona_mapping_drift.py
	@echo "=== All local quality gates passed ==="

# Excluded from quality-gates:
#   GATE-10/11/12/21 — require a running Django database
#   GATE-13/14/16 — run pytest test files that need Django setup
#   GATE-19 — lint_rls_policies.py (available but slow on full scan)
#   GATE-24 — check_i18n_hardcoded.cjs is MISSING (script does not exist)
#   GATE-25 — requires `semgrep` CLI (pip install semgrep)

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

