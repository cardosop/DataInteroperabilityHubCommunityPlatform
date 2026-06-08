-- Initialize database with extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create initial database structure will be handled by Django migrations
-- This file can be used for any pre-migration setup

-- RLS baseline test roles.  CREATE ROLE is idempotent when the role
-- already exists (PostgreSQL reports a NOTICE, not an error), so this
-- is safe to run on every container start as well as on a fresh volume.
-- meshant_app is the application-level role that is subject to RLS
-- (no BYPASSRLS).  meshant_admin is the admin role used by management
-- commands that need to see all rows across tenants (BYPASSRLS).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meshant_app') THEN
        CREATE ROLE meshant_app WITH LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meshant_admin') THEN
        CREATE ROLE meshant_admin WITH LOGIN BYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO meshant_app;
GRANT USAGE ON SCHEMA public TO meshant_admin;

-- Grant read access so RLS baseline tests can COUNT(*) on all tables.
-- Default privileges ensure future tables also allow reads.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO meshant_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO meshant_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO meshant_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO meshant_admin;

