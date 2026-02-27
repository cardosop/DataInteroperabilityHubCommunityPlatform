# Development Guide

Complete guide for developing the Data Interoperability Hub.

## Development Environment Setup

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Git
- Make (optional)

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd DataInteroperabilityHub

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Option A: Run all services via Docker Compose (recommended)
docker compose -f docker-compose.dev.yml up -d

# Option B: Run only infrastructure (postgres, Redis instances, MinIO, Fuseki)
docker compose -f docker-compose.dev.yml up -d postgres redis-cache redis-queue redis-events redis-channels minio fuseki

# Run migrations (if not using full stack, or after first bring-up)
cd hub && python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

**Run all services (production-style compose):**

```bash
# Full stack: API, workers, frontend, gateways, Prefect, monitoring, etc.
docker compose up -d
```

See `docs/DOCKER_COMPOSE_DEPLOYMENT.md` for full deployment steps and service list.

### Production and staging security

For **production and staging**:

- **MUST set** `SECRET_KEY` and `JWT_SECRET_KEY` via environment (or a secret manager). Never use the development default values. Django fails startup with `ENVIRONMENT=production` if these are unset or equal the dev defaults.
- **Never commit** production or staging secrets; use a secret manager or env in CI/CD.
- **CORS**: Use explicit allowed origins only (not `*`). See `docs/SECURITY.md` for Django `CORS_ALLOWED_ORIGINS` and Traefik CORS.

Full requirements and validation: **`docs/SECURITY.md`**.

## Development Workflow

### Code Structure

```
hub/
├── apps/              # Django apps
│   ├── contracts/    # Contract management
│   ├── assets/        # Asset catalog
│   ├── datasets/      # Dataset management
│   └── ...
├── core/              # Core functionality
│   ├── services/      # Service layer
│   ├── events/        # Event system
│   └── ...
└── settings.py        # Django settings
```

### Creating New Features

1. **Create Django App** (if needed)
   ```bash
   python manage.py startapp myapp
   ```

2. **Create Models**
   ```python
   # hub/apps/myapp/models.py
   from django.db import models
   from hub.apps.core.models import BaseModel

   class MyModel(BaseModel):
       name = models.CharField(max_length=255)
   ```

3. **Create Migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Create Service Layer**
   ```python
   # hub/apps/myapp/services.py
   from hub.apps.core.services import BaseService

   class MyService(BaseService):
       def create_item(self, tenant_id, data):
           # Business logic here
           pass
   ```

5. **Create API Views**
   ```python
   # hub/apps/myapp/views.py
   from rest_framework import viewsets
   from hub.apps.myapp.serializers import MySerializer

   class MyViewSet(viewsets.ModelViewSet):
       serializer_class = MySerializer
       # View logic here
   ```

6. **Create Tests**
   ```python
   # hub/apps/myapp/tests.py
   import pytest

   @pytest.mark.django_db
   def test_create_item():
       # Test logic here
       pass
   ```

## Coding Standards

### Python Style

Follow PEP 8 and use:

- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .

# Type check
mypy .
```

### Django Best Practices

1. **Use Service Layer**: Business logic in services, not views
2. **Use Serializers**: Data validation in serializers
3. **Use Permissions**: Implement proper permissions
4. **Use Signals Sparingly**: Prefer explicit calls
5. **Use Migrations**: Never edit migrations manually

### Code Organization

```
app/
├── models.py          # Database models
├── serializers.py    # API serializers
├── services.py       # Business logic
├── views.py          # API views
├── urls.py           # URL routing
├── permissions.py    # Custom permissions
└── tests/            # Tests
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

## Service Layer Pattern

All business logic should be in service classes:

```python
from hub.apps.core.services import BaseService
from hub.apps.core.exceptions import ValidationError

class ContractService(BaseService):
    def create_contract(self, tenant_id, user_id, contract_data):
        # Validate tenant
        tenant = self.get_tenant_or_raise(tenant_id)

        # Validate data
        if not contract_data.get('name'):
            raise ValidationError('Contract name is required')

        # Create contract
        contract = Contract.objects.create(
            tenant=tenant,
            created_by_id=user_id,
            **contract_data
        )

        # Emit event
        self.emit_event('contract.created', contract.id)

        return contract
```

### Service Layer Consistency (Phase 24.7)

**CRITICAL**: All create/update/delete operations for domain resources MUST go through a service layer. Views use serializers for request validation only.

**Rule**: No direct `serializer.save()` in views for writes. All mutations go through service layer methods that:
- Apply business rules validation
- Emit audit events once per mutation
- Handle transaction boundaries
- Publish domain events

