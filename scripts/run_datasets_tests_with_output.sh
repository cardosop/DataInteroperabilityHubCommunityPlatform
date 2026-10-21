#!/bin/bash
# Run datasets comprehensive tests and capture output

set -e

OUTPUT_FILE="/tmp/datasets_test_output_$(date +%s).txt"

echo "Running datasets comprehensive validation tests..."
echo "Output will be saved to: $OUTPUT_FILE"
echo ""

docker compose exec -T api-service bash -c \
  "cd /app && python hub/manage.py test \
   hub.apps.datasets.tests.test_datasets_service_comprehensive_validation \
   --verbosity=2 --keepdb --no-input 2>&1" | tee "$OUTPUT_FILE"

echo ""
echo "Test output saved to: $OUTPUT_FILE"
echo "Checking for failures..."

if grep -q "FAILED\|ERROR" "$OUTPUT_FILE"; then
    echo "❌ Tests failed! See output above or check $OUTPUT_FILE"
    exit 1
elif grep -q "OK" "$OUTPUT_FILE"; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "⚠️  Could not determine test status. Check $OUTPUT_FILE"
    exit 2
fi
