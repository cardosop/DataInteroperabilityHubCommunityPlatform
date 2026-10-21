#!/usr/bin/env python3
"""Pre-flight checks for pending migrations, to be run BEFORE ``migrate`` on deploy.

Two failure modes this catches, both of which otherwise surface mid-deploy with
the schema half-changed:

**Unique constraints that the data violates.** ``AddConstraint`` with a
``UniqueConstraint`` aborts if any duplicate group exists. The migration rolls
back, but the deploy is already underway. Checking first turns a failed deploy
into a "fix the data, then deploy" decision made in advance.

**Lock exposure.** Measured against PostgreSQL 16:

    CREATE INDEX (Django AddIndex)                 -> ShareLock
        blocks INSERT/UPDATE/DELETE, SELECT still works
    ALTER TABLE ADD CONSTRAINT UNIQUE (AddConstraint) -> AccessExclusiveLock
        blocks EVERYTHING, including SELECT

Neither uses ``CONCURRENTLY``, so the lock is held for the whole build. This
script reports the row count of each affected table so the maintenance window
can be sized from data rather than from optimism.

This is a REPORTING and GATING tool — it never modifies the schema.

Usage
=====
    python scripts/preflight_migrations.py                 # gate: exit 1 on duplicates
    python scripts/preflight_migrations.py --json
    python scripts/preflight_migrations.py --warn-only     # always exit 0

Exit codes: 0 clean, 1 duplicates found (deploy would fail), 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# A table this size or larger makes a non-CONCURRENT index build worth calling out.
LARGE_TABLE_ROWS = 100_000


@dataclass
class PendingOperation:
    migration: str
    operation: str
    model: str
    table: str
    columns: list[str]
    lock: str
    approx_rows: int | None = None
    duplicate_groups: int | None = None
    condition: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def blocks_deploy(self) -> bool:
        return bool(self.duplicate_groups)


def _setup_django(repo_root: Path):
    sys.path.insert(0, str(repo_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    import django

    django.setup()


def _unapplied_migrations(loader):
    """Migrations present in the graph but not recorded as applied."""
    return sorted(set(loader.graph.nodes) - set(loader.applied_migrations))


def _columns_for(model, field_names: tuple[str, ...]) -> list[str] | None:
    """Map model field names to physical column names."""
    columns = []
    for name in field_names:
        try:
            columns.append(model._meta.get_field(name).column)
        except Exception:
            return None
    return columns


def _approx_rows(cursor, table: str) -> int | None:
    """Row count for sizing the lock window.

    Prefers the planner estimate (cheap; a real COUNT(*) on a large table is
    itself a long read). PostgreSQL 14+ reports ``reltuples = -1`` for a table
    that has never been vacuumed or analyzed — which is NOT "empty", it is
    "unknown" — so fall back to an exact count rather than reporting nothing.
    A pre-flight runs in a maintenance context, where a correct number is worth
    more than a fast one.
    """
    cursor.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = to_regclass(%s)", [table])
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return None
    if row[0] >= 0:
        return int(row[0])
    try:
        cursor.execute(f'SELECT count(*) FROM "{table}"')
        return int(cursor.fetchone()[0])
    except Exception:
        return None


def _duplicate_groups(cursor, table: str, columns: list[str], condition_sql: str | None) -> int:
    quoted = ", ".join(f'"{c}"' for c in columns)
    where = f" WHERE {condition_sql}" if condition_sql else ""
    cursor.execute(
        f'SELECT count(*) FROM (SELECT 1 FROM "{table}"{where} '
        f"GROUP BY {quoted} HAVING count(*) > 1) dupes"
    )
    return int(cursor.fetchone()[0])


def collect(repo_root: Path) -> list[PendingOperation]:
    _setup_django(repo_root)

    from django.apps import apps as django_apps
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    from django.db.models import Index, UniqueConstraint

    loader = MigrationLoader(connection, ignore_no_migrations=True)
    results: list[PendingOperation] = []

    with connection.cursor() as cursor:
        for app_label, name in _unapplied_migrations(loader):
            migration = loader.disk_migrations.get((app_label, name))
            if migration is None:
                continue

            for operation in migration.operations:
                op_name = type(operation).__name__
                if op_name not in ("AddConstraint", "AddIndex"):
                    continue

                model_name = getattr(operation, "model_name", None)
                if not model_name:
                    continue
                try:
                    model = django_apps.get_model(app_label, model_name)
                except LookupError:
                    continue

                table = model._meta.db_table
                target = getattr(operation, "constraint", None) or getattr(operation, "index", None)
                fields = tuple(getattr(target, "fields", ()) or ())
                columns = _columns_for(model, fields)

                entry = PendingOperation(
                    migration=f"{app_label}.{name}",
                    operation=op_name,
                    model=f"{app_label}.{model_name}",
                    table=table,
                    columns=columns or list(fields),
                    lock="AccessExclusiveLock" if op_name == "AddConstraint" else "ShareLock",
                )
                entry.approx_rows = _approx_rows(cursor, table)

                if entry.approx_rows and entry.approx_rows >= LARGE_TABLE_ROWS:
                    blocked = "all traffic" if op_name == "AddConstraint" else "writes"
                    entry.notes.append(
                        f"~{entry.approx_rows:,} rows and no CONCURRENTLY — {blocked} "
                        f"blocked for the whole build."
                    )

                # Only unique constraints can be violated by existing data.
                is_unique = isinstance(target, UniqueConstraint) or (
                    isinstance(target, Index) and getattr(target, "unique", False)
                )
                if is_unique and columns:
                    condition = getattr(target, "condition", None)
                    if condition is not None:
                        # Partial constraints need the predicate to scope the check,
                        # and rendering a Q object to SQL reliably is not worth the
                        # risk of a wrong answer — say so instead of guessing.
                        entry.condition = str(condition)
                        entry.notes.append(
                            "Partial constraint — duplicate check skipped; verify the "
                            "predicate subset by hand."
                        )
                    else:
                        try:
                            entry.duplicate_groups = _duplicate_groups(cursor, table, columns, None)
                        except Exception as exc:
                            entry.notes.append(f"Duplicate check could not run: {exc}")
                        if entry.duplicate_groups:
                            entry.notes.append(
                                f"{entry.duplicate_groups} duplicate group(s) — "
                                f"this migration WILL fail. Deduplicate first."
                            )

                results.append(entry)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-flight checks for pending migrations")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--warn-only", action="store_true", help="Report but always exit 0.")
    args = parser.parse_args()

    try:
        operations = collect(args.repo_root.resolve())
    except Exception as exc:
        print(f"✗ Pre-flight could not run: {type(exc).__name__}: {exc}")
        return 2

    blocking = [o for o in operations if o.blocks_deploy]

    if args.as_json:
        print(
            json.dumps(
                {
                    "status": "fail" if blocking else "ok",
                    "pending_lock_operations": len(operations),
                    "blocking": len(blocking),
                    "operations": [asdict(o) for o in operations],
                },
                indent=2,
            )
        )
        return 0 if (args.warn_only or not blocking) else 1

    if not operations:
        print("Pre-flight: no pending index/constraint operations.")
        return 0

    print(f"Pre-flight: {len(operations)} pending index/constraint operation(s).\n")
    for op in operations:
        mark = "✗" if op.blocks_deploy else "•"
        rows = f"~{op.approx_rows:,} rows" if op.approx_rows is not None else "row count unknown"
        print(f"  {mark} {op.migration}")
        print(f"      {op.operation} on {op.table} ({', '.join(op.columns)}) — {op.lock}, {rows}")
        for note in op.notes:
            print(f"      ! {note}")

    if blocking:
        print(f"\n{len(blocking)} operation(s) would FAIL against current data.")
        return 0 if args.warn_only else 1

    print("\nNo duplicate-row blockers found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