**Pattern**:
```python
# ✅ CORRECT: Use service layer
def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    service = MyService(tenant_id=tenant_id, user_id=str(request.user.id))
    resource = service.create_resource(
        tenant_id=tenant_id,
        user_id=str(request.user.id),
        **serializer.validated_data,
    )
    return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)

# ❌ WRONG: Direct serializer.save() bypasses business rules and audit
def create(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    resource = serializer.save()  # ❌ Bypasses service layer
    return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)
```

**Examples**:
- `ScheduledIngestionViewSet`: Uses `IngestionService.create_scheduled_ingestion()`, `IngestionService.update_scheduled_ingestion()`, and `IngestionService.delete_scheduled_ingestion()`
- `UserViewSet`: Uses `UserService.create_user()`, `UserService.update_user()`, and `UserService.delete_user()`
- `APIKeyViewSet`: Uses `APIKeyService.create_api_key()` and `APIKeyService.delete_api_key()`

**Note**: Serializers are still used for request validation and response serialization. The service layer handles the actual database mutations.

See `docs/BUSINESS_LOGIC_INTEGRATION.md` for complete service layer patterns and examples.

## Event-Driven Development

### Emitting Events

```python
from hub.apps.core.events import emit_event

emit_event('contract.created', contract_id=contract.id, data={...})
```

### Handling Events

```python
from hub.apps.core.events import event_handler

@event_handler('contract.created')
def handle_contract_created(event):
    contract_id = event.data['contract_id']
    # Handle event
    pass
```

## Testing

### Testing Principles

**CRITICAL: No Mocks/Stubs for Core Behavior**

This project follows a strict principle: **no mocks or stubs for core platform behavior**. Tests MUST use real implementations to ensure reliability and catch real issues.

#### Core Behavior That MUST NOT Be Mocked

The following core platform behaviors MUST use real implementations in tests:

1. **Tenant Resolution**
   - ✅ **MUST use**: `get_request_tenant_id()` and `get_request_tenant()` from `hub.apps.tenants.request_tenant`
   - ❌ **MUST NOT mock**: Tenant resolution logic, `request.tenant_id`, `user.tenant`, or tenant lookup
   - **Rationale**: Tenant isolation is critical for security; mocking can hide real isolation bugs

2. **Business Rules**
   - ✅ **MUST use**: Real `BusinessRules` classes (e.g., `AssetBusinessRules`, `ContractBusinessRules`)
   - ❌ **MUST NOT mock**: Business rule validation, permission checks, or business logic
   - **Rationale**: Business rules enforce critical constraints; mocking can allow invalid states

3. **Service Layer**
   - ✅ **MUST use**: Real service classes (e.g., `AssetService`, `ContractService`, `DatasetService`)
   - ❌ **MUST NOT mock**: Service layer methods, CRUD operations, or service-to-service communication within the platform
   - **Rationale**: Service layer contains core business logic; mocking can hide integration issues

4. **Database Operations**
   - ✅ **MUST use**: Real Django models, real database (via `@pytest.mark.django_db` or `TestCase`)
   - ❌ **MUST NOT mock**: Model methods, querysets, database queries, or ORM operations
   - **Rationale**: Database constraints and relationships must be tested; mocking can hide data integrity issues

5. **Authentication & Authorization**
   - ✅ **MUST use**: Real authentication (via `APIClient.force_authenticate()` or real tokens)
   - ❌ **MUST NOT mock**: User authentication, permission checks, or authorization logic
   - **Rationale**: Security is critical; mocking can hide authorization bugs

#### When Mocking Is Acceptable

Mocking is ONLY acceptable at **external process boundaries**:

1. **External HTTP Services** (when not running in test environment)
   - External DQ service HTTP calls (if service not available in test env)
   - External Compliance service HTTP calls (if service not available in test env)
   - External Semantic service HTTP calls (if service not available in test env)
   - **Note**: If services ARE available (via Docker Compose), use real services

2. **External Third-Party APIs**
   - Payment gateways
   - Email services
   - SMS services
   - External OAuth providers

3. **Time-Dependent Operations** (when testing time-sensitive logic)
   - `time.time()`, `datetime.now()` for testing expiration, scheduling
   - **Note**: Prefer using Django's `timezone.now()` with test fixtures when possible

4. **File System Operations** (when testing file handling)
   - External file storage (S3, GCS) if not available in test env
   - **Note**: Use MinIO or local file storage in test environment when possible

#### Example: Correct Test Pattern

