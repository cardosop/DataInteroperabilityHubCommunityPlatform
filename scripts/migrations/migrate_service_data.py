#!/usr/bin/env python
"""
Migrate Service Data Script

Migrates data from public schema to service-specific schemas.
Supports incremental migration with validation.

Usage:
    python scripts/migrations/migrate_service_data.py --service CONTRACT_SERVICE [--dry-run] [--validate-only]
"""
import os
import sys
import argparse
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime


# Service to table mapping
SERVICE_TABLES = {
    'contract_service': ['contracts'],
    'asset_service': ['assets'],
    'dataset_service': ['datasets'],
    'dq_service': ['dq_runs', 'dq_anomalies', 'dq_trends', 'dq_scorecards', 'dq_alerting_rules'],
    'compliance_service': ['compliance_runs'],
    'search_service': ['search_index', 'search_analytics'],
    'governance_service': [
        'data_classifications',
        'access_requests',
        'retention_policies',
        'compliance_reports',
        'abac_policies',
        'access_certifications',
        'access_logs'
    ],
    'observability_service': [
        'data_observability_metrics',
        'pipeline_slas',
        'incidents'
    ],
    'ingestion_service': [
        'scheduled_ingestions',
        'scheduled_ingestion_runs',
        'ingestion_templates'
    ],
    'webhook_service': ['webhooks', 'webhook_deliveries'],
    'semantic_service': ['semantic_resources'],
}


def get_database_url():
    """Get database URL from environment or .env.dev file."""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        env_file = os.path.join(os.path.dirname(__file__), '../../.env.dev')
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        database_url = line.split('=', 1)[1].strip().strip('"\'')
                        break
    
    if not database_url:
        db_name = os.getenv('POSTGRES_DB', 'hub')
        db_user = os.getenv('POSTGRES_USER', 'hub')
        db_password = os.getenv('POSTGRES_PASSWORD', 'hub')
        db_host = os.getenv('POSTGRES_HOST', 'localhost')
        db_port = os.getenv('POSTGRES_PORT', '5432')
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    return database_url


def table_exists(conn, schema_name, table_name):
    """Check if table exists in schema."""
    cur = conn.cursor()
    try:
        cur.execute(
            sql.SQL("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = {} AND table_name = {}
                )
            """).format(
                sql.Literal(schema_name),
                sql.Literal(table_name)
            )
        )
        return cur.fetchone()[0]
    finally:
        cur.close()


def get_table_count(conn, schema_name, table_name):
    """Get row count for table."""
    cur = conn.cursor()
    try:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name)
            )
        )
        return cur.fetchone()[0]
    except psycopg2.Error:
        return 0
    finally:
        cur.close()


def migrate_table(conn, source_schema, target_schema, table_name, dry_run=False):
    """Migrate a single table from source schema to target schema."""
    cur = conn.cursor()
    
    try:
        # Check if source table exists
        if not table_exists(conn, source_schema, table_name):
            print(f"  ⚠ Source table {source_schema}.{table_name} does not exist, skipping")
            return True
        
        # Check if target table exists
        if table_exists(conn, target_schema, table_name):
            print(f"  ⚠ Target table {target_schema}.{table_name} already exists, skipping")
            return True
        
        # Get source count
        source_count = get_table_count(conn, source_schema, table_name)
        
        if dry_run:
            print(f"  [DRY RUN] Would migrate {source_count} rows from {source_schema}.{table_name} to {target_schema}.{table_name}")
            return True
        
        # Create table in target schema (copy structure)
        cur.execute(
            sql.SQL("""
                CREATE TABLE {}.{} AS 
                SELECT * FROM {}.{} WHERE 1=0
            """).format(
                sql.Identifier(target_schema),
                sql.Identifier(table_name),
                sql.Identifier(source_schema),
                sql.Identifier(table_name)
            )
        )
        
        # Copy indexes (basic indexes, constraints handled separately)
        cur.execute(
            sql.SQL("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE schemaname = {} AND tablename = {}
            """).format(
                sql.Literal(source_schema),
                sql.Literal(table_name)
            )
        )
        
        indexes = cur.fetchall()
        for index_name, index_def in indexes:
            # Replace schema name in index definition
            new_index_def = index_def.replace(
                f'"{source_schema}".',
                f'"{target_schema}".'
            ).replace(
                f'{source_schema}.',
                f'{target_schema}.'
            )
            try:
                cur.execute(new_index_def)
            except psycopg2.Error as e:
                print(f"    ⚠ Could not create index {index_name}: {e}")
        
        # Copy data
        cur.execute(
            sql.SQL("""
                INSERT INTO {}.{} 
                SELECT * FROM {}.{}
            """).format(
                sql.Identifier(target_schema),
                sql.Identifier(table_name),
                sql.Identifier(source_schema),
                sql.Identifier(table_name)
            )
        )
        
        # Verify count
        target_count = get_table_count(conn, target_schema, table_name)
        
        if source_count != target_count:
            raise ValueError(
                f"Migration count mismatch: source={source_count}, target={target_count}"
            )
        
        print(f"  ✓ Migrated {source_count} rows: {source_schema}.{table_name} → {target_schema}.{table_name}")
        return True
        
    except psycopg2.Error as e:
        print(f"  ✗ Error migrating {table_name}: {e}")
        return False
    finally:
        cur.close()


