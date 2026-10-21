"""
Contract tests for scripts/check_secret_scan_report.py (oss-release-remediation
W0.2, GATE-49).

The committed secret-scan report (docs/audits/secret-scan-2026-10-06.md)
must:

- exist and carry the mandated sections (summary with the
  zero-unremediated-HIGHs declaration, scan methodology naming both
  tools with versions, redacted findings inventory, remediation
  mapping, verification);
- declare ``Unremediated HIGH | 0`` in its summary table — every HIGH
  finding is mapped to a remediation workstream;
- contain no secret-like material: the gate re-scans the report with
  gitleaks (default rules, --no-git, on a temp copy) and fails on any
  hit — the redaction contract is enforced, not assumed;
- carry no TBD/TODO placeholders.

Plus the Makefile wiring pin: GATE-49 runs in ``quality-gates`` after
the root license gate.
"""

import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_secret_scan_report.py"
spec = importlib.util.spec_from_file_location("check_secret_scan_report", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ROOT = scripts_dir.parent
MAKEFILE = ROOT / "Makefile"
GITLEAKS_PRESENT = shutil.which("gitleaks") is not None

# A gitleaks-detectable GitHub PAT shape (proven to match the host
# build's default ruleset in `dir` mode — used ONLY to prove the
# self-scan bites; it is not a real credential).
PLANTED_SECRET = (
    "ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdef"
)  # split so no secret-shape exists in the tree

REPORT = (
    "# Secret Scan Report\n\n"
    "## Summary\n\n"
    "| Unremediated HIGH | 0 |\n\n"
    "## Scan methodology\n\n"
    "gitleaks 8.21.2 and trufflehog 3.80.0 over the full git history.\n\n"
    "## Findings inventory (redacted)\n\n"
    "| Rule | File | Hits |\n"
    "|---|---|---|\n"
    "| aws-access-token | legacy/.env.test | 3 |\n\n"
    "## Remediation mapping\n\n"
    "| Class | Workstream |\n"
    "|---|---|\n"
    "| env leaks | W0.4 history rewrite |\n\n"
    "## Verification\n\n"
    "git log -S re-verified after W0.4.\n"
)


@pytest.fixture
def report_file(tmp_path):
    path = tmp_path / "secret-scan-2026-10-06.md"
    path.write_text(REPORT)
    return path


REAL_CONFIG = ROOT / ".gitleaks.toml"

VACUOUS_CONFIG = """\
title = "vacuous"

[allowlist]
  paths = ["tests/"]
"""


def _run(report, config=None):
    return check.check(report, config or REAL_CONFIG)


def test_valid_report_passes(report_file):
    problems = _run(report_file)
    if GITLEAKS_PRESENT:
        assert problems == []
    else:
        # Deterministic either way: without the binary the gate reports
        # the missing self-scan requirement instead of silently passing.
        assert any("gitleaks" in p for p in problems)


def test_missing_report_fails(tmp_path):
    problems = _run(tmp_path / "secret-scan-2026-10-06.md")
    assert any("missing" in p for p in problems)


@pytest.mark.parametrize(
    "section",
    [
        "## Summary",
        "## Scan methodology",
        "## Findings inventory (redacted)",
        "## Remediation mapping",
        "## Verification",
    ],
)
def test_missing_section_fails(report_file, section):
    report_file.write_text(REPORT.replace(section, "## Other"))
    problems = _run(report_file)
    assert any(section in p for p in problems)


def test_unremediated_high_not_zero_fails(report_file):
    report_file.write_text(
        REPORT.replace("| Unremediated HIGH | 0 |", "| Unremediated HIGH | 3 |")
    )
    problems = _run(report_file)
    assert any("Unremediated HIGH" in p for p in problems)


def test_missing_unremediated_high_row_fails(report_file):
    report_file.write_text(REPORT.replace("| Unremediated HIGH | 0 |\n", ""))
    problems = _run(report_file)
    assert any("Unremediated HIGH" in p for p in problems)


def test_planted_secret_in_report_fails(report_file):
    report_file.write_text(REPORT + f"\naws_access_key_id = {PLANTED_SECRET}\n")
    problems = _run(report_file)
    if GITLEAKS_PRESENT:
        assert any("secret-like material" in p for p in problems)
    else:
        assert any("gitleaks" in p for p in problems)


def test_placeholder_in_report_fails(report_file):
    report_file.write_text(REPORT.replace("W0.4 history rewrite", "TODO"))
    problems = _run(report_file)
    assert any("TODO" in p for p in problems)


def test_vacuous_config_fails(report_file, tmp_path):
    """The W0.2 root cause: a config without [[rules]] must fail the gate."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text(VACUOUS_CONFIG)
    problems = _run(report_file, config=config)
    assert any("rules" in p and "vacuous" in p for p in problems)


def test_missing_config_fails(report_file, tmp_path):
    problems = _run(report_file, config=tmp_path / ".gitleaks.toml")
    assert any("config missing" in p for p in problems)


def test_shipped_config_is_non_vacuous():
    assert REAL_CONFIG.exists()
    cfg = check._check_config(REAL_CONFIG)
    assert cfg == []


def test_default_path_exists():
    assert (ROOT / "docs/audits/secret-scan-2026-10-06.md").exists()


class TestMainContract:
    def test_problems_exit_1(self, report_file, monkeypatch):
        report_file.write_text(
            REPORT.replace("| Unremediated HIGH | 0 |", "| Unremediated HIGH | 1 |")
        )
        monkeypatch.setattr(
            sys, "argv", ["check_secret_scan_report.py", "--report", str(report_file)]
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, report_file, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["check_secret_scan_report.py", "--report", str(report_file)]
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        if GITLEAKS_PRESENT:
            assert exc_info.value.code == 0
        else:
            assert exc_info.value.code == 1


def _quality_gates_recipe() -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(r"^quality-gates:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, "quality-gates target not found in Makefile"
    return list(match.group(1).splitlines())


class TestQualityGatesWiring:
    def test_gate49_wired_into_quality_gates(self):
        recipe = _quality_gates_recipe()
        joined = "\n".join(recipe)
        assert (
            "check_secret_scan_report.py" in joined
        ), "GATE-49 must run in quality-gates"

    def test_gate49_runs_after_the_license_gate(self):
        recipe = _quality_gates_recipe()
        gate48 = next(i for i, ln in enumerate(recipe) if "check_root_license.py" in ln)
        gate49 = next(
            i for i, ln in enumerate(recipe) if "check_secret_scan_report.py" in ln
        )
        assert gate48 < gate49, "the scan-report gate runs after the license gate"
