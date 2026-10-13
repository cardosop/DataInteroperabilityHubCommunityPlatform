#!/usr/bin/env python3
"""TEST_DB=auto resolver + auto-clone manager (pilot-readiness task 1.2).

The DB-only ``test-batch-*`` Makefile targets default to ``TEST_DB=auto``,
resolved to the per-machine clone ``hub_test_test_auto``. This script is
the single implementation behind three surfaces:

* ``--resolve SPEC [SUFFIX]`` — pure resolution to ``(db, suffix)``
  (used by the Makefile at parse time; pinned by the unit tests);
* ``--ensure DB`` — idempotent clone from the ``hub_test`` template for
  an explicit session DB (``make test-db-clone`` delegates here);
* ``--recreate DB`` — DROP + CREATE FROM TEMPLATE: the AUTO-mode default.
  One fresh clone per batch invocation is the antidote to cross-batch
  state on a reused clone — batches' TransactionTestCases TRUNCATE
  ``tenant_plans`` and usage counters ACCUMULATE across batches
  (observed incidents: 6-1-all → 6-4 PLAN_NOT_FOUND; 10-4a
  ``max_marketplace_connections`` exhausted).

Both ensure paths enforce the FREE-plan invariant: when the clone (or a
stale template) has no active ``slug='free'`` plan, ``seed_default_plans``
runs inside the api-service-test container against the clone's env, and
a postcondition check fails loudly instead of letting the next batch
degrade into plan-limit errors.

Pure logic lives in module-level functions so
``scripts/tests/test_testdb_auto.py`` pins every branch without docker.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Protocol

AUTO_DB_NAME = "hub_test_test_auto"
AUTO_SUFFIX = "auto"
SHARED_DB_NAME = "hub_test_test_shared"
SHARED_SUFFIX = "shared"
TEMPLATE_DB = "hub_test"
COMPOSE_FILE = "docker-compose.test.yml"
POSTGRES_SERVICE = "postgres-test"
POSTGRES_USER = "hub_test"
API_SERVICE = "api-service-test"


def resolve(spec: str, suffix: str = "") -> tuple[str, str]:
    """Resolve a TEST_DB spec to ``(db_name, suffix)``. Empty spec = auto.

    ``auto`` and ``shared`` FORCE their suffix regardless of the caller's
    value — a host shell that exports ``TEST_DB_SUFFIX`` (the host-side
    pytest recipe uses ``313full``) must never leak into compose-stack
    batches.
    """
    spec = (spec or "").strip()
    if spec in ("", "auto"):
        return AUTO_DB_NAME, AUTO_SUFFIX
    if spec == "shared":
        return SHARED_DB_NAME, SHARED_SUFFIX
    return spec, (suffix or SHARED_SUFFIX).strip()


def suffix_for(db_name: str) -> str:
    """The TEST_DB_SUFFIX that mirrors a resolved database name."""
    if "_test_" in db_name:
        return db_name.rsplit("_test_", 1)[-1]
    return SHARED_SUFFIX


class Runner(Protocol):
    """docker-compose exec abstraction; unit tests inject a fake."""

    def psql_ok(self, db: str, sql: str) -> bool: ...

    def run(self, argv: list[str]) -> None: ...


class DockerRunner:
    """Real runner: docker compose exec against the test stack."""

    def psql_ok(self, db: str, sql: str) -> bool:
        proc = subprocess.run(
            [
                "docker", "compose", "-f", COMPOSE_FILE, "exec", "-T",
                POSTGRES_SERVICE, "psql", "-U", POSTGRES_USER, "-d", db,
                "-tAc", sql,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "1"

    def run(self, argv: list[str]) -> None:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"command failed ({proc.returncode}): {' '.join(argv)}\n"
                f"stderr: {proc.stderr.strip()[:2000]}"
            )


def _exists_sql(db_name: str) -> str:
    return f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"


def _free_plan_sql() -> str:
    return "SELECT 1 FROM tenant_plans WHERE slug='free' AND is_active"


def _clone_cmd(db_name: str) -> list[str]:
    return [
        "docker", "compose", "-f", COMPOSE_FILE, "exec", "-T",
        POSTGRES_SERVICE, "psql", "-U", POSTGRES_USER, "-d", "postgres", "-c",
        f'CREATE DATABASE "{db_name}" WITH TEMPLATE {TEMPLATE_DB} ENCODING \'UTF8\'',
    ]


def _drop_cmd(db_name: str) -> list[str]:
    return [
        "docker", "compose", "-f", COMPOSE_FILE, "exec", "-T",
        POSTGRES_SERVICE, "psql", "-U", POSTGRES_USER, "-d", "postgres", "-c",
        f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)',
    ]


def _seed_plans_cmd(db_name: str) -> list[str]:
    return [
        "docker", "compose", "-f", COMPOSE_FILE, "exec", "-T",
        "-e", f"POSTGRES_DB={db_name}",
        "-e", f"TEST_DB_SUFFIX={suffix_for(db_name)}",
        API_SERVICE, "python", "manage.py", "seed_default_plans",
    ]


def ensure(
    db_name: str, runner: Runner | None = None, *, fresh: bool = False
) -> str:
    """Ensure ``db_name`` exists with a FREE plan.

    Returns ``"exists"`` (already there), ``"created"`` (cloned), or
    ``"recreated"`` (fresh mode). Raises ``RuntimeError`` when a
    postcondition does not materialize — never silently degrades.
    """
    runner = runner or DockerRunner()

    exists = runner.psql_ok("postgres", _exists_sql(db_name))
    if fresh and exists:
        runner.run(_drop_cmd(db_name))
        if runner.psql_ok("postgres", _exists_sql(db_name)):
            raise RuntimeError(
                f"auto-clone drop failed: {db_name} still exists after "
                "DROP DATABASE WITH (FORCE) — a live connection may be pinned"
            )
        exists = False

    created = False
    if not exists:
        runner.run(_clone_cmd(db_name))
        if not runner.psql_ok("postgres", _exists_sql(db_name)):
            raise RuntimeError(
                f"auto-clone failed: {db_name} was not created — the "
                f"{TEMPLATE_DB} template may be busy (another session is "
                "cloning or running against it); stop that session first"
            )
        created = True

    if not runner.psql_ok(db_name, _free_plan_sql()):
        runner.run(_seed_plans_cmd(db_name))
        if not runner.psql_ok(db_name, _free_plan_sql()):
            raise RuntimeError(
                f"seed_default_plans did not restore the FREE plan on "
                f"{db_name} — inspect the api-service-test container logs"
            )

    if fresh:
        return "recreated"
    return "created" if created else "exists"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="testdb_auto.py",
        description="TEST_DB=auto resolver and auto-clone manager",
    )
    parser.add_argument(
        "--resolve", nargs="+", metavar=("SPEC", "SUFFIX"),
        help="print '<db> <suffix>' for a TEST_DB spec (pure, no docker)",
    )
    parser.add_argument(
        "--ensure", metavar="DB",
        help="clone DB from the hub_test template if missing (explicit-session DBs)",
    )
    parser.add_argument(
        "--recreate", metavar="DB",
        help="DROP + recreate DB from the hub_test template (auto-mode default)",
    )
    args = parser.parse_args(argv)

    if args.resolve:
        spec = args.resolve[0]
        suffix = args.resolve[1] if len(args.resolve) > 1 else ""
        db, resolved_suffix = resolve(spec, suffix)
        print(f"{db} {resolved_suffix}")
        return 0

    if args.ensure:
        status = ensure(args.ensure, fresh=False)
        print(f"{args.ensure} {status} from {TEMPLATE_DB}.")
        if status == "created":
            print(
                f"Ready. Run batches with: DB={args.ensure} "
                f"TEST_DB_SUFFIX={suffix_for(args.ensure)}"
            )
        return 0

    if args.recreate:
        status = ensure(args.recreate, fresh=True)
        print(f"{args.recreate} {status} from {TEMPLATE_DB}.")
        return 0

    parser.error("one of --resolve, --ensure, --recreate is required")
    return 2


if __name__ == "__main__":
    sys.exit(main())
