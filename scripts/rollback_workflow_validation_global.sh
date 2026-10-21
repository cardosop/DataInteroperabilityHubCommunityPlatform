#!/bin/bash
# Quick global rollback script for workflow business rules validation

set -e

echo "Starting global rollback of workflow business rules validation..."

# Set environment variable
export ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=false

# Restart services
echo "Restarting services..."
docker-compose restart api-service worker-service

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Verify rollback
echo "Verifying rollback..."
if docker-compose logs api-service | grep -q "Business rules validation disabled"; then
    echo "✅ Rollback successful: Validation disabled"
else
    echo "❌ Rollback verification failed"
    exit 1
fi

echo "✅ Global rollback completed successfully"
