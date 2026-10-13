"""
Contract tests for scripts/check_credential_rotation.py (oss-release-remediation
W0.5, GATE-51).

The committed rotation record
(openspec/changes/oss-release-remediation/credential-rotation-2026-10-06.md)
must:

- exist and carry the mandated sections — the window re-check (guard +
  ListAgents evidence with the date), the named pre/post
  verify_test_stack_creds runs, the per-surface rotated steps, the
  Postgres TLS fingerprint evidence, and the U-gated console checklist;
- carry one `### step:` row per canonical surface with a `**Status:**`
  line — the gate is HONEST: any row that is not `**Status:** ROTATED`
  fails it (a gate that tolerates PENDING is the vacuous failure mode);
- record ≥2 sha256 fingerprints for the regenerated TLS material;
- carry no TBD/TODO placeholders.

Plus the Makefile wiring pin: GATE-51 runs in ``quality-gates`` after
the maintenance-window gate.
"""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_credential_rotation.py"
spec = importlib.util.spec_from_file_location("check_credential_rotation", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ROOT = scripts_dir.parent
MAKEFILE = ROOT / "Makefile"

STEPS = (
    "gcp-sa-key",
    "aws-pair",
    "azure-sp-secret",
    "databricks-pat",
    "snowflake-pat",
    "stripe-test-key",
    "secret-key",
    "staging-passwords",
    "postgres-certs",
)


def _record(status: str = "ROTATED") -> str:
    step_rows = "\n\n".join(f"### step: {name}\n\n**Status:** {status}\n" for name in STEPS)
    return (
        "# Credential Rotation\n\n"
        "## Window re-check\n\n"
        "2026-10-06 — ListAgents checked; peer session notified.\n"
        "scripts/check_no_live_tests.py — guard exit=0.\n\n"
        "## Pre/post test-stack verification\n\n"
        "PRE and POST runs of scripts/verify_test_stack_creds.py around "
        "every rotation.\n\n"
        "## Rotated surfaces\n\n"
        f"{step_rows}\n\n"
        "## Postgres TLS certs\n\n"
        "old ca.crt sha256: aaaa\nnew ca.crt sha256: bbbb\n\n"
        "## U-gated console checklist\n\n"
        "Six provider console rotations; key names and file paths only.\n"
    )


@pytest.fixture
def record_file(tmp_path):
    path = tmp_path / "credential-rotation-2026-10-06.md"
    path.write_text(_record())
    return path


def _run(record):
    return check.check(record)


def test_valid_record_passes(record_file):
    assert _run(record_file) == []


def test_missing_record_fails(tmp_path):
    problems = _run(tmp_path / "credential-rotation-2026-10-06.md")
    assert any("missing" in p for p in problems)


@pytest.mark.parametrize(
    "section",
    [
        "## Window re-check",
        "## Pre/post test-stack verification",
        "## Rotated surfaces",
        "## Postgres TLS certs",
        "## U-gated console checklist",
    ],
)
def test_missing_section_fails(record_file, section):
    record_file.write_text(_record().replace(section, "## Other"))
    problems = _run(record_file)
    assert any(section in p for p in problems)


@pytest.mark.parametrize("step", STEPS)
def test_missing_step_fails(record_file, step):
    record_file.write_text(_record().replace(f"### step: {step}\n", ""))
    problems = _run(record_file)
    assert any(step in p for p in problems)


def test_pending_row_fails_the_honest_gate(record_file):
    record_file.write_text(_record().replace("**Status:** ROTATED", "**Status:** PENDING-U", 1))
    problems = _run(record_file)
    assert any("PENDING-U" in p for p in problems)


def test_guard_evidence_flipped_fails(record_file):
    record_file.write_text(_record().replace("guard exit=0", "guard exit=1"))
    problems = _run(record_file)
    assert any("guard exit=0" in p for p in problems)


def test_prepost_instrument_missing_fails(record_file):
    record_file.write_text(_record().replace("verify_test_stack_creds.py", "other.py"))
    problems = _run(record_file)
    assert any("verify_test_stack_creds" in p for p in problems)


def test_fingerprints_missing_fails(record_file):
    record_file.write_text(_record().replace("sha256:", "md5:"))
    problems = _run(record_file)
    assert any("sha256" in p for p in problems)


def test_placeholder_fails(record_file):
    record_file.write_text(_record().replace("console rotations", "TODO"))
    problems = _run(record_file)
    assert any("TODO" in p for p in problems)


def test_default_path_exists():
    assert (
        ROOT / "openspec/changes/oss-release-remediation/credential-rotation-2026-10-06.md"
    ).exists()


class TestMainContract:
    def test_problems_exit_1(self, record_file, monkeypatch):
        record_file.write_text(_record().replace("guard exit=0", "guard exit=1"))
        monkeypatch.setattr(
            sys,
            "argv",
            ["check_credential_rotation.py", "--record", str(record_file)],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, record_file, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["check_credential_rotation.py", "--record", str(record_file)],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 0


def _quality_gates_recipe() -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(r"^quality-gates:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, "quality-gates target not found in Makefile"
    return list(match.group(1).splitlines())


class TestQualityGatesWiring:
    def test_gate51_wired_into_quality_gates(self):
        recipe = _quality_gates_recipe()
        joined = "\n".join(recipe)
        assert "check_credential_rotation.py" in joined, "GATE-51 must run in quality-gates"

    def test_gate51_runs_after_the_maintenance_window_gate(self):
        recipe = _quality_gates_recipe()
        gate50 = next(i for i, ln in enumerate(recipe) if "check_maintenance_window.py" in ln)
        gate51 = next(i for i, ln in enumerate(recipe) if "check_credential_rotation.py" in ln)
        assert gate50 < gate51, "the rotation gate runs after GATE-50"
