# Post-Deploy Test Strategy

**Document Version**: 1.0.0
**Last Updated**: 2026-03-26
**Status**: Active

---

## Overview

This document defines the post-deployment testing strategy for Meshant, covering Smoke tests, integration verification, and rollback procedures.

## Smoke Tests

Post-deploy smoke tests run automatically after each deployment to verify core services are operational.

### Smoke Test Suite

Located in `tests/smoke/`, the suite covers:
- **Health endpoints** — verify API and dependent services respond
- **Authentication** — verify JWT login/refresh flow works
- **Core CRUD** — verify basic asset and contract operations
- **Tenant isolation** — verify cross-tenant data is isolated

### Execution

```bash
make test-smoke
# or directly:
pytest tests/smoke/ -v --timeout=30
```

## Staging Checklist

Before promoting to production:

- [ ] All smoke tests pass on staging
- [ ] Health endpoints return 200
- [ ] JWT authentication flow succeeds
- [ ] Database migrations applied cleanly
- [ ] No elevated error rates in observability dashboards
- [ ] Helm deployment completes without pod restarts
- [ ] External secrets sync correctly from Vault

## Rollback Strategy

If post-deploy verification fails:

1. **Immediate rollback**: `helm rollback meshant <previous-revision>`
2. **Database**: Migrations are backwards-compatible; no manual rollback needed
3. **Cache**: Redis cache is flushed on rollback to avoid stale data
4. **DNS**: No DNS changes required; rollback is transparent

### Rollback Decision Matrix

| Signal                       | Action                           |
|------------------------------|----------------------------------|
| Smoke tests fail             | Automatic rollback               |
| Error rate > 5%              | Manual rollback within 5 minutes |
| P0 bug in production         | Hotfix or rollback               |
| Performance degradation > 2x | Investigate, rollback if needed  |

## Evidence Collection

Post-deploy evidence is collected automatically by CI:

- Smoke test results (JUnit XML)
- Health check responses
- Deployment timestamps and Helm revision
- Evidence bundle stored in `evidence/` directory

### Evidence Bundle Contents

Each deployment produces:
- `smoke-results.xml` — test results
- `health-check.json` — endpoint health snapshot
- `deploy-metadata.json` — Helm revision, image digests, timestamps
