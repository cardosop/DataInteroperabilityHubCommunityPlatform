# Local Development Guide

Complete guide for setting up and running the Interoperable Data Hub MVP in a local development environment.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Initial Setup](#initial-setup)
4. [Docker Services](#docker-services)
5. [Development Workflow](#development-workflow)
6. [Service Configuration](#service-configuration)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Run the development setup script
./scripts/dev-setup.sh

# 2. Start all Docker services
docker compose up -d

# 3. Activate virtual environment and start development server
source venv/bin/activate
python hub/manage.py runserver

# 4. In another terminal, start the worker
source venv/bin/activate
python hub/manage.py rqworker default
```

---

## Prerequisites

- **Python 3.11+**: Required for Django and all Python dependencies
- **Docker & Docker Compose**: Required for running infrastructure services
- **Git**: For version control
- **Make** (optional): For convenience commands

### Verify Prerequisites

```bash
python3 --version  # Should be 3.11+
docker --version
docker compose version
```

---

## Initial Setup

### Option 1: Automated Setup (Recommended)

Run the development setup script:

```bash
./scripts/dev-setup.sh
```

This script will:
- ✅ Check prerequisites
- ✅ Create Python virtual environment
- ✅ Install all dependencies
- ✅ Create `.env.dev` configuration file
- ✅ Start Docker services (PostgreSQL, Redis, MinIO, Fuseki)
- ✅ Run database migrations
- ✅ Optionally create test users

### Option 2: Manual Setup

#### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

#### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### 3. Create Environment File

Copy `.env.example` to `.env.dev` and update with your configuration:

```bash
cp .env.example .env.dev
# Edit .env.dev with your settings
```

#### 4. Start Docker Services

```bash
docker compose up -d postgres redis minio fuseki
```

#### 5. Run Migrations

```bash
source venv/bin/activate
python hub/manage.py migrate
```

---

## Docker Services

The project uses Docker Compose to run infrastructure services locally.

### Service Overview

| Service | Container Name | Port | Purpose |
|---------|---------------|------|---------|
| PostgreSQL | `hub-postgres` | 5432 | Primary database |
| Redis | `hub-redis` | 6379 | Job queue and caching |
| MinIO | `hub-minio` | 9000 (API)<br>9001 (Console) | S3-compatible object storage |
| Apache Jena Fuseki | `hub-fuseki` | 3030 | RDF triple store |

### Service Management

#### Start Services

```bash
# Start infrastructure services only
docker compose up -d postgres redis minio fuseki

# Start all services (including microservices)
docker compose up -d

# Start specific service
docker compose up -d postgres
```

#### Stop Services

```bash
# Stop all services
docker compose down

# Stop specific service
docker compose stop postgres
```

#### View Service Status

```bash
docker compose ps
```

#### View Service Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f postgres
```

#### Service Health Checks

All services include health checks. Verify they're healthy:

```bash
docker compose ps
# Look for "healthy" status
```

---

## Development Workflow

### Daily Development

1. **Start Services** (if not already running):
   ```bash
   docker compose up -d
   ```

2. **Activate Virtual Environment**:
   ```bash
   source venv/bin/activate
   ```

3. **Start Development Server**:
   ```bash
   python hub/manage.py runserver
   ```
   Server runs at: http://localhost:8000

4. **Start Worker** (in separate terminal):
   ```bash
   source venv/bin/activate
   python hub/manage.py rqworker default
   ```

5. **Access Services**:
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/api-docs/
   - MinIO Console: http://localhost:9001 (minio/minio123)
   - Fuseki: http://localhost:3030

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest -m "not integration"

# Integration tests
pytest -m integration

# With coverage
pytest --cov=. --cov-report=html
```

### Database Operations

```bash
# Create migrations
python hub/manage.py makemigrations

# Apply migrations
python hub/manage.py migrate

# Create superuser
python hub/manage.py createsuperuser

# Django shell
python hub/manage.py shell

# Database shell
python hub/manage.py dbshell
```

### Code Quality

The project uses Ruff (linting), Black (formatting), and Mypy (type checking) for code quality.

**Configuration files**:
- `pyproject.toml`: Main configuration for all tools
- `.ruff.toml`: Ruff configuration (legacy)
- `mypy.ini`: Mypy configuration (legacy)
- `.pre-commit-config.yaml`: Pre-commit hooks

**Usage**:
```bash
# Format code
black .
ruff check --fix .

# Lint
ruff check .
mypy hub/

# Or use Makefile
make format  # Format code and auto-fix issues
make lint    # Run all linters

# Install pre-commit hooks (optional)
pre-commit install
pre-commit run --all-files
```

See `CODE_QUALITY.md` for detailed documentation.

---

## Service Configuration

### PostgreSQL

**Connection Details** (when running locally):
- Host: `localhost`
- Port: `5432`
- Database: `hub` (default)
- User: `hub` (default)
- Password: `hub` (default)

**Connection Details** (when running in Docker):
- Host: `postgres`
- Port: `5432`
- Database: `hub`
- User: `hub`
- Password: `hub`

**Environment Variables**:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=hub
POSTGRES_USER=hub
POSTGRES_PASSWORD=hub
```

### Redis

**Connection URL** (when running locally):
```
redis://localhost:6379/0
```

**Connection URL** (when running in Docker):
```
redis://redis:6379/0
```

**Environment Variable**:
```bash
REDIS_URL=redis://localhost:6379/0
```

### MinIO (S3-compatible)

**Access Details**:
- API Endpoint: http://localhost:9000
- Console: http://localhost:9001
- Access Key: `minio` (default)
- Secret Key: `minio123` (default)
- Bucket: `hub-files` (create manually or via script)

**Environment Variables**:
```bash
AWS_ACCESS_KEY_ID=minio
AWS_SECRET_ACCESS_KEY=minio123
S3_ENDPOINT_URL=http://localhost:9000
S3_BUCKET_NAME=hub-files
```

**Creating Bucket**:
1. Open http://localhost:9001
2. Login with `minio` / `minio123`
3. Create bucket named `hub-files`

### Apache Jena Fuseki

**Access Details**:
- URL: http://localhost:3030
- Dataset: `hub` (default)
- Admin Password: `admin` (default)

**Environment Variables**:
```bash
FUSEKI_URL=http://localhost:3030
FUSEKI_DATASET=hub
FUSEKI_ADMIN_PASSWORD=admin
```

---

## Development Modes

### Mode 1: Django Locally, Services in Docker (Recommended)

**Best for**: Active development, debugging, hot-reload

- Django runs on your machine
- Services run in Docker
- Fast iteration, easy debugging
- Use `POSTGRES_HOST=localhost` in `.env.dev`

**Setup**:
```bash
docker compose up -d postgres redis minio fuseki
source venv/bin/activate
python hub/manage.py runserver
```

### Mode 2: Everything in Docker

**Best for**: Testing production-like environment

- All services including Django run in Docker
- Closer to production setup
- Use `POSTGRES_HOST=postgres` in `.env.dev`

**Setup**:
```bash
docker compose up -d
docker compose logs -f api-service
```

---

## Troubleshooting

### Database Connection Issues

**Error**: `could not translate host name 'postgres'`

**Cause**: Django is trying to connect to Docker service name but running locally

**Fix**: Set `POSTGRES_HOST=localhost` in `.env.dev`

---

**Error**: `Connection refused`

**Cause**: PostgreSQL container not running

**Fix**:
```bash
docker compose ps | grep postgres
docker compose up -d postgres
```

---

**Error**: `Authentication failed`

**Cause**: Wrong database credentials

**Fix**: Check `.env.dev` matches your PostgreSQL container settings:
- Default: `hub` / `hub` / `hub`

---

### Redis Connection Issues

**Error**: `Error 111 connecting to localhost:6379`

**Cause**: Redis container not running

**Fix**:
```bash
docker compose up -d redis
```

---

### MinIO Issues

**Error**: `Bucket does not exist`

**Cause**: Bucket not created

**Fix**:
1. Open http://localhost:9001
2. Login: `minio` / `minio123`
3. Create bucket: `hub-files`

---

### Port Already in Use

**Error**: `Error: That port is already in use`

**Cause**: Another service is using the port

**Fix**:
```bash
# Find process using port
lsof -i :8000  # For API server
lsof -i :5432  # For PostgreSQL

# Kill process or change port in docker-compose.yml
```

---

### Migration Issues

**Error**: `django.db.utils.ProgrammingError: relation "..." does not exist`

**Cause**: Migrations not run

**Fix**:
```bash
python hub/manage.py migrate
```

---

### Virtual Environment Issues

**Error**: `ModuleNotFoundError`

**Cause**: Virtual environment not activated or dependencies not installed

**Fix**:
```bash
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## Useful Commands

### Docker

```bash
# View all services
docker compose ps

# View logs
docker compose logs -f [service-name]

# Restart service
docker compose restart [service-name]

# Stop all services
docker compose down

# Remove volumes (⚠️ deletes data)
docker compose down -v
```

### Django

```bash
# Development server
python hub/manage.py runserver

# Worker
python hub/manage.py rqworker default

# Shell
python hub/manage.py shell

# Check configuration
python hub/manage.py check

# Collect static files
python hub/manage.py collectstatic
```

### Makefile Commands

```bash
make help              # Show all commands
make docker-up        # Start infrastructure services
make docker-down      # Stop all services
make migrate          # Run migrations
make test             # Run tests
make lint             # Run linters
make format           # Format code
```

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| API Server | http://localhost:8000 | - |
| API Documentation | http://localhost:8000/api-docs/ | - |
| MinIO Console | http://localhost:9001 | minio / minio123 |
| MinIO API | http://localhost:9000 | minio / minio123 |
| Fuseki | http://localhost:3030 | admin / admin |
| PostgreSQL | localhost:5432 | hub / hub |
| Redis | localhost:6379 | - |

---

## Next Steps

1. **Create Superuser**:
   ```bash
   python hub/manage.py createsuperuser
   ```

2. **Create Test Users** (for performance testing):
   ```bash
   python tests/performance/setup_test_users.py
   ```

3. **Explore API**:
   - Visit http://localhost:8000/api-docs/
   - Try the interactive API documentation

4. **Run Tests**:
   ```bash
   pytest
   ```

5. **Start Development**:
   - Read the codebase structure
   - Check `openspec/` for specifications
   - Review `InputDocs/` for requirements

---

## Additional Resources

- **Quick Start**: See `QUICK_START.md`
- **Installation Guide**: See `INSTALLATION_GUIDE.md`
- **API Documentation**: http://localhost:8000/api-docs/
- **Specifications**: See `openspec/changes/implement-mvp-foundation/`
- **Requirements**: See `InputDocs/`

---

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review service logs: `docker compose logs -f`
3. Check Django logs in the terminal
4. Verify environment variables in `.env.dev`
5. Ensure all services are healthy: `docker compose ps`
