#!/usr/bin/env python
"""
Create Service Schemas Migration Script

Creates separate schemas for each microservice in the PostgreSQL database.
This script supports the "Database per Service" migration strategy.

Usage:
    python scripts/migrations/create_service_schemas.py [--database DATABASE_URL]

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (default: from .env.dev)
"""
import os
import sys
import argparse
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


# Service schemas to create
SERVICE_SCHEMAS = [
    'contract_service',
    'asset_service',
    'dataset_service',
    'lineage_service',
    'normalization_service',
    'dq_service',
    'compliance_service',
    'search_service',
    'governance_service',
    'observability_service',
    'ingestion_service',
    'versioning_service',
    'webhook_service',
    'semantic_service',
]

# Infrastructure schemas (shared)
INFRASTRUCTURE_SCHEMAS = [
    'tenants',
    'users',
    'jobs',
    'files',
    'audit',
]


def get_database_url():
    """Get database URL from environment or .env.dev file."""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        # Try to load from .env.dev
        env_file = os.path.join(os.path.dirname(__file__), '../../.env.dev')
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        database_url = line.split('=', 1)[1].strip().strip('"\'')
                        break
    
    if not database_url:
        # Construct from individual env vars
        db_name = os.getenv('POSTGRES_DB', 'hub')
        db_user = os.getenv('POSTGRES_USER', 'hub')
        db_password = os.getenv('POSTGRES_PASSWORD', 'hub')
        db_host = os.getenv('POSTGRES_HOST', 'localhost')
        db_port = os.getenv('POSTGRES_PORT', '5432')
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    return database_url


def create_schema(conn, schema_name, dry_run=False):
    """Create a schema if it doesn't exist."""
    cur = conn.cursor()
    
    try:
        if dry_run:
            print(f"[DRY RUN] Would create schema: {schema_name}")
            return True
        
        # Check if schema exists
        cur.execute(
            sql.SQL("SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = {})").format(
                sql.Literal(schema_name)
            )
        )
        exists = cur.fetchone()[0]
        
        if exists:
            print(f"✓ Schema already exists: {schema_name}")
            return True
        
        # Create schema
        cur.execute(
            sql.SQL("CREATE SCHEMA {}").format(
                sql.Identifier(schema_name)
            )
        )
        print(f"✓ Created schema: {schema_name}")
        return True
        
    except psycopg2.Error as e:
        print(f"✗ Error creating schema {schema_name}: {e}")
        return False
    finally:
        cur.close()


def create_schemas(database_url, dry_run=False, service_schemas=True, infrastructure_schemas=True):
    """Create all service schemas."""
    try:
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        print(f"Connected to database: {database_url.split('@')[1] if '@' in database_url else 'local'}")
        print()
        
        created_count = 0
        failed_count = 0
        
        # Create service schemas
        if service_schemas:
            print("Creating service schemas...")
            for schema_name in SERVICE_SCHEMAS:
                if create_schema(conn, schema_name, dry_run):
                    created_count += 1
                else:
                    failed_count += 1
            print()
        
        # Create infrastructure schemas
        if infrastructure_schemas:
            print("Creating infrastructure schemas...")
            for schema_name in INFRASTRUCTURE_SCHEMAS:
                if create_schema(conn, schema_name, dry_run):
                    created_count += 1
                else:
                    failed_count += 1
            print()
        
        conn.close()
        
        print(f"Summary: {created_count} schemas created, {failed_count} failed")
        
        if failed_count > 0:
            sys.exit(1)
        
    except psycopg2.Error as e:
        print(f"✗ Database connection error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Create service schemas for microservices migration'
    )
    parser.add_argument(
        '--database',
        help='Database connection URL (default: from DATABASE_URL env var)',
        default=None
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without actually creating'
    )
    parser.add_argument(
        '--services-only',
        action='store_true',
        help='Create only service schemas (skip infrastructure)'
    )
    parser.add_argument(
        '--infrastructure-only',
        action='store_true',
        help='Create only infrastructure schemas (skip services)'
    )
    
    args = parser.parse_args()
    
    database_url = args.database or get_database_url()
    
    if not database_url:
        print("✗ Error: DATABASE_URL not found. Please set DATABASE_URL environment variable or use --database option.")
        sys.exit(1)
    
    service_schemas = not args.infrastructure_only
    infrastructure_schemas = not args.services_only
    
    create_schemas(
        database_url,
        dry_run=args.dry_run,
        service_schemas=service_schemas,
        infrastructure_schemas=infrastructure_schemas
    )


if __name__ == '__main__':
    main()

