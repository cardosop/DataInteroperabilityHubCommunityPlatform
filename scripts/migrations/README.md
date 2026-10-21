# Database Migration Scripts

This directory contains scripts for migrating from a monolithic database to a microservices architecture with separate schemas/databases per service.

## Scripts

### `create_service_schemas.py`

Creates separate schemas for each microservice in PostgreSQL.

**Usage:**
```bash
# Dry run (show what would be created)
python scripts/migrations/create_service_schemas.py --dry-run

# Create all schemas
python scripts/migrations/create_service_schemas.py

# Create only service schemas (skip infrastructure)
python scripts/migrations/create_service_schemas.py --services-only

# Create only infrastructure schemas
python scripts/migrations/create_service_schemas.py --infrastructure-only
```

**Environment Variables:**
- `DATABASE_URL`: PostgreSQL connection string (default: from .env.dev)
- `POSTGRES_DB`: Database name (default: hub)
- `POSTGRES_USER`: Database user (default: hub)
- `POSTGRES_PASSWORD`: Database password (default: hub)
- `POSTGRES_HOST`: Database host (default: localhost)
- `POSTGRES_PORT`: Database port (default: 5432)

### `migrate_service_data.py`

Migrates data from public schema to service-specific schemas.

**Usage:**
```bash
# Migrate contract service data
python scripts/migrations/migrate_service_data.py --service contract_service

# Dry run
python scripts/migrations/migrate_service_data.py --service contract_service --dry-run

# Validate existing migration
python scripts/migrations/migrate_service_data.py --service contract_service --validate-only
```

**Available Services:**
- `contract_service`
- `asset_service`
- `dataset_service`
- `dq_service`
- `compliance_service`
- `search_service`
- `governance_service`
- `observability_service`
- `ingestion_service`
- `webhook_service`
- `semantic_service`

## Migration Process

### Step 1: Create Schemas

```bash
python scripts/migrations/create_service_schemas.py
```

### Step 2: Migrate Data (Service by Service)

```bash
# Start with low-risk services
python scripts/migrations/migrate_service_data.py --service search_service
python scripts/migrations/migrate_service_data.py --service observability_service

# Then core services
python scripts/migrations/migrate_service_data.py --service contract_service
python scripts/migrations/migrate_service_data.py --service asset_service
python scripts/migrations/migrate_service_data.py --service dataset_service

# Continue with remaining services...
```

### Step 3: Validate Migrations

```bash
# Validate each service
python scripts/migrations/migrate_service_data.py --service contract_service --validate-only
```

### Step 4: Update Application Code

- Update Django settings to use service-specific schemas
- Replace ForeignKey references with UUID fields
- Use ServiceClient for cross-service access
- Implement event subscriptions for read models

## Rollback

If migration fails, data remains in the public schema. To rollback:

1. Drop service schema: `DROP SCHEMA IF EXISTS contract_service CASCADE;`
2. Restore application code to use public schema
3. Investigate and fix issues
4. Re-attempt migration

## Best Practices

1. **Backup First:** Always backup database before migration
2. **Test in Staging:** Test migration in staging environment first
3. **One Service at a Time:** Migrate one service at a time
4. **Validate:** Validate each migration before proceeding
5. **Monitor:** Monitor application after migration

## Troubleshooting

### Schema Already Exists

If schema already exists, the script will skip it. To recreate:

```sql
DROP SCHEMA IF EXISTS contract_service CASCADE;
```

Then run the script again.

### Migration Count Mismatch

If validation shows count mismatch:

1. Check for data filtering issues
2. Verify tenant_id filtering
3. Check for soft-deleted records
4. Review migration script logic

### Connection Errors

If connection fails:

1. Verify DATABASE_URL or individual connection parameters
2. Check PostgreSQL is running
3. Verify network connectivity
4. Check firewall rules

---

**Last Updated:** 2025-01-15

