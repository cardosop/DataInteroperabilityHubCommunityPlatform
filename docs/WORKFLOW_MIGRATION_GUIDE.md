# Workflow Migration Guide: Integrating Business Rules

**Version:** 1.0.0  
**Last Updated:** 2026-01-27  
**Status:** ✅ Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Migration Strategy](#migration-strategy)
3. [Step-by-Step Migration](#step-by-step-migration)
4. [Common Patterns](#common-patterns)
5. [Migration Examples](#migration-examples)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

---

## Overview

This guide provides comprehensive instructions for migrating workflows to use the Business Rules Framework for validation. The migration ensures consistent validation, error handling, and observability across all workflow operations.

### Benefits of Migration

- **Consistent Validation**: All workflows use the same validation framework
- **Better Error Messages**: Detailed error messages with validation context
- **Observability**: Metrics, events, logs, and traces for all validations
- **Performance**: Validation caching reduces overhead (<5% per step)
- **Maintainability**: Centralized validation logic reduces code duplication

### Prerequisites

- Understanding of the [Business Rules Framework](BUSINESS_RULES_FRAMEWORK_GUIDE.md)
- Understanding of the [Workflow Orchestration](WORKFLOW_ORCHESTRATION.md) system
- Access to workflow codebase

---

## Migration Strategy

### Phased Approach

1. **Phase 1**: Migrate workflow engine integration (automatic validation)
2. **Phase 2**: Migrate task functions to use service-specific business rules
3. **Phase 3**: Update compensation logic to use business rules
4. **Phase 4**: Remove duplicate validation logic
5. **Phase 5**: Update tests and documentation

### Migration Checklist

- [ ] Review existing validation logic in workflows
- [ ] Identify service-specific business rules to use
- [ ] Update workflow engine integration (if needed)
- [ ] Update task functions to use business rules
- [ ] Update compensation logic to use business rules
- [ ] Remove duplicate validation logic
- [ ] Update tests
- [ ] Update documentation
- [ ] Verify observability (metrics, events, logs, traces)

---

## Step-by-Step Migration

### Step 1: Review Existing Validation Logic

**Before Migration**:
```python
def my_task_function(input_data, instance, step):
    # Manual validation
    if not input_data.get("required_field"):
        raise ValueError("required_field is required")
    
    if input_data.get("value") < 0:
        raise ValueError("value must be non-negative")
    
    # Perform operation
    return {"result": "success"}
```

**Action**: Identify all validation logic in task functions and workflows.

### Step 2: Identify Service-Specific Business Rules

**Action**: Determine which business rules class to use for validation:

- **OrchestrationBusinessRules**: Workflow state, step execution validation
- **ContractsBusinessRules**: Contract creation, update validation
- **ODPSBusinessRules**: ODPS document validation
- **AssetsBusinessRules**: Asset lifecycle validation
- **MarketplaceBusinessRules**: Marketplace listing validation
- **Other service-specific rules**: As needed

### Step 3: Update Workflow Engine Integration

**Status**: ✅ Already implemented

The `WorkflowEngine` automatically uses `OrchestrationBusinessRules` for validation. No changes needed unless custom validation is required.

**Verification**:
```python
# Check that WorkflowEngine uses business rules
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
# WorkflowEngine._execute_task_step() should use OrchestrationBusinessRules
```

### Step 4: Update Task Functions

**Before Migration**:
```python
def create_contract_task(input_data, instance, step):
    # Manual validation
    contract_data = input_data.get("contract_data")
    if not contract_data:
        raise ValueError("contract_data is required")
    
    if not contract_data.get("name"):
        raise ValueError("Contract name is required")
    
    # Create contract
    contract = Contract.objects.create(**contract_data)
    return {"contract_id": str(contract.id)}
```

**After Migration**:
```python
def create_contract_task(input_data, instance, step):
    """Create contract with business rules validation"""
    from hub.apps.contracts.business_rules import ContractsBusinessRules
    
    # Get tenant and user context
    tenant = instance.tenant
    user = instance.created_by
    
    # Create business rules instance
    contract_rules = ContractsBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )
    
    # Validate contract creation using business rules
    contract_data = input_data.get("contract_data")
    validation_result = contract_rules.validate_contract_creation(
        contract_data=contract_data,
        tenant=tenant,
        user=user
    )
    
    if not validation_result.is_valid:
        raise ValueError(
            f"Contract validation failed: {', '.join(validation_result.errors)}"
        )
    
    # Log warnings if any
    if validation_result.warnings:
        logger.warning(
            f"Contract validation warnings: {', '.join(validation_result.warnings)}"
        )
    
    # Create contract
    contract = Contract.objects.create(**contract_data)
    return {"contract_id": str(contract.id)}
```

**Key Changes**:
1. Import service-specific business rules
2. Create business rules instance with tenant/user context
3. Use business rules validation instead of manual validation
4. Handle validation errors appropriately
5. Log warnings if any

### Step 5: Update Compensation Logic

**Before Migration**:
```python
def _compensate_step(self, instance, step):
    """Compensate a workflow step"""
    # No validation
    compensation_result = self._execute_compensation_task(instance, step)
    return compensation_result
```

**After Migration**:
```python
def _compensate_step(self, instance, step):
    """Compensate a workflow step with business rules validation"""
    from hub.apps.orchestration.business_rules import OrchestrationBusinessRules
    
    # Get tenant and user context
    tenant = instance.tenant
    user = instance.created_by
    
    # Create business rules instance
    business_rules = OrchestrationBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )
    
    # Validate compensation step (warnings don't block)
    compensation_step_result = business_rules.validate_workflow_step_execution(
        instance, step, tenant, user
    )
    
    if compensation_step_result.warnings:
        logger.warning(
            f"Compensation step validation warnings: "
            f"{', '.join(compensation_step_result.warnings)}"
        )
    
    # Execute compensation logic
    compensation_result = self._execute_compensation_task(instance, step, compensation_def)
    
    # Include validation results in compensation logs
    return {
        "status": "compensated",
        "result": compensation_result,
        "validation": {
            "is_valid": compensation_step_result.is_valid,
            "warnings": compensation_step_result.warnings,
            "details": compensation_step_result.details
        }
    }
```

**Key Changes**:
1. Import OrchestrationBusinessRules
2. Create business rules instance
3. Validate compensation step
4. Log warnings (don't block compensation)
5. Include validation results in compensation logs

### Step 6: Remove Duplicate Validation Logic

**Action**: Remove manual validation logic that is now handled by business rules:

**Before**:
```python
def my_task_function(input_data, instance, step):
    # Manual validation (duplicate)
    if not input_data.get("field"):
        raise ValueError("field is required")
    
    # Business rules validation (new)
    validation_result = business_rules.validate_my_operation(input_data)
    if not validation_result.is_valid:
        raise ValueError(...)
    
    # Perform operation
    return {"result": "success"}
```

**After**:
```python
def my_task_function(input_data, instance, step):
    # Business rules validation only
    validation_result = business_rules.validate_my_operation(input_data)
    if not validation_result.is_valid:
        raise ValueError(...)
    
    # Perform operation
    return {"result": "success"}
```

### Step 7: Update Tests

**Before Migration**:
```python
def test_create_contract_task():
    """Test contract creation task"""
    input_data = {"contract_data": {"name": "Test Contract"}}
    result = create_contract_task(input_data, instance, step)
    assert result["contract_id"] is not None
```

**After Migration**:
```python
def test_create_contract_task():
    """Test contract creation task with business rules validation"""
    from hub.apps.contracts.business_rules import ContractsBusinessRules
    
    # Test successful validation
    input_data = {"contract_data": {"name": "Test Contract"}}
    result = create_contract_task(input_data, instance, step)
    assert result["contract_id"] is not None
    
    # Test validation failure
    invalid_input = {"contract_data": {}}  # Missing name
    with pytest.raises(ValueError, match="Contract validation failed"):
        create_contract_task(invalid_input, instance, step)
```

**Key Changes**:
1. Test successful validation path
2. Test validation failure path
3. Test validation warnings (if applicable)
4. Verify error messages include validation context

---

## Common Patterns

### Pattern 1: Basic Task Function Migration

**Use Case**: Simple task function with basic validation

**Before**:
```python
def simple_task(input_data, instance, step):
    if not input_data.get("field"):
        raise ValueError("field is required")
    return {"result": "success"}
```

**After**:
```python
def simple_task(input_data, instance, step):
    from hub.apps.my_service.business_rules import MyServiceBusinessRules
    
    my_rules = MyServiceBusinessRules(
        tenant_id=str(instance.tenant.id),
        user_id=str(instance.created_by.id)
    )
    
    validation_result = my_rules.validate_my_operation(
        resource=input_data.get("field"),
        tenant=instance.tenant,
        user=instance.created_by
    )
    
    if not validation_result.is_valid:
        raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")
    
    return {"result": "success"}
```

### Pattern 2: Task Function with Multiple Validations

**Use Case**: Task function requiring multiple validations

**Before**:
```python
def complex_task(input_data, instance, step):
    # Multiple manual validations
    if not input_data.get("field1"):
        raise ValueError("field1 is required")
    if not input_data.get("field2"):
        raise ValueError("field2 is required")
    if input_data.get("field3") < 0:
        raise ValueError("field3 must be non-negative")
    
    return {"result": "success"}
```

**After**:
```python
def complex_task(input_data, instance, step):
    from hub.apps.my_service.business_rules import MyServiceBusinessRules
    
    my_rules = MyServiceBusinessRules(
        tenant_id=str(instance.tenant.id),
        user_id=str(instance.created_by.id)
    )
    
    # Single comprehensive validation
    validation_result = my_rules.validate_complex_operation(
        field1=input_data.get("field1"),
        field2=input_data.get("field2"),
        field3=input_data.get("field3"),
        tenant=instance.tenant,
        user=instance.created_by
    )
    
    if not validation_result.is_valid:
        raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")
    
    if validation_result.warnings:
        logger.warning(f"Validation warnings: {', '.join(validation_result.warnings)}")
    
    return {"result": "success"}
```

### Pattern 3: Task Function with Service Integration

**Use Case**: Task function that integrates with multiple services

**Before**:
```python
def integrated_task(input_data, instance, step):
    # Manual validation for each service
    contract_data = input_data.get("contract_data")
    if not contract_data:
        raise ValueError("contract_data is required")
    
    asset_data = input_data.get("asset_data")
    if not asset_data:
        raise ValueError("asset_data is required")
    
    # Create resources
    contract = Contract.objects.create(**contract_data)
    asset = Asset.objects.create(**asset_data)
    
    return {"contract_id": str(contract.id), "asset_id": str(asset.id)}
```

**After**:
```python
def integrated_task(input_data, instance, step):
    from hub.apps.contracts.business_rules import ContractsBusinessRules
    from hub.apps.assets.business_rules import AssetsBusinessRules
    
    tenant = instance.tenant
    user = instance.created_by
    
    # Validate contract creation
    contract_rules = ContractsBusinessRules(
        tenant_id=str(tenant.id),
        user_id=str(user.id)
    )
    contract_data = input_data.get("contract_data")
    contract_result = contract_rules.validate_contract_creation(
        contract_data=contract_data,
        tenant=tenant,
        user=user
    )
    if not contract_result.is_valid:
        raise ValueError(f"Contract validation failed: {', '.join(contract_result.errors)}")
    
    # Validate asset creation
    asset_rules = AssetsBusinessRules(
        tenant_id=str(tenant.id),
        user_id=str(user.id)
    )
    asset_data = input_data.get("asset_data")
    asset_result = asset_rules.validate_asset_creation(
        asset_data=asset_data,
        tenant=tenant,
        user=user
    )
    if not asset_result.is_valid:
        raise ValueError(f"Asset validation failed: {', '.join(asset_result.errors)}")
    
    # Create resources
    contract = Contract.objects.create(**contract_data)
    asset = Asset.objects.create(**asset_data)
    
    return {"contract_id": str(contract.id), "asset_id": str(asset.id)}
```

### Pattern 4: Compensation Migration

**Use Case**: Migrating compensation logic to use business rules

**Before**:
```python
def _compensate_step(self, instance, step):
    """Compensate a workflow step"""
    # No validation
    try:
        compensation_result = self._execute_compensation_task(instance, step)
        return {"status": "compensated", "result": compensation_result}
    except Exception as e:
        logger.error(f"Compensation failed: {str(e)}")
        return {"status": "failed", "error": str(e)}
```

**After**:
```python
def _compensate_step(self, instance, step):
    """Compensate a workflow step with business rules validation"""
    from hub.apps.orchestration.business_rules import OrchestrationBusinessRules
    
    tenant = instance.tenant
    user = instance.created_by
    
    business_rules = OrchestrationBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )
    
    # Validate compensation step (warnings don't block)
    compensation_step_result = business_rules.validate_workflow_step_execution(
        instance, step, tenant, user
    )
    
    if compensation_step_result.warnings:
        logger.warning(
            f"Compensation step validation warnings: "
            f"{', '.join(compensation_step_result.warnings)}"
        )
    
    try:
        compensation_result = self._execute_compensation_task(instance, step, compensation_def)
        
        return {
            "status": "compensated",
            "result": compensation_result,
            "validation": {
                "is_valid": compensation_step_result.is_valid,
                "warnings": compensation_step_result.warnings,
                "details": compensation_step_result.details
            }
        }
    except Exception as e:
        logger.error(
            f"Compensation failed: {str(e)}",
            workflow_instance_id=str(instance.id),
            step_name=step.step_name,
            validation_warnings=compensation_step_result.warnings
        )
        return {
            "status": "failed",
            "error": str(e),
            "validation": {
                "is_valid": compensation_step_result.is_valid,
                "warnings": compensation_step_result.warnings
            }
        }
```

---

## Migration Examples

### Example 1: ProductCreationWorkflow

**Location**: `hub/apps/orchestration/workflows/product_creation.py`

**Migration**: ✅ Already migrated

**Key Changes**:
- `_parse_odps_task()` uses `ODPSBusinessRules.validate_odps_document()`
- `_validate_odcs_task()` uses `ODPSBusinessRules.validate_odcs_document()`
- `_create_odps_contract_task()` uses `ODPSBusinessRules.validate_contract_creation()`
- `_link_contracts_task()` uses `ODPSLinkingRules.validate_linking()`

**Reference**: See `hub/apps/orchestration/workflows/product_creation.py` for complete implementation.

### Example 2: ContractCreationWorkflow

**Location**: `hub/apps/orchestration/workflows/contract_creation.py`

**Migration**: ✅ Already migrated

**Key Changes**:
- Contract creation tasks use `ContractsBusinessRules.validate_contract_creation()`
- Contract update tasks use `ContractsBusinessRules.validate_contract_update()`
- Contract lifecycle tasks use `ContractsBusinessRules.validate_contract_lifecycle()`

**Reference**: See `hub/apps/orchestration/workflows/contract_creation.py` for complete implementation.

### Example 3: DataQualityCheckWorkflow

**Location**: `hub/apps/orchestration/workflows/data_quality.py`

**Migration**: ✅ Already migrated

**Key Changes**:
- `_execute_quality_rules_task()` uses `DQBusinessRules.validate_dq_run_execution()`

**Reference**: See `hub/apps/orchestration/workflows/data_quality.py` for complete implementation.

---

## Troubleshooting

### Common Issues

#### 1. Validation Errors Not Propagating

**Symptom**: Validation errors not appearing in workflow error messages

**Root Cause**: Error formatting or propagation issue

**Solution**:
1. Check that `WorkflowExecutionError` includes validation context
2. Verify `_format_validation_error()` method is used
3. Check structured logs for validation errors

**Example Fix**:
```python
# Ensure error includes validation context
if not validation_result.is_valid:
    error_message = self._format_validation_error(
        "workflow state validation",
        validation_result,
        instance,
        step
    )
    raise WorkflowExecutionError(error_message)
```

#### 2. Business Rules Not Found

**Symptom**: `ValueError: Rule 'my_rule' not found`

**Root Cause**: Business rules class not registered

**Solution**:
1. Ensure business rules class uses `@register_rule` decorator
2. Verify business rules class is imported
3. Check rule name matches registration

**Example Fix**:
```python
@register_rule(
    rule_name="my_service_validation",
    description="Validates my service operations",
    tags=["my_service", "validation"],
    priority=10
)
class MyServiceBusinessRules(BusinessRules):
    # ...
```

#### 3. Validation Performance Issues

**Symptom**: Workflow execution is slow after migration

**Root Cause**: Validation overhead without caching

**Solution**:
1. Enable validation caching (default: enabled)
2. Check cache hit rates in metrics
3. Review validation logic for performance bottlenecks

**Example Fix**:
```python
# Ensure caching is enabled
business_rules = MyServiceBusinessRules(
    tenant_id=tenant_id,
    user_id=user_id,
    enable_caching=True  # Default: True
)
```

#### 4. Compensation Validation Blocking Rollback

**Symptom**: Compensation fails due to validation errors

**Root Cause**: Validation errors blocking compensation

**Solution**:
1. Ensure compensation validation only logs warnings
2. Don't raise exceptions for validation errors in compensation
3. Check compensation validation logic

**Example Fix**:
```python
# Compensation validation should not block
compensation_result = business_rules.validate_workflow_step_execution(
    instance, step, tenant, user
)

if compensation_result.warnings:
    # Log warnings but don't block
    logger.warning(f"Compensation warnings: {', '.join(compensation_result.warnings)}")

# Proceed with compensation even if validation has warnings
compensation_result = self._execute_compensation_task(instance, step)
```

---

## Best Practices

### 1. Always Use Business Rules for Validation

**Do**:
```python
# Use business rules for validation
business_rules = MyServiceBusinessRules(tenant_id=tenant_id, user_id=user_id)
validation_result = business_rules.validate_my_operation(resource)
if not validation_result.is_valid:
    raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")
```

**Don't**:
```python
# Don't skip validation or duplicate validation logic
if not resource:
    raise ValueError("Resource is required")
```

### 2. Use Service-Specific Business Rules

**Do**:
```python
# Use service-specific business rules
from hub.apps.contracts.business_rules import ContractsBusinessRules
contract_rules = ContractsBusinessRules(tenant_id=tenant_id, user_id=user_id)
```

**Don't**:
```python
# Don't use OrchestrationBusinessRules for domain validation
orchestration_rules = OrchestrationBusinessRules(tenant_id=tenant_id, user_id=user_id)
# Use OrchestrationBusinessRules only for workflow state validation
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
    raise ValueError("Validation warnings found")
```

### 4. Include Validation Context in Error Messages

**Do**:
```python
# Include validation context in error messages
if not validation_result.is_valid:
    error_message = (
        f"Validation failed: {', '.join(validation_result.errors)}. "
        f"Rule: {business_rules.get_rule_name()}, "
        f"Workflow: {instance.workflow_name}, "
        f"Step: {step.step_name}"
    )
    raise ValueError(error_message)
```

**Don't**:
```python
# Don't create generic error messages
if not validation_result.is_valid:
    raise ValueError("Validation failed")
```

### 5. Test Validation Paths

**Do**:
```python
# Test both success and failure paths
def test_my_task_function():
    # Test successful validation
    result = my_task_function(valid_input, instance, step)
    assert result["status"] == "success"
    
    # Test validation failure
    with pytest.raises(ValueError, match="Validation failed"):
        my_task_function(invalid_input, instance, step)
```

**Don't**:
```python
# Don't skip testing validation failures
def test_my_task_function():
    result = my_task_function(valid_input, instance, step)
    assert result["status"] == "success"
```

---

## Related Documentation

- [Workflow Orchestration Guide](WORKFLOW_ORCHESTRATION.md) - Complete workflow documentation
- [Business Rules Framework Guide](BUSINESS_RULES_FRAMEWORK_GUIDE.md) - Business rules framework
- [Business Logic Integration](BUSINESS_LOGIC_INTEGRATION.md) - Service layer coordination

---

**Last Updated**: 2026-01-27  
**Maintainer**: Platform Team
