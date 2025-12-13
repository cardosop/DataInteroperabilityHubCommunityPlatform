#!/bin/bash
#
# Metrics Deployment Verification Script
#
# This script verifies that OpenTelemetry metrics are properly deployed and
# accessible after deployment to staging or production.
#
# Usage:
#   ./scripts/verify_metrics_deployment.sh [staging|production] [api-url]
#
# Example:
#   ./scripts/verify_metrics_deployment.sh staging http://staging.example.com
#   ./scripts/verify_metrics_deployment.sh production http://api.example.com
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-staging}"
API_URL="${2:-http://localhost:8000}"
TIMEOUT=30

echo "=========================================="
echo "Metrics Deployment Verification"
echo "Environment: $ENVIRONMENT"
echo "API URL: $API_URL"
echo "=========================================="
echo ""

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# Function to check HTTP endpoint
check_endpoint() {
    local url=$1
    local expected_status=${2:-200}
    local description=$3
    
    response=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$url" || echo -e "\n000")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ] || [ "$http_code" = "503" ]; then
        print_status 0 "$description (HTTP $http_code)"
        echo "$body"
        return 0
    else
        print_status 1 "$description (HTTP $http_code, expected $expected_status)"
        return 1
    fi
}

# Track overall success
OVERALL_SUCCESS=0

echo "1. Checking API health endpoint..."
if ! check_endpoint "$API_URL/health/" 200 "Health endpoint"; then
    OVERALL_SUCCESS=1
fi
echo ""

echo "2. Checking metrics endpoint accessibility..."
METRICS_RESPONSE=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$API_URL/metrics/" || echo -e "\n000")
METRICS_HTTP_CODE=$(echo "$METRICS_RESPONSE" | tail -n1)
METRICS_BODY=$(echo "$METRICS_RESPONSE" | sed '$d')

if [ "$METRICS_HTTP_CODE" = "200" ]; then
    print_status 0 "Metrics endpoint accessible (HTTP 200)"
elif [ "$METRICS_HTTP_CODE" = "503" ]; then
    print_status 1 "Metrics endpoint returned 503 (service unavailable)"
    OVERALL_SUCCESS=1
else
    print_status 1 "Metrics endpoint failed (HTTP $METRICS_HTTP_CODE)"
    OVERALL_SUCCESS=1
fi
echo ""

if [ "$METRICS_HTTP_CODE" = "200" ]; then
    echo "3. Verifying Prometheus format..."
    
    # Check for Prometheus format indicators
    if echo "$METRICS_BODY" | grep -q "# HELP"; then
        print_status 0 "HELP comments present"
    else
        print_status 1 "HELP comments missing"
        OVERALL_SUCCESS=1
    fi
    
    if echo "$METRICS_BODY" | grep -q "# TYPE"; then
        print_status 0 "TYPE comments present"
    else
        print_status 1 "TYPE comments missing"
        OVERALL_SUCCESS=1
    fi
    
    echo ""
    
    echo "4. Verifying metric names..."
    
    REQUIRED_METRICS=(
        "http_requests_total"
        "http_request_duration_seconds"
        "jobs_started_total"
        "jobs_completed_total"
        "tenant_running_jobs"
    )
    
    MISSING_METRICS=0
    for metric in "${REQUIRED_METRICS[@]}"; do
        if echo "$METRICS_BODY" | grep -q "$metric"; then
            print_status 0 "Metric '$metric' present"
        else
            print_status 1 "Metric '$metric' missing"
            MISSING_METRICS=$((MISSING_METRICS + 1))
        fi
    done
    
    if [ $MISSING_METRICS -gt 0 ]; then
        OVERALL_SUCCESS=1
    fi
    echo ""
    
    echo "5. Verifying metric format validity..."
    
    # Check for valid Prometheus metric lines
    METRIC_LINES=$(echo "$METRICS_BODY" | grep -v "^#" | grep -v "^$" | head -20)
    INVALID_LINES=0
    
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            # Check if line has metric name and value
            if echo "$line" | grep -qE '^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]+\})?\s+[\d.]+'; then
                : # Valid line
            else
                INVALID_LINES=$((INVALID_LINES + 1))
            fi
        fi
    done <<< "$METRIC_LINES"
    
    if [ $INVALID_LINES -eq 0 ]; then
        print_status 0 "Metric format valid (checked first 20 lines)"
    else
        print_status 1 "Found $INVALID_LINES invalid metric lines"
        OVERALL_SUCCESS=1
    fi
    echo ""
    
    echo "6. Checking Content-Type header..."
    CONTENT_TYPE=$(curl -s -I --max-time $TIMEOUT "$API_URL/metrics/" | grep -i "content-type" || echo "")
    if echo "$CONTENT_TYPE" | grep -qi "text/plain"; then
        print_status 0 "Content-Type is text/plain"
    else
        print_status 1 "Content-Type incorrect: $CONTENT_TYPE"
        OVERALL_SUCCESS=1
    fi
    echo ""
fi

echo "7. Testing Prometheus scraping simulation..."
if [ "$METRICS_HTTP_CODE" = "200" ]; then
    # Simulate Prometheus scraping by checking if we can parse the response
    if command -v promtool >/dev/null 2>&1; then
        # Use promtool if available
        echo "$METRICS_BODY" | promtool check metrics 2>&1 | head -5
        if [ ${PIPESTATUS[1]} -eq 0 ]; then
            print_status 0 "Prometheus format validation passed"
        else
            print_status 1 "Prometheus format validation failed"
            OVERALL_SUCCESS=1
        fi
    else
        # Basic validation without promtool
        if echo "$METRICS_BODY" | grep -qE '^[a-zA-Z_:][a-zA-Z0-9_:]*'; then
            print_status 0 "Basic Prometheus format check passed (promtool not available)"
        else
            print_status 1 "Basic Prometheus format check failed"
            OVERALL_SUCCESS=1
        fi
    fi
else
    print_status 1 "Cannot test Prometheus scraping (metrics endpoint not available)"
    OVERALL_SUCCESS=1
fi
echo ""

echo "=========================================="
if [ $OVERALL_SUCCESS -eq 0 ]; then
    echo -e "${GREEN}✓ All metrics verification checks passed${NC}"
    exit 0
else
    echo -e "${RED}✗ Some metrics verification checks failed${NC}"
    exit 1
fi

