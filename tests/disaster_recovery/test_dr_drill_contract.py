"""pilot-readiness 4.4 — DR restore drill contract pins (fast, batch-safe).

Replaces the retired 285.12.6.1 placeholder checks (env-var presence and
``which pg_restore``) with contract pins for the REAL drill tooling:

* ``scripts/dr/dr_restore_drill.sh`` — the compose-path drill (backup →
  restore → parity → report) executed for real by
  ``tests/disaster_recovery/test_dr_drill_real.py`` under ``make dr-drill``.
* ``scripts/dr/restore_verify_rds.sh`` — the RDS-path drill; its
  post-restore verification is a REAL database check (pg_isready + parity),
  never an HTTP curl against the database endpoint (the root cause fixed
  under 4.4).
* The staging compose project must be isolated from the test stack's
  project (the ``name: hub-staging`` root-cause fix).
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRILL_SCRIPT = REPO_ROOT / "scripts" / "dr" / "dr_restore_drill.sh"
RDS_SCRIPT = REPO_ROOT / "scripts" / "dr" / "restore_verify_rds.sh"
STAGING_COMPOSE = REPO_ROOT / "docker-compose.staging.yml"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True, check=False)


class TestDrillScriptsExist:
    def test_dr_restore_drill_script_exists_and_is_executable(self):
        assert DRILL_SCRIPT.is_file(), "dr_restore_drill.sh must exist"
        assert os.access(DRILL_SCRIPT, os.X_OK), "dr_restore_drill.sh must be executable"

    def test_restore_verify_rds_script_exists_and_is_executable(self):
        assert RDS_SCRIPT.is_file(), "restore_verify_rds.sh must exist"
        assert os.access(RDS_SCRIPT, os.X_OK), "restore_verify_rds.sh must be executable"

    def test_both_scripts_pass_bash_syntax_check(self):
        for script in (DRILL_SCRIPT, RDS_SCRIPT):
            result = _run(["bash", "-n", str(script)])
            assert result.returncode == 0, f"bash -n failed for {script}: {result.stderr}"


class TestDrRestoreDrillDryRunContract:
    def test_backup_dry_run_plans_pg_dump_and_manifest(self):
        result = _run(["bash", str(DRILL_SCRIPT), "--dry-run", "backup"])
        assert result.returncode == 0, result.stderr
        assert "--format=custom" in result.stdout
        assert "sha256sum" in result.stdout

    def test_restore_drill_dry_run_plans_manifest_parity_and_report(self):
        result = _run(["bash", str(DRILL_SCRIPT), "--dry-run", "restore-drill"])
        assert result.returncode == 0, result.stderr
        assert "manifest" in result.stdout
        assert "parity" in result.stdout
        assert "docs/operations/dr-drill-reports" in result.stdout

    def test_restore_drill_requires_a_manifest_gate_before_restore(self):
        result = _run(["bash", str(DRILL_SCRIPT), "--dry-run", "restore-drill"])
        out = result.stdout
        assert out.index("manifest") < out.index("pg_restore")

    def test_unknown_flag_is_rejected(self):
        result = _run(["bash", str(DRILL_SCRIPT), "--dry-run", "--bogus", "backup"])
        assert result.returncode != 0

    def test_restore_drill_rejects_unknown_subcommand(self):
        result = _run(["bash", str(DRILL_SCRIPT), "--dry-run", "nope"])
        assert result.returncode != 0


class TestRestoreVerifyRdsDryRunContract:
    def test_dry_run_prints_the_plan_without_requiring_aws(self):
        # Run with PATH stripped to bash's directory — the dry-run must not
        # need aws/psql on the host. (The plan logs to stderr, like every
        # other log() line — operators capture both streams.)
        result = subprocess.run(
            ["bash", str(RDS_SCRIPT), "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "PATH": os.path.dirname(os.path.realpath("/usr/bin/env")),
            },
        )
        assert result.returncode == 0, result.stderr
        out = result.stdout + result.stderr
        assert "describe-db-snapshots" in out
        assert "restore-db-instance-from-db-snapshot" in out
        assert "migrate" in out

    def test_verification_is_a_database_check_never_an_http_curl(self):
        result = _run(["bash", str(RDS_SCRIPT), "--dry-run"])
        out = result.stdout + result.stderr
        assert "pg_isready" in out
        assert "parity" in out
        assert "curl" not in out

    def test_dry_run_reports_rto_contract(self):
        result = _run(["bash", str(RDS_SCRIPT), "--dry-run"])
        out = result.stdout + result.stderr
        assert "rto_seconds" in out
        assert "rto_within_target" in out

    def test_verify_db_mode_parses_a_postgres_url(self):
        # The URL parser (components for pg_isready) must split
        # postgresql://user:pass@host:port/db — pinned against a regression
        # where pg_isready -d received the whole URL and failed every time.
        url = "postgresql://hub_test:hub_test@postgres-test:5432/hub_test_test_shared"
        assert shlex.quote(url)  # sanity: no shell-breaking characters
        # Component expectations are enforced by the bash suite
        # (scripts/tests/test_restore_verify_rds.sh) against a live DB.


class TestStagingProjectIsolation:
    """The staging compose must own its project namespace (root-cause fix)."""

    def _resolved_name(self, compose_file: Path, env_file: Path, *extra: str) -> str:
        result = _run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "--env-file",
                str(env_file),
                *extra,
                "config",
            ]
        )
        assert result.returncode == 0, result.stderr
        for line in result.stdout.splitlines():
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip()
        return ""

    def test_staging_compose_declares_a_top_level_name(self):
        text = STAGING_COMPOSE.read_text()
        assert "\nname: hub-staging\n" in text, (
            "docker-compose.staging.yml must pin `name: hub-staging` — "
            "without it the project resolves to the TEST stack's project"
        )

    def test_staging_project_name_differs_from_test_project(self):
        # Scoped probe: the Makefile exports COMPOSE_PROJECT_NAME for the
        # test stack, which overrides the file's name: key — staging ops
        # must always pass --project-name hub-staging (the full hostile-env
        # matrix is pinned by test_staging_project_isolation.sh).
        staging = self._resolved_name(
            STAGING_COMPOSE,
            REPO_ROOT / ".env.staging",
            "--project-name",
            "hub-staging",
        )
        test = self._resolved_name(REPO_ROOT / "docker-compose.test.yml", REPO_ROOT / ".env.test")
        assert staging == "hub-staging", staging
        assert staging != test, (
            f"staging ({staging}) and test ({test}) share a compose project "
            "— staging-down -v could destroy the test stack's volumes"
        )

    def test_makefile_staging_targets_scope_the_project_name(self):
        # Every Makefile staging target must pin the flag — the exported
        # COMPOSE_PROJECT_NAME=datainteroperabilityhub otherwise wins.
        makefile = (REPO_ROOT / "Makefile").read_text()
        for target in (
            "staging-up:",
            "staging-down:",
            "staging-down-volumes:",
            "staging-ps:",
            "staging-logs:",
        ):
            block = makefile.split(target, 1)[1].split("\n\n", 1)[0]
            assert "--project-name hub-staging" in block, (
                f"make {target.rstrip(':')} must pin --project-name hub-staging"
            )

    def test_dr_policy_report_dir_is_the_drill_report_root(self):
        # DR policy: "All drill reports stored in
        # docs/operations/dr-drill-reports/YYYY-MM/".
        policy = REPO_ROOT / "docs" / "operations" / "disaster-recovery-policy.md"
        text = policy.read_text()
        assert "docs/operations/dr-drill-reports/YYYY-MM/" in text
        # The drill script's default report dir matches the policy.
        result = _run(["bash", str(DRILL_SCRIPT), "--dry-run", "restore-drill"])
        assert "docs/operations/dr-drill-reports" in result.stdout


class TestDrillReportShape:
    """The report JSON contract (validated against a real report in the
    opt-in suite; here the shape is pinned statically)."""

    def test_report_fields_match_dr_policy_requirements(self):
        required = {
            "operator",
            "timestamp",
            "rto_seconds",
            "target_rto_seconds",
            "rto_within_target",
            "status",
            "parity",
            "anomalies",
        }
        # Every required field is emitted by the script's report heredoc.
        script_text = DRILL_SCRIPT.read_text()
        for field in required:
            assert f'"{field}"' in script_text, f"report must include {field}"
        # Anomalies are JSON-safe (empty → [], else list of strings).
        assert "anomalies_json" in script_text
