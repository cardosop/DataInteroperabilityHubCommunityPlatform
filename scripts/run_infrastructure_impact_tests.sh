#!/bin/bash
# Script to run infrastructure impact report tests
# Can run locally or in Docker Compose environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Running infrastructure impact report tests..."

# Check if running in Docker Compose or locally
if [ -n "${DOCKER_COMPOSE_ENV:-}" ] || [ -f "/.dockerenv" ]; then
    echo "Running in Docker environment..."
    cd "$PROJECT_ROOT"
    python3 -m unittest tests.test_generate_infrastructure_impact_report -v
else
    echo "Running locally..."
    cd "$PROJECT_ROOT"

    # Check if virtual environment exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    python3 -m unittest tests.test_generate_infrastructure_impact_report -v
fi

echo "Tests completed successfully!"