```python
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from hub.apps.tenants.request_tenant import get_request_tenant_id
from hub.apps.assets.services import AssetService
from hub.apps.assets.models import Asset

@pytest.mark.django_db(transaction=True)
class AssetViewSetTest(TestCase):
    """Test AssetViewSet with real services (no mocks)."""

    def setUp(self):
        """Set up test fixtures with real DB."""
        self.client = APIClient()
        self.tenant1 = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
        )
        self.user1 = User.objects.create_user(
            email="user1@test.com",
            password="testpass123",
            tenant=self.tenant1,
        )
        self.client.force_authenticate(user=self.user1)

    def test_asset_list_follows_tenant_isolation(self):
        """Test that asset list respects tenant isolation."""
        # Create asset in tenant1 (real DB operation)
        asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key="test-asset",
            name="Test Asset",
            domain="test",
        )

        # Create asset in tenant2 (real DB operation)
        tenant2 = Tenant.objects.create(name="Tenant 2", slug="tenant-2")
        asset2 = Asset.objects.create(
            tenant=tenant2,
            key="test-asset-2",
            name="Test Asset 2",
            domain="test",
        )

        # Make API request (real request, real view, real service)
        response = self.client.get("/api/v1/assets/")

        # Verify tenant isolation (real queryset filtering)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [a["id"] for a in response.data.get("results", response.data)]
        self.assertIn(str(asset1.id), ids)
        self.assertNotIn(str(asset2.id), ids)

    def test_asset_create_uses_real_service(self):
        """Test asset creation uses real service layer."""
        # Make API request (real service will be called)
        response = self.client.post(
            "/api/v1/assets/",
            {
                "key": "new-asset",
                "name": "New Asset",
                "domain": "test",
            },
            format="json",
        )

        # Verify creation (real DB query)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        asset = Asset.objects.get(key="new-asset")
        self.assertEqual(asset.tenant_id, self.tenant1.id)

        # Verify tenant resolution used real helper (not mocked)
        # This is implicit - if mocked, tenant isolation would fail
```

#### Example: Incorrect Test Pattern (DO NOT DO THIS)

```python
# ❌ WRONG: Mocking tenant resolution
from unittest.mock import patch, Mock

@patch('hub.apps.tenants.request_tenant.get_request_tenant_id')
def test_asset_list(mock_get_tenant_id):
    mock_get_tenant_id.return_value = "fake-tenant-id"
    # This hides real tenant isolation bugs!

# ❌ WRONG: Mocking service layer
@patch('hub.apps.assets.services.AssetService.create_asset')
def test_asset_create(mock_create):
    mock_create.return_value = Mock(id="fake-id")
    # This hides real service logic bugs!

# ❌ WRONG: Mocking business rules
@patch('hub.apps.assets.business_rules.AssetBusinessRules.validate')
def test_asset_validation(mock_validate):
    mock_validate.return_value = True
    # This allows invalid data to pass!
```

#### Migration Strategy

For existing tests that use mocks:

