#!/bin/bash
set -e

# Initialize CKAN test databases
# This script creates the datastore database and user for CKAN test instance

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    -- Create datastore database
    CREATE DATABASE datastore_test;

    -- Create datastore read-only user
    CREATE USER datastore_ro WITH PASSWORD 'datastore_ro';
    GRANT CONNECT ON DATABASE datastore_test TO datastore_ro;

    -- Grant permissions on datastore database
    \c datastore_test
    GRANT USAGE ON SCHEMA public TO datastore_ro;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO datastore_ro;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO datastore_ro;

    -- Grant permissions to ckan user
    GRANT ALL PRIVILEGES ON DATABASE datastore_test TO ckan;
    \c datastore_test
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ckan;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ckan;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ckan;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ckan;
EOSQL

echo "CKAN test databases initialized successfully"

