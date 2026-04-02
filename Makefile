.PHONY: help setup install test test-ci test-ci-backend test-ci-frontend test-ci-lint lint format clean docker-up docker-down docker-logs migrate createsuperuser runserver dev-env

help: ## Show this help message
	@echo "Interoperable Data Hub MVP - Makefile Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

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
		python -m pytest hub/apps/ hub/tests/test_mvp_mode.py --reuse-db -x -q --timeout=300; \
	rc=$$?; \
	docker compose -f docker-compose.test.yml down -v --remove-orphans; \
	exit $$rc

test-ci-frontend: ## Run frontend unit tests (same as CI test-frontend-unit job)
	cd frontend && npm ci && npx vitest --run

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