1. **Identify mocked core behavior**: Find tests mocking tenant resolution, business rules, or services
2. **Replace with real implementations**: Use real DB, real services, real business rules
3. **Fix root causes**: If tests fail after removing mocks, fix the underlying issues (don't add more mocks)
4. **Verify isolation**: Ensure tests are properly isolated using Django's test framework

**Reference Implementations**:
- ✅ **Scheduled Ingestion Tests** (`hub/apps/scheduled_ingestion/tests/`): Already follow no-mock principle (Phase 3-4, 7)
- ✅ **Tenant Isolation Tests** (`tests/integration/test_tenant_isolation.py`): Use real DB and real tenant resolution
- ✅ **Phase 10 Tests**: All use real `get_request_tenant_id()` helper without mocks

### Exception Handling (Phase 24.1)

**CRITICAL: Specific Exception Types, Structured Logging, No Bare Except/Pass**

All exception handling MUST follow these rules:

1. **Use Specific Exception Types**
   - ✅ **CORRECT**: `except ValueError as e:`, `except ConnectionError as e:`, `except ValidationError as e:`
   - ❌ **WRONG**: `except Exception as e:` (too broad, hides specific failure modes)
   - ❌ **WRONG**: `except:` (bare except, catches everything including SystemExit/KeyboardInterrupt)
   - **Rationale**: Specific exceptions allow proper error handling and root cause identification

2. **Structured Logging**
   - ✅ **CORRECT**: Log with context using `logger.warning()` or `logger.exception()` with `extra={}` dict
   - ✅ **CORRECT**: Include `error_type`, `error`, and relevant context in `extra` dict
   - ❌ **WRONG**: `logger.warning(f"Error: {e}")` (string formatting loses context)
   - ❌ **WRONG**: No logging for unexpected errors

3. **Error Response or Re-raise**
   - ✅ **CORRECT**: Return structured error response using `api_error_response()` helper
   - ✅ **CORRECT**: Re-raise exceptions that should propagate (e.g., `ValidationError`)
   - ❌ **WRONG**: `except ...: pass` (hides failures silently)
   - ❌ **WRONG**: Generic error responses without context

4. **Non-Critical Operations**
   - For cache invalidation, metrics, optional features: Catch specific exceptions (`ConnectionError`, `TimeoutError`, `RuntimeError`) and log with context
   - Never use bare `except:` or `except Exception: pass` - always log with context

#### Example: Correct Exception Handling

```python
# ✅ CORRECT: Specific exception types, structured logging
try:
    invalidate_cache()
except (ConnectionError, TimeoutError, RuntimeError) as e:
    logger.warning(
        "Failed to invalidate cache",
        extra={"error": str(e), "error_type": type(e).__name__},
        exc_info=True,
    )
except Exception as e:
    # Unexpected error - log with full context
    logger.exception(
        "Unexpected error invalidating cache",
        extra={"error_type": type(e).__name__},
    )

# ✅ CORRECT: Service layer exception handling
try:
    result = service.create_resource(...)
except ValidationError as e:
    return handle_service_exception(e)  # Uses api_error_response internally
except NotFoundError as e:
    return handle_service_exception(e)
except Exception as e:
    logger.exception(
        "Unexpected error creating resource",
        extra={"error_type": type(e).__name__},
    )
    return api_error_response(
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
    )
```

#### Example: Incorrect Exception Handling (DO NOT DO THIS)

```python
# ❌ WRONG: Bare except or too broad
try:
    process_data()
except:  # Catches SystemExit, KeyboardInterrupt, everything
    pass

# ❌ WRONG: Generic Exception without logging
try:
    invalidate_cache()
except Exception:
    pass  # Hides failures silently

# ❌ WRONG: No structured logging
try:
    result = service.create_resource(...)
except Exception as e:
    logger.warning(f"Error: {e}")  # No context, no error_type
    return Response({"error": str(e)}, status=500)  # Inconsistent format
```

### Audit Event Rule (Phase 12.4)

**CRITICAL: Exactly One Audit Event Per Mutation**

Every create/update/delete operation on a domain resource MUST emit exactly one audit event. This ensures audit trail completeness and prevents duplicate logging.

#### Audit Event Requirements

1. **Service Layer Preference**
   - ✅ **PREFERRED**: Emit audit events in the service layer (`create_*`, `update_*`, `delete_*` methods)
   - ❌ **AVOID**: Emitting audit events in views when service layer already emits them
   - **Rationale**: Service layer is the single source of truth for business logic; audit events belong with the mutation

2. **One Event Per Mutation**
   - ✅ **CORRECT**: Service method emits exactly one audit event after successful persistence
   - ❌ **WRONG**: Both view and service emit audit events for the same mutation
   - ❌ **WRONG**: Multiple audit events for a single create/update/delete operation

3. **Audit Event Location**
   - **Service Layer**: All `create_*`, `update_*`, `delete_*` methods in services MUST emit audit events
   - **View Layer**: Views should NOT emit audit events if the service layer already does
   - **Exception**: `destroy()` operations may emit audit events in views if no service method exists (legacy pattern)

#### Example: Correct Audit Pattern

```python
# ✅ CORRECT: Service emits audit event
class RetentionService(BaseService):
    @transaction.atomic
    def create_retention_policy(self, tenant_id: str, user_id: str, *args, **kwargs):
        # ... validation and business rules ...

        # Create policy
        policy = RetentionPolicy.objects.create(**kwargs)

        # Emit exactly one audit event (Phase 12.4.1)
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            actor_user=user,
            tenant=tenant,
            resource_id=str(policy.id),
            details={...},
        )

        return policy

# ✅ CORRECT: View calls service (no audit event in view)
class RetentionPolicyViewSet(viewsets.ModelViewSet):
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Service handles validation, persistence, and audit
        service = GovernanceService(...)
        policy = service.create_retention_policy(...)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

#### Example: Incorrect Audit Pattern (DO NOT DO THIS)

```python
# ❌ WRONG: Both view and service emit audit events
class RetentionPolicyViewSet(viewsets.ModelViewSet):
    def create(self, request):
        # ... validation ...

        policy = serializer.save(...)

        # ❌ DUPLICATE: Service will also emit audit event
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            tenant_id=request.tenant_id,
            resource_id=str(policy.id),
        )

        return Response(serializer.data)

