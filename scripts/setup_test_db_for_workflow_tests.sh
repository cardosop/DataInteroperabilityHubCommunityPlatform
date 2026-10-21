#!/bin/bash
# Script to set up test database for workflow tests
# This pre-creates the test database with migrations to avoid timeouts during test runs

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Check if docker compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    echo "Error: docker-compose or docker compose not found"
    exit 1
fi

echo "Setting up test database for workflow tests..."

# Create test database and run migrations
# This uses Django's test database creation which pytest-django will reuse
docker compose exec -T api-service bash -c "cd /app && python hub/manage.py test --keepdb hub.apps.orchestration.tests.test_workflow_business_rules_integration.TestProductCreationWorkflowBusinessRulesIntegration.test_successful_workflow_execution --verbosity=0 2>&1 | head -5 || true"

echo "Test database setup complete. You can now run tests with --reuse-db"
