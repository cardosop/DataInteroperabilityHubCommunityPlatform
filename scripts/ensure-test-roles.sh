#!/bin/sh
# ---------------------------------------------------------------------------
# ensure-test-roles.sh — Idempotent test database and role setup.
#
# Runs on every `docker compose up` via the ensure-test-db service.  All
# commands are guarded with `2>/dev/null || true` so the service never fails.
#
# Why this exists separately from init-db.sql:
#   docker-entrypoint-initdb.d/*.sql only runs on the *first* volume
#   initialization.  This script fills the gap for persistent volumes,
#   ensuring meshant_admin (BYPASSRLS) exists regardless of volume age.
# ---------------------------------------------------------------------------
set -e

PGHOST="${PGHOST:-postgres-test}"
PGUSER="${PGUSER:-hub_test}"
PGPASSWORD="${PGPASSWORD:-hub_test}"
export PGHOST PGUSER PGPASSWORD

# ── Idempotent database creation ───────────────────────────────────────────
for db in hub_test hub_test_test_shared hub_test_test_phase13; do
    psql -d template1 -c "CREATE DATABASE $db;" 2>/dev/null || true
done

# ── Create meshant_admin with BYPASSRLS (idempotent) ───────────────────────
# This role is used by the admin DB alias for pre-auth user lookups (login,
# password reset) where app.current_tenant_id is not yet set and RLS would
# filter all rows.  BYPASSRLS allows these queries to see all users.
psql -d hub_test -c "
DO \$\$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meshant_admin') THEN
        CREATE ROLE meshant_admin WITH LOGIN BYPASSRLS;
    END IF;
END \$\$;" 2>/dev/null || true

# Also ensure meshant_app exists (subject to RLS, no BYPASSRLS).
psql -d hub_test -c "
DO \$\$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'meshant_app') THEN
        CREATE ROLE meshant_app WITH LOGIN;
    END IF;
END \$\$;" 2>/dev/null || true

# ── Permissions for meshant_admin / meshant_app ────────────────────────────
# The API service connects to hub_test_test_shared, so permissions must be
# granted on BOTH databases (roles are cluster-global, but schema privileges
# are per-database).  We also apply to hub_test so tests that use the default
# DB directly also work.
for db in hub_test hub_test_test_shared; do
    psql -d "$db" -c "GRANT USAGE ON SCHEMA public TO meshant_admin;"               2>/dev/null || true
    psql -d "$db" -c "GRANT USAGE ON SCHEMA public TO meshant_app;"                 2>/dev/null || true
    psql -d "$db" -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO meshant_app;"  2>/dev/null || true
    psql -d "$db" -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO meshant_admin;" 2>/dev/null || true
    psql -d "$db" -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO meshant_admin;"     2>/dev/null || true
    psql -d "$db" -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO meshant_admin;"  2>/dev/null || true
    psql -d "$db" -c "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO meshant_admin;"  2>/dev/null || true
    psql -d "$db" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO meshant_admin;"    2>/dev/null || true
    psql -d "$db" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO meshant_admin;" 2>/dev/null || true
    psql -d "$db" -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO meshant_app;"              2>/dev/null || true
done

# ── Set password ───────────────────────────────────────────────────────────
psql -d hub_test -c "ALTER ROLE meshant_admin WITH PASSWORD 'admin_test_password';" 2>/dev/null || true
