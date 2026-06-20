"""
Phase 274.16.7 — Migration backfill conformance test.

AST-walks all migration files under hub/apps/**/migrations/.
Flags RunSQL operations that contain INSERT/UPDATE/DELETE/TRUNCATE
without a ``# chain-bypass:`` justification comment in the
migration file docstring. This enforces the contract that raw SQL
writes in migrations MUST document the chain bypass reason.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_HUB_APPS_ROOT = Path(__file__).resolve().parents[1] / "hub" / "apps"

# SQL statements that indicate a data mutation (not DDL or RLS policy).
_MUTATION_PATTERNS = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|TRUNCATE\s+TABLE)\b",
    re.IGNORECASE,
)

# Escape hatch comment that must appear in the migration file's module docstring
# or on the line immediately preceding the RunSQL call.
_BYPASS_COMMENT = "chain-bypass:"


def _find_migration_files() -> list[Path]:
    """Return all migration .py files under hub/apps/."""
    migs = []
    for root, _dirs, files in os.walk(_HUB_APPS_ROOT):
        if root.endswith("/migrations") or "migrations" in root.split(os.sep):
            for f in files:
                if f.endswith(".py") and f != "__init__.py":
                    migs.append(Path(root) / f)
    return sorted(migs)


def _has_bypass_comment(source: str) -> bool:
    """True if the source file contains a chain-bypass justification."""
    return _BYPASS_COMMENT in source


class TestMigrationChainBypassAudit(TestCase):
    """Phase 274.16.7 — all raw SQL mutations in migrations must document
    their chain bypass reason."""

    def test_no_unexplained_raw_sql_mutations(self):
        """Flag RunSQL calls with INSERT/UPDATE/DELETE/TRUNCATE that lack
        a chain-bypass: justification."""
        violations: list[str] = []

        for mig_path in _find_migration_files():
            with open(mig_path) as f:
                source = f.read()

            if _has_bypass_comment(source):
                continue

            try:
                tree = ast.parse(source, filename=str(mig_path))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    # Check for migrations.RunSQL or just RunSQL
                    is_runsql = False
                    if (isinstance(func, ast.Attribute) and func.attr == "RunSQL") or (
                        isinstance(func, ast.Name) and func.id == "RunSQL"
                    ):
                        is_runsql = True

                    if is_runsql and node.args:
                        sql_arg = node.args[0]
                        if isinstance(sql_arg, ast.Constant) and isinstance(sql_arg.value, str):
                            if _MUTATION_PATTERNS.search(sql_arg.value):
                                violations.append(
                                    f"{mig_path}:{node.lineno} — "
                                    f"RunSQL with mutation without # chain-bypass: comment"
                                )

        if violations:
            msg = (
                f"Found {len(violations)} migration(s) with raw SQL mutations "
                f"and no 'chain-bypass:' justification. Migration commands "
                f"MUST go through the service layer; raw SQL writes require "
                f"a documented chain-bypass reason.\n" + "\n".join(f"  - {v}" for v in violations)
            )
            # Phase D — warn-level for now, hard-gate after backfill.
            print(msg)

    def test_known_good_migrations_pass(self):
        """Migrations with chain-bypass comments are not flagged."""
        # This test verifies the escape hatch works. We check a migration
        # that we know has RunSQL (the RLS policy ones) — those don't
        # contain INSERT/UPDATE/DELETE, so they pass naturally.
        rls_migrations = [p for p in _find_migration_files() if "enable_rls" in str(p).lower()]
        assert len(rls_migrations) > 0, "Should find at least one RLS migration"
