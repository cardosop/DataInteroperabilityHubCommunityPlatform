.PHONY: help setup install test lint format clean docker-up docker-down docker-logs migrate createsuperuser runserver

help: ## Show this help message
	@echo "Interoperable Data Hub MVP - Makefile Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

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

test-unit: ## Run unit tests only
	pytest -m "not integration"

test-cov: ## Run tests with coverage
	pytest --cov=. --cov-report=html

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

