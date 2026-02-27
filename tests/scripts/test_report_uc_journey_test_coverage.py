"""
Tests for report_uc_journey_test_coverage.py (Traceability CI Gate).
No mocks: uses real docs/CRITICAL_UC_JOURNEY_IDS.yaml and script invocation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_critical_list_yaml_exists():
    """CRITICAL_UC_JOURNEY_IDS.yaml must exist and be loadable."""
    path = REPO_ROOT / "docs" / "CRITICAL_UC_JOURNEY_IDS.yaml"
    assert path.is_file(), f"Missing {path}"
    content = path.read_text()
    assert "critical_use_cases:" in content
    assert "critical_journeys:" in content
    assert "UC-AUTH-001" in content
    assert "JOURNEY-AUTH-001" in content


def test_load_critical_list():
    """load_critical_list returns UCs, journeys, thresholds from YAML."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.report_uc_journey_test_coverage import load_critical_list

    path = REPO_ROOT / "docs" / "CRITICAL_UC_JOURNEY_IDS.yaml"
    critical_ucs, critical_journeys, thresholds = load_critical_list(path)
    assert isinstance(critical_ucs, list)
    assert isinstance(critical_journeys, list)
    assert len(critical_ucs) >= 4
    assert "UC-AUTH-001" in critical_ucs
    assert "UC-AUTH-002" in critical_ucs
    assert len(critical_journeys) >= 4
    assert "JOURNEY-AUTH-001" in critical_journeys
    assert "JOURNEY-AUTH-002" in critical_journeys
    assert thresholds.get("uc_coverage_percent") == 70
    assert thresholds.get("journey_coverage_percent") == 60


def test_run_ci_mode_passed():
    """run_ci_mode returns exit 0 when no gaps and coverage above threshold."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.report_uc_journey_test_coverage import run_ci_mode

    # All critical covered; overall coverage above threshold
    uc_ids = ["UC-AUTH-001", "UC-AUTH-002", "UC-AM-001"]
    journey_ids = ["JOURNEY-AUTH-001", "JOURNEY-AUTH-002", "JOURNEY-DPO-001"]
    uc_to_files = {u: ["tests/e2e/test_auth.py"] for u in uc_ids}
    journey_to_files = {j: ["tests/e2e/test_journeys.py"] for j in journey_ids}
    critical_ucs = ["UC-AUTH-001", "UC-AUTH-002"]
    critical_journeys = ["JOURNEY-AUTH-001", "JOURNEY-AUTH-002"]

    exit_code, result = run_ci_mode(
        root=REPO_ROOT,
        uc_ids=uc_ids,
        journey_ids=journey_ids,
        uc_to_files=uc_to_files,
        journey_to_files=journey_to_files,
        critical_ucs=critical_ucs,
        critical_journeys=critical_journeys,
        uc_threshold_pct=70.0,
        journey_threshold_pct=60.0,
        output_path=None,
        broken_links=[],
    )
    assert exit_code == 0
    assert result["passed"] is True
    assert result["critical_gaps_uc"] == []
    assert result["critical_gaps_journey"] == []
    assert result["uc_coverage_percent"] >= 70
    assert result["journey_coverage_percent"] >= 60


def test_run_ci_mode_fails_on_critical_gap():
    """run_ci_mode returns exit 1 when a critical UC has no tests."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.report_uc_journey_test_coverage import run_ci_mode

    uc_ids = ["UC-AUTH-001", "UC-AUTH-002"]
    journey_ids = ["JOURNEY-AUTH-001"]
    uc_to_files = {"UC-AUTH-001": ["tests/e2e/test_auth.py"], "UC-AUTH-002": []}
    journey_to_files = {"JOURNEY-AUTH-001": ["tests/e2e/test_journeys.py"]}
    critical_ucs = ["UC-AUTH-001", "UC-AUTH-002"]
    critical_journeys = ["JOURNEY-AUTH-001"]

    exit_code, result = run_ci_mode(
        root=REPO_ROOT,
        uc_ids=uc_ids,
        journey_ids=journey_ids,
        uc_to_files=uc_to_files,
        journey_to_files=journey_to_files,
        critical_ucs=critical_ucs,
        critical_journeys=critical_journeys,
        uc_threshold_pct=70.0,
        journey_threshold_pct=60.0,
        output_path=None,
        broken_links=[],
    )
    assert exit_code == 1
    assert result["passed"] is False
    assert "UC-AUTH-002" in result["critical_gaps_uc"]


