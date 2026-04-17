# Developer Guide

Full development setup and workflow for contributing to the Meshant platform.

## Prerequisites

| Requirement | Version | Purpose |
|------------|---------|---------|
| Python | 3.12+ | Backend API, CLI, Python SDK |
| Node.js | 20+ | Frontend SPA, JavaScript SDK |
| Docker + Compose | 20.10+ / 2.0+ | Backing services (PostgreSQL, Redis, MinIO) |
| Git | 2.x | Version control |

**Recommended**: VS Code or PyCharm, `pre-commit`, `kubectl` (for K8s debugging).

## Initial Setup

```bash
# 1. Clone and enter the repository
git clone <repo-url>
cd DataInteroperabilityHub

# 2. Run the automated setup script
./scripts/dev_setup.sh
# Creates venv, installs dependencies, sets up pre-commit hooks

# 3. Copy environment config
cp .env.example .env
# Edit .env with local values (database URL, Redis URL, etc.)

# 4. Start infrastructure services
docker compose -f docker-compose.dev.yml up -d

# 5. Apply database migrations
python hub/manage.py migrate

# 6. Create a superuser (optional)
python hub/manage.py createsuperuser
```

## Running Services

| Service | Command | Port |
|---------|---------|------|
| Backend API | `python hub/manage.py runserver` | 8000 |
| Frontend SPA | `cd frontend && npm run dev` | 3000 |
| RQ Worker | `python hub/manage.py rqworker job_critical job_default job_low` | -- |

## Development Workflow

1. Create a feature branch from `staging`
2. Make changes, write tests
3. Run linting: `ruff check hub/`
4. Run formatting: `black hub/`
5. Run type checking: `mypy hub/`
6. Run tests: `pytest hub/ -x --tb=short`
7. Push and create a PR against `staging`

## Code Quality

Pre-commit hooks run automatically on `git commit`:

- **ruff** — fast Python linter (replaces flake8)
- **black** — code formatter (line-length 100)
- **mypy** — type checker
- **codespell** — spell checker

```bash
# Run all hooks manually
pre-commit run --all-files
```

## Database Migrations

```bash
# Create a migration after model changes
python hub/manage.py makemigrations <app_name> --name descriptive_name

# Apply migrations
python hub/manage.py migrate

# Show migration status
python hub/manage.py showmigrations
```

## Configuration Validation

Before starting the API in staging or production, validate config:

```bash
python hub/manage.py validate_config
# Exit 0 = valid, Exit 1 = missing required settings
```

## Related

- [Local Development](local-dev.md) -- quick-start setup
- [Testing Guide](testing-guide.md) -- test framework and running tests
- [Configuration Reference](configuration-reference.md) -- all environment variables
