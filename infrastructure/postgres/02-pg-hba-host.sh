#!/bin/sh
# =============================================================================
# infrastructure/postgres/02-pg-hba-host.sh — Production pg_hba.conf hardening
#
# Runs inside the postgres container during initdb (docker-entrypoint-initdb.d).
# Appends a pg_hba.conf rule that REQUIRES SSL for all TCP connections.
#
# Why hostssl instead of host?
#   - PgBouncer connects with server_tls_sslmode=require (TLS enforced end-to-end).
#   - Direct connections (backup pg_dump via POSTGRES_DIRECT_HOST) also use SSL
#     (psycopg2 sslmode=require set in settings.py for ENVIRONMENT=production).
#   - Rejecting non-SSL connections prevents accidental plaintext access if a
#     client is misconfigured.
#
# Unix socket connections (pg_isready healthcheck, local psql, initdb scripts)
# are handled by the pre-existing 'local all all trust' rule — this rule only
# affects TCP connections, so healthchecks are unaffected.
#
# Staging: this script is NOT mounted in docker-compose.staging.yml.
#          Staging uses the postgres docker default pg_hba.conf (non-SSL, scram-sha-256).
# =============================================================================
set -e

echo "hostssl all all 0.0.0.0/0 scram-sha-256" >> "$PGDATA/pg_hba.conf"
echo "[pg-hba] Added hostssl rule: all TCP connections now require TLS."
