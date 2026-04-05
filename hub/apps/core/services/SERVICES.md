# Service Layer Architecture Documentation

## Overview

This document describes the service layer architecture implemented for the Data Interoperability Hub. The service layer extracts business logic from views to enable reuse, testability, and maintainability.

## Service Layer Principles

1. **Separation of Concerns**: Business logic is separated from HTTP request/response handling
2. **Reusability**: Services can be called from views, workflows, or other services
3. **Testability**: Services are easily unit testable without HTTP layer
4. **Consistency**: All services inherit from `BaseService` for consistent error handling, logging, and metrics
5. **Tenant Isolation**: All services enforce tenant isolation automatically

## Base Service

All services inherit from `BaseService` (`hub/apps/core/services/base.py`), which provides:

- **Error Handling**: Standardized error types (`ValidationError`, `NotFoundError`, `ConflictError`, etc.)
- **Logging**: Structured logging with tenant/user/request context
- **Metrics**: Automatic metrics recording for all operations
- **Transaction Management**: Helper methods for database transactions
- **Tenant Validation**: Automatic tenant existence and access validation

### Base Service Methods

- `execute_with_metrics()`: Execute operation with automatic metrics and logging
- `execute_with_transaction()`: Execute operation within a database transaction
- `get_resource_or_raise()`: Get resource by ID or raise `NotFoundError`
- `validate_tenant()`: Validate tenant exists and is active
- `get_tenant_or_raise()`: Get tenant or raise `NotFoundError`

## Service Catalog

### 1. ContractService (`hub/apps/contracts/services.py`)

**Purpose**: Contract management operations

**Methods**:
- `create_contract()`: Create a new contract using workflow orchestration
- `update_contract()`: Update contract with normalization
- `delete_contract()`: Soft delete contract (set status to RETIRED)
- `get_contract()`: Retrieve contract with caching and migration support
- `list_contracts()`: List contracts with filtering, sorting, and pagination
- `validate_contract()`: Validate contract using DataContract CLI (sync or async)

### 2. LineageService (`hub/apps/contracts/lineage_service.py`)

**Purpose**: Lineage operations

**Methods**:
- `get_contract_lineage()`: Get contract-level lineage
- `get_model_lineage()`: Get model-level lineage
- `get_field_lineage()`: Get field-level lineage
- `get_full_lineage()`: Get full hierarchical lineage
- `get_lineage_visualization()`: Get lineage visualization (JSON, DOT, Mermaid)
- `analyze_impact()`: Analyze impact of contract changes
- `notify_impact()`: Send notifications for impact analysis

### 3. NormalizationService (`hub/apps/contracts/normalization_service.py`)

**Purpose**: Contract normalization operations

**Methods**:
- `normalize_contract()`: Normalize contract from ODCS to HubContract format
- `validate_hubcontract()`: Validate HubContract schema

### 4. SearchService (`hub/apps/search/services.py`)

**Purpose**: Search operations

**Methods**:
- `search()`: Perform full-text search with filters and ranking

### 5. VersioningService (`hub/apps/datasets/versioning_service.py`)

**Purpose**: Dataset versioning operations

**Methods**:
- `create_version()`: Create a new dataset version
- `compare_versions()`: Compare two dataset versions
- `get_version_history()`: Get version history for a dataset

### 6. GovernanceService (`hub/apps/governance/services.py`)

**Purpose**: Governance operations

**Methods**:
- `create_access_request()`: Create an access request using workflow orchestration
- `approve_access_request()`: Approve an access request
- `reject_access_request()`: Reject an access request
- `get_access_request()`: Get access request by ID
- `list_access_requests()`: List access requests with filters

### 7. ObservabilityService (`hub/apps/observability/services.py`)

**Purpose**: Observability operations

**Methods**:
- `get_freshness_dashboard()`: Get data freshness dashboard
- `get_volume_dashboard()`: Get volume monitoring dashboard
- `get_schema_drift_dashboard()`: Get schema drift detection dashboard

