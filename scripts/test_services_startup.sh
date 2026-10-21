#!/bin/bash
# Test Services Startup with Python 3.12+
# This script starts services and verifies they start correctly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Service Startup Test - Python 3.12+${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
    exit 1
fi

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo -e "${RED}❌ Docker Compose is not available${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker found: $(docker --version)${NC}"
echo -e "${GREEN}✅ Docker Compose found${NC}"
echo ""

# Start infrastructure services first
echo -e "${BLUE}Starting infrastructure services...${NC}"
$DOCKER_COMPOSE_CMD up -d postgres redis minio fuseki

echo -e "${BLUE}Waiting for infrastructure services to be ready...${NC}"
sleep 10

# Check infrastructure services
echo -e "${BLUE}Checking infrastructure services...${NC}"

# Check PostgreSQL
if docker exec hub-postgres pg_isready -U hub > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
else
    echo -e "${RED}❌ PostgreSQL is not ready${NC}"
fi

# Check Redis
if docker exec hub-redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis is ready${NC}"
else
    echo -e "${RED}❌ Redis is not ready${NC}"
fi

# Check MinIO
if curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MinIO is ready${NC}"
else
    echo -e "${YELLOW}⚠️  MinIO health check failed (may still be starting)${NC}"
fi

# Check Fuseki
if curl -f http://localhost:3030/\$/ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Fuseki is ready${NC}"
else
    echo -e "${YELLOW}⚠️  Fuseki health check failed (may still be starting)${NC}"
fi

echo ""

# Build and start application services
echo -e "${BLUE}Building application services with Python 3.12+...${NC}"
$DOCKER_COMPOSE_CMD build api-service worker-service datacontract-service compliance-service dq-service semantic-service

echo -e "${BLUE}Starting application services...${NC}"
$DOCKER_COMPOSE_CMD up -d api-service worker-service datacontract-service compliance-service dq-service semantic-service

echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 15

# Test service health endpoints
echo -e "${BLUE}Testing service health endpoints...${NC}"
echo ""

SERVICES=(
    "api-service:8000:/health/"
    "worker-service:8084:/healthz"
    "datacontract-service:8080:/health"
    "compliance-service:8082:/health"
    "dq-service:8083:/health"
    "semantic-service:8081:/health"
)

SUCCESS_COUNT=0
FAIL_COUNT=0

for service_info in "${SERVICES[@]}"; do
    IFS=':' read -r service_name port endpoint <<< "$service_info"
    
    echo -e "${BLUE}Testing ${service_name}...${NC}"
    echo -e "  Endpoint: http://localhost:${port}${endpoint}"
    
    # Wait a bit for service to be ready
    sleep 2
    
    if curl -f -s "http://localhost:${port}${endpoint}" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ ${service_name} is healthy${NC}"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        
        # Get Python version from container if possible
        CONTAINER_NAME="hub-${service_name}"
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            PYTHON_VERSION=$(docker exec "${CONTAINER_NAME}" python --version 2>&1 || echo "unknown")
            echo -e "${BLUE}  Python version: ${PYTHON_VERSION}${NC}"
        fi
    else
        echo -e "${RED}  ❌ ${service_name} health check failed${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        
        # Show logs for failed service
        echo -e "${YELLOW}  Showing last 10 lines of logs:${NC}"
        docker logs --tail 10 "${CONTAINER_NAME}" 2>&1 | sed 's/^/    /'
    fi
    echo ""
done

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Service Startup Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}✅ Healthy services: ${SUCCESS_COUNT}${NC}"
echo -e "${RED}❌ Failed services: ${FAIL_COUNT}${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ All services started successfully!${NC}"
    echo ""
    echo -e "${BLUE}Service URLs:${NC}"
    echo "  - API Service: http://localhost:8000"
    echo "  - Worker Service: http://localhost:8084"
    echo "  - Datacontract Service: http://localhost:8080"
    echo "  - Compliance Service: http://localhost:8082"
    echo "  - DQ Service: http://localhost:8083"
    echo "  - Semantic Service: http://localhost:8081"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some services failed to start${NC}"
    echo -e "${YELLOW}Check logs with: docker-compose logs <service-name>${NC}"
    exit 1
fi