# Service also emits audit event (duplicate!)
class RetentionService(BaseService):
    def create_retention_policy(self, *args, **kwargs):
        policy = RetentionPolicy.objects.create(**kwargs)
        create_audit_event(resource_type="RETENTION_POLICY", action="CREATED", **kwargs)  # ❌ DUPLICATE
        return policy
```

#### Migration Strategy

For existing code with duplicate audit events:

1. **Identify duplicates**: Search for `create_audit_event` calls in both views and services for the same resource type
2. **Remove view-layer audit**: Remove audit event calls from views when service layer already emits them
3. **Verify service-layer audit**: Ensure service layer methods emit audit events for all mutations
4. **Test**: Verify exactly one audit event is created per mutation

#### Verified Implementations (Phase 12)

- ✅ **Retention Policies** (`hub/apps/governance/services.py`): `create_retention_policy()`, `update_retention_policy()` emit audit events; views do not
- ✅ **Webhooks** (`hub/apps/webhooks/webhook_service.py`): `create_webhook()`, `update_webhook()` emit audit events; views do not
- ✅ **Social Features** (`hub/apps/social/services.py`): `create_review()`, `create_comment()`, `create_community_member()` emit audit events; views do not

#### Contracts and Assets (Phase 12.5)

**Primary Mutations**:
- ✅ **Contracts**: `ContractService.create_contract()` and `ODPSService.create_odps()` emit audit events in service layer
- ✅ **Assets**: `AssetService.create_asset()` and `AssetService.update_asset()` are used by views; views emit audit events for primary create/update operations

**Intentional Direct Saves** (Side Effects):
- **Contract Validation Status Updates** (`hub/apps/contracts/views.py`): Direct `.save()` calls for validation status updates are intentional side effects; these emit separate audit events for validation operations
- **Asset Relationship Updates** (`hub/apps/assets/views.py`): Direct `.save()` calls for attaching contracts to assets, updating dataset versions, etc. are intentional relationship updates; these emit separate audit events for relationship operations

**Note**: These direct saves are acceptable as they represent side effects (validation status, relationships) rather than primary mutations. Primary mutations (create/update/delete) go through services with audit events.

### Running Tests

Test environment variables (e.g. `PYTEST_DOCKER_COMPOSE_RUNTIME`, `DATE`, `COMPOSE_FILE`, `API_SERVICE_NAME`) and coverage paths are documented in [TEST_EXECUTION_PLAN.md — Environment Configuration](TEST_EXECUTION_PLAN.md#environment-configuration).

```bash
# All tests
pytest

# Specific app
pytest hub/apps/contracts/tests/

# With coverage
pytest --cov=hub --cov-report=html

# Integration tests (use real services)
pytest tests/integration/ -v

# E2E tests (use real Docker Compose services)
pytest tests/e2e/ -v
```

### Running Tests with Visible Output

For local development and debugging, use verbose output and detailed tracebacks:

```bash
# Verbose output with short traceback (recommended for local development)
pytest -v --tb=short

# Verbose output with all test outcomes (shows passed, failed, skipped, etc.)
pytest -v --tb=short -rA

# Run specific test file with verbose output
pytest -v --tb=short tests/integration/test_scheduled_export_apis_comprehensive.py

# Run with markers for filtered execution
pytest -v -m e2e                    # Run only E2E tests
pytest -v -m integration           # Run only integration tests
pytest -v -m regression             # Run only regression tests
pytest -v -m security               # Run only security tests
pytest -v -m performance            # Run only performance tests
pytest -v -m scheduled_export       # Run only scheduled export tests
pytest -v -m saas_platform          # Run only SaaS platform tests
pytest -v -m cli_sdk                # Run only CLI/SDK tests
```

**Available Markers** (defined in `pytest.ini`):
- `e2e`: End-to-end tests
- `integration`: Integration tests (require services to be running)
- `regression`: Regression tests
- `security`: Security-related tests
- `performance`: Performance tests (can be skipped for faster runs)
- `scheduled_export`: Scheduled export feature tests
- `saas_platform`: SaaS platform feature tests
- `cli_sdk`: CLI and SDK tests
- `unit`: Unit tests
- `slow`: Slow running tests

**Note**: CI continues to use default output (`--tb=short`) and parallel execution where appropriate. Verbose output is for local follow-along only.

### Writing Tests

```python
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from hub.apps.contracts.services import ContractService
from hub.apps.contracts.models import Contract

