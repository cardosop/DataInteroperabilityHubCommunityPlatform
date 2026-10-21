#!/bin/bash
# Script to run BaaS Platform Comprehensive Validation tests
# This script runs tests in smaller batches to identify issues faster

set -e

echo "Running BaaS Platform Comprehensive Validation Tests..."
echo "=================================================="

cd "$(dirname "$0")/.."

# Run tests in smaller batches
echo ""
echo "1. Testing Usage Tracking (10.1.37.2)..."
docker compose exec -T api-service python /app/hub/manage.py test \
    hub.apps.baas.tests.test_baas_platform_comprehensive_validation.UsageTrackingTestingTest \
    --verbosity=1 --keepdb 2>&1 | tail -50

echo ""
echo "2. Testing Developer Portal (10.1.37.3)..."
docker compose exec -T api-service python /app/hub/manage.py test \
    hub.apps.baas.tests.test_baas_platform_comprehensive_validation.DeveloperPortalTestingTest \
    --verbosity=1 --keepdb 2>&1 | tail -50

echo ""
echo "3. Testing BaaS Platform API (10.1.37.4)..."
docker compose exec -T api-service python /app/hub/manage.py test \
    hub.apps.baas.tests.test_baas_platform_comprehensive_validation.BaaSPlatformAPITestingTest \
    --verbosity=1 --keepdb 2>&1 | tail -50

echo ""
echo "4. Testing Performance (10.1.37.5)..."
docker compose exec -T api-service python /app/hub/manage.py test \
    hub.apps.baas.tests.test_baas_platform_comprehensive_validation.BaaSPlatformPerformanceTestingTest \
    --verbosity=1 --keepdb 2>&1 | tail -50

echo ""
echo "5. Testing Security (10.1.37.6)..."
docker compose exec -T api-service python /app/hub/manage.py test \
    hub.apps.baas.tests.test_baas_platform_comprehensive_validation.BaaSPlatformSecurityTestingTest \
    --verbosity=1 --keepdb 2>&1 | tail -50

echo ""
echo "Tests completed!"