### 8. IngestionService (`hub/apps/scheduled_ingestion/services.py`)

**Purpose**: Scheduled ingestion operations

**Methods**:
- `execute_ingestion()`: Execute a scheduled ingestion using workflow orchestration
- `get_ingestion_status()`: Get scheduled ingestion status

### 9. AssetService (`hub/apps/assets/services.py`)

**Purpose**: Asset management operations

**Methods**:
- `create_asset()`: Create a new asset
- `update_asset()`: Update asset with optimistic locking
- `delete_asset()`: Soft delete asset (set status to RETIRED)
- `get_asset()`: Get asset by ID

### 10. DatasetService (`hub/apps/datasets/services.py`)

**Purpose**: Dataset management operations

**Methods**:
- `create_dataset()`: Create a dataset from a file with schema inference
- `get_dataset()`: Get dataset by ID

### 11. MarketplaceService (`hub/apps/marketplace/services.py`)

**Purpose**: Marketplace operations

**Methods**:
- `create_listing()`: Create a marketplace listing
- `publish_listing()`: Publish a marketplace listing
- `create_order()`: Create a marketplace order
- `approve_order()`: Approve a marketplace order
- `reject_order()`: Reject a marketplace order
- `get_listing()`: Get listing by ID
- `get_order()`: Get order by ID

## Service-to-Service Communication

Services can call other services using the `ServiceClient` pattern (`hub/apps/core/services/communication.py`):

```python
from hub.apps.core.services.communication import ServiceClient
from hub.apps.contracts.services import ContractService

# In your service method
client = ServiceClient(
    calling_service=self,
    target_service_class=ContractService,
    tenant_id=tenant_id
)
contract = client.call('get_contract', contract_id=contract_id)
```

## Error Handling

All services use standardized error types:

- `ValidationError`: Client provided invalid input (HTTP 400)
- `NotFoundError`: Resource not found (HTTP 404)
- `ConflictError`: Resource conflict (HTTP 409)
- `PermissionError`: Permission denied (HTTP 403)
- `ServiceError`: Generic service error (HTTP 500)

## Usage Examples

### Example 1: Using ContractService in a View

```python
from hub.apps.contracts.services import ContractService

class ContractViewSet(viewsets.ModelViewSet):
    def create(self, request):
        service = ContractService(
            tenant_id=str(request.user.tenant.id),
            user_id=str(request.user.id)
        )
        try:
            contract = service.create_contract(
                original_raw=request.data['original_raw'],
                original_format=request.data['original_format'],
                tenant_id=str(request.user.tenant.id),
                user_id=str(request.user.id)
            )
            return Response(ContractSerializer(contract).data, status=201)
        except ValidationError as e:
            return Response({'error': e.message}, status=e.http_status)
```

### Example 2: Service-to-Service Communication

```python
from hub.apps.core.services.communication import ServiceClient
from hub.apps.contracts.services import ContractService

class AssetService(BaseService):
    def create_asset_with_contract(self, asset_data, contract_data):
        # Create asset
        asset = self.create_asset(**asset_data)
        
        # Create contract using ContractService
        contract_client = ServiceClient(
            calling_service=self,
            target_service_class=ContractService
        )
        contract = contract_client.call(
            'create_contract',
            original_raw=contract_data['original_raw'],
            original_format=contract_data['original_format'],
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            asset_id=str(asset.id)
        )
        
        return asset, contract
```

## Testing

All services have comprehensive unit tests in their respective `tests/test_services.py` files. Tests cover:

- Success scenarios
- Error scenarios (validation errors, not found, conflicts)
- Edge cases
- Service-to-service communication

## Migration from Views

To migrate view logic to services:

1. Identify business logic in views (not HTTP-specific code)
2. Extract to service methods
3. Update views to call services
4. Write unit tests for services
5. Update integration tests to verify view-service integration

## Future Enhancements

- Service caching layer
- Service rate limiting
- Service circuit breakers
- Service health checks
- Service versioning

