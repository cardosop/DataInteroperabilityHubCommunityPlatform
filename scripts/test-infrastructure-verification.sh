#!/bin/bash
# Comprehensive Infrastructure Verification Test Script
# Tests all infrastructure updates from tasks 9.6.3.4.1-9.6.3.4.4

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Infrastructure Update Verification Tests"
echo "=========================================="
echo ""
echo "This script verifies all infrastructure updates:"
echo "  - 9.6.3.4.1: CI/CD pipelines"
echo "  - 9.6.3.4.2: Monitoring configurations"
echo "  - 9.6.3.4.3: Rate limiting configurations"
echo "  - 9.6.3.4.4: API gateway configurations"
echo ""

# Check Docker Compose services
echo -e "${BLUE}Checking Docker Compose services...${NC}"
if ! docker compose ps api-service | grep -q "Up"; then
    echo -e "${RED}❌ API service is not running. Please start Docker Compose services.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose services are running${NC}"
echo ""

# Run comprehensive verification
echo -e "${BLUE}Running comprehensive infrastructure verification...${NC}"
echo ""

if python3 scripts/verify-infrastructure-updates.py; then
    echo ""
    echo "=========================================="
    echo -e "${GREEN}✅ All infrastructure verification tests passed!${NC}"
    echo "=========================================="
    echo ""
    echo "Reports generated:"
    echo "  - docs/infrastructure-update-verification-report.md"
    echo "  - docs/infrastructure-update-verification-report.json"
    exit 0
else
    echo ""
    echo "=========================================="
    echo -e "${RED}❌ Infrastructure verification tests failed!${NC}"
    echo "=========================================="
    echo ""
    echo "Please check the reports for details:"
    echo "  - docs/infrastructure-update-verification-report.md"
    echo "  - docs/infrastructure-update-verification-report.json"
    exit 1
fi

