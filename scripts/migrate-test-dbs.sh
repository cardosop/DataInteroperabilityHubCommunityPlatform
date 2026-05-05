#!/usr/bin/env bash
# Run migrations for all test databases.
#
# On WARM RESTART (volume already migrated): exits in <5 s via schema guard.
# On COLD BOOT or after new migrations land: runs full migrate + template clone.
#
# Template DBs created from hub_test (one migrate, N fast pg_dump copies):
#   hub_test_test_shared  — api runserver + worker + prefect-integration + most pytest
#   hub_test_test_phase13 — isolation DB for compliance/security/E2E/dataset-creation tests
#                           (TEST_DB_SUFFIX=phase13 and TEST_DB_SUFFIX=phase68 both use this;
#                            do NOT run phase13 and dataset-creation tests concurrently)
#
# NOTE: makemigrations is intentionally NOT run here. Running makemigrations in automated
# infra is dangerous — it silently creates migration files inside ephemeral containers.
# Developers who need makemigrations should run it explicitly:
#   docker compose -f docker-compose.test.yml exec api-service-test python hub/manage.py makemigrations
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH=/app
export DJANGO_SETTINGS_MODULE=hub.settings

PGHOST="${POSTGRES_HOST:-postgres-test}"
PGUSER="${POSTGRES_USER:-hub_test}"
PGPASSWORD="${POSTGRES_PASSWORD:-hub_test}"
export PGPASSWORD

# ── helpers ───────────────────────────────────────────────────────────────────

_psql() { psql -h "$PGHOST" -U "$PGUSER" "$@"; }

# Check whether a database exists.
_db_exists() {
  _psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$1'" 2>/dev/null | grep -q 1
}

# PostgreSQL marks partially created databases as invalid with datconnlimit = -2.
# Those databases cannot be connected to and must be dropped before reuse.
_db_is_invalid() {
  _psql -d postgres -tAc \
    "SELECT CASE WHEN datconnlimit = -2 THEN 1 ELSE 0 END FROM pg_database WHERE datname='$1'" \
    2>/dev/null | grep -q 1
}

# Check whether a table exists in a given database.
_table_exists() {
  local db="$1" table="$2"
  _psql -d "$db" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='$table'" 2>/dev/null | grep -q 1
}

# Count applied Django migrations in hub_test.
_migration_count() {
  _psql -d "${POSTGRES_DB:-hub_test}" -tAc "SELECT COUNT(*) FROM django_migrations" 2>/dev/null | tr -d '[:space:]'
}

# ── warm-restart guard ────────────────────────────────────────────────────────
# Skip all expensive work when:
#   1. hub_test already has migrations applied
#   2. All template DBs exist and have the critical tables
#   3. No unapplied Django migrations (migrate --check exits 0)
#
check_all_dbs_ready() {
  echo "== Checking whether test DBs are already up to date..."

  # 1. hub_test must have migrations
  local count
  count=$(_migration_count 2>/dev/null || echo 0)
  if [ "${count:-0}" -eq 0 ] 2>/dev/null || ! [ "${count:-0}" -gt 0 ] 2>/dev/null; then
    echo "   hub_test: no migrations recorded — full migrate required."
    return 1
  fi

  # 2. Template DBs must exist and have the critical tables.
  for db in hub_test_test_shared hub_test_test_phase13; do
    if ! _db_exists "$db"; then
      echo "   $db: does not exist — will create."
      return 1
    fi
    for table in django_admin_log security_audit_logs tenants; do
      if ! _table_exists "$db" "$table"; then
        echo "   $db: missing table '$table' — will recreate."
        return 1
      fi
    done
  done

  # 3. Django must report no unapplied migrations.
  if ! python hub/manage.py migrate --check 2>/dev/null; then
    echo "   Unapplied migrations detected — running migrate."
    return 1
  fi

  echo "== All test DBs are up to date. Skipping migration (warm restart)."
  return 0
}

if check_all_dbs_ready; then
  exit 0
fi

# ── full migration path ───────────────────────────────────────────────────────

echo "== Migrating hub_test..."
# Retry migrate on deadlock (transient when postgres/other processes contend; 3 attempts)
for attempt in 1 2 3; do
  if python hub/manage.py migrate --noinput 2>&1; then
    break
  fi
  if [ $attempt -lt 3 ]; then
    echo "Migrate attempt $attempt failed (possibly deadlock), retrying in 10s..."
    sleep 10
  else
    echo "ERROR: migrate failed after 3 attempts." >&2
    exit 1
  fi
done

# ── connection drain helper ───────────────────────────────────────────────────
# Aggressively terminate connections to a DB before using it as a TEMPLATE or DROPping it.
# Retries with exponential back-off so that even lingering health-check connections clear.
drain_connections() {
  local db="$1"
  for i in 1 2 3 4 5; do
    local remaining
    remaining=$(_psql -d postgres -tAc \
      "SELECT COUNT(*) FROM pg_stat_activity WHERE datname='$db' AND pid <> pg_backend_pid()" \
      2>/dev/null | tr -d '[:space:]')
    [ "${remaining:-0}" = "0" ] && return 0
    echo "   $db: $remaining connection(s) active, terminating (attempt $i/5)..."
    _psql -d postgres -c \
      "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$db' AND pid <> pg_backend_pid()" \
      2>/dev/null || true
    sleep $((i * 2))   # 2 4 6 8 10 s
  done
  # One final check — proceed even if a stray connection remains (CREATE TEMPLATE may still work)
  local remaining
  remaining=$(_psql -d postgres -tAc \
    "SELECT COUNT(*) FROM pg_stat_activity WHERE datname='$db' AND pid <> pg_backend_pid()" \
    2>/dev/null | tr -d '[:space:]')
  [ "${remaining:-0}" != "0" ] && \
    echo "   WARNING: $remaining connection(s) to $db still active after drain — proceeding anyway."
  return 0
}

