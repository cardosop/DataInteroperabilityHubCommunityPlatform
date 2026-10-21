"""Tests for scripts/check_migration_state_sync.py.

The lint exists because ``SeparateDatabaseAndState(database_operations=[...],
state_operations=[])`` silently desynchronises Django's migration state from
the database, which is how this repo accumulated 70 pending operations across
16 apps (four of them destructive). These tests pin both directions: the
pattern must fail, and the legitimate shapes must not.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_migration_state_sync.py"


def _write_migration(tmp_path: Path, body: str) -> Path:
    migrations = tmp_path / "hub" / "apps" / "demo" / "migrations"
    migrations.mkdir(parents=True, exist_ok=True)
    path = migrations / "0001_demo.py"
    path.write_text(body, encoding="utf-8")
    return path


def _run(tmp_path: Path, path: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path), "--json", str(path)],
        check=False,
        text=True,
        capture_output=True,
    )
    # --json must emit JSON and nothing else, so CI can pipe it.
    return proc.returncode, json.loads(proc.stdout)


DDL_WITHOUT_STATE = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL("ALTER TABLE demo ADD COLUMN c varchar(9)"),
            ],
            state_operations=[],
        ),
    ]
"""

DDL_WITH_STATE = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL("ALTER TABLE demo ADD COLUMN c varchar(9)"),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="demo", name="c", field=models.CharField(max_length=9),
                ),
            ],
        ),
    ]
"""

STATE_ONLY = """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="demo", name="c", field=models.CharField(max_length=9),
                ),
            ],
        ),
    ]
"""

# RLS / GRANT / EXTENSION SQL does not affect Django's model state, so it must
# not be reported — a false positive here would make the gate unusable, since
# this repo pairs every tenant-scoped model with an RLS policy migration.
RLS_POLICY = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE demo ENABLE ROW LEVEL SECURITY;",
            reverse_sql="ALTER TABLE demo DISABLE ROW LEVEL SECURITY;",
        ),
    ]
"""

# Prose mentioning DDL must not be matched. The older regex-based linter
# flagged docstrings like this as "irreversible data loss".
PROSE_ONLY = '''
"""This migration explains why we avoid DROP COLUMN and ALTER COLUMN TYPE."""
from django.db import migrations

class Migration(migrations.Migration):
    # RENAME TO is also mentioned here, in a comment.
    operations = []
'''

# The reverse direction is *supposed* to drop what forward created.
REVERSE_DROP = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="SELECT 1",
                    reverse_sql="ALTER TABLE demo DROP COLUMN c",
                ),
            ],
            state_operations=[
                migrations.RunSQL.noop,
            ],
        ),
    ]
"""


def test_ddl_without_state_is_blocked(tmp_path):
    code, report = _run(tmp_path, _write_migration(tmp_path, DDL_WITHOUT_STATE))
    assert code == 1
    assert report["status"] == "fail"
    assert [f["rule"] for f in report["findings"]] == ["state-not-recorded"]


def test_ddl_with_state_is_allowed(tmp_path):
    code, report = _run(tmp_path, _write_migration(tmp_path, DDL_WITH_STATE))
    assert code == 0, report
    assert report["errors"] == 0


def test_state_only_migration_is_allowed(tmp_path):
    """The corrected shape of transformation/0017 — no DDL, state only."""
    code, report = _run(tmp_path, _write_migration(tmp_path, STATE_ONLY))
    assert code == 0, report
    assert report["findings"] == []


def test_rls_policy_sql_is_not_flagged(tmp_path):
    code, report = _run(tmp_path, _write_migration(tmp_path, RLS_POLICY))
    assert code == 0, report
    assert report["findings"] == []


def test_prose_mentioning_ddl_is_not_flagged(tmp_path):
    code, report = _run(tmp_path, _write_migration(tmp_path, PROSE_ONLY))
    assert code == 0, report
    assert report["findings"] == []


def test_reverse_sql_drop_is_not_flagged(tmp_path):
    code, report = _run(tmp_path, _write_migration(tmp_path, REVERSE_DROP))
    assert code == 0, report
    assert report["errors"] == 0


def test_bare_runsql_ddl_is_warned_not_errored(tmp_path):
    body = """
from django.db import migrations

class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL(sql="ALTER TABLE demo ADD COLUMN c varchar(9)"),
    ]
"""
    code, report = _run(tmp_path, _write_migration(tmp_path, body))
    assert code == 0, "warnings must not block"
    assert [f["rule"] for f in report["findings"]] == ["ddl-outside-state"]


def test_real_repo_is_clean():
    """The committed tree must stay clean, so the gate can be blocking."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT), "--all", "--json"],
        check=False,
        text=True,
        capture_output=True,
    )
    report = json.loads(proc.stdout)
    assert proc.returncode == 0, [f for f in report["findings"] if f["severity"] == "error"]
