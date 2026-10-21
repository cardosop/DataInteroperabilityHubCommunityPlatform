# PostgreSQL Runbook

## Required Extensions

| Extension | Used By | Purpose |
|-----------|---------|---------|
| `pg_trgm` | `hub.apps.search.search_engine` | Trigram similarity for search suggestions |
| `unaccent` | (future) | Accent-insensitive search |

### Provisioning (Phase 273.9)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
```

CI provisions these via `docker exec hub-test-postgres psql ...` in
the GitHub Actions workflow (`.github/workflows/ci.yml`).

Staging/production: extensions are provisioned via Terraform or a
one-time `psql` command during cluster bootstrap. Verify with:
```sql
SELECT extname, extversion FROM pg_extension WHERE extname IN ('pg_trgm', 'unaccent');
```

## Connection Pooling

See PgBouncer configuration in `docker-compose.yml` and Helm values.
