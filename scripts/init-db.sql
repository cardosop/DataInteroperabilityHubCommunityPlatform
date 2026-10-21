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
-- Tables are created by the app DB role (hub_test) during migrate, NOT by
-- the superuser running this script — a bare ALTER DEFAULT PRIVILEGES only
-- covers tables created by the CURRENT role (postgres). The FOR ROLE clause
-- makes future hub_test-created tables inherit the RLS-probe grants.
ALTER DEFAULT PRIVILEGES FOR ROLE hub_test IN SCHEMA public GRANT SELECT ON TABLES TO meshant_app;
ALTER DEFAULT PRIVILEGES FOR ROLE hub_test IN SCHEMA public GRANT SELECT ON TABLES TO meshant_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO meshant_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO meshant_admin;

-- Phase U.6: meshant_admin is the BYPASSRLS role the settings' `admin` DB
-- alias connects as (B-RLS-0.5) — cross-tenant flows (e.g. login's
-- _record_login_attempt user.save()) WRITE through it. The SELECT-only
-- grants above made those writes fail with "permission denied for table
-- users" on the staging bring-up. The admin role gets full DML (BYPASSRLS
-- makes row-level policies irrelevant; it is for internal admin paths,
-- never tenant-facing connections).
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO meshant_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT INSERT, UPDATE, DELETE ON TABLES TO meshant_admin;

