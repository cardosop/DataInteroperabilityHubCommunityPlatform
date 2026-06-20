#!/usr/bin/env python3
"""
Ensure the Django test database exists with migrations applied.

Pre-runs ``migrate`` on the test database so the first ``pytest --reuse-db``
invocation doesn't pay the migration cost.

Usage:
  ENVIRONMENT=test \\
  POSTGRES_HOST=localhost POSTGRES_PORT=5434 POSTGRES_USER=hub_test \\
  POSTGRES_PASSWORD=hub_test POSTGRES_DB=hub_test \\
  python scripts/ensure_test_db.py
"""

import argparse
import os
import sys
import time


def _env(key, default=""):
    return os.environ.get(key, default)


def _db_config():
    host = _env("POSTGRES_HOST", "localhost")
    port = int(_env("POSTGRES_PORT", "5432"))
    user = _env("POSTGRES_USER", "hub")
    password = _env("POSTGRES_PASSWORD", "hub")
    postgres_db = _env("POSTGRES_DB", "hub")
    test_db_name = f"test_{postgres_db}"

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "postgres_db": postgres_db,
        "test_db_name": test_db_name,
    }


def _pg_connect(db_config, dbname="postgres"):
    import psycopg2

    last_err = None
    for attempt in range(12):
        try:
            conn = psycopg2.connect(
                host=db_config["host"],
                port=db_config["port"],
                user=db_config["user"],
                password=db_config["password"],
                dbname=dbname,
                connect_timeout=5,
            )
            conn.autocommit = True
            return conn
        except psycopg2.OperationalError as e:
            last_err = e
            msg = str(e).lower()
            retryable = any(
                kw in msg
                for kw in (
                    "starting up",
                    "refused",
                    "not yet accepting",
                    "could not translate",
                    "temporary failure",
                    "name or service not known",
                )
            )
            if retryable and attempt < 11:
                time.sleep(2)
                continue
            raise
    raise last_err


def _database_exists(conn, dbname):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", [dbname])
    return cur.fetchone() is not None


def _drop_database(db_config, dbname):
    conn = _pg_connect(db_config, "postgres")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            [dbname],
        )
        cur.execute('DROP DATABASE IF EXISTS "%s"' % dbname)
    finally:
        conn.close()


def _tables_count(db_config, dbname):
    conn = _pg_connect(db_config, dbname)
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
        return cur.fetchone()[0]
    finally:
        conn.close()


def _migrate_database(db_config, dbname):
    from pathlib import Path

    _project_root = Path(__file__).resolve().parent.parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    os.environ["SKIP_DB_CONNECTIVITY_CHECK"] = "1"
    os.environ["TESTING"] = "1"

    import django

    django.setup()

    from django.conf import settings
    from django.core.management import call_command
    from django.db import IntegrityError

    cfg = settings.DATABASES["default"].copy()
    cfg["NAME"] = dbname
    settings.DATABASES["_ensure_db"] = cfg

    try:
        call_command("migrate", database="_ensure_db", verbosity=0, interactive=False)
    except IntegrityError:
        # ``post_migrate`` signal from ``django.contrib.auth`` does a
        # ``Permission.objects.bulk_create()`` that can race/conflict
        # when the DB already has migrations + data from a prior run.
        # The DB is still usable — swallow and continue.
        pass

    from django.db import connections

    if "_ensure_db" in connections:
        connections["_ensure_db"].close()


def main():
    parser = argparse.ArgumentParser(description="Ensure test database exists with migrations")
    parser.add_argument(
        "--force", action="store_true", help="Drop and recreate the test DB even if it exists"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of parallel test workers (for pre-creating per-worker DBs)",
    )
    args = parser.parse_args()

    db_config = _db_config()
    test_db = db_config["test_db_name"]

    print(f"[ensure_test_db] Test DB: {test_db}")

    conn = _pg_connect(db_config, "postgres")
    exists = _database_exists(conn, test_db)
    conn.close()

    if args.force and exists:
        print(f"[ensure_test_db] Dropping existing test DB {test_db} (--force)...")
        _drop_database(db_config, test_db)
        exists = False

    if not exists:
        print(f"[ensure_test_db] Test DB {test_db} does not exist yet, creating...")
        # Create the database outside of Django so the test runner doesn't
        # have to pay the full migration cost on first --reuse-db.
        conn = _pg_connect(db_config, "postgres")
        try:
            cur = conn.cursor()
            cur.execute('CREATE DATABASE "%s" OWNER %s' % (test_db, db_config["user"]))
        finally:
            conn.close()
        print(f"[ensure_test_db] Test DB {test_db} created, running migrate...")
        _migrate_database(db_config, test_db)
        tables = _tables_count(db_config, test_db)
        print(f"[ensure_test_db] Migrations applied ({tables} tables)")
        print("[ensure_test_db] Done.")
        return

    tables = _tables_count(db_config, test_db)
    if tables == 0:
        print(f"[ensure_test_db] Test DB {test_db} exists but is empty, running migrate...")
        _migrate_database(db_config, test_db)
        tables = _tables_count(db_config, test_db)
        print(f"[ensure_test_db] Migrations applied ({tables} tables)")
    else:
        print(
            f"[ensure_test_db] Test DB {test_db} exists ({tables} tables), "
            f"running migrate for pending migrations..."
        )
        _migrate_database(db_config, test_db)
        tables = _tables_count(db_config, test_db)
        print(f"[ensure_test_db] Migrations checked ({tables} tables)")

    print("[ensure_test_db] Done.")


if __name__ == "__main__":
    main()