def validate_migration(conn, source_schema, target_schema, table_name):
    """Validate that migration was successful."""
    source_count = get_table_count(conn, source_schema, table_name)
    target_count = get_table_count(conn, target_schema, table_name)
    
    if source_count != target_count:
        print(f"  ✗ Validation failed: {table_name} (source={source_count}, target={target_count})")
        return False
    
    print(f"  ✓ Validated: {table_name} ({source_count} rows)")
    return True


def migrate_service(conn, service_name, dry_run=False, validate_only=False):
    """Migrate all tables for a service."""
    if service_name not in SERVICE_TABLES:
        print(f"✗ Unknown service: {service_name}")
        print(f"Available services: {', '.join(SERVICE_TABLES.keys())}")
        return False
    
    tables = SERVICE_TABLES[service_name]
    source_schema = 'public'
    target_schema = service_name
    
    print(f"Migrating {service_name}...")
    print(f"Source schema: {source_schema}")
    print(f"Target schema: {target_schema}")
    print(f"Tables: {', '.join(tables)}")
    print()
    
    if validate_only:
        print("Validating existing migration...")
        all_valid = True
        for table_name in tables:
            if not validate_migration(conn, source_schema, target_schema, table_name):
                all_valid = False
        return all_valid
    
    success_count = 0
    failed_count = 0
    
    for table_name in tables:
        if migrate_table(conn, source_schema, target_schema, table_name, dry_run):
            success_count += 1
        else:
            failed_count += 1
    
    print()
    print(f"Summary: {success_count} tables migrated, {failed_count} failed")
    
    return failed_count == 0


def main():
    parser = argparse.ArgumentParser(
        description='Migrate data from public schema to service-specific schemas'
    )
    parser.add_argument(
        '--service',
        required=True,
        choices=list(SERVICE_TABLES.keys()),
        help='Service to migrate'
    )
    parser.add_argument(
        '--database',
        help='Database connection URL (default: from DATABASE_URL env var)',
        default=None
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without actually migrating'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate existing migration (do not migrate)'
    )
    
    args = parser.parse_args()
    
    database_url = args.database or get_database_url()
    
    if not database_url:
        print("✗ Error: DATABASE_URL not found. Please set DATABASE_URL environment variable or use --database option.")
        sys.exit(1)
    
    try:
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        print(f"Connected to database: {database_url.split('@')[1] if '@' in database_url else 'local'}")
        print()
        
        success = migrate_service(
            conn,
            args.service,
            dry_run=args.dry_run,
            validate_only=args.validate_only
        )
        
        conn.close()
        
        if not success:
            sys.exit(1)
        
    except psycopg2.Error as e:
        print(f"✗ Database connection error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

