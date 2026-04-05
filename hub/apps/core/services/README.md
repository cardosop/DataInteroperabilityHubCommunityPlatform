# Service Layer Architecture

## Overview

The service layer provides a clean abstraction between the API layer (views) and the data layer (models). All business logic should be implemented in service classes that inherit from `BaseService`.

## Base Service Class

The `BaseService` class provides common functionality for all services:

- **Error Handling**: Standardized error types and exception handling
- **Logging**: Structured logging with context (tenant_id, user_id, request_id)
- **Metrics**: Automatic metrics recording for operations
- **Transaction Management**: Database transaction support
- **Tenant Isolation**: Automatic tenant validation and filtering
- **Resource Validation**: Helper methods for resource retrieval and validation

## Service Interface Protocol

All services should follow this protocol:

1. **Inherit from BaseService**
2. **Set service_name class attribute**
3. **Use execute_with_metrics for all operations**
4. **Use execute_with_transaction for database operations**
5. **Raise ServiceError subclasses for errors**
6. **Validate tenant and resources before operations**

## Error Types

### ServiceError
Base exception for all service errors. Includes:
- `message`: Human-readable error message
- `code`: Error code for programmatic handling
- `details`: Additional error details
- `http_status`: HTTP status code for API responses

### ValidationError
Raised when client input is invalid (HTTP 400).

### NotFoundError
Raised when a resource is not found (HTTP 404).

### PermissionError
Raised when access is denied (HTTP 403).

### ConflictError
Raised when a resource conflict occurs (HTTP 409).

## Usage Examples

### Basic Service Implementation

```python
from hub.apps.core.services.base import BaseService, ValidationError, NotFoundError
from hub.apps.assets.models import Asset

class AssetService(BaseService):
    service_name = "asset_service"
    
    def create_asset(self, tenant_id: str, data: Dict[str, Any]) -> Asset:
        """Create a new asset."""
        return self.execute_with_transaction(
            operation="create_asset",
            tenant_id=tenant_id,
            func=lambda: self._create_asset_impl(tenant_id, data)
        )
    
    def _create_asset_impl(self, tenant_id: str, data: Dict[str, Any]) -> Asset:
        # Validate tenant
        self.validate_tenant(tenant_id)
        tenant = self.get_tenant_or_raise(tenant_id)
        
        # Validate required fields
        self.validate_required_fields(data, ["key", "name"])
        
        # Create asset
        asset = Asset.objects.create(
            tenant=tenant,
            key=data["key"],
            name=data["name"],
            status=AssetStatus.ACTIVE
        )
        
        return asset
    
    def get_asset(self, tenant_id: str, asset_id: str) -> Asset:
        """Get asset by ID."""
        return self.execute_with_metrics(
            operation="get_asset",
            tenant_id=tenant_id,
            func=lambda: self._get_asset_impl(tenant_id, asset_id)
        )
    
    def _get_asset_impl(self, tenant_id: str, asset_id: str) -> Asset:
        # Validate tenant
        self.validate_tenant(tenant_id)
        
        # Get asset with tenant isolation
        return self.get_resource_or_raise(
            Asset,
            asset_id,
            resource_type="Asset",
            tenant_id=tenant_id
        )
```

### Service Initialization

```python
# Initialize with context
service = AssetService(
    tenant_id="tenant-uuid",
    user_id="user-uuid",
    request_id="request-uuid"  # Optional, auto-generated if not provided
)

# Initialize without context (for background jobs)
service = AssetService()
```

### Operation Execution

#### With Metrics Only

```python
def get_resource(self, resource_id: str) -> Resource:
    return self.execute_with_metrics(
        operation="get_resource",
        func=lambda: self._get_resource_impl(resource_id)
    )
```

#### With Transaction

```python
def create_resource(self, data: Dict[str, Any]) -> Resource:
    return self.execute_with_transaction(
        operation="create_resource",
        func=lambda: self._create_resource_impl(data)
    )
```

#### With Tenant Override

```python
def get_resource(self, resource_id: str, tenant_id: str) -> Resource:
    return self.execute_with_metrics(
        operation="get_resource",
        tenant_id=tenant_id,  # Override service tenant_id
        func=lambda: self._get_resource_impl(resource_id, tenant_id)
    )
```

### Error Handling

```python
def update_asset(self, asset_id: str, data: Dict[str, Any]) -> Asset:
    def _update():
        asset = self.get_resource_or_raise(Asset, asset_id)
        
        # Validate business rules
        if "status" in data and data["status"] not in ["ACTIVE", "DRAFT"]:
            raise ValidationError(
                "Invalid status",
                details={"status": data["status"], "allowed": ["ACTIVE", "DRAFT"]}
            )
        
        # Check for conflicts
        if Asset.objects.filter(key=data.get("key")).exclude(id=asset_id).exists():
            raise ConflictError(
                f"Asset with key '{data['key']}' already exists",
                details={"key": data["key"]}
            )
        
        # Update asset
        for key, value in data.items():
            setattr(asset, key, value)
        asset.save()
        
        return asset
    
    return self.execute_with_transaction(
        operation="update_asset",
        func=_update
    )
```

### Tenant Validation

```python
def create_resource(self, tenant_id: str, data: Dict[str, Any]) -> Resource:
    # Validate tenant exists and is active
    self.validate_tenant(tenant_id)
    
    # Get tenant object
    tenant = self.get_tenant_or_raise(tenant_id)
    
    # Continue with operation...
```

