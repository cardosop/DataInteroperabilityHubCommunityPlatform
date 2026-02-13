#!/bin/bash
# Verification script for workflow business rules validation rollback

set -e

echo "Verifying workflow business rules validation rollback..."

# Check environment variables
echo "Checking environment variables..."
if [ -n "$ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION" ]; then
    echo "  ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION: $ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION"
else
    echo "  ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION: not set (default: true)"
fi

if [ -n "$WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE" ]; then
    echo "  ROLLOUT_PERCENTAGE: $WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE%"
else
    echo "  ROLLOUT_PERCENTAGE: not set (default: 100%)"
fi

# Check service logs
echo ""
echo "Checking service logs..."
VALIDATION_DISABLED_COUNT=$(docker-compose logs api-service | grep -c "Business rules validation disabled" || true)
echo "  Validation disabled messages: $VALIDATION_DISABLED_COUNT"

# Check Prometheus metrics (if available)
echo ""
echo "Checking Prometheus metrics..."
if command -v curl > /dev/null; then
    VALIDATION_COUNT=$(curl -s "http://localhost:9090/api/v1/query?query=workflow_business_rules_validations_total" | grep -o '"value":\[[0-9]*,"[0-9.]*"\]' | wc -l || echo "0")
    echo "  Validation metrics count: $VALIDATION_COUNT"
else
    echo "  Prometheus check skipped (curl not available)"
fi

# Summary
echo ""
echo "✅ Rollback verification completed"