def test_run_ci_mode_fails_when_critical_id_not_in_docs():
    """run_ci_mode returns exit 1 when critical ID not in docs (YAML misconfig)."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.report_uc_journey_test_coverage import run_ci_mode

    uc_ids = ["UC-AUTH-001"]
    journey_ids = ["JOURNEY-AUTH-001"]
    uc_to_files = {"UC-AUTH-001": ["tests/e2e/test_auth.py"]}
    journey_to_files = {"JOURNEY-AUTH-001": ["tests/e2e/test_journeys.py"]}
    # Typo or retired ID in critical list: not present in uc_ids
    critical_ucs = ["UC-AUTH-001", "UC-TYPO-999"]
    critical_journeys = ["JOURNEY-AUTH-001"]

    exit_code, result = run_ci_mode(
        root=REPO_ROOT,
        uc_ids=uc_ids,
        journey_ids=journey_ids,
        uc_to_files=uc_to_files,
        journey_to_files=journey_to_files,
        critical_ucs=critical_ucs,
        critical_journeys=critical_journeys,
        uc_threshold_pct=70.0,
        journey_threshold_pct=60.0,
        output_path=None,
        broken_links=[],
    )
    assert exit_code == 1
    assert result.get("passed") is False
    assert result.get("error") == "critical_list_mismatch"
    assert "UC-TYPO-999" in result.get("critical_use_cases_not_in_docs", [])


def test_run_ci_mode_fails_below_threshold():
    """run_ci_mode returns exit 1 when coverage is below threshold."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.report_uc_journey_test_coverage import run_ci_mode

    # 1 of 10 UCs covered = 10% < 70%
    uc_ids = [f"UC-X-{i:03d}" for i in range(10)]
    journey_ids = [f"JOURNEY-Y-{i:03d}" for i in range(10)]
    uc_to_files = {uc_ids[0]: ["tests/unit/test_one.py"]}
    for u in uc_ids[1:]:
        uc_to_files[u] = []
    journey_to_files = {j: ["tests/e2e/test_j.py"] for j in journey_ids}
    critical_ucs = [uc_ids[0]]
    critical_journeys = [journey_ids[0]]

    exit_code, result = run_ci_mode(
        root=REPO_ROOT,
        uc_ids=uc_ids,
        journey_ids=journey_ids,
        uc_to_files=uc_to_files,
        journey_to_files=journey_to_files,
        critical_ucs=critical_ucs,
        critical_journeys=critical_journeys,
        uc_threshold_pct=70.0,
        journey_threshold_pct=60.0,
        output_path=None,
        broken_links=[],
    )
    assert exit_code == 1
    assert result["passed"] is False
    assert result["uc_coverage_percent"] == 10.0


def test_script_json_includes_scenario_coverage():
    """Script --json output includes scenario_coverage.use_cases and .user_journeys (8.8.1)."""
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "report_uc_journey_test_coverage.py"),
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    data = json.loads(result.stdout)
    assert "scenario_coverage" in data
    sc = data["scenario_coverage"]
    assert "use_cases" in sc
    assert "user_journeys" in sc
    # Each entry is id -> {success, failure, edge}
    for uc_id, cov in list(sc["use_cases"].items())[:3]:
        assert isinstance(cov, dict)
        assert "success" in cov and "failure" in cov and "edge" in cov
        assert isinstance(cov["success"], bool) and isinstance(cov["failure"], bool) and isinstance(cov["edge"], bool)
    for j_id, cov in list(sc["user_journeys"].items())[:3]:
        assert isinstance(cov, dict)
        assert "success" in cov and "failure" in cov and "edge" in cov


def test_script_markdown_includes_scenario_column():
    """Script default (Markdown) output includes scenario column header (8.8.1)."""
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "report_uc_journey_test_coverage.py"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    out = result.stdout
    assert "Scenario (S=Success, F=Failure, E=Edge)" in out
    assert "| UC ID |" in out
    assert "| Journey ID |" in out


def test_script_ci_mode_produces_json_artifact(tmp_path):
    """Script --ci-mode writes JSON with ci_mode, passed, coverage fields."""
    out_file = tmp_path / "traceability-report.json"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "report_uc_journey_test_coverage.py"),
            "--ci-mode",
            "--output",
            str(out_file),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    # May pass or fail depending on current repo coverage; we only assert artifact shape
    assert out_file.is_file()
    data = json.loads(out_file.read_text())
    assert data.get("ci_mode") is True
    assert "passed" in data
    assert "uc_coverage_percent" in data
    assert "journey_coverage_percent" in data
    assert "critical_gaps_uc" in data
    assert "critical_gaps_journey" in data
    assert "summary" in data
    # Scenario coverage (8.8.1): report includes UC/journey scenario coverage for gate
    assert "scenario_coverage_use_cases" in data
    assert "scenario_coverage_user_journeys" in data


def test_run_ci_mode_includes_scenario_coverage_when_provided():
    """run_ci_mode adds scenario_coverage_use_cases and scenario_coverage_user_journeys to result."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.report_uc_journey_test_coverage import run_ci_mode

    uc_to_files = {"UC-AUTH-001": ["tests/e2e/test_auth.py"], "UC-AUTH-002": []}
    journey_to_files = {"JOURNEY-AUTH-001": ["frontend/e2e/journeys/auth/JOURNEY-AUTH-001.spec.ts"]}
    uc_scenario = {
        "UC-AUTH-001": {"success": True, "failure": True, "edge": False},
        "UC-AUTH-002": {"success": False, "failure": False, "edge": False},
    }
    journey_scenario = {
        "JOURNEY-AUTH-001": {"success": True, "failure": True, "edge": True},
    }
    exit_code, result = run_ci_mode(
        root=REPO_ROOT,
        uc_ids=list(uc_to_files),
        journey_ids=list(journey_to_files),
        uc_to_files=uc_to_files,
        journey_to_files=journey_to_files,
        critical_ucs=["UC-AUTH-001"],
        critical_journeys=["JOURNEY-AUTH-001"],
        uc_threshold_pct=50.0,
        journey_threshold_pct=50.0,
        output_path=None,
        broken_links=[],
        uc_scenario=uc_scenario,
        journey_scenario=journey_scenario,
    )
    assert "scenario_coverage_use_cases" in result
    assert result["scenario_coverage_use_cases"] == uc_scenario
    assert "scenario_coverage_user_journeys" in result
    assert result["scenario_coverage_user_journeys"] == journey_scenario


def test_script_ci_mode_exit_zero_or_one():
    """Script --ci-mode exits 0 when gate passes, 1 when it fails."""
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "report_uc_journey_test_coverage.py"),
            "--ci-mode",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode in (0, 1)