### Resource Retrieval

```python
def get_resource(self, resource_id: str) -> Resource:
    # Get resource with automatic tenant isolation
    resource = self.get_resource_or_raise(
        ResourceModel,
        resource_id,
        resource_type="Resource",
        tenant_id=self.tenant_id  # Optional, uses service tenant_id if not provided
    )
    
    return resource
```

### Field Validation

```python
def create_resource(self, data: Dict[str, Any]) -> Resource:
    # Validate required fields
    self.validate_required_fields(
        data,
        ["field1", "field2", "field3"]
    )
    
    # Continue with operation...
```

## Best Practices

### 1. Service Method Naming

- Public methods: `create_resource`, `get_resource`, `update_resource`, `delete_resource`
- Private implementation methods: `_create_resource_impl`, `_get_resource_impl`

### 2. Error Handling

- Always use `ServiceError` subclasses
- Provide meaningful error messages
- Include relevant details in error details
- Let `execute_with_metrics` handle error transformation

### 3. Transaction Management

- Use `execute_with_transaction` for operations that modify data
- Keep transactions short-lived
- Don't include external API calls in transactions
- Use `transaction_context` for complex multi-step operations

### 4. Logging

- Use structured logging via `_logger`
- Include operation context (tenant_id, user_id, request_id)
- Log at appropriate levels:
  - `info`: Normal operations
  - `warning`: Recoverable issues
  - `error`: Failures with exception details

### 5. Metrics

- All operations are automatically instrumented
- Metrics include: operation count, duration, error count
- Labels: service, operation, tenant_id, error_code

### 6. Tenant Isolation

- Always validate tenant before operations
- Use `get_resource_or_raise` for automatic tenant filtering
- Never expose cross-tenant data

### 7. Resource Validation

- Use `get_resource_or_raise` for resource retrieval
- Provide resource_type for better error messages
- Use filters for additional validation

## Testing

Services should be tested using Django's TestCase:

```python
from django.test import TestCase
from hub.apps.core.services.base import ValidationError, NotFoundError
from hub.apps.core.services.asset_service import AssetService

class AssetServiceTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(...)
        self.service = AssetService(tenant_id=str(self.tenant.id))
    
    def test_create_asset_success(self):
        asset = self.service.create_asset(
            tenant_id=str(self.tenant.id),
            data={"key": "test", "name": "Test Asset"}
        )
        self.assertIsNotNone(asset.id)
    
    def test_create_asset_validation_error(self):
        with self.assertRaises(ValidationError):
            self.service.create_asset(
                tenant_id=str(self.tenant.id),
                data={}  # Missing required fields
            )
```

## Migration Guide

### Migrating from Views to Services

1. **Extract business logic from views**
   ```python
   # Before (in views.py)
   def create_asset(request):
       data = request.data
       asset = Asset.objects.create(...)
       return Response(...)
   
   # After (in service.py)
   class AssetService(BaseService):
       def create_asset(self, tenant_id: str, data: Dict) -> Asset:
           return self.execute_with_transaction(...)
   
   # In views.py
   def create_asset(request):
       service = AssetService(tenant_id=request.user.tenant_id)
       asset = service.create_asset(tenant_id, request.data)
       return Response(...)
   ```

2. **Replace direct model access**
   ```python
   # Before
   asset = Asset.objects.get(id=asset_id)
   
   # After
   asset = self.get_resource_or_raise(Asset, asset_id)
   ```

3. **Replace error handling**
   ```python
   # Before
   try:
       asset = Asset.objects.get(id=asset_id)
   except Asset.DoesNotExist:
       return Response({"error": "Not found"}, status=404)
   
   # After
   asset = self.get_resource_or_raise(Asset, asset_id)  # Raises NotFoundError
   ```

4. **Add metrics and logging**
   ```python
   # Before
   def create_asset(data):
       asset = Asset.objects.create(...)
       return asset
   
   # After
   def create_asset(self, tenant_id: str, data: Dict) -> Asset:
       return self.execute_with_metrics(
           operation="create_asset",
           func=lambda: self._create_asset_impl(tenant_id, data)
       )
   ```

## Service Registry

Services should be registered in `hub/apps/core/services/__init__.py`:

```python
from .base import BaseService, ServiceError, ValidationError, NotFoundError
from .asset_service import AssetService
from .dataset_service import DatasetService

__all__ = [
    'BaseService',
    'ServiceError',
    'ValidationError',
    'NotFoundError',
    'AssetService',
    'DatasetService',
]
```

## Performance Considerations

1. **Metrics Overhead**: Metrics recording has minimal overhead (~0.1ms per operation)
2. **Logging**: Structured logging is efficient, but avoid excessive logging in hot paths
3. **Transactions**: Keep transactions short to avoid lock contention
4. **Tenant Validation**: Tenant validation adds one database query per operation

## Security Considerations

1. **Tenant Isolation**: Always enforce tenant isolation via `get_resource_or_raise`
2. **Permission Checks**: Implement permission checks in service methods
3. **Input Validation**: Validate all inputs using `validate_required_fields`
4. **Error Messages**: Don't expose sensitive information in error messages

## Future Enhancements

- Service-to-service communication patterns
- Caching layer integration
- Event publishing for service operations
- Service health checks
- Circuit breaker pattern for external dependencies

