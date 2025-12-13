# Workflow Tests - Fixes Needed

## Test Results Summary

**Total Tests**: 168
- **Passed**: 141
- **Failed**: 4
- **Errors**: 23
- **Skipped**: 1

## Core Workflow Tests (All Passed ✅)
- State Machine: 14/14 passed
- DSL Parser: 12/12 passed
- Registry: 10/10 passed
- Models: 20/20 passed
- Versioning: 10/10 passed
- **Total Core**: 66/66 passed

## Integration & Monitoring Tests (All Passed ✅)
- Integration: 2/2 passed
- Metrics: 13/13 passed
- Alerting: 10/10 passed
- Cleanup Command: 7/7 passed
- **Total Integration**: 32/32 passed

## Business Workflow Tests (Issues Found)

### Marketplace Publication Workflow
**Status**: 1 failure, 0 errors (after initial fix)

**Issues**:
1. ✅ **FIXED**: `WorkflowInstance` creation missing `workflow_definition` - Fixed by adding workflow_definition from registry
2. ❌ **FAILING**: `test_rollback_publication_task` - Listing status cannot be changed from PUBLISHED to DRAFT (model constraint)

**Fix Needed**:
- The rollback test expects to change listing status from PUBLISHED to DRAFT, but the model has a constraint preventing this
- Either update the test to use a different status transition, or update the rollback logic to handle this constraint

### Contract Creation Workflow
**Status**: 2 failures

**Issues**:
1. ❌ **FAILING**: `test_contract_creation_via_viewset` - `contract.created_by` is None instead of the user
2. ❌ **FAILING**: `test_contract_creation_with_dcs_contract` - Expected 400 but got 201 (DCS validation not working)

**Root Causes**:
- The viewset may not be setting `created_by` when creating contracts via workflow
- DCS contract validation may not be rejecting contracts with `dataContractSpecification` field

**Fixes Needed**:
- Ensure the contract creation workflow/viewset sets `created_by` from the authenticated user
- Verify DCS contract detection logic in the contract creation workflow

### Data Quality Check Workflow
**Status**: 1 failure, 15 errors

**Issues**:
1. ❌ **FAILING**: `test_workflow_execution_with_dq_service_unavailable` - Error message doesn't match expected
2. ❌ **ERRORS**: Multiple tests failing due to missing `workflow_definition` in `WorkflowInstance` creation

**Root Causes**:
- The test expects "DQ service is unavailable" but gets "Redis connection refused" error
- Tests creating `WorkflowInstance` directly without getting workflow_definition from registry

**Fixes Needed**:
- Update DQ workflow to check service availability before attempting execution
- Fix all test setUp methods to create `WorkflowInstance` with `workflow_definition` from registry

### Other Workflow Tests
**Status**: Multiple errors

**Common Pattern**:
- All errors follow the same pattern: `WorkflowInstance.objects.create()` called without `workflow_definition`
- Tests need to:
  1. Register workflow with registry
  2. Get workflow definition: `workflow_def = registry.get_workflow(WorkflowName.WORKFLOW_NAME)`
  3. Create instance with: `WorkflowInstance.objects.create(workflow_definition=workflow_def, ...)`

**Affected Test Files**:
- `test_asset_creation.py` - 4 errors
- `test_compliance_reporting.py` - 3 errors
- `test_data_quality.py` - 15 errors
- `test_dataset_creation.py` - 6 errors

## Fix Priority

### High Priority (Blocking)
1. Fix `WorkflowInstance` creation pattern in all test files (will fix 23 errors)
2. Fix contract creation `created_by` issue
3. Fix DCS contract validation

### Medium Priority
4. Fix marketplace publication rollback test
5. Fix DQ service unavailable error message

### Low Priority
6. Review skipped tests
7. Add missing test coverage

## Implementation Notes

### Pattern to Fix WorkflowInstance Creation

**Before**:
```python
self.workflow_instance = WorkflowInstance.objects.create(
    workflow_name=WorkflowName.WORKFLOW_NAME,
    tenant=self.tenant,
    ...
)
```

**After**:
```python
self.registry = WorkflowRegistry()
WorkflowName.register_workflow(self.registry)
workflow_def = self.registry.get_workflow(WorkflowName.WORKFLOW_NAME)
self.workflow_instance = WorkflowInstance.objects.create(
    workflow_definition=workflow_def,
    workflow_name=WorkflowName.WORKFLOW_NAME,
    workflow_version=workflow_def.version,
    tenant=self.tenant,
    ...
)
```

## Next Steps

1. Apply the `WorkflowInstance` creation fix to all affected test files
2. Investigate and fix contract creation viewset/workflow issues
3. Fix marketplace publication rollback logic
4. Update DQ workflow error handling
5. Re-run all tests to verify fixes

