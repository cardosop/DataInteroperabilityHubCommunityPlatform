# Developer Onboarding Guide

Complete guide for new developers joining the Interoperable Data Hub project.

## Table of Contents

1. [Welcome](#welcome)
2. [Prerequisites](#prerequisites)
3. [Initial Setup](#initial-setup)
4. [Development Workflow](#development-workflow)
5. [Project Structure](#project-structure)
6. [Coding Standards](#coding-standards)
7. [Testing](#testing)
8. [Common Tasks](#common-tasks)
9. [Resources](#resources)

---

## Welcome

Welcome to the Interoperable Data Hub development team! This guide will help you get started with the project.

**What is the Interoperable Data Hub?**

The Interoperable Data Hub is a platform for managing data assets, contracts, compliance, and marketplace operations. It provides:

- Data asset catalog management
- Data contract validation and migration
- Compliance scanning and risk assessment
- Data quality checks
- Semantic mapping and RDF storage
- Marketplace for data sharing

**Tech Stack:**

- **Backend**: Django (Python 3.11+)
- **Microservices**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16
- **Cache/Queue**: Redis 7
- **Storage**: MinIO/S3
- **Triple Store**: Apache Jena Fuseki
- **Frontend**: (Future - React/TypeScript)

---

## Prerequisites

### Required Software

- **Python 3.11+**: [Download](https://www.python.org/downloads/)
- **Docker & Docker Compose**: [Install Docker](https://docs.docker.com/get-docker/)
- **Git**: [Install Git](https://git-scm.com/downloads)
- **Code Editor**: VS Code, PyCharm, or your preferred editor

### Recommended Tools

- **Make**: For convenience commands
- **PostgreSQL Client**: For database operations
- **Redis CLI**: For queue inspection
- **HTTP Client**: Postman, Insomnia, or curl

### Verify Installation

```bash
python3 --version  # Should be 3.11+
docker --version
docker compose version
git --version
```

---

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/datainteroperabilityhub.git
cd datainteroperabilityhub
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Set Up Docker Services

```bash
# Start infrastructure services
docker compose up -d postgres redis minio fuseki

# Wait for services to be ready
docker compose ps
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your local settings
# At minimum, set:
# - DATABASE_URL
# - REDIS_URL
# - SECRET_KEY
```

### 5. Set Up Database

```bash
# Run migrations
python hub/manage.py migrate

# Create superuser (optional)
python hub/manage.py createsuperuser
```

### 6. Start Development Server

```bash
# Terminal 1: Django API server
python hub/manage.py runserver

# Terminal 2: Worker service
python hub/manage.py rqworker default

# Terminal 3: Microservices (if developing them)
docker compose up datacontract-service compliance-service dq-service semantic-service
```

### 7. Verify Setup

```bash
# Check API health
curl http://localhost:8000/health/

# Check API documentation
open http://localhost:8000/api-docs/
```

---

## Development Workflow

### Git Workflow

We use **GitHub Flow**:

1. **Create feature branch** from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes** and commit:
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

3. **Push and create PR**:
   ```bash
   git push origin feature/my-feature
   # Create PR on GitHub
   ```

4. **Review and merge** after CI passes

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance

**Examples:**
```
feat(assets): add asset activation endpoint
fix(contracts): resolve validation error for empty contracts
docs(api): update API documentation
```

### Code Review Process

1. **Create PR** with clear description
2. **Wait for CI** to pass
3. **Request review** from team
4. **Address feedback** and update PR
5. **Merge** after approval

---

## Project Structure

```
datainteroperabilityhub/
├── hub/                    # Django application
│   ├── apps/              # Django apps
│   │   ├── assets/        # Asset catalog
│   │   ├── contracts/     # Contract management
│   │   ├── datasets/      # Dataset management
│   │   ├── semantic/      # Semantic layer
│   │   └── ...
│   ├── settings.py        # Django settings
│   └── urls.py            # URL configuration
├── services/              # Microservices
│   ├── api/              # Django API service
│   ├── datacontract-service/
│   ├── compliance-service/
│   ├── dq-service/
│   └── semantic-service/
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/       # Integration tests
│   └── e2e/              # End-to-end tests
├── sdk/                   # SDKs
│   ├── python/           # Python SDK
│   └── js/               # JavaScript SDK
├── docs/                  # Documentation
├── runbooks/             # Operational runbooks
└── docker-compose.yml     # Docker Compose config
```

### Key Directories

- **`hub/apps/`**: Django applications (models, views, serializers)
- **`services/`**: Microservices (FastAPI)
- **`tests/`**: Test suite
- **`docs/`**: Documentation
- **`runbooks/`**: Operational procedures

---

## Coding Standards

### Python Style Guide

We follow **PEP 8** with some modifications:

- **Line length**: 100 characters (not 79)
- **Import order**: Standard library, third-party, local
- **Type hints**: Required for all functions

### Code Formatting

We use **Black** for formatting and **Ruff** for linting:

```bash
# Format code
black .

# Lint code
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Type Checking

We use **MyPy** for type checking:

```bash
# Run type checker
mypy .
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_assets.py

# Run with coverage
pytest --cov=hub --cov-report=html

# Run E2E tests
pytest tests/e2e/
```

### Test Structure

- **Unit tests**: `tests/unit/` - Fast, isolated tests
- **Integration tests**: `tests/integration/` - Test component interactions
- **E2E tests**: `tests/e2e/` - Full system tests

### Writing Tests

```python
import pytest
from django.test import TestCase

class AssetTestCase(TestCase):
    def setUp(self):
        # Set up test data
        pass
    
    def test_create_asset(self):
        # Test asset creation
        pass
```

### Test Coverage

- **Target**: 80%+ coverage
- **Critical paths**: 90%+ coverage
- **New code**: 100% coverage required

---

## Common Tasks

### Adding a New API Endpoint

1. **Define model** (if needed):
   ```python
   # hub/apps/myapp/models.py
   class MyModel(models.Model):
       name = models.CharField(max_length=255)
   ```

2. **Create serializer**:
   ```python
   # hub/apps/myapp/serializers.py
   class MyModelSerializer(serializers.ModelSerializer):
       class Meta:
           model = MyModel
           fields = '__all__'
   ```

3. **Create view**:
   ```python
   # hub/apps/myapp/views.py
   class MyModelViewSet(viewsets.ModelViewSet):
       queryset = MyModel.objects.all()
       serializer_class = MyModelSerializer
   ```

4. **Register URL**:
   ```python
   # hub/apps/myapp/urls.py
   router.register(r'mymodels', MyModelViewSet)
   ```

5. **Write tests**:
   ```python
   # tests/unit/test_myapp.py
   def test_create_mymodel():
       # Test implementation
   ```

### Adding a New Microservice

1. **Create service directory**:
   ```bash
   mkdir -p services/my-service
   ```

2. **Create FastAPI app**:
   ```python
   # services/my-service/main.py
   from fastapi import FastAPI
   
   app = FastAPI()
   
   @app.get("/health")
   async def health():
       return {"status": "healthy"}
   ```

3. **Add Dockerfile**:
   ```dockerfile
   # services/my-service/Dockerfile
   FROM python:3.11-slim
   # ...
   ```

4. **Update docker-compose.yml**:
   ```yaml
   my-service:
     build:
       context: .
       dockerfile: services/my-service/Dockerfile
   ```

### Running Migrations

```bash
# Create migration
python hub/manage.py makemigrations

# Apply migration
python hub/manage.py migrate

# Show migration status
python hub/manage.py showmigrations
```

### Accessing Services

```bash
# PostgreSQL
psql -h localhost -U hub -d hub

# Redis
redis-cli -h localhost

# MinIO
# Access at http://localhost:9001
# Default credentials: minioadmin/minioadmin
```

---

## Resources

### Documentation

- **API Documentation**: `/api-docs/` (when server running)
- **OpenAPI Schema**: `/api-docs/openapi.json`
- **Project Docs**: `docs/`
- **Runbooks**: `runbooks/`

### External Resources

- **Django Docs**: https://docs.djangoproject.com/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **DRF Docs**: https://www.django-rest-framework.org/
- **Pytest Docs**: https://docs.pytest.org/

### Getting Help

- **Slack**: #datainteroperabilityhub
- **GitHub Issues**: https://github.com/your-org/datainteroperabilityhub/issues
- **Email**: dev-team@hub.example.com

### Learning Resources

- **Django Tutorial**: https://docs.djangoproject.com/en/stable/intro/tutorial01/
- **FastAPI Tutorial**: https://fastapi.tiangolo.com/tutorial/
- **REST API Design**: https://restfulapi.net/

---

## Next Steps

1. ✅ Complete initial setup
2. ✅ Run test suite
3. ✅ Explore codebase
4. ✅ Pick a first issue (look for "good first issue" label)
5. ✅ Join team Slack channel
6. ✅ Attend team standup

---

**Welcome to the team! 🎉**

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

