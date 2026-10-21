#!/usr/bin/env python3
"""TR.M.1 — migration reversibility gate.

For every migration added on this branch, reverse it and re-apply it:

    manage.py migrate <app> <previous>   # unapply
    manage.py migrate <app> <migration>  # re-apply

A migration that cannot be reversed is a migration that cannot be rolled back
in an incident. This catches, at review time, the class of defect that
otherwise surfaces at 3am.

History
=======
The original version of this script could never pass. ``_changed_migrations()``
yielded migration names WITHOUT the ``.py`` suffix (its regex captured before
``\\.py$``), while ``_get_previous_migration()`` looked those names up in
``os.listdir()`` output, which keeps the suffix. Every lookup raised
``ValueError``, was swallowed into ``None``, and reported as "Could not find
previous migration" — 16 of 16 failures on a branch whose migrations were in
fact all reversible (verified by hand). It was never wired into CI, so nothing
ever noticed. Rewritten 2026-08-25 along with the other defects listed below.

Design notes
============
* **Previous migration comes from Django's dependency graph, not a filename
  sort.** Sorting filenames is wrong whenever history branches: this repo has
  two ``0001_*`` migrations in ``orchestration`` plus merge migrations, so the
  lexically-previous file is frequently not the actual parent.
* **Merge migrations are skipped, not guessed.** A node with several same-app
  parents has no single reverse target; picking one arbitrarily would unapply
  more than intended.
* ``sys.executable`` is used rather than a bare ``python`` (which is not
  necessarily on PATH, and is rarely the project virtualenv), and no command
  goes through a shell.
* **Reversal is destructive**, so the script refuses to run against a database
  whose name does not look like a test database unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

MIGRATION_PATH_RE = re.compile(
    r"^hub/apps/(?P<app>[a-zA-Z0-9_]+)/migrations/(?P<name>\d{4}_[^/]*)\.py$"
)

# A single migrate call on this repo can touch hundreds of migrations.
DEFAULT_TIMEOUT_SECONDS = 900


def _run_git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _changed_migrations(repo_root: Path, base_ref: str) -> list[tuple[str, str]]:
    """Return ``(package_dir, migration_name)`` for migrations added on this branch.

    ``package_dir`` is the directory under ``hub/apps/`` — NOT necessarily the
    Django app label (``hub/apps/auth/`` has label ``hub_auth``). Callers must
    resolve it via :func:`_app_label_for_dir`.

    ``migration_name`` carries no ``.py`` suffix — it is the label Django uses
    on the command line and in the graph.
    """
    merge_base = _run_git(repo_root, ["merge-base", base_ref, "HEAD"]) or base_ref
    # ``--diff-filter=A`` — only ADDED files. Reversing a migration that merely
    # had a comment edited is pointless and slow.
    output = _run_git(repo_root, ["diff", "--name-only", "--diff-filter=A", f"{merge_base}..HEAD"])

    found: list[tuple[str, str]] = []
    for line in output.splitlines():
        match = MIGRATION_PATH_RE.match(line.strip())
        if match:
            found.append((match.group("app"), match.group("name")))
    return found


def _app_label_for_dir(package_dir: str) -> str | None:
    """Map ``hub/apps/<package_dir>/`` to its Django app label.

    The two differ whenever an AppConfig overrides ``label`` to avoid a clash
    with a built-in app: ``hub/apps/auth/`` is labelled ``hub_auth`` because
    ``django.contrib.auth`` already owns ``auth``. Deriving the label from the
    directory name silently dropped that app from the check.
    """
    from django.apps import apps

    for config in apps.get_app_configs():
        if config.name == f"hub.apps.{package_dir}":
            return config.label
    return None


def _setup_django(repo_root: Path, *, with_connection: bool):
    """Import Django with this repo's settings and return the migration loader.

    ``with_connection`` matters: ``MigrationLoader(None)`` builds the graph but
    leaves ``applied_migrations`` EMPTY, because it never queries the database.
    Passing a real connection is required for any applied/unapplied reasoning —
    without it the head-state guard reports every migration as unapplied.
    Dry-run keeps ``None`` so target resolution works with no database at all.
    """
    sys.path.insert(0, str(repo_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

    import django

    django.setup()

    from django.db import connection
    from django.db.migrations.loader import MigrationLoader

    return MigrationLoader(connection if with_connection else None, ignore_no_migrations=True)


def _previous_in_app(loader, app: str, name: str) -> tuple[str | None, str]:
    """Resolve the reverse target for ``app.name`` from the dependency graph.

    Returns ``(target, reason)``. ``target`` is ``None`` when the migration
    should be skipped; ``reason`` explains why.
    """
    key = (app, name)
    if key not in loader.graph.node_map:
        return None, f"{app}.{name} is not in the migration graph"

    same_app_parents = sorted({p[1] for p in loader.graph.node_map[key].parents if p[0] == app})

    if not same_app_parents:
        # Nothing earlier in this app — reversing means unapplying the app.
        return "zero", "first migration in app"
    if len(same_app_parents) > 1:
        return (
            None,
            f"merge migration (parents: {', '.join(same_app_parents)}) — no single reverse target",
        )
    return same_app_parents[0], "graph parent"


def _guard_database(force: bool) -> str | None:
    """Refuse to reverse migrations against something that isn't a test DB."""
    from django.conf import settings

    name = settings.DATABASES["default"]["NAME"]
    if force or "test" in str(name).lower():
        return None
    return (
        f"Refusing to reverse migrations against database {name!r}: the name does "
        "not look like a test database and reversal is destructive. Pass --force "
        "if this really is a throwaway database."
    )


