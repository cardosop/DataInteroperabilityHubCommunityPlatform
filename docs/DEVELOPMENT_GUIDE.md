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

# Start infrastructure services
docker compose up -d postgres redis minio fuseki

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

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

### Running Tests

```bash
# All tests
pytest

# Specific app
pytest hub/apps/contracts/tests/

# With coverage
pytest --cov=hub --cov-report=html
```

### Writing Tests

```python
import pytest
from hub.apps.contracts.services import ContractService

@pytest.mark.django_db
def test_create_contract():
    service = ContractService()
    contract = service.create_contract(
        tenant_id=tenant.id,
        user_id=user.id,
        contract_data={'name': 'Test'}
    )
    assert contract.name == 'Test'
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

## Related Documentation

- [Developer Onboarding](DEVELOPER_ONBOARDING.md) - Complete onboarding guide
- [Testing Guide](TESTING_GUIDE.md) - Testing strategies
- [Code Quality Standards](CODE_QUALITY_STANDARDS.md) - Quality guidelines
- [API Standards](API_STANDARDS.md) - API development standards

