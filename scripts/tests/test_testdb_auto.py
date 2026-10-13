"""Unit tests for scripts/testdb_auto.py (pilot-readiness task 1.2).

TDD pins for the TEST_DB=auto resolver + auto-clone manager:

* ``resolve()`` — the pure TEST_DB spec → (db, suffix) matrix, including
  the env-leak guard: a caller-supplied suffix must NEVER override the
  forced ``auto`` suffix (host shells export TEST_DB_SUFFIX=313full and
  that must not leak into compose-stack batches).
* ``ensure()`` — the clone/seed decision matrix via a fake runner.
  ``fresh=True`` (the auto-mode default: DROP + CREATE FROM TEMPLATE per
  batch invocation) is the cross-batch-state antidote: batches'
  TransactionTestCases TRUNCATE tenant_plans and usage counters
  ACCUMULATE across batches on a reused clone (observed incident:
  test-batch-6-1-all → 6-4 PLAN_NOT_FOUND, 10-4a
  max_marketplace_connections exhausted). A fresh clone per invocation
  makes every batch deterministic. The FREE-plan invariant check seeds
  ``seed_default_plans`` when the template itself is stale, and the
  postconditions fail loudly instead of silently degrading.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import testdb_auto as tdb

# ── resolve() matrix ──────────────────────────────────────────────────


class TestResolve:
    def test_auto_spec_resolves_to_auto_clone(self):
        assert tdb.resolve("auto") == ("hub_test_test_auto", "auto")

    def test_empty_spec_defaults_to_auto(self):
        assert tdb.resolve("") == ("hub_test_test_auto", "auto")

    def test_shared_spec_resolves_to_shared_db(self):
        assert tdb.resolve("shared") == ("hub_test_test_shared", "shared")

    def test_explicit_name_passes_through_with_suffix(self):
        assert tdb.resolve("hub_test_batchNN", "batchNN") == (
            "hub_test_batchNN",
            "batchNN",
        )

    def test_explicit_name_without_suffix_defaults_to_shared(self):
        assert tdb.resolve("hub_test_foo") == ("hub_test_foo", "shared")

    def test_auto_ignores_callers_suffix(self):
        """Env-leak guard: TEST_DB=auto forces suffix=auto regardless."""
        assert tdb.resolve("auto", "313full") == ("hub_test_test_auto", "auto")

    def test_shared_ignores_callers_suffix(self):
        assert tdb.resolve("shared", "313full") == (
            "hub_test_test_shared",
            "shared",
        )


# ── ensure() decision matrix ──────────────────────────────────────────


class FakeRunner:
    """Scripted stand-in for the docker-compose exec runner."""

    def __init__(self, psql_answers: list[bool]):
        self.psql_answers = list(psql_answers)
        self.psql_queries: list[tuple[str, str]] = []
        self.commands: list[list[str]] = []

    def psql_ok(self, db: str, sql: str) -> bool:
        self.psql_queries.append((db, sql))
        if not self.psql_answers:
            raise AssertionError("FakeRunner ran out of scripted psql answers")
        return self.psql_answers.pop(0)

    def run(self, argv: list[str]) -> None:
        self.commands.append(list(argv))


def test_ensure_existing_db_with_free_plan_is_noop():
    runner = FakeRunner([True, True])
    assert tdb.ensure("hub_test_test_auto", runner, fresh=False) == "exists"
    assert runner.commands == []


def test_ensure_missing_db_clones_from_template():
    runner = FakeRunner([False, True, True])
    assert tdb.ensure("hub_test_test_auto", runner, fresh=False) == "created"
    create_cmds = [c for c in runner.commands if "CREATE DATABASE" in " ".join(c)]
    assert len(create_cmds) == 1
    assert "WITH TEMPLATE hub_test" in " ".join(create_cmds[0])
    # The FREE-plan re-check ran against the clone, not postgres.
    assert runner.psql_queries[-1][0] == "hub_test_test_auto"


def test_ensure_existing_db_without_free_plan_seeds():
    runner = FakeRunner([True, False, True])
    assert tdb.ensure("hub_test_test_auto", runner, fresh=False) == "exists"
    seed_cmds = [c for c in runner.commands if "seed_default_plans" in c]
    assert len(seed_cmds) == 1
    # The seed ran against the clone's env, not the shared DB env.
    assert "-e" in seed_cmds[0]
    assert "POSTGRES_DB=hub_test_test_auto" in seed_cmds[0]
    assert "TEST_DB_SUFFIX=auto" in seed_cmds[0]


def test_ensure_missing_db_without_free_plan_clones_then_seeds():
    runner = FakeRunner([False, True, False, True])
    assert tdb.ensure("hub_test_test_auto", runner, fresh=False) == "created"
    kinds = ["CREATE DATABASE" if "CREATE DATABASE" in " ".join(c) else "seed" for c in runner.commands]
    assert kinds == ["CREATE DATABASE", "seed"]


def test_ensure_clone_postcondition_failure_raises():
    runner = FakeRunner([False, False])
    with pytest.raises(RuntimeError, match="clone"):
        tdb.ensure("hub_test_test_auto", runner, fresh=False)


def test_ensure_seed_postcondition_failure_raises():
    runner = FakeRunner([True, False, False])
    with pytest.raises(RuntimeError, match="FREE plan"):
        tdb.ensure("hub_test_test_auto", runner, fresh=False)


def test_ensure_free_plan_check_queries_slug_and_active():
    runner = FakeRunner([True, True])
    tdb.ensure("hub_test_test_auto", runner, fresh=False)
    free_sql = runner.psql_queries[1][1]
    assert "tenant_plans" in free_sql
    assert "slug='free'" in free_sql
    assert "is_active" in free_sql


def test_ensure_existence_check_queries_pg_database():
    runner = FakeRunner([True, True])
    tdb.ensure("hub_test_test_auto", runner, fresh=False)
    exists_sql = runner.psql_queries[0][1]
    assert "pg_database" in exists_sql
    assert runner.psql_queries[0][0] == "postgres"


# ── fresh=True (auto mode): DROP + CREATE per batch invocation ───────


def test_ensure_fresh_existing_db_drops_then_recreates():
    runner = FakeRunner([True, False, True, True])
    assert tdb.ensure("hub_test_test_auto", runner, fresh=True) == "recreated"
    cmds = [" ".join(c) for c in runner.commands]
    assert any("DROP DATABASE" in c and "WITH (FORCE)" in c for c in cmds)
    assert any("CREATE DATABASE" in c and "WITH TEMPLATE hub_test" in c for c in cmds)
    # Drop happens before create.
    drop_idx = next(i for i, c in enumerate(cmds) if "DROP DATABASE" in c)
    create_idx = next(i for i, c in enumerate(cmds) if "CREATE DATABASE" in c)
    assert drop_idx < create_idx


def test_ensure_fresh_missing_db_creates_without_drop():
    runner = FakeRunner([False, True, True])
    assert tdb.ensure("hub_test_test_auto", runner, fresh=True) == "recreated"
    assert not any("DROP DATABASE" in " ".join(c) for c in runner.commands)
    assert any("CREATE DATABASE" in " ".join(c) for c in runner.commands)


def test_ensure_fresh_still_enforces_free_plan_invariant():
    runner = FakeRunner([True, False, True, False, True])
    assert tdb.ensure("hub_test_test_auto", runner, fresh=True) == "recreated"
    seed_cmds = [c for c in runner.commands if "seed_default_plans" in c]
    assert len(seed_cmds) == 1


def test_ensure_fresh_drop_postcondition_failure_raises():
    runner = FakeRunner([True, True, True, False])
    with pytest.raises(RuntimeError, match="clone"):
        tdb.ensure("hub_test_test_auto", runner, fresh=True)


def test_makefile_exports_compose_project_name():
    """The compose invocations must target the RUNNING stack's project
    regardless of the checkout directory: compose infers the project name
    from the compose-file directory, so a worktree/renamed checkout would
    otherwise address a different (non-existent) project and every
    docker compose exec fails — the exact clean-checkout failure class
    this pins (pilot-1.3)."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "export COMPOSE_PROJECT_NAME" in makefile
    assert "datainteroperabilityhub" in makefile
