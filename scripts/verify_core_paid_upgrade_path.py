#!/usr/bin/env python3
"""P.3b — verify the core→paid UPGRADE path on a scratch database.

Fresh-install migration is covered by every CI run. The UPGRADE direction
is not: an existing core-only deployment that later installs the paid
layer must (a) have the guarded RunPython schema additions fire against
the PRE-EXISTING database and (b) have the paid backfill migrations copy
legacy values. A fresh full install no-ops both branches.

This script drives that path against a scratch test database (never the
shared stack):

1. ``HUB_CORE_ONLY=1`` migrate → core schema only; the paid-ward physical
   columns (``api_keys.tier_id``, ``access_requests.order_id``) MUST NOT
   exist; no paid tables exist.
2. Seed a legacy-shaped upgrade: add the legacy columns + rows WITH data
   (simulating a pre-313 full install's leftovers), plus the minimal rows
   they reference.
3. Full-mode migrate over the SAME database → the guarded additions must
   see the columns already exist (no-op on the columns), the paid tables
   appear, and the ``baas/0011`` + ``marketplace/0031`` backfills must
   COPY the legacy values into the new homes.
4. ``makemigrations --check --dry-run`` must be clean in full mode.

Usage (host-side, docker stack up):
  POSTGRES_HOST=localhost POSTGRES_PORT=54329 ... \
  venv/bin/python scripts/verify_core_paid_upgrade_path.py

The TEST_DB_SUFFIX gating trick (memory: test-infra-host-side-pytest):
settings apply the suffix DB name only when ``pytest`` is in ``sys.modules``;
plain ``manage.py migrate`` would target the shared ``hub`` DB.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

# Repo root must be importable BEFORE django.setup() resolves hub.settings.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REQUIRED_ENV = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
]

#: settings.py:659-661 — with TEST_DB_SUFFIX=p3upgrade and POSTGRES_DB=hub,
#: Django resolves the test DB name to hub_test_p3upgrade.
SCRATCH_DB = "hub_test_p3upgrade"


def _fail(message: str) -> None:
    print(f"UPGRADE-PATH FAIL: {message}")
    sys.exit(1)


def _ok(message: str) -> None:
    print(f"UPGRADE-PATH OK: {message}")


def _setup_django(core_only: bool) -> None:
    # Gate the suffix DB name the way settings expect (memory recipe).
    if "pytest" not in sys.modules:
        sys.modules["pytest"] = types.ModuleType("pytest")
    os.environ["TEST_DB_SUFFIX"] = "p3upgrade"
    os.environ["ENVIRONMENT"] = "test"
    if core_only:
        os.environ["HUB_CORE_ONLY"] = "1"
    else:
        os.environ.pop("HUB_CORE_ONLY", None)
    os.environ.setdefault("JWT_ALGORITHM", "HS256")


def _migrate(core_only: bool) -> None:
    import django

    _setup_django(core_only)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    django.setup()
    from django.conf import settings
    from django.core.management import call_command

    # Migration is a maintenance connection, not a request: the test-env
    # statement/idle timeouts (120s) kill long migrations on a loaded host
    # ("server closed the connection unexpectedly" / idle-in-transaction
    # FATAL) and the retry loop never completes — same env class the BaaS
    # verifier documents. Neutralize both for the migrate connection.
    settings.DATABASES["default"].setdefault("OPTIONS", {})["options"] = (
        "-c statement_timeout=0 -c idle_in_transaction_session_timeout=0"
    )

    call_command("migrate", interactive=False, run_syncdb=False, verbosity=0)


def _connect(dbname: str, autocommit: bool = True):
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=dbname,
    )
    if autocommit:
        # DROP/CREATE DATABASE cannot run inside a transaction block.
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def _query_admin(sql: str, params=()):
    """DDL against the base DB (dropping/creating the scratch DB)."""
    # NOTE: no `with conn` — this psycopg2's connection context manager
    # re-enters an implicit transaction, defeating ISOLATION_LEVEL_AUTOCOMMIT
    # ("DROP DATABASE cannot run inside a transaction block").
    conn = _connect(os.environ["POSTGRES_DB"])
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall() if cursor.description else None
    finally:
        conn.close()


def _query(sql: str, params=()):
    """Assertions/seed against the SCRATCH database under verification."""
    conn = _connect(SCRATCH_DB)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall() if cursor.description else None
    finally:
        conn.close()


def _migration_names_from_disk(app_dir: str) -> list[str]:
    """All migration names on disk for an app directory (drift-proof)."""
    migrations_dir = (
        Path(__file__).resolve().parent.parent / "hub" / "apps" / app_dir / "migrations"
    )
    names = []
    for path in sorted(migrations_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        if not path.name.split("_", 1)[0].isdigit():
            continue
        names.append(path.name[:-3])
    return names


def _record_applied(app_label: str, names: list[str]) -> None:
    for name in names:
        _query(
            "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, now()) "
            "ON CONFLICT DO NOTHING",
            (app_label, name),
        )


def _mark_migrations_applied(
    app_label: str, split_prefix: str, hub_app_dir: str | None = None
) -> None:
    """Record pre-split migrations as applied (legacy-upgrade simulation).

    Marks every migration whose numeric prefix is BEFORE the split point —
    the same rows a real pre-upgrade install would carry. Migrations at/after
    the split stay unapplied so the full-mode migrate runs them.
    """
    app_dir = hub_app_dir or app_label
    split_number = int(split_prefix)
    names = [
        name
        for name in _migration_names_from_disk(app_dir)
        if int(name.split("_", 1)[0]) < split_number
    ]
    if not names:
        _fail(f"no pre-split migrations found for {app_label}")
    _record_applied(app_label, names)


def _mark_migrations_applied_from(
    app_label: str, from_prefix: str, hub_app_dir: str | None = None
) -> None:
    """Mark migrations at/after a prefix as applied (skip-set helper)."""
    app_dir = hub_app_dir or app_label
    from_number = int(from_prefix)
    names = [
        name
        for name in _migration_names_from_disk(app_dir)
        if int(name.split("_", 1)[0]) >= from_number
    ]
    _record_applied(app_label, names)


def _mark_all_other_migrations_applied(exclude_apps: set[str]) -> None:
    """Mark every migration of every OTHER installed app as applied.

    The minimal legacy seed creates only the tables the backfill/guarded
    migrations touch; the remaining apps' migrations (including the newer
    drift migrations) must not run against tables that do not exist in
    this simulation — they are proven separately by the shared-DB upgrade
    migrate. App label ↔ directory mapping follows hub/apps layout with
    the known label differences (auth → hub_auth).
    """
    apps_root = Path(__file__).resolve().parent.parent / "hub" / "apps"
    label_overrides = {"auth": "hub_auth"}
    for app_dir in sorted(p.name for p in apps_root.iterdir() if p.is_dir()):
        label = label_overrides.get(app_dir, app_dir)
        if label in exclude_apps:
            continue
        migrations_dir = apps_root / app_dir / "migrations"
        if not migrations_dir.is_dir():
            continue
        names = _migration_names_from_disk(app_dir)
        if names:
            _record_applied(label, names)


def _seed_tenant() -> str:
    """Insert a minimal tenant row using the LIVE schema's NOT NULL columns.

    Drift-proof: values are synthesized by column type, never hand-listed
    (the tenants table gains required columns over phases).
    """
    import uuid as uuid_mod

    rows = _query(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='tenants' AND is_nullable='NO' AND column_default IS NULL "
        "ORDER BY ordinal_position"
    )
    values = {}
    for name, raw_data_type in rows:
        data_type = str(raw_data_type).lower()
        if name in ("id",):
            values[name] = f"'{uuid_mod.uuid4()}'"
        elif data_type == "uuid":
            values[name] = "gen_random_uuid()"
        elif "timestamp" in data_type:
            values[name] = "now()"
        elif data_type in ("integer", "bigint", "smallint", "numeric"):
            values[name] = "0"
        elif data_type == "boolean":
            values[name] = "false"
        elif "json" in data_type:
            values[name] = "'{}'::jsonb"
        elif "array" in data_type:
            values[name] = "'{}'"
        else:
            values[name] = "'seed'"
    values["name"] = "'Seed Tenant'"
    values["slug"] = f"'seed-{uuid_mod.uuid4().hex[:8]}'"
    values["status"] = "'ACTIVE'"
    values["kyc_status"] = "'UNVERIFIED'"
    columns = ", ".join(values)
    placeholders = ", ".join(values[name] for name in values)
    _query(f"INSERT INTO tenants ({columns}) VALUES ({placeholders})")
    return _query("SELECT id FROM tenants LIMIT 1")[0][0]


def _column_exists(table: str, column: str) -> bool:
    rows = _query(
        "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
        (table, column),
    )
    return bool(rows)


def _table_exists(table: str) -> bool:
    rows = _query("SELECT 1 FROM information_schema.tables WHERE table_name=%s", (table,))
    return bool(rows)


def _run_migrate_subprocess(core_only: bool) -> None:
    """Run a migrate phase in a CLEAN process.

    Both modes cannot share one process: ``django.setup()`` populates the
    app registry ONCE, so a second setup() with a different HUB_CORE_ONLY
    is a no-op and the "full-mode" migrate would silently use the core-only
    registry (paid migrations never discovered — measured in run 11).
    """
    import subprocess

    core_flag = "1" if core_only else "0"
    code = (
        "import os, sys, types; "
        "sys.modules['pytest'] = types.ModuleType('pytest'); "
        "os.environ['TEST_DB_SUFFIX'] = 'p3upgrade'; "
        "os.environ['HUB_CORE_ONLY'] = '" + core_flag + "'; "
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE','hub.settings'); "
        "import django; django.setup(); "
        "from django.conf import settings; "
        "settings.DATABASES['default'].setdefault('OPTIONS', {})['options'] = "
        "'-c statement_timeout=0 -c idle_in_transaction_session_timeout=0'; "
        "from django.core.management import call_command; "
        "call_command('migrate', interactive=False, run_syncdb=False, verbosity=0); "
        "print('MIGRATE-SUBPROCESS-DONE')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=dict(os.environ),
        timeout=3600,
    )
    if result.returncode != 0 or "MIGRATE-SUBPROCESS-DONE" not in result.stdout:
        _fail(
            f"migrate subprocess failed (core_only={core_only}):\n"
            f"stdout={result.stdout[-800:]}\nstderr={result.stderr[-800:]}"
        )


def main() -> None:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        _fail(f"missing env: {missing}")

    # Recreate the scratch DB from zero for a deterministic run.
    _query_admin(f"DROP DATABASE IF EXISTS {SCRATCH_DB} WITH (FORCE)")
    _query_admin(f"CREATE DATABASE {SCRATCH_DB} OWNER {os.environ['POSTGRES_USER']}")

    # ── Phase 1: core-only migration (clean subprocess) ─────────────────
    _run_migrate_subprocess(core_only=True)
    _ok("core-only migrate completed")
    if _column_exists("api_keys", "tier_id"):
        _fail("core-only DB must NOT have api_keys.tier_id")
    _ok("api_keys.tier_id absent in core-only")
    if _column_exists("access_requests", "order_id"):
        _fail("core-only DB must NOT have access_requests.order_id")
    _ok("access_requests.order_id absent in core-only")
    for paid_table in ("baas_api_key_tier_assignments", "marketplace_listings", "orders"):
        if _table_exists(paid_table):
            _fail(f"core-only DB must NOT have paid table {paid_table}")
    _ok("no paid tables in core-only DB")

    # ── Phase 2: legacy-shaped upgrade seed ──────────────────────────────
    # Simulate a pre-313 full install: the paid apps' PRE-split migrations
    # are already applied (recorded in django_migrations) and their tables
    # exist with data. The post-split paid migrations that remain are
    # exactly 0011 (baas) / 0031 (marketplace) — the backfill migrations.
    # The legacy simulation marks every project migration applied EXCEPT the
    # set this verifier exists to exercise: the guarded column adds
    # (hub_auth/0004+, governance/0005+) and the two paid backfills
    # (baas/0011+, marketplace/0031 ONLY — later marketplace migrations
    # target tables outside the minimal legacy seed's scope and are proven
    # by the shared-DB upgrade migrate instead). Everything else must be
    # marked applied or the full-mode migrate would run the newer drift
    # migrations against tables the minimal seed does not create.
    _mark_migrations_applied("hub_auth", split_prefix="0004", hub_app_dir="auth")
    _mark_migrations_applied("governance", split_prefix="0005")
    _mark_migrations_applied("baas", split_prefix="0011")
    _mark_migrations_applied("marketplace", split_prefix="0031")
    # marketplace 0032/0033 target tables outside the minimal legacy seed's
    # scope — mark them applied too, leaving exactly 0031 (the backfill) to
    # run here; those migrations are proven by the shared-DB upgrade migrate.
    _mark_migrations_applied_from("marketplace", from_prefix="0032")
    _mark_all_other_migrations_applied(
        exclude_apps={"hub_auth", "governance", "baas", "marketplace"}
    )
    # Legacy tables the backfill migrations need:
    # baas_api_tier — the FK target of baas/0011's assignment table.
    if not _table_exists("baas_api_tier"):
        _query("CREATE TABLE baas_api_tier (id uuid PRIMARY KEY, name varchar(255) NOT NULL)")
    _query(
        "INSERT INTO baas_api_tier (id, name) "
        "VALUES (gen_random_uuid(), 'LEGACY_TIER') ON CONFLICT DO NOTHING"
    )
    legacy_tier_id = _query("SELECT id FROM baas_api_tier WHERE name='LEGACY_TIER'")[0][0]
    # orders — the table marketplace/0031 adds its column to.
    if not _table_exists("orders"):
        _query(
            "CREATE TABLE orders ("
            "id uuid PRIMARY KEY, tenant_id uuid, listing_id uuid, "
            "status varchar(32) NOT NULL DEFAULT 'REQUESTED', "
            "created_by_id uuid)"
        )
    # The physical paid-ward columns with legacy data.
    _query("ALTER TABLE api_keys ADD COLUMN tier_id uuid")
    _query("ALTER TABLE access_requests ADD COLUMN order_id uuid")
    # A key row with a legacy tier assignment. Copy the column list from an
    # existing api_keys row (INSERT … SELECT) so the seed never drifts from
    # the real model schema — only key_hash/name/scopes/tier_id override.
    tenant_id = (
        _query("SELECT id FROM tenants LIMIT 1")[0][0]
        if _query("SELECT id FROM tenants LIMIT 1")
        else _seed_tenant()
    )
    source_key = _query("SELECT id FROM api_keys WHERE tenant_id=%s LIMIT 1", (tenant_id,))
    if not source_key:
        # Fresh core-only DB has no key rows either — seed one from the
        # live NOT NULL columns, same drift-proof synthesis as the tenant.
        import uuid as uuid_mod

        key_rows = _query(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='api_keys' AND is_nullable='NO' "
            "AND column_default IS NULL ORDER BY ordinal_position"
        )
        key_values = {}
        for name, raw_data_type in key_rows:
            data_type = str(raw_data_type).lower()
            if name == "id":
                key_values[name] = f"'{uuid_mod.uuid4()}'"
            elif data_type == "uuid":
                key_values[name] = f"'{tenant_id}'" if name == "tenant_id" else "gen_random_uuid()"
            elif "timestamp" in data_type:
                key_values[name] = "now()"
            elif data_type in ("integer", "bigint", "smallint"):
                key_values[name] = "0"
            elif data_type == "boolean":
                key_values[name] = "false"
            elif "json" in data_type:
                key_values[name] = "'{}'::jsonb"
            elif "array" in data_type:
                key_values[name] = "'{}'"
            else:
                key_values[name] = "'seed-key'"
        key_values["key_hash"] = "'legacy-hash'"
        key_values["name"] = "'Legacy key'"
        _query(
            f"INSERT INTO api_keys ({', '.join(key_values)}) "
            f"VALUES ({', '.join(key_values[n] for n in key_values)})"
        )
        _query(
            "UPDATE api_keys SET tier_id=%s WHERE key_hash='legacy-hash'",
            (legacy_tier_id,),
        )
    else:
        columns = [
            row[0]
            for row in _query(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='api_keys' ORDER BY ordinal_position"
            )
        ]
        copied = [c for c in columns if c not in ("id", "key_hash", "name", "scopes", "tier_id")]
        _query(
            f"INSERT INTO api_keys (id, {', '.join(copied)}, key_hash, name, scopes, tier_id) "
            f"SELECT gen_random_uuid(), {', '.join(copied)}, 'legacy-hash', 'Legacy key', '[]', %s "
            f"FROM api_keys WHERE id=%s",
            (legacy_tier_id, source_key[0][0]),
        )
    # marketplace/0031 backfill seed: an Order row + an access_request whose
    # legacy order_id column points at it — the pre-313 link direction.
    _query(
        "INSERT INTO orders (id, tenant_id, status) VALUES (gen_random_uuid(), %s, 'REQUESTED')",
        (tenant_id,),
    )
    legacy_order_id = _query("SELECT id FROM orders LIMIT 1")[0][0]
    # Seed an access_request row (drift-proof synthesis) then set its
    # legacy order_id column to the order id. Its NOT NULL FK columns
    # (requested_by_id → users, tenant_id → tenants) must reference real
    # rows — seed a users row first.
    user_rows = _query(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='users' AND is_nullable='NO' "
        "AND column_default IS NULL ORDER BY ordinal_position"
    )
    user_values = {}
    import uuid as uuid_mod3

    for name, raw_data_type in user_rows:
        data_type = str(raw_data_type).lower()
        if name == "id":
            user_values[name] = f"'{uuid_mod3.uuid4()}'"
        elif data_type == "uuid":
            user_values[name] = f"'{tenant_id}'" if name in ("tenant_id",) else "gen_random_uuid()"
        elif "timestamp" in data_type:
            user_values[name] = "now()"
        elif data_type in ("integer", "bigint", "smallint"):
            user_values[name] = "0"
        elif data_type == "boolean":
            user_values[name] = "false"
        elif "json" in data_type:
            user_values[name] = "'{}'::jsonb"
        elif "array" in data_type:
            user_values[name] = "'{}'"
        else:
            user_values[name] = "'seed-user@meshant.test'"
    user_values["status"] = "'ACTIVE'"
    _query(
        f"INSERT INTO users ({', '.join(user_values)}) "
        f"VALUES ({', '.join(user_values[n] for n in user_values)})"
    )
    seed_user_id = _query("SELECT id FROM users LIMIT 1")[0][0]

    ar_rows = _query(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='access_requests' AND is_nullable='NO' "
        "AND column_default IS NULL ORDER BY ordinal_position"
    )
    ar_values = {}
    import uuid as uuid_mod2

    for name, raw_data_type in ar_rows:
        data_type = str(raw_data_type).lower()
        if name == "id":
            ar_values[name] = f"'{uuid_mod2.uuid4()}'"
        elif data_type == "uuid":
            ar_values[name] = (
                f"'{tenant_id}'"
                if name == "tenant_id"
                else f"'{seed_user_id}'"
                if name == "requested_by_id"
                else f"'{legacy_order_id}'"
                if name == "order_id"
                else "gen_random_uuid()"
            )
        elif "timestamp" in data_type:
            ar_values[name] = "now()"
        elif data_type in ("integer", "bigint", "smallint"):
            ar_values[name] = "0"
        elif data_type == "boolean":
            ar_values[name] = "false"
        elif "json" in data_type:
            ar_values[name] = "'{}'::jsonb"
        elif "array" in data_type:
            ar_values[name] = "'{}'"
        else:
            ar_values[name] = "'seed'"
    ar_values["status"] = "'PENDING'"
    _query(
        f"INSERT INTO access_requests ({', '.join(ar_values)}) "
        f"VALUES ({', '.join(ar_values[n] for n in ar_values)})"
    )
    # The legacy link itself: order_id is a nullable added column (the
    # drift-proof seeder only fills NOT NULL columns), set it explicitly —
    # this is the value marketplace/0031's backfill must copy.
    seed_ar_id = _query("SELECT id FROM access_requests LIMIT 1")[0][0]
    _query(
        "UPDATE access_requests SET order_id=%s WHERE id=%s",
        (legacy_order_id, seed_ar_id),
    )
    _ok("legacy columns + seed rows in place")

    # ── Phase 3: full-mode migration over the SAME database ─────────────
    _run_migrate_subprocess(core_only=False)
    _ok("full-mode migrate completed over the core-only DB")
    if not _column_exists("api_keys", "tier_id"):
        _fail("full-mode upgrade must keep the legacy api_keys.tier_id column")
    _ok("legacy api_keys.tier_id preserved")
    if not _table_exists("baas_api_key_tier_assignments"):
        _fail("baas/0011 must create the assignment table on upgrade")
    assignments = _query(
        "SELECT count(*) FROM baas_api_key_tier_assignments a "
        "JOIN api_keys k ON k.id = a.api_key_id WHERE k.key_hash='legacy-hash'"
    )
    if assignments[0][0] != 1:
        _fail(f"baas/0011 backfill must copy the legacy tier (got {assignments[0][0]})")
    _ok("baas/0011 backfill copied the legacy tier")
    if not _table_exists("orders"):
        _fail("marketplace tables must exist after full-mode upgrade")
    if not _column_exists("orders", "access_request_id"):
        _fail("marketplace Order.access_request must exist after upgrade")
    copied = _query(
        "SELECT count(*) FROM orders o "
        "JOIN access_requests ar ON ar.id = o.access_request_id "
        "WHERE o.id = %s",
        (legacy_order_id,),
    )
    if copied[0][0] != 1:
        _fail(
            f"marketplace/0031 backfill must copy the legacy order link "
            f"(got {copied[0][0]} rows for the seeded order)"
        )
    _ok("marketplace/0031 backfill copied the legacy access-request link")

    # ── Phase 4: makemigrations cleanliness ─────────────────────────────
    import django

    _setup_django(core_only=False)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    django.setup()
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("makemigrations", dry_run=True, check=True, stdout=out, verbosity=1)
    output = out.getvalue()
    if "No changes detected" not in output and "no changes" not in output.lower():
        _fail(f"makemigrations --check not clean: {output[:400]}")
    _ok("makemigrations --check clean in full mode")

    print("UPGRADE-PATH: all assertions passed")


if __name__ == "__main__":
    main()
