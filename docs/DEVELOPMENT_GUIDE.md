# Development Guide

## Code organization
- `hub/` — Django monolith (API, models, business logic)
- `services/` — FastAPI microservices
- `frontend/` — React SPA
- `cli/` — Python CLI tool
- `sdk/` — Python and TypeScript SDKs

## Testing
Run tests via Makefile targets:
- `make test` — all tests
- `make test-unit` — unit tests only
- `make test-integration` — integration tests
- `make test-ci` — full CI pipeline

## API patterns
Use standardized nested resource patterns:
- `/api/v1/compliance/runs/` for compliance runs
- `/api/v1/dq/runs/` for DQ runs

## Conventions
- See `CLAUDE.md` for RLS, feature flag, and business rules contracts
- All new models with `tenant_id` must ship a paired RLS policy migration
