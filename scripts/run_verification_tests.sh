#!/bin/bash
# Script to run existing functionality verification tests
# Ensures proper environment setup and database connectivity

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Running Existing Functionality Verification Tests ===${NC}"

# Check if docker compose services are running
echo -e "${YELLOW}Checking Docker Compose services...${NC}"
if ! docker compose ps postgres | grep -q "Up"; then
    echo -e "${RED}PostgreSQL container is not running. Starting it...${NC}"
    docker compose up -d postgres
    echo "Waiting for PostgreSQL to be ready..."
    sleep 5
fi

if ! docker compose ps redis-cache | grep -q "Up"; then
    echo -e "${YELLOW}Redis container is not running. Starting it...${NC}"
    docker compose up -d redis-cache
    echo "Waiting for Redis to be ready..."
    sleep 3
fi

# Verify PostgreSQL connection
echo -e "${YELLOW}Verifying PostgreSQL connection...${NC}"
if docker compose exec -T postgres psql -U hub -d hub -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL connection verified${NC}"
else
    echo -e "${RED}✗ PostgreSQL connection failed. Please check docker compose services.${NC}"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=hub
export POSTGRES_USER=hub
export POSTGRES_PASSWORD=hub
export REDIS_HOST=localhost
export REDIS_PORT=6379
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Run tests with pytest
echo -e "${GREEN}Running verification tests...${NC}"
python -m pytest tests/regression/test_existing_functionality_verification.py \
    -v \
    --tb=short \
    --durations=10 \
    "$@"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed. Exit code: $EXIT_CODE${NC}"
fi

exit $EXIT_CODE