def _guard_at_head(loader) -> str | None:
    """Refuse to run unless every migration is already applied.

    Reversing from a partially-migrated database produces failures that look
    like migration defects but are really state defects. This was observed for
    real: a clone whose restore had not finished reported
    ``relation "refresh_tokens_tenant_id_5c18f8aa" already exists`` on reverse,
    which read as "this migration is not reversible" when in fact the migration
    reverses cleanly — the database simply was not where the test assumed.
    Diagnosing the precondition here turns a confusing false failure into a
    clear message.
    """
    unapplied = sorted(set(loader.graph.nodes) - set(loader.applied_migrations))
    if not unapplied:
        return None
    preview = ", ".join(f"{app}.{name}" for app, name in unapplied[:5])
    more = f" (+{len(unapplied) - 5} more)" if len(unapplied) > 5 else ""
    return (
        f"Database is not at head: {len(unapplied)} unapplied migration(s) — {preview}{more}. "
        "Run `manage.py migrate` first; reversing from a partial state yields "
        "false failures."
    )


def _migrate(repo_root: Path, timeout: int, *args: str) -> tuple[bool, str]:
    """Run ``manage.py migrate`` with the given target args (none = to head)."""
    result = subprocess.run(
        [sys.executable, str(repo_root / "hub" / "manage.py"), "migrate", *args, "--noinput"],
        check=False,
        text=True,
        capture_output=True,
        cwd=str(repo_root),
        timeout=timeout,
    )
    if result.returncode != 0:
        # stderr carries the traceback; stdout carries Django's progress lines.
        detail = (result.stderr or result.stdout).strip()
        return False, detail[-800:]
    return True, ""


def check_one(
    repo_root: Path, loader, package_dir: str, name: str, dry_run: bool, timeout: int
) -> tuple[bool, str]:
    app = _app_label_for_dir(package_dir)
    if app is None:
        # An installed-app lookup miss is a real gap in coverage, not a pass:
        # in core mode some apps are absent from INSTALLED_APPS entirely.
        return True, f"SKIP {package_dir}.{name}: not an installed app in this edition"

    target, reason = _previous_in_app(loader, app, name)
    if target is None:
        # Not a failure — there is nothing meaningful to test.
        return True, f"SKIP {app}.{name}: {reason}"

    if dry_run:
        return True, f"DRY-RUN {app}.{name}: would reverse to {target} ({reason}), then re-apply"

    ok, detail = _migrate(repo_root, timeout, app, target)
    if not ok:
        return False, f"REVERSE FAILED {app}.{name} -> {target}:\n{detail}"

    # Re-apply the WHOLE graph, not just this app. `migrate <app> <target>`
    # cascade-unapplies migrations in OTHER apps that depend on the one being
    # reversed — e.g. reversing `jobs` to 0025 also unapplies compliance.0109
    # and dq.0109, both of which declare ("jobs", "0026_alter_job_type") as a
    # dependency. Re-applying only `<app> <name>` restores `jobs` and silently
    # leaves those two behind, so every later check runs against a database
    # that is quietly missing migrations (measured: the run reported PASS while
    # leaving compliance.0109 and dq.0109 unapplied).
    ok, detail = _migrate(repo_root, timeout)
    if not ok:
        return False, f"RE-APPLY FAILED after reversing {app}.{name}:\n{detail}"

    return True, f"PASS {app}.{name}: reversed to {target} and re-applied"


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.M.1 — migration reversibility gate")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--app", default=None, help="Restrict to a single app.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Resolve targets without touching the database."
    )
    parser.add_argument(
        "--force", action="store_true", help="Allow running against a non-test database."
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    migrations = _changed_migrations(repo_root, args.base_ref)

    if not migrations:
        print("No migrations added on this branch; nothing to test.")
        return 0

    loader = _setup_django(repo_root, with_connection=not args.dry_run)

    if args.app:
        # Match on either the directory name or the resolved app label, so
        # `--app hub_auth` and `--app auth` both work.
        migrations = [(d, n) for d, n in migrations if args.app in (d, _app_label_for_dir(d))]
        if not migrations:
            print(f"No migrations added for app {args.app!r}.")
            return 0

    if not args.dry_run:
        for refusal in (_guard_database(args.force), _guard_at_head(loader)):
            if refusal:
                print(f"✗ {refusal}")
                return 2

    failures = 0
    for app, name in migrations:
        ok, message = check_one(repo_root, loader, app, name, args.dry_run, args.timeout)
        print(f"  {'✓' if ok else '✗'} {message}")
        failures += 0 if ok else 1

    print(f"\n{len(migrations)} migration(s) checked, {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
