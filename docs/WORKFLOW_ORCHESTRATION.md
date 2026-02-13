# Workflow Orchestration Guide

**Version:** 2.0.0
**Last Updated:** 2026-01-27
**Status:** ✅ Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Business Rules Integration](#business-rules-integration)
4. [Validation Behavior](#validation-behavior)
5. [Error Handling](#error-handling)
6. [Workflow Execution](#workflow-execution)
7. [Compensation and Rollback](#compensation-and-rollback)
8. [Observability](#observability)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Workflow Orchestration system provides a robust, production-grade framework for executing multi-step operations with comprehensive validation, error handling, compensation, and observability. All workflows integrate seamlessly with the Business Rules Framework to ensure consistent validation and business logic enforcement.

### Key Features

- **Business Rules Integration**: Automatic validation at every workflow step using the Business Rules Framework
- **Comprehensive Validation**: Pre-step, post-step, and workflow state validation
- **Error Handling**: Detailed error messages with validation context
- **Compensation**: Automatic rollback using Saga pattern with business rules validation
- **Observability**: Metrics, events, logs, and distributed tracing
- **Performance**: Validation caching with <5% overhead per step
- **Gateway Independence**: Workflow execution is completely independent of whether requests arrive via Traefik API Gateway or direct api-service access

### Workflow Engine

**Location**: `hub/apps/orchestration/workflow_engine.py`

The `WorkflowEngine` class orchestrates workflow execution with integrated business rules validation at every step.

---

## Architecture

### Gateway Independence

**Workflow execution is completely independent of request routing.**

Workflows can be triggered via:
- **Direct api-service access**: Frontend → api-service (Django)
- **Via Traefik API Gateway**: Frontend → Traefik → API Gateway (FastAPI) → api-service (Django)

**Key Points:**
- Workflow execution methods (`execute()`, `execute_start()`, etc.) take only workflow-specific parameters (tenant_id, user_id, workflow data)
- No request objects are passed to workflow execution methods
- No gateway headers (`X-Gateway-*`) are accessed in workflow code
- No URL building depends on request host
- Workflow execution is purely data-driven based on `WorkflowInstance` model

**Testing:**
- All workflow E2E and integration tests work identically whether triggered via gateway or direct access
- Tests explicitly verify gateway independence (see `hub/apps/orchestration/tests/test_workflow_gateway_independence.py`)
- Workflow execution results are identical regardless of request source

**Documentation:**
- See `openspec/changes/workflows1/artifacts/WORKFLOW_GATEWAY_REVIEW.md` for detailed review
- See `docs/API_GATEWAY_TRAEFIK.md` for API Gateway routing details

### Workflow Components

```
┌─────────────────────────────────────────────────────────┐
│                  Workflow Engine                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Workflow    │  │   Business   │  │  Validation  │ │
│  │   Execution   │  │    Rules     │  │    Layer     │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                  │                  │         │
│         └──────────────────┼──────────────────┘         │
│                            │                              │
│                   ┌────────▼────────┐                    │
│                   │  Step Execution  │                    │
│                   │   with Validation│                    │
│                   └─────────────────┘                    │
│                                                           │
└───────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Metrics     │    │    Events    │    │    Logs     │
│  (Prometheus) │    │  (Event Bus) │    │ (Structured)│
└──────────────┘    └──────────────┘    └──────────────┘
```

### Workflow Lifecycle

1. **Create Instance**: Workflow instance created with input data
2. **Start Instance**: Workflow status set to RUNNING
3. **Execute Steps**: Each step executed with validation:
   - Pre-step validation (workflow state, step input)
   - Step execution
   - Post-step validation (step output, workflow state)
4. **Compensation**: On failure, rollback with validation
5. **Complete**: Workflow marked as COMPLETED or FAILED

---

## Business Rules Integration

### Integration Points

Business rules are integrated at three key points in workflow execution:

1. **Pre-Step Validation**: Before executing a workflow step
2. **Post-Step Validation**: After executing a workflow step
3. **Compensation Validation**: During workflow rollback

### OrchestrationBusinessRules

**Location**: `hub/apps/orchestration/business_rules.py`

The `OrchestrationBusinessRules` class provides workflow-specific validation methods:

- `validate_workflow_step_execution()`: Validates step can execute
- `validate_step_input()`: Validates step input data
- `validate_step_output()`: Validates step output data
- `validate_workflow_state()`: Validates workflow state consistency

### Integration in Workflow Engine

The `WorkflowEngine._execute_task_step()` method integrates business rules validation:

```python
def _execute_task_step(
    self, instance: WorkflowInstance, step: WorkflowStep, step_def: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a task step with business rules validation"""

    # Get tenant and user for business rules validation
    tenant = instance.tenant
    user = instance.created_by

    # Create business rules instance with tenant/user context
    business_rules = OrchestrationBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )

    # Pre-step validation: Validate workflow state
    workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
    if not workflow_state_result.is_valid:
        raise WorkflowExecutionError(...)

    # Pre-step validation: Validate step input
    step_input_result = business_rules.validate_step_input(instance, step, task_input, tenant, user)
    if not step_input_result.is_valid:
        raise WorkflowExecutionError(...)

    # Execute task
    result = task_func(task_input, instance, step)

    # Post-step validation: Validate step output
    step_output_result = business_rules.validate_step_output(instance, step, result, tenant, user)
    if not step_output_result.is_valid:
        raise WorkflowExecutionError(...)

    # Post-step validation: Validate workflow state after step
    post_workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
    if not post_workflow_state_result.is_valid:
        raise WorkflowExecutionError(...)

    return result
```

### Service-Specific Business Rules

Workflows can also use service-specific business rules for domain validation:

```python
# Example: Using ODPSBusinessRules in ProductCreationWorkflow
from hub.apps.contracts.business_rules import ODPSBusinessRules

odps_rules = ODPSBusinessRules(
    tenant_id=str(tenant.id),
    user_id=str(user.id)
)

# Validate ODPS document before parsing
odps_result = odps_rules.validate_odps_document(odps_document)
if not odps_result.is_valid:
    raise ValueError(f"ODPS validation failed: {', '.join(odps_result.errors)}")
```

---

## Validation Behavior

### Validation Phases

Workflow execution includes validation at multiple phases:

#### 1. Pre-Step Validation

**Purpose**: Ensure workflow and step are ready for execution

**Validations**:
- **Workflow State**: Workflow status is RUNNING, state is consistent
- **Step Execution**: Step can execute in current workflow state
- **Step Input**: Input data structure and schema validation
- **Tenant Context**: Tenant consistency validation
- **User Permissions**: User has permission to execute step

**Example**:
```python
# Validate workflow state before step execution
workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
# Validates:
# - Workflow status is RUNNING
# - Workflow state_data is consistent
# - Step indices match workflow current_step_index
# - Completed steps are in correct order
```

#### 2. Step Input Validation

**Purpose**: Ensure step input data is valid

**Validations**:
- Input is a dictionary
- Input is JSON serializable (for state persistence)
- Required fields are present (if schema defined)
- Data types are correct (if schema defined)

**Example**:
```python
# Validate step input data
step_input_result = business_rules.validate_step_input(instance, step, task_input, tenant, user)
# Validates:
# - task_input is a dict
# - task_input is JSON serializable
# - Input size is reasonable (<10MB)
```

#### 3. Step Output Validation

**Purpose**: Ensure step output data is valid

**Validations**:
- Output is a dictionary
- Output is JSON serializable (for state persistence)
- Required fields are present (if schema defined)
- Data types are correct (if schema defined)

**Example**:
```python
# Validate step output data
step_output_result = business_rules.validate_step_output(instance, step, result, tenant, user)
# Validates:
# - result is a dict
# - result is JSON serializable
# - Output size is reasonable (<10MB)
```

#### 4. Post-Step Validation

**Purpose**: Ensure workflow state is consistent after step execution

**Validations**:
- Workflow state is consistent
- Step status is COMPLETED
- State data is valid
- Step output merged correctly into state_data

**Example**:
```python
# Validate workflow state after step
post_workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
# Validates:
# - Workflow state_data includes step output
# - Step status transition is valid (PENDING → COMPLETED)
# - Workflow current_step_index is updated
```

### Validation Caching

Validation results are cached to improve performance:

- **Cache Key**: Generated from rule name, workflow ID, step index, and validation type
- **Cache TTL**: Configurable per rule (default: 300 seconds)
- **Cache Invalidation**: Automatic expiration, manual invalidation on state changes

**Performance**: Validation overhead is <5% per step with caching enabled.

---

## Error Handling

### Error Propagation

Validation errors from business rules are propagated to workflow execution errors:

```python
# Validation failure raises WorkflowExecutionError
if not workflow_state_result.is_valid:
    error_message = self._format_validation_error(
        "workflow state validation",
        workflow_state_result,
        instance,
        step
    )
    raise WorkflowExecutionError(error_message)
```

### Error Message Format

Error messages include comprehensive context:

```
Business rules validation failed (workflow state validation) |
Rule: OrchestrationBusinessRules |
Workflow: product_creation (id: 123e4567-e89b-12d3-a456-426614174000) |
Step: parse_odps (index: 0) |
Errors: Workflow step cannot execute: workflow status is DRAFT, expected RUNNING |
Warnings: Step index (0) does not match workflow current_step_index (1)
```

### Error Details

Workflow errors include detailed validation information:

```python
# Error details structure
{
    "validation_type": "workflow_state",
    "rule_name": "OrchestrationBusinessRules",
    "errors": ["Workflow step cannot execute: workflow status is DRAFT"],
    "warnings": ["Step index mismatch"],
    "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
    "step_id": "789e0123-e45f-67g8-h901-234567890123",
    "step_name": "parse_odps",
    "step_index": 0
}
```

### Structured Logging

All validation errors are logged with structured logging:

```python
logger.error(
    "Workflow validation failed",
    workflow_instance_id=str(instance.id),
    workflow_name=instance.workflow_name,
    workflow_version=instance.workflow_version,
    step_name=step.step_name,
    step_index=step.step_index,
    rule_name=rule_name,
    validation_type=validation_type,
    errors=validation_result.errors,
    warnings=validation_result.warnings,
    validation_details=validation_result.details,
    tenant_id=tenant_id_str,
)
```

### Error Recovery

Workflows support error recovery:

1. **Retry**: Workflow can be retried after fixing validation issues
2. **Compensation**: Automatic rollback on failure
3. **State Recovery**: Workflow state can be recovered from last successful step

---

## Workflow Execution

### Creating a Workflow Instance

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()

# Create workflow instance
instance = engine.create_instance(
    workflow_name="product_creation",
    input_data={
        "odps_document": {...},
        "asset_id": "asset-123"
    },
    tenant_id="tenant-123",
    created_by_id="user-456"
)
```

### Starting Workflow Execution

```python
# Start workflow execution
instance = engine.start_instance(str(instance.id))

# Execute workflow (synchronously or asynchronously)
engine.execute_instance(str(instance.id))
```

### Workflow DSL

Workflows are defined using a JSON/YAML DSL:

```json
{
  "version": "1.0.0",
  "steps": [
    {
      "name": "parse_odps",
      "type": "task",
      "task": "product_creation.parse_odps",
      "input": {
        "odps_document": "{{input.odps_document}}"
      }
    },
    {
      "name": "validate_odcs",
      "type": "task",
      "task": "product_creation.validate_odcs",
      "input": {
        "odcs_contract": "{{state.odcs_contract}}"
      }
    }
  ]
}
```

### Task Functions

Task functions receive workflow context and return step output:

```python
def parse_odps_task(
    input_data: Dict[str, Any],
    instance: WorkflowInstance,
    step: WorkflowStep
) -> Dict[str, Any]:
    """Parse ODPS document with business rules validation"""

    # Get tenant and user for business rules
    tenant = instance.tenant
    user = instance.created_by

    # Use service-specific business rules
    from hub.apps.contracts.business_rules import ODPSBusinessRules

    odps_rules = ODPSBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )

    # Validate ODPS document
    odps_document = input_data.get("odps_document")
    validation_result = odps_rules.validate_odps_document(odps_document)

    if not validation_result.is_valid:
        raise ValueError(f"ODPS validation failed: {', '.join(validation_result.errors)}")

    # Parse ODPS document
    parsed_odps = parse_odps_document(odps_document)

    # Return step output (merged into state_data)
    return {
        "parsed_odps": parsed_odps,
        "odps_version": parsed_odps.get("version")
    }
```

---

## Compensation and Rollback

### Compensation with Business Rules

Compensation validates using business rules but does not block rollback:

```python
def rollback_workflow(
    self,
    instance: WorkflowInstance,
    failed_step: WorkflowStep
) -> WorkflowInstance:
    """Rollback workflow using compensation logic (Saga pattern)"""

    # Create business rules instance
    business_rules = OrchestrationBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )

    # Validate compensation can execute (warnings don't block)
    compensation_validation_result = business_rules.validate_workflow_state(instance, tenant, user)
    if not compensation_validation_result.is_valid:
        # Log validation errors but don't block compensation
        logger.warning(
            f"Compensation validation errors: {', '.join(compensation_validation_result.errors)}"
        )

    # Compensate each completed step
    for step in completed_steps:
        compensation_result = self._compensate_step(instance, step)
```

### Compensation Step Validation

Each compensation step is validated using business rules:

```python
def _compensate_step(
    self,
    instance: WorkflowInstance,
    step: WorkflowStep
) -> Dict[str, Any]:
    """Compensate a workflow step with business rules validation"""

    # Validate compensation step
    compensation_step_result = business_rules.validate_workflow_step_execution(
        instance, step, tenant, user
    )

    if compensation_step_result.warnings:
        # Log warnings but proceed with compensation
        logger.warning(
            f"Compensation step validation warnings: {', '.join(compensation_step_result.warnings)}"
        )

    # Execute compensation logic
    compensation_result = self._execute_compensation_task(instance, step, compensation_def)

    # Include validation results in compensation logs
    return {
        "status": "compensated",
        "result": compensation_result,
        "validation": {
            "is_valid": compensation_step_result.is_valid,
            "warnings": compensation_step_result.warnings
        }
    }
```

---

## Observability

### Metrics

Workflow validation metrics are recorded in Prometheus:

- **`workflow_business_rules_validations_total`** (Counter)
  - Labels: `workflow_name`, `step_name`, `rule_name`, `validation_type`, `result` (valid/invalid), `tenant_id`

- **`workflow_business_rules_validation_duration_seconds`** (Histogram)
  - Labels: `workflow_name`, `step_name`, `rule_name`, `validation_type`, `result`, `tenant_id`

- **`workflow_business_rules_validation_cache_hits_total`** (Counter)
  - Labels: `workflow_name`, `step_name`, `rule_name`, `validation_type`, `tenant_id`

- **`workflow_business_rules_validation_cache_misses_total`** (Counter)
  - Labels: `workflow_name`, `step_name`, `rule_name`, `validation_type`, `tenant_id`

### Events

Workflow events include validation results:

- **`workflow.step.started`**: Includes validation status
- **`workflow.step.completed`**: Includes validation results
- **`workflow.step.failed`**: Includes validation errors

**Example Event**:
```json
{
  "event_type": "workflow.step.completed",
  "workflow_instance_id": "123e4567-e89b-12d3-a456-426614174000",
  "workflow_name": "product_creation",
  "step_name": "parse_odps",
  "step_index": 0,
  "validation": {
    "workflow_state": {
      "is_valid": true,
      "duration_seconds": 0.002
    },
    "step_input": {
      "is_valid": true,
      "duration_seconds": 0.001
    },
    "step_output": {
      "is_valid": true,
      "duration_seconds": 0.001
    }
  }
}
```

### Structured Logging

All workflow operations are logged with structured logging:

```python
logger.info(
    "Workflow step validation completed",
    workflow_instance_id=str(instance.id),
    workflow_name=instance.workflow_name,
    step_name=step.step_name,
    step_index=step.step_index,
    validation_type="workflow_state",
    rule_name="OrchestrationBusinessRules",
    is_valid=True,
    duration_seconds=0.002,
    cached=False
)
```

### Distributed Tracing

Validation spans are created in OpenTelemetry traces:

```python
validation_span = tracer.start_span(
    name="workflow.validation.workflow_state",
    attributes={
        "workflow.instance_id": str(instance.id),
        "workflow.name": instance.workflow_name,
        "workflow.step.name": step.step_name,
        "workflow.step.index": step.step_index,
        "business_rules.rule_name": rule_name,
        "business_rules.validation_type": "workflow_state",
    },
)
```

---

## Best Practices

### 1. Always Use Business Rules for Validation

**Do**:
```python
# Use business rules for validation
business_rules = OrchestrationBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = business_rules.validate_workflow_state(instance, tenant, user)
if not result.is_valid:
    raise WorkflowExecutionError(...)
```

**Don't**:
```python
# Don't skip validation
if instance.status != WorkflowStatus.RUNNING:
    raise WorkflowExecutionError("Invalid status")
```

### 2. Use Service-Specific Business Rules in Task Functions

**Do**:
```python
def create_contract_task(input_data, instance, step):
    from hub.apps.contracts.business_rules import ContractsBusinessRules

    contract_rules = ContractsBusinessRules(tenant_id=tenant_id, user_id=user_id)
    validation_result = contract_rules.validate_contract_creation(contract_data)
    if not validation_result.is_valid:
        raise ValueError(f"Contract validation failed: {', '.join(validation_result.errors)}")
```

**Don't**:
```python
# Don't duplicate validation logic in task functions
def create_contract_task(input_data, instance, step):
    if not contract_data.get("name"):
        raise ValueError("Contract name is required")
```

### 3. Handle Validation Warnings Appropriately

**Do**:
```python
# Log warnings but don't block execution
if validation_result.warnings:
    logger.warning(f"Validation warnings: {', '.join(validation_result.warnings)}")
```

**Don't**:
```python
# Don't treat warnings as errors
if validation_result.warnings:
    raise WorkflowExecutionError("Validation warnings found")
```

### 4. Include Validation Context in Error Messages

**Do**:
```python
# Use _format_validation_error for consistent error messages
error_message = self._format_validation_error(
    "workflow state validation",
    validation_result,
    instance,
    step
)
raise WorkflowExecutionError(error_message)
```

**Don't**:
```python
# Don't create generic error messages
raise WorkflowExecutionError("Validation failed")
```

### 5. Use Structured Logging

**Do**:
```python
logger.error(
    "Workflow validation failed",
    workflow_instance_id=str(instance.id),
    step_name=step.step_name,
    errors=validation_result.errors,
    tenant_id=tenant_id_str,
)
```

**Don't**:
```python
logger.error(f"Validation failed for workflow {instance.id}")
```

---

## Troubleshooting

### Common Issues

#### 1. Validation Failures Blocking Workflow Execution

**Symptom**: Workflow fails with validation errors

**Root Cause**: Business rules validation is failing

**Solution**:
1. Check validation error messages in workflow error_details
2. Verify workflow state is consistent
3. Check tenant and user context
4. Review business rules validation logic

**Example**:
```python
# Check workflow error details
instance = WorkflowInstance.objects.get(id=workflow_id)
if instance.error_details:
    validation_errors = instance.error_details.get("validation_errors", [])
    for error in validation_errors:
        print(f"Validation error: {error}")
```

#### 2. Performance Degradation from Validation

**Symptom**: Workflow execution is slow

**Root Cause**: Validation overhead without caching

**Solution**:
1. Enable validation caching (default: enabled)
2. Check cache hit rates in metrics
3. Review validation logic for performance bottlenecks
4. Consider optimizing validation logic

**Example**:
```python
# Check cache hit rates
# Prometheus query:
# rate(workflow_business_rules_validation_cache_hits_total[5m]) /
# rate(workflow_business_rules_validations_total[5m])
```

#### 3. Compensation Validation Warnings

**Symptom**: Compensation logs show validation warnings

**Root Cause**: Workflow state may be inconsistent during rollback

**Solution**:
1. Review compensation validation warnings (warnings don't block compensation)
2. Verify compensation logic handles inconsistent state
3. Check workflow state after compensation

**Example**:
```python
# Check compensation validation warnings
compensation_logs = instance.error_details.get("compensation_results", [])
for result in compensation_logs:
    if result.get("validation", {}).get("warnings"):
        warnings = result["validation"]["warnings"]
        logger.warning(f"Compensation warnings: {warnings}")
```

#### 4. Validation Errors Not Propagating

**Symptom**: Validation errors not appearing in workflow error messages

**Root Cause**: Error formatting or propagation issue

**Solution**:
1. Check `_format_validation_error` method
2. Verify `WorkflowExecutionError` includes validation context
3. Check structured logs for validation errors

**Example**:
```python
# Check structured logs
# Search for: "Workflow validation failed"
# Should include: errors, warnings, validation_details
```

### Debugging Workflow Validation

1. **Enable Debug Logging**:
   ```python
   import logging
   logging.getLogger("hub.apps.orchestration").setLevel(logging.DEBUG)
   ```

2. **Check Validation Results**:
   ```python
   # In workflow execution, check validation results
   validation_results = instance.state_data.get("validation_results", {})
   for validation_type, result in validation_results.items():
       print(f"{validation_type}: is_valid={result['result'].is_valid}")
   ```

3. **Review Metrics**:
   ```python
   # Check Prometheus metrics
   # workflow_business_rules_validations_total
   # workflow_business_rules_validation_duration_seconds
   ```

4. **Inspect Traces**:
   ```python
   # Check OpenTelemetry traces
   # Look for spans: workflow.validation.*
   ```

---

## Related Documentation

- [Business Rules Framework Guide](BUSINESS_RULES_FRAMEWORK_GUIDE.md) - Complete guide to business rules
- [Business Logic Integration](BUSINESS_LOGIC_INTEGRATION.md) - Service layer coordination
- [Workflow Migration Guide](WORKFLOW_MIGRATION_GUIDE.md) - Migrating workflows to use business rules
- [Monitoring Guide](MONITORING.md) - Monitoring workflows and validation metrics

---

**Last Updated**: 2026-01-27
**Maintainer**: Platform Team
