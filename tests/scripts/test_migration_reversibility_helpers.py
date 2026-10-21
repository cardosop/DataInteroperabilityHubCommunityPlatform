"""Tests for the pure helpers in scripts/test_migration_reversibility.py.

These pin the two defects that made the original version useless:

1. It resolved the "previous migration" by ``files.index(name)`` against
   ``os.listdir()`` output. The name carried no ``.py`` suffix while the
   listing did, so every lookup raised ``ValueError``, was swallowed into
   ``None``, and surfaced as "Could not find previous migration" — 16 of 16
   failures on a branch whose migrations were all in fact reversible.
2. It derived the Django app label from the directory name, so
   ``hub/apps/auth/`` (label ``hub_auth``) silently fell out of the check.

The database-backed behaviour is covered by the `migration-reversibility`
workflow; these tests deliberately stay import-only and fast.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "test_migration_reversibility.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("migration_reversibility", SCRIPT)
    assert spec is not None, f"cannot load {SCRIPT}"
    assert spec.loader is not None, f"cannot load {SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclasses resolve their module from sys.modules.
    sys.modules["migration_reversibility"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


class TestMigrationPathRegex:
    """The regex feeds every downstream lookup, so its output shape matters."""

    def test_matches_migration_and_strips_py_suffix(self):
        match = mod.MIGRATION_PATH_RE.match("hub/apps/files/migrations/0018_alter_file_status.py")
        assert match is not None
        assert match.group("app") == "files"
        # No ".py" — this is the label Django expects on the command line.
        assert match.group("name") == "0018_alter_file_status"

    def test_ignores_init_and_non_migration_paths(self):
        for path in (
            "hub/apps/files/migrations/__init__.py",
            "hub/apps/files/models.py",
            "scripts/whatever.py",
            "hub/apps/files/migrations/notes.txt",
        ):
            assert mod.MIGRATION_PATH_RE.match(path) is None, path

    def test_captures_directory_not_app_label(self):
        """hub/apps/auth/ is the directory; the app LABEL is hub_auth.

        The regex cannot know that, which is exactly why callers must go
        through _app_label_for_dir rather than using this value directly.
        """
        match = mod.MIGRATION_PATH_RE.match(
            "hub/apps/auth/migrations/0016_alter_apikey_last_rotation_reminder_at_and_more.py"
        )
        assert match.group("app") == "auth"


class TestPreviousInApp:
    """Reverse targets come from the dependency graph, never a filename sort."""

    class _Node:
        def __init__(self, parents):
            self.parents = parents

    class _Graph:
        def __init__(self, node_map):
            self.node_map = node_map

    class _Loader:
        def __init__(self, node_map):
            self.graph = TestPreviousInApp._Graph(node_map)

    def test_single_same_app_parent_is_the_target(self):
        loader = self._Loader({("files", "0018"): self._Node([("files", "0017")])})
        target, reason = mod._previous_in_app(loader, "files", "0018")
        assert target == "0017"
        assert reason == "graph parent"

    def test_cross_app_parents_are_ignored(self):
        """compliance.0109 depends on jobs.0026; the reverse target is same-app."""
        loader = self._Loader(
            {("compliance", "0109"): self._Node([("compliance", "0108"), ("jobs", "0026")])}
        )
        target, _ = mod._previous_in_app(loader, "compliance", "0109")
        assert target == "0108"

    def test_first_migration_reverses_to_zero(self):
        loader = self._Loader({("demo", "0001"): self._Node([("other", "0001")])})
        target, reason = mod._previous_in_app(loader, "demo", "0001")
        assert target == "zero"
        assert "first migration" in reason

    def test_merge_migration_is_skipped_not_guessed(self):
        """Two same-app parents have no single reverse target.

        Picking one would unapply more than intended, so the script must skip.
        """
        loader = self._Loader({("orch", "0009"): self._Node([("orch", "0008"), ("orch", "0007")])})
        target, reason = mod._previous_in_app(loader, "orch", "0009")
        assert target is None
        assert "merge migration" in reason

    def test_unknown_node_is_reported(self):
        loader = self._Loader({})
        target, reason = mod._previous_in_app(loader, "ghost", "0001")
        assert target is None
        assert "not in the migration graph" in reason


class TestDatabaseGuard:
    """Reversal is destructive, so a non-test database must be refused."""

    @pytest.fixture(autouse=True)
    def _fake_settings(self, monkeypatch):
        import types

        def make(name):
            fake = types.ModuleType("django.conf")
            fake.settings = types.SimpleNamespace(DATABASES={"default": {"NAME": name}})
            return fake

        self._make = make
        self._monkeypatch = monkeypatch

    def _guard(self, db_name, force=False):
        self._monkeypatch.setitem(sys.modules, "django.conf", self._make(db_name))
        return mod._guard_database(force)

    def test_test_database_is_allowed(self):
        assert self._guard("hub_test") is None
        assert self._guard("meshant_test") is None

    def test_production_database_is_refused(self):
        refusal = self._guard("meshant")
        assert refusal is not None
        assert "Refusing" in refusal

    def test_force_overrides_the_refusal(self):
        assert self._guard("meshant", force=True) is None
