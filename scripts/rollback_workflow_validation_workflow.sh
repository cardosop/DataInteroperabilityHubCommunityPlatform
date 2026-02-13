#!/bin/bash
# Per-workflow rollback script for workflow business rules validation

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <workflow_name> [workflow_name2] ..."
    exit 1
fi

WORKFLOWS="$@"
echo "Rolling back validation for workflows: $WORKFLOWS"

# Build JSON array for disabled workflows
DISABLED_WORKFLOWS="["
for workflow in $WORKFLOWS; do
    DISABLED_WORKFLOWS="${DISABLED_WORKFLOWS}\"${workflow}\","
done
DISABLED_WORKFLOWS="${DISABLED_WORKFLOWS%,}]"

# Set environment variable
export WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS="$DISABLED_WORKFLOWS"

# Restart services
echo "Restarting services..."
docker-compose restart api-service worker-service

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Verify rollback
echo "Verifying rollback..."
for workflow in $WORKFLOWS; do
    if docker-compose logs api-service | grep -q "${workflow}.*validation disabled"; then
        echo "✅ Rollback successful for workflow: $workflow"
    else
        echo "❌ Rollback verification failed for workflow: $workflow"
        exit 1
    fi
done

echo "✅ Per-workflow rollback completed successfully"
