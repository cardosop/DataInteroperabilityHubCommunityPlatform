#!/bin/bash
# Test Docker Builds with Python 3.12+
# This script builds all Docker images to verify Python 3.12+ compatibility

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Docker Build Test - Python 3.12+${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker found: $(docker --version)${NC}"
echo ""

# List of Dockerfiles to test
DOCKERFILES=(
    "services/api/Dockerfile:api-service"
    "services/worker/Dockerfile:worker-service"
    "services/datacontract-service/Dockerfile:datacontract-service"
    "services/compliance-service/Dockerfile:compliance-service"
    "services/dq-service/Dockerfile:dq-service"
    "services/semantic-service/Dockerfile:semantic-service"
)

SUCCESS_COUNT=0
FAIL_COUNT=0
FAILED_BUILDS=()

# Test each Dockerfile
for dockerfile_info in "${DOCKERFILES[@]}"; do
    IFS=':' read -r dockerfile service_name <<< "$dockerfile_info"
    
    echo -e "${BLUE}Building ${service_name}...${NC}"
    echo -e "  Dockerfile: ${dockerfile}"
    
    if [ ! -f "$dockerfile" ]; then
        echo -e "${RED}❌ Dockerfile not found: ${dockerfile}${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILED_BUILDS+=("${service_name} (file not found)")
        continue
    fi
    
    # Check if Dockerfile uses Python 3.12+
    if grep -q "FROM python:3.1[2-9]" "$dockerfile"; then
        echo -e "${GREEN}  ✅ Uses Python 3.12+${NC}"
    else
        echo -e "${RED}  ❌ Does not use Python 3.12+${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILED_BUILDS+=("${service_name} (wrong Python version)")
        continue
    fi
    
    # Try to build the image
    IMAGE_TAG="test-${service_name}-python312:latest"
    
    if docker build -t "$IMAGE_TAG" -f "$dockerfile" . > /tmp/docker-build-${service_name}.log 2>&1; then
        echo -e "${GREEN}✅ ${service_name} built successfully${NC}"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        
        # Verify Python version in the image
        echo -e "${BLUE}  Verifying Python version in image...${NC}"
        PYTHON_VERSION=$(docker run --rm "$IMAGE_TAG" python --version 2>&1 || echo "unknown")
        echo -e "${BLUE}  Python version: ${PYTHON_VERSION}${NC}"
        
        # Clean up test image
        docker rmi "$IMAGE_TAG" > /dev/null 2>&1 || true
    else
        echo -e "${RED}❌ ${service_name} build failed${NC}"
        echo -e "${YELLOW}  Build log saved to: /tmp/docker-build-${service_name}.log${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILED_BUILDS+=("${service_name}")
    fi
    
    echo ""
done

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Build Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}✅ Successful builds: ${SUCCESS_COUNT}${NC}"
echo -e "${RED}❌ Failed builds: ${FAIL_COUNT}${NC}"
echo ""

if [ ${#FAILED_BUILDS[@]} -gt 0 ]; then
    echo -e "${RED}Failed builds:${NC}"
    for build in "${FAILED_BUILDS[@]}"; do
        echo -e "${RED}  - ${build}${NC}"
    done
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ All Docker builds passed!${NC}"
exit 0