# Force-drop a database and wait until catalog entry disappears.
# Uses statement_timeout=0 to avoid local 120s session timeout.
drop_db_force() {
  local db="$1"
  for i in 1 2 3 4 5; do
    PGOPTIONS='-c statement_timeout=0' \
      _psql -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $db WITH (FORCE)" \
      >/dev/null 2>&1 || true
    if ! _db_exists "$db"; then
      return 0
    fi
    sleep $((i * 2))
  done
  return 1
}

# ── create template DB helper ─────────────────────────────────────────────────
# Creates a DB from hub_test as TEMPLATE.  Falls back to empty DB + migrate on failure.
create_from_template() {
  local db="$1"
  echo "== Creating $db from hub_test template..."

  drain_connections "$db"
  if ! drop_db_force "$db"; then
    echo "ERROR: failed to drop existing database $db before template clone." >&2
    exit 1
  fi

  # Drain hub_test connections before using it as TEMPLATE.
  drain_connections hub_test

  if _psql -d postgres -c "CREATE DATABASE $db WITH TEMPLATE hub_test ENCODING 'UTF8'" 2>&1; then
    if ! _table_exists "$db" tenants; then
      echo "ERROR: $db missing tenants table (template copy incomplete)." >&2
      exit 1
    fi
    echo "$db ready (copied from hub_test via TEMPLATE)."
    return 0
  fi

  echo "WARNING: $db CREATE FROM TEMPLATE failed, falling back to migrate..."

  # A failed CREATE ... TEMPLATE can leave an "invalid database" shell behind.
  # Always force-drop any leftover before creating the fallback DB.
  if _db_exists "$db"; then
    if _db_is_invalid "$db"; then
      echo "   $db is marked invalid (datconnlimit=-2); recreating clean fallback DB."
    else
      echo "   $db already exists; recreating clean fallback DB."
    fi
    if ! drop_db_force "$db"; then
      echo "ERROR: failed to drop stale fallback database $db." >&2
      exit 1
    fi
  fi

  if ! _psql -d postgres -c "CREATE DATABASE $db ENCODING 'UTF8'" 2>/dev/null; then
    echo "ERROR: failed to create fallback database $db." >&2
    exit 1
  fi
  for m_attempt in 1 2 3; do
    if POSTGRES_DB=$db python hub/manage.py migrate --noinput 2>&1; then
      break
    fi
    [ $m_attempt -lt 3 ] && echo "  Fallback migrate attempt $m_attempt failed, retrying in 10s..." && sleep 10 || exit 1
  done
}

# ── hub_test_test_shared ──────────────────────────────────────────────────────
echo "== Creating hub_test_test_shared from hub_test..."
drain_connections hub_test_test_shared
if ! drop_db_force hub_test_test_shared; then
  echo "ERROR: failed to drop hub_test_test_shared before template clone." >&2
  exit 1
fi

drain_connections hub_test

CREATE_OK=false
for attempt in 1 2 3; do
  if _psql -d postgres -c "CREATE DATABASE hub_test_test_shared WITH TEMPLATE hub_test ENCODING 'UTF8'" 2>&1; then
    CREATE_OK=true
    break
  fi
  echo "CREATE hub_test_test_shared attempt $attempt failed, retrying..."
  drain_connections hub_test_test_shared
  drain_connections hub_test
  if ! drop_db_force hub_test_test_shared; then
    echo "ERROR: failed to drop hub_test_test_shared during retry." >&2
    exit 1
  fi
done

if [ "$CREATE_OK" != "true" ]; then
  echo "WARNING: CREATE DATABASE hub_test_test_shared FROM TEMPLATE hub_test failed after 3 attempts."
  echo "Falling back: creating empty DB and running migrate..."
  drain_connections hub_test_test_shared
  if ! drop_db_force hub_test_test_shared; then
    echo "ERROR: failed to drop hub_test_test_shared for fallback migrate." >&2
    exit 1
  fi
  _psql -d postgres -c "CREATE DATABASE hub_test_test_shared ENCODING 'UTF8'"
  for m_attempt in 1 2 3; do
    if POSTGRES_DB=hub_test_test_shared python hub/manage.py migrate --noinput 2>&1; then
      break
    fi
    [ $m_attempt -lt 3 ] && echo "Fallback migrate attempt $m_attempt failed, retrying in 10s..." && sleep 10 || exit 1
  done
fi

# Verify critical tables in hub_test_test_shared.
for table in django_admin_log security_audit_logs; do
  if ! _table_exists hub_test_test_shared "$table"; then
    echo "ERROR: hub_test_test_shared missing '$table' (template copy incomplete)." >&2
    exit 1
  fi
done
echo "hub_test_test_shared ready."

# ── hub_test_test_phase13 (isolation DB) ─────────────────────────────────────
# Used by:
#   TEST_DB_SUFFIX=phase13 — compliance/security/E2E/platform tests
#   TEST_DB_SUFFIX=phase68 — dataset creation flow tests (aliased to this DB)
# Do NOT run phase13 and dataset-creation tests concurrently.
create_from_template hub_test_test_phase13

echo "== All test DB migrations complete."
