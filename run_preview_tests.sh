#!/bin/bash
# Script to run preview transformation tests

set -e

echo "Running preview transformation tests..."

docker compose exec -T api-service bash -c "
    cd /app/hub &&
    python manage.py test apps.transformation.tests.test_services.PreviewTransformationTest \
        --verbosity=2 \
        --keepdb \
        2>&1 | tee /tmp/preview_test_results.log
"

echo "Test results saved to /tmp/preview_test_results.log"
echo "Checking for failures..."

docker compose exec -T api-service bash -c "
    grep -E '(FAILED|ERROR|OK|test_preview)' /tmp/preview_test_results.log | tail -50
"

