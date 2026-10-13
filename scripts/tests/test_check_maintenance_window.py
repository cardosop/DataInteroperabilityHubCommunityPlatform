"""
Contract tests for scripts/check_maintenance_window.py (oss-release-remediation
W0.3, GATE-50).

The committed maintenance-window notice
(openspec/changes/oss-release-remediation/maintenance-window-2026-10-06.md)
must:

- exist and carry the mandated sections — the window scope, the peer
  notification record (ListAgents check with outcome + date), the
  zero-live-pytest guard evidence (a recorded `guard exit=0` run), and
  the destructive steps the window gates;
- name the re-run rule (the guard is re-run immediately before W0.4);
- carry no TBD/TODO placeholders.

Plus the Makefile wiring pin: GATE-50 runs in ``quality-gates`` after
the scan-report gate.
"""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_maintenance_window.py"
spec = importlib.util.spec_from_file_location("check_maintenance_window", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ROOT = scripts_dir.parent
MAKEFILE = ROOT / "Makefile"

NOTICE = (
    "# Maintenance Window\n\n"
    "## Window\n\n"
    "2026-10-06 — gates the W0.4 history rewrite and the W0.5 console rotations.\n\n"
    "## Peer notification\n\n"
    "ListAgents on 2026-10-06: no other session active on this machine.\n\n"
    "## Zero-live-pytest guard\n\n"
    "scripts/check_no_live_tests.py — guard exit=0, no live pytest/playwright "
    "runs found (host + containers).\n\n"
    "## Gated destructive steps\n\n"
    "git filter-repo rewrite + force-push; credential rotations.\n"
    "The guard is re-run immediately before W0.4.\n"
)


@pytest.fixture
def notice_file(tmp_path):
    path = tmp_path / "maintenance-window-2026-10-06.md"
    path.write_text(NOTICE)
    return path


def _run(notice):
    return check.check(notice)


def test_valid_notice_passes(notice_file):
    assert _run(notice_file) == []


def test_missing_notice_fails(tmp_path):
    problems = _run(tmp_path / "maintenance-window-2026-10-06.md")
    assert any("missing" in p for p in problems)


@pytest.mark.parametrize(
    "section",
    [
        "## Window",
        "## Peer notification",
        "## Zero-live-pytest guard",
        "## Gated destructive steps",
    ],
)
def test_missing_section_fails(notice_file, section):
    notice_file.write_text(NOTICE.replace(section, "## Other"))
    problems = _run(notice_file)
    assert any(section in p for p in problems)


def test_guard_evidence_flipped_fails(notice_file):
    notice_file.write_text(NOTICE.replace("guard exit=0", "guard exit=1"))
    problems = _run(notice_file)
    assert any("guard exit=0" in p for p in problems)


def test_peer_check_evidence_missing_fails(notice_file):
    notice_file.write_text(NOTICE.replace("ListAgents", "Emails"))
    problems = _run(notice_file)
    assert any("ListAgents" in p for p in problems)


def test_rerun_rule_missing_fails(notice_file):
    notice_file.write_text(
        NOTICE.replace("is re-run immediately before W0.4", "was run once")
    )
    problems = _run(notice_file)
    assert any("re-run" in p for p in problems)


def test_placeholder_fails(notice_file):
    notice_file.write_text(NOTICE.replace("credential rotations", "TODO"))
    problems = _run(notice_file)
    assert any("TODO" in p for p in problems)


def test_default_path_exists():
    assert (
        ROOT
        / "openspec/changes/oss-release-remediation/maintenance-window-2026-10-06.md"
    ).exists()


class TestMainContract:
    def test_problems_exit_1(self, notice_file, monkeypatch):
        notice_file.write_text(NOTICE.replace("guard exit=0", "guard exit=1"))
        monkeypatch.setattr(
            sys,
            "argv",
            ["check_maintenance_window.py", "--notice", str(notice_file)],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, notice_file, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            ["check_maintenance_window.py", "--notice", str(notice_file)],
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
    def test_gate50_wired_into_quality_gates(self):
        recipe = _quality_gates_recipe()
        joined = "\n".join(recipe)
        assert (
            "check_maintenance_window.py" in joined
        ), "GATE-50 must run in quality-gates"

    def test_gate50_runs_after_the_scan_report_gate(self):
        recipe = _quality_gates_recipe()
        gate49 = next(
            i for i, ln in enumerate(recipe) if "check_secret_scan_report.py" in ln
        )
        gate50 = next(
            i for i, ln in enumerate(recipe) if "check_maintenance_window.py" in ln
        )
        assert gate49 < gate50, "the maintenance-window gate runs after GATE-49"
