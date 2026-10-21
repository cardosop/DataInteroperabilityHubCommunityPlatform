#!/bin/bash
# Run Phase 25 tests and capture results

set -e

echo "Starting Phase 25 test execution..."
echo "Timestamp: $(date)"

cd /home/ph/Desktop/DataInteroperabilityHub

# Run tests with timeout
timeout 1800 docker compose exec -T api-service python manage.py test \
  hub.apps.tenants.tests.test_plan_limit_enforcement_comprehensive \
  hub.apps.billing.tests.test_subscription_integration \
  hub.apps.gdpr.tests.test_erasure_integration \
  hub.apps.api.tests.test_versioning_headers \
  --verbosity=2 \
  --keepdb \
  2>&1 | tee /tmp/phase25_test_results_$(date +%Y%m%d_%H%M%S).log

echo "Test execution completed at $(date)"
