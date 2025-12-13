# Bug Prevention Patterns

Comprehensive guide for bug prevention patterns including input/output validation, transaction management, idempotency keys, and request deduplication.

## Table of Contents

1. [Overview](#overview)
2. [Input Validation](#input-validation)
3. [Output Validation](#output-validation)
4. [Transaction Management](#transaction-management)
5. [Idempotency Keys](#idempotency-keys)
6. [Request Deduplication](#request-deduplication)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

---

## Overview

The bug prevention module provides comprehensive tools to prevent common bugs and ensure data consistency:

- **Input Validation**: Validate all incoming data using Pydantic models
- **Output Validation**: Validate all outgoing data before sending to clients
- **Transaction Management**: Ensure atomic operations and data consistency
- **Idempotency Keys**: Prevent duplicate operations from retries
- **Request Deduplication**: Detect and prevent duplicate requests

### Module Location

All bug prevention functionality is in `hub.apps.core.bug_prevention`:

- `models.py`: Database models for idempotency and deduplication
- `validators.py`: Input/output validation utilities
- `services.py`: Services for idempotency and deduplication
- `transaction_utils.py`: Transaction management utilities

---

## Input Validation

### Overview

Input validation ensures all incoming data conforms to expected schemas before processing. This prevents:
- Invalid data causing errors
- Security vulnerabilities from malformed input
- Data corruption from unexpected formats

### Usage

**Basic Validation:**

```python
from hub.apps.core.bug_prevention.validators import InputValidator
from pydantic import BaseModel, Field

class CreateContractRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

# Validate input
result = InputValidator.validate(CreateContractRequest, request.data)
if not result.is_valid:
    return Response({"errors": result.errors}, status=400)

# Use validated data
contract_data = result.data
```

**Validation with Exception:**

```python
from hub.apps.core.bug_prevention.validators import InputValidator

# Raises DRFValidationError if invalid
validated_data = InputValidator.validate_and_raise(
    CreateContractRequest,
    request.data
)
```

**In DRF Views:**

```python
from rest_framework.views import APIView
from hub.apps.core.bug_prevention.validators import InputValidator

class ContractViewSet(APIView):
    def create(self, request):
        # Validate input
        validated_data = InputValidator.validate_and_raise(
            CreateContractRequest,
            request.data
        )
        
        # Use validated data
        contract = ContractService.create_contract(
            tenant_id=request.user.tenant_id,
            data=validated_data
        )
        
        return Response(contract, status=201)
```

### Validation Models

Create Pydantic models for all input schemas:

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class CreateAssetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    asset_type: str = Field(..., pattern="^(DATASET|API|FILE)$")
    domain: Optional[str] = None
    tags: List[str] = Field(default_factory=list, max_items=10)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return value.strip()
```

---

## Output Validation

### Overview

Output validation ensures all outgoing data conforms to expected schemas before sending to clients. This prevents:
- Inconsistent API responses
- Data leaks from unexpected fields
- Type mismatches in responses

### Usage

**Basic Validation:**

```python
from hub.apps.core.bug_prevention.validators import OutputValidator

class ContractResponse(BaseModel):
    id: str
    name: str
    status: str

# Validate output
result = OutputValidator.validate(ContractResponse, contract_data)
if not result.is_valid:
    logger.error("Output validation failed", errors=result.errors)
    # Handle error appropriately

# Use validated data
return Response(result.data, status=200)
```

**Validation and Serialization:**

```python
# Validates and returns serialized dict
serialized_data = OutputValidator.validate_and_serialize(
    ContractResponse,
    contract_data
)

return Response(serialized_data, status=200)
```

**In DRF Views:**

```python
class ContractViewSet(APIView):
    def retrieve(self, request, pk):
        contract = ContractService.get_contract(
            tenant_id=request.user.tenant_id,
            contract_id=pk
        )
        
        # Validate output
        serialized = OutputValidator.validate_and_serialize(
            ContractResponse,
            contract
        )
        
        return Response(serialized, status=200)
```

---

## Transaction Management

### Overview

Transaction management ensures atomic operations and data consistency. This prevents:
- Partial updates causing inconsistent state
- Race conditions in concurrent operations
- Data corruption from interrupted operations

### Usage

**Context Manager:**

```python
from hub.apps.core.bug_prevention.transaction_utils import transaction_atomic

def create_contract_with_assets(contract_data, assets_data):
    with transaction_atomic():
        # All operations succeed or all fail
        contract = Contract.objects.create(**contract_data)
        for asset_data in assets_data:
            Asset.objects.create(contract=contract, **asset_data)
        return contract
```

**Decorator:**

```python
from hub.apps.core.bug_prevention.transaction_utils import with_transaction

@with_transaction()
def create_contract_with_assets(contract_data, assets_data):
    contract = Contract.objects.create(**contract_data)
    for asset_data in assets_data:
        Asset.objects.create(contract=contract, **asset_data)
    return contract
```

**Transaction Manager (Complex Operations):**

```python
from hub.apps.core.bug_prevention.transaction_utils import TransactionManager

def complex_operation():
    manager = TransactionManager()
    
    with transaction.atomic():
        # Step 1: Create contract
        contract = Contract.objects.create(...)
        
        # Step 2: Create assets (can rollback independently)
        with manager.savepoint():
            assets = []
            for asset_data in assets_data:
                assets.append(Asset.objects.create(contract=contract, **asset_data))
        
        # Step 3: Create datasets (can rollback independently)
        with manager.savepoint():
            datasets = []
            for dataset_data in datasets_data:
                datasets.append(Dataset.objects.create(contract=contract, **dataset_data))
        
        return contract, assets, datasets
```

**Retry on Deadlock:**

```python
from hub.apps.core.bug_prevention.transaction_utils import retry_on_deadlock

@retry_on_deadlock(max_retries=3)
def update_contract_status(contract_id, new_status):
    # This will retry up to 3 times on deadlock
    contract = Contract.objects.get(id=contract_id)
    contract.status = new_status
    contract.save()
```

---

## Idempotency Keys

### Overview

Idempotency keys prevent duplicate operations from retries. This ensures:
- Safe retries on network failures
- No duplicate resource creation
- Consistent responses for same requests

### Usage

**In DRF Views:**

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from hub.apps.core.bug_prevention.services import (
    IdempotencyService,
    IdempotencyConflictError
)

class DQRunViewSet(APIView):
    def create(self, request):
        # Get idempotency key from header
        idempotency_key = request.headers.get("Idempotency-Key")
        
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header required"},
                status=400
            )
        
        tenant_id = str(request.user.tenant_id)
        method = request.method
        path = request.path
        body = request.data
        
        # Check idempotency
        try:
            record, cached_response = IdempotencyService.check_idempotency(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                method=method,
                path=path,
                body=body
            )
            
            # If cached response exists, return it
            if cached_response:
                return Response(
                    cached_response["data"],
                    status=cached_response["status_code"]
                )
            
            # Execute operation
            dq_run = DQService.create_run(
                tenant_id=tenant_id,
                dataset_id=body["dataset_id"]
            )
            
            # Store idempotency key
            IdempotencyService.store_idempotency(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                method=method,
                path=path,
                body=body,
                response_status=201,
                response_body={"id": str(dq_run.id), "status": dq_run.status}
            )
            
            return Response({"id": str(dq_run.id), "status": dq_run.status}, status=201)
            
        except IdempotencyConflictError as e:
            return Response(
                {"error": str(e.detail)},
                status=409
            )
```

**Idempotency Key Format:**

- Length: 8-256 characters
- Characters: Alphanumeric, hyphens, underscores, forward slashes
- Pattern: `^[a-zA-Z0-9\-_/]{8,256}$`

**Example Keys:**

```
dq-run-2025-01-15-abc123
contract/create/user-123
job-550e8400-e29b-41d4-a716-446655440000
```

**Cleanup:**

```python
# Clean up expired idempotency keys (run as background job)
deleted_count = IdempotencyService.cleanup_expired(older_than_hours=24)
```

---

## Request Deduplication

### Overview

Request deduplication detects and prevents duplicate requests within a time window. This prevents:
- Accidental duplicate submissions
- Race conditions from concurrent requests
- Unnecessary processing of duplicate requests

### Usage

**In DRF Views:**

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from hub.apps.core.bug_prevention.services import RequestDeduplicationService

class ContractViewSet(APIView):
    def create(self, request):
        tenant_id = str(request.user.tenant_id)
        method = request.method
        path = request.path
        body = request.data
        headers = {
            "Content-Type": request.headers.get("Content-Type", ""),
            "Accept": request.headers.get("Accept", "")
        }
        
        # Check for duplicate
        is_duplicate, record = RequestDeduplicationService.check_duplicate(
            tenant_id=tenant_id,
            method=method,
            path=path,
            body=body,
            headers=headers
        )
        
        if is_duplicate:
            return Response(
                {"error": "Duplicate request detected"},
                status=429  # Too Many Requests
            )
        
        # Store request fingerprint
        RequestDeduplicationService.store_request(
            tenant_id=tenant_id,
            method=method,
            path=path,
            body=body,
            headers=headers
        )
        
        # Process request
        contract = ContractService.create_contract(
            tenant_id=tenant_id,
            data=body
        )
        
        return Response({"id": str(contract.id)}, status=201)
```

**Deduplication Window:**

- Default: 5 minutes
- Configurable per request type
- Automatic cleanup of expired records

**Cleanup:**

```python
# Clean up expired deduplication records (run as background job)
deleted_count = RequestDeduplicationService.cleanup_expired(older_than_minutes=5)
```

---

## Best Practices

### 1. Input Validation

- **Validate all inputs**: Never trust user input
- **Use Pydantic models**: Create models for all input schemas
- **Validate early**: Validate as soon as data enters the system
- **Provide clear errors**: Return detailed validation error messages

### 2. Output Validation

- **Validate all outputs**: Ensure responses match schemas
- **Use Pydantic models**: Create models for all output schemas
- **Log validation failures**: Monitor for unexpected data issues
- **Fail safe**: Return error if output validation fails

### 3. Transaction Management

- **Use transactions for multi-step operations**: Ensure atomicity
- **Keep transactions short**: Don't hold locks for long periods
- **Handle deadlocks**: Use retry logic for deadlock scenarios
- **Use savepoints**: For complex operations with partial rollback

### 4. Idempotency Keys

- **Require for create operations**: All POST endpoints should support idempotency
- **Validate key format**: Ensure keys meet format requirements
- **Store responses**: Cache responses for idempotency key lookups
- **Clean up expired keys**: Run cleanup job regularly

### 5. Request Deduplication

- **Use for non-idempotent operations**: Prevent accidental duplicates
- **Set appropriate windows**: Balance between protection and usability
- **Clean up expired records**: Run cleanup job regularly
- **Monitor deduplication rate**: Track how often duplicates are detected

### 6. Error Handling

- **Handle validation errors gracefully**: Return clear error messages
- **Log all errors**: Monitor for patterns and issues
- **Don't expose internals**: Keep error messages user-friendly
- **Use appropriate status codes**: 400 for validation, 409 for conflicts

---

## Examples

### Complete Example: Create Contract with Validation and Idempotency

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from hub.apps.core.bug_prevention.validators import InputValidator, OutputValidator
from hub.apps.core.bug_prevention.services import IdempotencyService, IdempotencyConflictError
from hub.apps.core.bug_prevention.transaction_utils import transaction_atomic
from pydantic import BaseModel, Field

class CreateContractRequest(BaseModel):
    original_raw: str = Field(..., min_length=1)
    original_format: str = Field(..., pattern="^(JSON|YAML)$")

class ContractResponse(BaseModel):
    id: str
    status: str
    normalization_status: str

class ContractViewSet(APIView):
    def create(self, request):
        # Get idempotency key
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header required"},
                status=400
            )
        
        tenant_id = str(request.user.tenant_id)
        
        # Check idempotency
        try:
            record, cached_response = IdempotencyService.check_idempotency(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                method=request.method,
                path=request.path,
                body=request.data
            )
            
            if cached_response:
                return Response(
                    cached_response["data"],
                    status=cached_response["status_code"]
                )
        except IdempotencyConflictError as e:
            return Response(
                {"error": str(e.detail)},
                status=409
            )
        
        # Validate input
        try:
            validated_data = InputValidator.validate_and_raise(
                CreateContractRequest,
                request.data
            )
        except ValidationError as e:
            return Response(
                {"errors": e.detail},
                status=400
            )
        
        # Create contract in transaction
        try:
            with transaction_atomic():
                contract = ContractService.create_contract(
                    tenant_id=tenant_id,
                    data=validated_data
                )
                
                # Validate output
                serialized = OutputValidator.validate_and_serialize(
                    ContractResponse,
                    {
                        "id": str(contract.id),
                        "status": contract.status,
                        "normalization_status": contract.normalization_status
                    }
                )
                
                # Store idempotency key
                IdempotencyService.store_idempotency(
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    method=request.method,
                    path=request.path,
                    body=request.data,
                    response_status=201,
                    response_body=serialized
                )
                
                return Response(serialized, status=201)
                
        except Exception as e:
            logger.error("Contract creation failed", error=str(e))
            return Response(
                {"error": "Contract creation failed"},
                status=500
            )
```

---

## Summary

Bug prevention patterns ensure:

1. ✅ **Input Validation**: All incoming data is validated
2. ✅ **Output Validation**: All outgoing data is validated
3. ✅ **Transaction Management**: Operations are atomic and consistent
4. ✅ **Idempotency Keys**: Duplicate operations are prevented
5. ✅ **Request Deduplication**: Duplicate requests are detected

By following these patterns, we ensure:
- **Data Integrity**: Consistent and valid data
- **Reliability**: Operations are safe to retry
- **Security**: Invalid input is rejected
- **Performance**: Duplicate processing is avoided

