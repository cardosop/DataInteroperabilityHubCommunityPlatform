"""pilot-readiness 4.4 — the DR restore drill executed FOR REAL.

This is the "disaster_recovery suite as a REAL drill" leg: it drives
``scripts/dr/dr_restore_drill.sh`` against the live compose stack's Postgres —
a real pg_dump (custom format), a real SHA-256 integrity gate, a real
pg_restore into a scratch database, real row-count parity against the live
database, the scratch drop, and the written drill report under
``docs/operations/dr-drill-reports/``. The tamper test rehearses the
failure path: a corrupted manifest MUST refuse the restore (exit 3).

Opt-in: the drill takes a real dump/restore cycle of the shared database, so
it runs only under ``make dr-drill`` (RUN_REAL_DR_DRILL=1). W16 policy: once
opted in, an unreachable stack SKIPS locally and RAISES in CI — a drill that
cannot run must never silently pass.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from envpolicy import skip_or_fail

REPO_ROOT = Path(__file__).resolve().parents[2]
DRILL_SCRIPT = REPO_ROOT / "scripts" / "dr" / "dr_restore_drill.sh"
BACKUP_DIR = REPO_ROOT / "backups" / "dr-drill"
REPORT_ROOT = REPO_ROOT / "docs" / "operations" / "dr-drill-reports"

# The shared test-stack database (live data, real tenants/users/audit rows).
DRILL_DB = os.environ.get("DR_DRILL_DB", "hub_test_test_shared")
DRILL_SERVICE = os.environ.get("DR_DRILL_SERVICE", "postgres-test")
DRILL_ENV_FILE = os.environ.get("DR_DRILL_ENV_FILE", ".env.test")
# The compose project the running stack was brought up under. Host runs
# derive `datainteroperabilityhub` from the checkout path; inside the api
# container the same cwd is /app and the derivation differs — the pin makes
# the drill reach the real stack from either side.
DRILL_PROJECT = os.environ.get("DR_DRILL_PROJECT", "datainteroperabilityhub")

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RUN_REAL_DR_DRILL") != "1",
        reason="opt-in real drill — run `make dr-drill`",
    ),
]

DEFAULT_PARITY_TABLES = ["tenants", "users", "audit_events", "files", "assets"]


def _drill(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **(env or {})}
    cmd = ["bash", str(DRILL_SCRIPT)]
    if DRILL_SERVICE:
        cmd += ["--service", DRILL_SERVICE]
    if DRILL_ENV_FILE:
        cmd += ["--env-file", DRILL_ENV_FILE]
    if DRILL_PROJECT:
        cmd += ["--project-name", DRILL_PROJECT]
    cmd += list(args)
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
    )


def _drill_env() -> dict[str, str]:
    return {
        "POSTGRES_DB": DRILL_DB,
        "DR_TARGET_RTO_SECONDS": "14400",
        "DR_OPERATOR": os.environ.get("USER", "drill-runner"),
    }


def _stack_reachable() -> bool:
    cmd = ["docker", "compose"]
    if DRILL_PROJECT:
        cmd += ["--project-name", DRILL_PROJECT]
    cmd += [
        "-f",
        "docker-compose.test.yml",
        "--env-file",
        DRILL_ENV_FILE,
        "ps",
        "--status",
        "running",
        DRILL_SERVICE,
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return result.returncode == 0


def _scratch_db_exists() -> bool:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "hub-test-postgres",
            "psql",
            "-U",
            "hub_test",
            "-d",
            "postgres",
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname='{DRILL_DB}_restore_drill'",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() == "1"


def _latest_report() -> Path:
    files = sorted(REPORT_ROOT.rglob("dr-drill-*.json"))
    assert files, "no drill report found after a successful drill"
    return files[-1]


class TestRealBackup:
    def test_backup_creates_dump_and_manifest(self):
        if not _stack_reachable():
            skip_or_fail("postgres-test service not running — bring the test stack up")
        before = set(BACKUP_DIR.glob("*.dump")) if BACKUP_DIR.exists() else set()
        result = _drill("backup", env=_drill_env())
        assert result.returncode == 0, result.stderr
        after = set(BACKUP_DIR.glob("*.dump"))
        new_dumps = after - before
        assert len(new_dumps) == 1, f"expected exactly one new dump, got {new_dumps}"
        dump = new_dumps.pop()
        assert dump.with_suffix(dump.suffix + ".sha256").is_file(), (
            "manifest must be written alongside the dump"
        )
        # The dump is a real, non-trivial custom-format backup.
        assert dump.stat().st_size > 0


class TestRealRestoreDrill:
    def test_restore_drill_passes_parity_and_writes_report(self):
        if not _stack_reachable():
            skip_or_fail("postgres-test service not running — bring the test stack up")
        if not BACKUP_DIR.exists() or not list(BACKUP_DIR.glob("*.dump")):
            skip_or_fail("no backup in backups/dr-drill — run the backup test first")

        result = _drill("restore-drill", "--label", "pilot 4.4", env=_drill_env())
        assert result.returncode == 0, result.stderr

        report_file = _latest_report()
        report = json.loads(report_file.read_text())

        assert report["drill"] == "dr-restore-drill"
        assert report["label"] == "pilot 4.4"
        assert report["status"] == "PASSED", report
        assert report["rto_seconds"] > 0
        assert report["rto_seconds"] <= report["target_rto_seconds"]
        assert report["rto_within_target"] is True
        # No anomalies on a clean drill — pins the empty-array rendering
        # (a bash `${arr[@]:-}` trap once rendered [""]).
        assert report["anomalies"] == []

        parity = {p["table"]: p for p in report["parity"]}
        for table in DEFAULT_PARITY_TABLES:
            assert table in parity, f"parity must probe {table}"
            assert parity[table]["match"] is True, f"parity mismatch on {table}: {parity[table]}"
            assert parity[table]["live_count"] == parity[table]["scratch_count"]

        assert report_file.with_suffix(".md").is_file(), "markdown report twin"

        # The scratch database must be gone — the drill cleans up after itself.
        assert not _scratch_db_exists(), "scratch DB must be dropped after the drill"

    def test_tampered_manifest_refuses_to_restore(self):
        """Real failure-path rehearsal: a corrupted manifest MUST block the
        restore before any byte is loaded (exit 3, no scratch DB)."""
        if not _stack_reachable():
            skip_or_fail("postgres-test service not running — bring the test stack up")
        dumps = sorted(BACKUP_DIR.glob("*.dump"))
        if not dumps:
            skip_or_fail("no backup in backups/dr-drill — run the backup test first")

        # Gitignored working area (backups/), cleaned per run — never
        # leave dump copies in the source tree.
        tampered_dir = BACKUP_DIR / ".tampered"
        tampered_dir.mkdir(exist_ok=True)
        for old in tampered_dir.glob("*.dump*"):
            old.unlink()
        dump = dumps[-1]
        copy = tampered_dir / dump.name
        copy.write_bytes(dump.read_bytes())
        (tampered_dir / f"{dump.name}.sha256").write_text("0" * 64 + "  " + dump.name + "\n")

        result = _drill(
            "restore-drill",
            "--backup-dir",
            str(tampered_dir),
            env=_drill_env(),
        )
        assert result.returncode == 3, result.stdout + result.stderr
        assert "manifest check FAILED" in result.stdout + result.stderr
        assert not _scratch_db_exists(), "tampered restore must not touch the scratch DB"
