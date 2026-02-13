# Workflow Business Rules Validation Rollback Guide

**Version:** 1.0.0  
**Last Updated:** 2026-01-27  
**Status:** ✅ Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Rollback Scenarios](#rollback-scenarios)
3. [Rollback Procedures](#rollback-procedures)
4. [Rollback Scripts](#rollback-scripts)
5. [Verification](#verification)
6. [Best Practices](#best-practices)

---

## Overview

This guide provides comprehensive procedures for rolling back workflow business rules validation in case of issues. The rollback can be performed at multiple levels:

- **Global**: Disable validation for all workflows
- **Per-Workflow**: Disable validation for specific workflows
- **Per-Tenant**: Disable validation for specific tenants
- **Gradual**: Reduce rollout percentage

### Rollback Methods

1. **Feature Flag Rollback**: Disable via environment variables (fastest)
2. **Database Rollback**: Revert workflow instances to previous state (if needed)
3. **Code Rollback**: Revert code changes (last resort)

---

## Rollback Scenarios

### Scenario 1: High Validation Failure Rate

**Symptom**: High percentage of workflows failing due to validation errors

**Impact**: Workflows cannot complete, blocking business operations

**Rollback**: Disable validation globally or for affected workflows

### Scenario 2: Performance Degradation

**Symptom**: Workflow execution time increased significantly

**Impact**: System performance degraded, user experience impacted

**Rollback**: Disable validation or reduce rollout percentage

### Scenario 3: Validation Logic Error

**Symptom**: Valid workflows being rejected by validation

**Impact**: False positives blocking legitimate operations

**Rollback**: Disable validation for affected workflows, fix validation logic

### Scenario 4: Cache Issues

**Symptom**: Validation cache causing incorrect results

**Impact**: Inconsistent validation behavior

**Rollback**: Disable validation temporarily, clear cache, re-enable

---

## Rollback Procedures

### Procedure 1: Global Rollback (Disable All Validation)

**Use Case**: Critical issue affecting all workflows

**Steps**:

1. **Set Environment Variable**:
   ```bash
   export ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=false
   ```

2. **Restart Services**:
   ```bash
   # Docker Compose
   docker-compose restart api-service worker-service
   
   # Kubernetes
   kubectl rollout restart deployment/api-service -n production
   kubectl rollout restart deployment/worker-service -n production
   ```

3. **Verify Rollback**:
   ```bash
   # Check logs for validation disabled messages
   docker-compose logs api-service | grep "Business rules validation disabled"
   ```

4. **Monitor Metrics**:
   - Check Prometheus: `workflow_business_rules_validations_total` should drop to 0
   - Check Grafana dashboard: Validation metrics should show no activity

**Time to Rollback**: < 5 minutes

### Procedure 2: Per-Workflow Rollback

**Use Case**: Issue affecting specific workflows

**Steps**:

1. **Add Workflow to Disabled List**:
   ```bash
   export WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS='["product_creation","contract_creation"]'
   ```

2. **Or Use Per-Workflow Config**:
   ```bash
   export WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS='{"product_creation":false,"contract_creation":false}'
   ```

3. **Restart Services**:
   ```bash
   docker-compose restart api-service worker-service
   ```

4. **Verify Rollback**:
   ```bash
   # Check logs for specific workflow
   docker-compose logs api-service | grep "product_creation" | grep "validation disabled"
   ```

**Time to Rollback**: < 5 minutes

### Procedure 3: Gradual Rollback (Reduce Rollout Percentage)

**Use Case**: Reduce impact while investigating issue

**Steps**:

1. **Reduce Rollout Percentage**:
   ```bash
   # Reduce from 100% to 50%
   export WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=50
   
   # Or reduce to 0% (disable)
   export WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0
   ```

2. **Restart Services**:
   ```bash
   docker-compose restart api-service worker-service
   ```

3. **Monitor Impact**:
   - Check validation metrics: Should show ~50% reduction
   - Monitor workflow success rates: Should improve

**Time to Rollback**: < 5 minutes

### Procedure 4: Per-Tenant Rollback

**Use Case**: Issue affecting specific tenants

**Steps**:

1. **Disable for Specific Tenant**:
   ```bash
   export WORKFLOW_BUSINESS_RULES_VALIDATION_TENANTS='{"tenant-123":false,"tenant-456":false}'
   ```

2. **Restart Services**:
   ```bash
   docker-compose restart api-service worker-service
   ```

3. **Verify Rollback**:
   ```bash
   # Check logs for tenant
   docker-compose logs api-service | grep "tenant-123" | grep "validation disabled"
   ```

**Time to Rollback**: < 5 minutes

### Procedure 5: Complete Code Rollback

**Use Case**: Critical bug requiring code revert

**Steps**:

1. **Identify Commit to Revert**:
   ```bash
   git log --oneline | grep "workflow.*business.*rules"
   ```

2. **Revert Commit**:
   ```bash
   git revert <commit-hash>
   ```

3. **Build and Deploy**:
   ```bash
   # Build
   docker-compose build api-service worker-service
   
   # Deploy
   docker-compose up -d api-service worker-service
   ```

4. **Verify Rollback**:
   - Check service health
   - Verify validation code removed from logs
   - Monitor workflow execution

**Time to Rollback**: 15-30 minutes (depending on build/deploy time)

---

## Rollback Scripts

### Script 1: Quick Global Rollback

**File**: `scripts/rollback_workflow_validation_global.sh`

```bash
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
```

### Script 2: Per-Workflow Rollback

**File**: `scripts/rollback_workflow_validation_workflow.sh`

```bash
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
```

### Script 3: Gradual Rollback

**File**: `scripts/rollback_workflow_validation_gradual.sh`

```bash
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
```

### Script 4: Rollback Verification

**File**: `scripts/verify_workflow_validation_rollback.sh`

```bash
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
```

---

## Verification

### Verification Checklist

After performing rollback, verify:

- [ ] Services restarted successfully
- [ ] Logs show validation disabled messages
- [ ] Prometheus metrics show reduced/zero validation activity
- [ ] Grafana dashboards reflect rollback
- [ ] Workflow execution resumes normally
- [ ] No new validation errors in logs
- [ ] System performance improved (if performance was the issue)

### Verification Commands

```bash
# Check service status
docker-compose ps

# Check logs for validation disabled
docker-compose logs api-service | grep "validation disabled"

# Check Prometheus metrics
curl "http://localhost:9090/api/v1/query?query=workflow_business_rules_validations_total"

# Check workflow execution
docker-compose logs api-service | grep "workflow.*completed"

# Run verification script
./scripts/verify_workflow_validation_rollback.sh
```

---

## Best Practices

### 1. Test Rollback Procedures

**Do**:
- Test rollback procedures in staging environment
- Document any issues encountered
- Update procedures based on test results

**Don't**:
- Test rollback in production without staging test
- Skip verification steps

### 2. Monitor After Rollback

**Do**:
- Monitor metrics for 30 minutes after rollback
- Check workflow success rates
- Verify no new issues introduced

**Don't**:
- Assume rollback is complete without verification
- Ignore monitoring alerts

### 3. Document Rollback Events

**Do**:
- Document rollback reason
- Record rollback time and duration
- Track impact metrics (before/after)

**Don't**:
- Perform rollback without documentation
- Skip post-rollback analysis

### 4. Gradual Rollback When Possible

**Do**:
- Use gradual rollback (reduce percentage) when possible
- Monitor impact at each step
- Adjust rollout percentage incrementally

**Don't**:
- Always use full rollback immediately
- Ignore gradual rollback option

### 5. Root Cause Analysis

**Do**:
- Investigate root cause after rollback
- Fix underlying issue
- Re-enable validation after fix

**Don't**:
- Leave validation disabled permanently
- Skip root cause analysis

---

## Running the Deployment Preparation Tests (5.1)

The tests that validate feature flags (5.1.1), monitoring (5.1.2), and rollback (5.1.3) require **PostgreSQL and api-service to be running** (e.g. via Docker Compose).

### Prerequisites

1. **Start services** (if not already running):
   ```bash
   docker compose up -d postgres api-service
   ```
2. **Wait for Postgres to accept connections** (health: healthy). If Postgres was just started, wait until:
   ```bash
   docker compose exec postgres pg_isready -U hub
   ```
   returns "accepting connections".

### Run the full test suite (Django)

From the project root, run the three test modules inside the api-service container:

```bash
docker compose exec api-service python hub/manage.py test \
  hub.apps.orchestration.tests.test_feature_flags \
  hub.apps.orchestration.tests.test_monitoring_validation \
  hub.apps.orchestration.tests.test_rollback_procedures \
  --keepdb -v 2
```

- `--keepdb` reuses the test database so subsequent runs are faster.
- Expect 21 tests; first run may take several minutes (migrations on test DB).

### Quick checks (no database)

- **Feature flags logic** (no DB used for assertions):
  ```bash
  docker compose exec -e PYTHONPATH=/app api-service python /app/scripts/test_feature_flags_quick.py
  ```
- **Rollback scripts exist** (standalone, no Django):
  ```bash
  docker compose exec api-service python /app/scripts/verify_rollback_scripts.py
  ```

---

## Related Documentation

- [Workflow Business Rules Gradual Rollout Guide](WORKFLOW_BUSINESS_RULES_GRADUAL_ROLLOUT_GUIDE.md) - Phased enablement (5.2)
- [Workflow Orchestration Guide](WORKFLOW_ORCHESTRATION.md) - Complete workflow documentation
- [Business Rules Framework Guide](BUSINESS_RULES_FRAMEWORK_GUIDE.md) - Business rules framework
- [Monitoring Guide](MONITORING.md) - Monitoring and observability

---

**Last Updated**: 2026-01-27  
**Maintainer**: Platform Team
