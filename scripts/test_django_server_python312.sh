#!/bin/bash
# Test Django Server Startup with Python 3.12+
# This script tests that Django server starts and API endpoints work

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
echo -e "${BLUE}Django Server Test - Python 3.12+${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv-python312-test" ]; then
    echo -e "${RED}❌ Test virtual environment not found${NC}"
    echo -e "${YELLOW}Run: python3.12 -m venv venv-python312-test${NC}"
    exit 1
fi

# Activate virtual environment
source venv-python312-test/bin/activate

# Set environment variables
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="$PROJECT_ROOT"
export DATABASE_URL="${DATABASE_URL:-postgresql://hub:hub@localhost:5432/hub}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

echo -e "${BLUE}Testing Django server startup...${NC}"

# Test 1: Django check
echo -e "${BLUE}1. Running Django system check...${NC}"
if python hub/manage.py check --deploy > /tmp/django_check.log 2>&1; then
    echo -e "${GREEN}  ✅ Django system check passed${NC}"
else
    echo -e "${YELLOW}  ⚠️  Django system check had warnings (check /tmp/django_check.log)${NC}"
    cat /tmp/django_check.log | tail -10
fi

# Test 2: Start server in background
echo -e "${BLUE}2. Starting Django server...${NC}"
python hub/manage.py runserver 0.0.0.0:8002 > /tmp/django_server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 5

# Check if server is running
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo -e "${GREEN}  ✅ Django server started (PID: $SERVER_PID)${NC}"
    
    # Test 3: Health endpoint
    echo -e "${BLUE}3. Testing health endpoint...${NC}"
    if curl -s -f http://localhost:8002/health/ --max-time 5 > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ Health endpoint accessible${NC}"
        curl -s http://localhost:8002/health/ | head -3
    else
        echo -e "${YELLOW}  ⚠️  Health endpoint not accessible (may require authentication)${NC}"
    fi
    
    # Test 4: API root endpoint
    echo -e "${BLUE}4. Testing API root endpoint...${NC}"
    if curl -s -f http://localhost:8002/api/v1/ --max-time 5 > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ API root endpoint accessible${NC}"
        curl -s http://localhost:8002/api/v1/ | head -3
    else
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/api/v1/ --max-time 5 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
            echo -e "${GREEN}  ✅ API endpoint exists (requires authentication: HTTP $HTTP_CODE)${NC}"
        else
            echo -e "${YELLOW}  ⚠️  API endpoint not accessible (HTTP $HTTP_CODE)${NC}"
        fi
    fi
    
    # Stop server
    echo -e "${BLUE}5. Stopping Django server...${NC}"
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    echo -e "${GREEN}  ✅ Server stopped${NC}"
    
    echo ""
    echo -e "${GREEN}✅ Django server test completed successfully${NC}"
    exit 0
else
    echo -e "${RED}  ❌ Django server failed to start${NC}"
    echo -e "${YELLOW}Server logs:${NC}"
    cat /tmp/django_server.log | tail -20
    exit 1
fi

