#!/bin/bash
# Gradual rollback script for workflow business rules validation

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <rollout_percentage>"
    echo "Example: $0 50  (reduces to 50%)"
    echo "Example: $0 0   (disables completely)"
    exit 1
fi

ROLLOUT_PERCENTAGE=$1

if [ "$ROLLOUT_PERCENTAGE" -lt 0 ] || [ "$ROLLOUT_PERCENTAGE" -gt 100 ]; then
    echo "Error: Rollout percentage must be between 0 and 100"
    exit 1
fi

echo "Setting rollout percentage to: $ROLLOUT_PERCENTAGE%"

# Set environment variable
export WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=$ROLLOUT_PERCENTAGE

# Restart services
echo "Restarting services..."
docker-compose restart api-service worker-service

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Verify rollback
echo "Verifying rollback..."
echo "✅ Gradual rollback completed. Rollout percentage: $ROLLOUT_PERCENTAGE%"
echo "Monitor metrics to verify impact reduction"
