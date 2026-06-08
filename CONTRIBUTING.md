# Contributing to Meshant

**311.31 (G20)** — Sprint 5

## Prerequisites

- Docker 24+ & docker-compose v2
- Python 3.12
- Node 22 & npm 10+
- AWS CLI (for DR drills and S3 operations)
- jq (for JSON processing in scripts)

## Local Setup

```bash
# Clone and enter repo
git clone git@github.com:your-org/DataInteroperabilityHub.git
cd DataInteroperabilityHub

# Start all services
make dev-env
docker compose up -d

# Wait for health checks
curl http://localhost:8000/api/v1/health/
```

## Running Tests

```bash
# Backend tests (reuse DB for speed)
pytest hub/ -x --reuse-db

# Single app tests
pytest hub/apps/billing/tests/ -x --reuse-db

# Frontend tests
cd frontend && npm test

# E2E tests (requires backend running)
npx playwright test

# Load tests
k6 run tests/load/search_load.k6.js
```

## Code Style

| Language | Tool | Config |
|----------|------|--------|
| Python | Ruff | `pyproject.toml` |
| TypeScript/TSX | Prettier + ESLint | `frontend/.prettierrc` |
| CSS | Stylelint | `frontend/.stylelintrc` |
| YAML/JSON | Prettier | `frontend/.prettierrc` |

```bash
# Lint all
make lint

# Auto-fix
make lint-fix
```

## PR Process

1. Branch naming: `feature/<ticket-id>-<short-desc>` or `fix/<ticket-id>-<short-desc>`
2. Commit format: `type(scope): description` (e.g. `feat(billing): add sandbox plan tier`)
3. Breaking changes: prefix with `BREAKING:` in commit message
4. Minimum 1 approving review before merge to `main` or `staging`
5. CI must pass: lint, type-check, tests, security scan
6. Squash merge preferred

## CI Pipeline

| Stage | What runs |
|-------|-----------|
| Lint | Ruff, Prettier, ESLint, Stylelint |
| Type-check | mypy (Python), tsc (TypeScript) |
| Test | pytest, vitest, RLS migration check |
| Security | gitleaks, pip-audit, trivy image scan |
| Verify | validate_plan_config, check_throttle_coverage |
| Deploy | Docker build → ECR push → Helm deploy |

## Documentation

- Architecture decisions: `docs/adr/`
- Runbooks: `docs/runbooks/`
- API docs: `GET /api/v1/openapi/` (auto-generated)
- Product guide: `docs/PRODUCT_GUIDE.md`
- Breaking changes: see `docs/BREAKING_CHANGE_POLICY.md`