@pytest.mark.django_db(transaction=True)
class ContractServiceTest(TestCase):
    """Test ContractService with real DB and real services."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test", slug="test")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant
        )
        self.service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_create_contract(self):
        """Test contract creation with real service."""
        contract = self.service.create_contract({
            'name': 'Test Contract',
            'original_format': 'JSON',
            'original_spec_type': 'ODCS',
            'original_spec_version': '1.0',
            'original_raw': '{}'
        })
        assert contract.name == 'Test Contract'
        assert contract.tenant_id == self.tenant.id

        # Verify in real DB
        db_contract = Contract.objects.get(id=contract.id)
        assert db_contract.name == 'Test Contract'
```

## Database Migrations

### Creating Migrations

```bash
# Create migration
python manage.py makemigrations

# Apply migration
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

### Migration Best Practices

1. **Never edit existing migrations**: Create new ones
2. **Test migrations**: Test both forward and backward
3. **Use data migrations**: For data transformations
4. **Keep migrations small**: One logical change per migration

## API Development

### Creating API Endpoints

```python
from rest_framework import viewsets
from rest_framework.decorators import action
from hub.apps.api.standards import StandardResponseMixin

class ContractViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        contract = self.get_object()
        result = validate_contract(contract)
        return self.standard_response(data=result)
```

### API Standards

Follow API standards:
- [API Standards](API_STANDARDS.md) - Response formats, pagination, etc.
- [API Error Codes](API_ERROR_CODES.md) - Error handling

## Rate Limiting (Phase 13)

### Single Rate Limiting Implementation

**CRITICAL**: The platform uses a **single rate limiting implementation** via `hub.apps.rate_limiting.middleware.RateLimitMiddleware`. This middleware is configured in `hub/settings.py` MIDDLEWARE and applies globally to all `/api/v1/` endpoints.

**Deprecated Middleware**: `hub.apps.api.middleware.RateLimitMiddleware` is deprecated and should not be used. It is not included in MIDDLEWARE settings and will be removed in a future version.

### Platform Rate Limiting

**Middleware**: `hub.apps.rate_limiting.middleware.RateLimitMiddleware`
- Applied globally to all `/api/v1/` endpoints
- Uses sliding window algorithm with Redis
- Supports multiple time windows (BURST, SUSTAINED, DAILY)
- Enforces limits at tenant, user, and API key levels
- Automatically adds rate limit headers to responses

**Service Layer**: `hub.apps.rate_limiting.service.check_rate_limit()`
- Used for in-view rate limit checks (stricter per-action limits)
- Used by mesh, virtualization, and integrations views for additional rate limiting
- Returns `(allowed: bool, results: List[RateLimitResult])`
- Headers can be retrieved via `get_rate_limit_headers(request, results)`

**Example: In-View Rate Limit Check**:
```python
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers
from rest_framework.exceptions import Throttled

@action(detail=True, methods=["post"])
def expensive_operation(self, request, id=None):
    # Check rate limit before expensive operation
    allowed, rate_limit_results = check_rate_limit(request)
    if not allowed:
        headers = get_rate_limit_headers(request, rate_limit_results)
        raise Throttled(headers=headers)

    # Perform expensive operation
    result = perform_expensive_operation()

    # Get rate limit headers for response
    _, rate_limit_results = check_rate_limit(request)
    headers = get_rate_limit_headers(request, rate_limit_results)

    return Response(result, headers=headers)
```

**When to Use In-View Checks**:
- **Stricter per-action limits**: When an endpoint needs stricter limits than the middleware provides (e.g., expensive operations like query execution, compliance checks)
- **Per-resource limits**: When rate limiting needs to be per-resource (e.g., per virtual dataset, per domain)
- **Custom rate limit categories**: When an endpoint needs a different category than auto-detected

**When NOT to Use In-View Checks**:
- **General API endpoints**: Middleware handles these automatically
- **Standard CRUD operations**: Middleware provides sufficient protection
- **Read-only endpoints**: Middleware limits are typically sufficient

**Current Usage**:
- **Mesh** (`hub/apps/mesh/views.py`): Uses in-view checks for compliance checks and topology operations (stricter limits for expensive operations)
- **Virtualization** (`hub/apps/virtualization/views.py`): Uses in-view checks for query execution and topology operations (stricter limits for expensive operations)
- **Integrations** (`hub/apps/integrations/views.py`): Uses in-view checks for marketplace sync operations (stricter limits for expensive operations)

### ODPS Ref-Resolver Rate Limiting

**Separate Implementation**: ODPS $ref resolution uses a **separate rate limiting system** (`hub.apps.contracts.odps_rate_limiting`) with specialized limits:

- **Per-tenant**: 100 requests per hour
- **Per-user**: 50 requests per hour
- **Global**: 1000 requests per hour

**Rationale for Separation**:
1. **Different use case**: ODPS $ref resolution involves external HTTP requests and caching, requiring different limits than general API endpoints
2. **Specialized limits**: Lower limits (100/tenant/hour vs 600/tenant/minute for general API) to prevent abuse of external resource fetching
3. **Different error handling**: Uses `ODPSRefResolutionError` with specialized retry-after logic
4. **Separate metrics**: Tracks `odps_rate_limit_violations_total` separately from platform rate limiting metrics

**Usage**: ODPS ref-resolver (`hub/apps/contracts/ref_resolver.py`) calls `check_rate_limit()` from `odps_rate_limiting` module before resolving external $refs.

**Documentation**: See `hub/apps/contracts/docs/ODPS_RATE_LIMITING_DESIGN.md` for detailed design rationale and `hub/apps/contracts/odps_rate_limiting.py` for implementation details.

## Debugging

### Django Debug Toolbar

```python
# settings.py (development only)
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

### Logging

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info('Contract created', contract_id=contract.id, tenant_id=tenant.id)
```

### Debugging in Docker

```bash
# View logs
docker compose logs -f api-service

# Access shell
docker compose exec api-service python manage.py shell

# Access database
docker compose exec postgres psql -U hub -d hub
```

## Code Quality

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

### Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] No hardcoded values
- [ ] Error handling implemented
- [ ] Logging added where appropriate
- [ ] Security considerations addressed

## Git Workflow

### Branch Naming

- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates

### Commit Messages

```
feat: Add contract validation endpoint

- Implement contract validation logic
- Add validation tests
- Update API documentation
```

### Pull Request Process

1. Create feature branch
2. Make changes
3. Write tests
4. Update documentation
5. Create pull request
6. Address review comments
7. Merge after approval

## BaaS Platform Development

### Development Setup

The BaaS Platform is integrated into the main Django application (`hub/apps/baas/`).

**Key Components**:
- `hub/apps/baas/models.py` - APIKey, APIUsage, APITier models
- `hub/apps/baas/services.py` - UsageTrackingService
- `hub/apps/baas/developer_portal.py` - APIKeyViewSet, DeveloperDocumentationViewSet
- `hub/apps/baas/business_rules.py` - BaaSBusinessRules
- `services/api-gateway/` - API Gateway service for rate limiting

**Setup Steps**:
```bash
# BaaS models are included in main migrations
python manage.py migrate

# Create test API keys
python manage.py shell
>>> from hub.apps.baas.models import APIKey, APITier
>>> tier = APITier.objects.get(name='FREE')
>>> api_key = APIKey.objects.create(name='Test Key', tier=tier, tenant_id='...')
```

### Testing Patterns

**Unit Tests**:
```python
# hub/apps/baas/tests/test_services.py
from hub.apps.baas.services import UsageTrackingService

def test_track_request():
    service = UsageTrackingService()
    usage = service.track_request(
        api_key_id='...',
        endpoint='/api/v1/assets/',
        method='GET',
        status_code=200,
        response_time_ms=100
    )
    assert usage.total_requests == 1
```

**Integration Tests**:
```python
# hub/apps/baas/tests/test_views.py
def test_create_api_key(client):
    response = client.post('/api/v1/baas/api-keys/', {
        'name': 'Test Key',
        'tier': 'FREE'
    })
    assert response.status_code == 201
    assert 'api_key' in response.json()
```

### Debugging Tips

**API Gateway Issues**:
- Check rate limiting logs: `docker logs api-gateway`
- Verify tier configuration: `APITier.objects.all()`
- Check usage tracking: `APIUsage.objects.filter(api_key_id='...')`

**Usage Tracking Issues**:
- Verify UsageTrackingService is called on each request
- Check Redis cache for usage counters
- Review PostgreSQL APIUsage table for historical data

### Code Examples

**Creating API Key Programmatically**:
```python
from hub.apps.baas.models import APIKey, APITier
from hub.apps.baas.services import UsageTrackingService

tier = APITier.objects.get(name='FREE')
api_key = APIKey.objects.create(
    name='My API Key',
    tier=tier,
    tenant_id=tenant_id
)
# API key value is generated and hashed
```

**Tracking API Usage**:
```python
from hub.apps.baas.services import UsageTrackingService

service = UsageTrackingService(tenant_id=tenant_id)
usage = service.track_request(
    api_key_id=api_key.id,
    endpoint='/api/v1/assets/',
    method='GET',
    status_code=200,
    response_time_ms=150
)
```

**Integration Patterns**:
- Use `BaaSBusinessRules` for tier validation
- Implement `BaaSEventPublisher` for event-driven coordination
- Use `UsageTrackingService` for all API request tracking

## ODH Integration Development

### Development Setup

The ODH Integration is integrated into the main Django application (`hub/apps/ml/`).

**Key Components**:
- `hub/apps/ml/models.py` - MLModel, TrainingJob, InferenceDeployment models
- `hub/apps/ml/services.py` - ModelRegistryBridgeService
- `hub/apps/ml/inference_service.py` - InferenceValidationService
- `hub/apps/ml/business_rules.py` - ODHIntegrationBusinessRules
- `services/odh-integration/` - ODH client services

**Setup Steps**:
```bash
# ML models are included in main migrations
python manage.py migrate

# ODH integration clients (optional, for local testing)
cd services/odh-integration
pip install -r requirements.txt
```

### Testing Patterns

**Unit Tests**:
```python
# hub/apps/ml/tests/test_services.py
from hub.apps.ml.services import ModelRegistryBridgeService

def test_link_model_to_asset():
    service = ModelRegistryBridgeService()
    model = service.link_model_to_asset(
        odh_model_id='my-model-123',
        odh_model_version='1.0.0',
        asset_id='...',
        model_type='CLASSIFICATION'
    )
    assert model.odh_model_id == 'my-model-123'
```

**Integration Tests**:
```python
# hub/apps/ml/tests/test_views.py
def test_create_model(client):
    response = client.post('/api/v1/ml/models/', {
        'odh_model_id': 'my-model-123',
        'odh_model_version': '1.0.0',
        'model_type': 'CLASSIFICATION',
        'asset_id': '...'
    })
    assert response.status_code == 201
```

**ODH Client Mocking**:
```python
# For testing without ODH services
from unittest.mock import Mock, patch

@patch('hub.apps.ml.services.ODHModelRegistryClient')
def test_model_sync(mock_client):
    mock_client.return_value.get_model.return_value = {
        'id': 'my-model-123',
        'version': '1.0.0'
    }
    # Test model sync logic
```

### Debugging Tips

**ODH Connection Issues**:
- Check ODH service availability: `curl http://odh-service:8080/health`
- Verify ODH client configuration: `ODH_CLIENT_URL` environment variable
- Review ODH client logs: `services/odh-integration/logs/`

**Training Job Issues**:
- Check training job status: `TrainingJob.objects.get(id='...')`
- Review ODH Training Operator logs
- Verify dataset accessibility before training

**Inference Issues**:
- Check inference deployment status: `InferenceDeployment.objects.get(id='...')`
- Verify input/output contract validation
- Review inference metrics: `GET /api/v1/ml/inference/deployments/{id}/metrics/`

### Code Examples

**Creating ML Model**:
```python
from hub.apps.ml.models import MLModel, ModelType, ModelStatus

model = MLModel.objects.create(
    odh_model_id='my-model-123',
    odh_model_version='1.0.0',
    model_type=ModelType.CLASSIFICATION,
    status=ModelStatus.TRAINING,
    asset_id=asset_id,
    tenant_id=tenant_id
)
```

**Submitting Training Job**:
```python
from hub.apps.ml.services import ModelRegistryBridgeService
from hub.apps.orchestration.workflows.model_training import ModelTrainingWorkflow

service = ModelRegistryBridgeService()
workflow = ModelTrainingWorkflow()
job = workflow.execute(
    model_id=model.id,
    dataset_id=dataset_id,
    config={'epochs': 100, 'batch_size': 32}
)
```

**Running Inference**:
```python
from hub.apps.ml.inference_service import InferenceValidationService

service = InferenceValidationService()
prediction = service.predict(
    model_id=model.id,
    input_data={'feature1': 0.5, 'feature2': 0.8}
)
```

**Integration Patterns**:
- Use `ODHIntegrationBusinessRules` for validation
- Implement `MLEventPublisher` for event-driven coordination
- Use `ModelTrainingWorkflow` for orchestrated training
- Use `InferenceValidationService` for contract validation

## Related Documentation

- [Developer Onboarding](DEVELOPER_ONBOARDING.md) - Complete onboarding guide
- [Testing Guide](TESTING_GUIDE.md) - Testing strategies
- [Code Quality Standards](CODE_QUALITY_STANDARDS.md) - Quality guidelines
- [API Standards](API_STANDARDS.md) - API development standards
- [BaaS Platform CLI Usage Guide](../cli/docs/BAAS_USAGE.md) - BaaS CLI commands
- [BaaS Platform SDK Usage Guide](../sdk/python/docs/BAAS_USAGE.md) - BaaS SDK APIs
- [ODH Integration CLI Usage Guide](../cli/docs/ODH_USAGE.md) - ODH CLI commands
- [ODH Integration SDK Usage Guide](../sdk/python/docs/ODH_USAGE.md) - ODH SDK APIs

