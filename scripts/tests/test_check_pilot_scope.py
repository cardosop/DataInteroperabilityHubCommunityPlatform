"""
Contract tests for scripts/check_pilot_scope.py (pilot-readiness 3.2,
GATE-45).

The pilot-scope record (docs/runbooks/PILOT_SCOPE.md) must:
- contain the four mandated workshop sections;
- select 18-22 journey/UC IDs, anchored to the critical registry
  (>=18 critical IDs);
- list only IDs that exist in the canonical registries;
- name only RUNTIME capability keys (AST-parsed from
  hub/apps/api/capabilities.py — no drift, no invented keys);
- record the Unity Catalog / Delta Sharing decisions and the
  data-migration approach without TBD/TODO placeholders.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_pilot_scope.py"
spec = importlib.util.spec_from_file_location("check_pilot_scope", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

JOURNEY_IDS = [f"JOURNEY-P-{i:03d}" for i in range(1, 10)]
UC_IDS = [f"UC-P-{i:03d}" for i in range(1, 10)]


def _scope(rows=None):
    """The 18-ID selection table (9 journeys + 9 UCs), overridable."""
    ids = rows or [*JOURNEY_IDS, *UC_IDS]
    table = "".join(f"| {n} | {i} | role |\n" for n, i in enumerate(ids, 1))
    return f"""# Pilot Scope

## Journey selection

| # | ID | Role |
|---|---|---|
{table}
## Capability manifest

| Runtime key | Pilot state |
|---|---|
| lineage.snapshots | ON |

## Unity Catalog / Delta Sharing decision

Unity Catalog is used. Delta Sharing is not built for P1.

## Data-migration approach

The dlt spine moves the data.
"""


SCOPE = _scope()


@pytest.fixture
def fixture_files(tmp_path):
    report = tmp_path / "PILOT_SCOPE.md"
    report.write_text(SCOPE)
    journeys = tmp_path / "USER_JOURNEYS.md"
    journeys.write_text("\n".join(f"- [ ] {j} — journey" for j in JOURNEY_IDS))
    use_cases = tmp_path / "USE_CASES.md"
    use_cases.write_text("\n".join(f"- [ ] {u} — uc" for u in UC_IDS))
    critical = tmp_path / "CRITICAL.yaml"
    critical.write_text(f"critical_journeys: {JOURNEY_IDS}\ncritical_use_cases: {UC_IDS}\n")
    return report, journeys, use_cases, critical


def _run(report, journeys, use_cases, critical, caps_path=None):
    caps = caps_path or (scripts_dir.parent / "hub/apps/api/capabilities.py")
    return check.check(report, journeys, use_cases, critical, caps)


def test_valid_scope_passes(fixture_files):
    problems = _run(*fixture_files)
    assert problems == []


def test_missing_section_fails(fixture_files):
    report, journeys, use_cases, critical = fixture_files
    report.write_text(SCOPE.replace("## Capability manifest", "## Missing"))
    problems = _run(report, journeys, use_cases, critical)
    assert any("## Capability manifest" in p for p in problems)


def test_unknown_id_fails(fixture_files):
    report, journeys, use_cases, critical = fixture_files
    report.write_text(_scope(rows=[*JOURNEY_IDS, *UC_IDS[:8], "UC-BOGUS-999"]))
    problems = _run(report, journeys, use_cases, critical)
    assert any("UC-BOGUS-999" in p for p in problems)


def test_too_few_selected_ids_fails(fixture_files):
    report, journeys, use_cases, critical = fixture_files
    report.write_text(_scope(rows=[*JOURNEY_IDS, *UC_IDS[:8]]))  # 17 selected
    problems = _run(report, journeys, use_cases, critical)
    assert any("count" in p for p in problems)


def test_critical_anchoring_fails_when_below_threshold(fixture_files):
    # The doc lists 18 IDs; the critical registry carries only 17 of
    # them — the anchoring share must still be >= 18, the checker
    # reports the gap.
    report, journeys, use_cases, critical = fixture_files
    critical.write_text(f"critical_journeys: {JOURNEY_IDS}\ncritical_use_cases: {UC_IDS[:8]}\n")
    problems = _run(report, journeys, use_cases, critical)
    assert any("critical" in p for p in problems)


def test_invented_capability_key_fails(fixture_files):
    report, journeys, use_cases, critical = fixture_files
    report.write_text(SCOPE.replace("lineage.snapshots", "lineage.magic_teleport"))
    problems = _run(report, journeys, use_cases, critical)
    assert any("lineage.magic_teleport" in p for p in problems)


def test_tbd_placeholder_fails(fixture_files):
    report, journeys, use_cases, critical = fixture_files
    report.write_text(SCOPE.replace("is not built for P1", "is TBD"))
    problems = _run(report, journeys, use_cases, critical)
    assert any("TBD" in p for p in problems)


def test_default_paths_exist():
    root = scripts_dir.parent
    assert (root / "docs/runbooks/PILOT_SCOPE.md").exists()
    assert (root / "docs/USER_JOURNEYS.md").exists()
    assert (root / "docs/USE_CASES.md").exists()
    assert (root / "docs/CRITICAL_UC_JOURNEY_IDS.yaml").exists()
    assert (root / "hub/apps/api/capabilities.py").exists()


class TestMainContract:
    def test_problems_exit_1(self, fixture_files, monkeypatch):
        report, journeys, use_cases, critical = fixture_files
        report.write_text(SCOPE.replace("## Capability manifest", "## Missing"))
        caps = scripts_dir.parent / "hub/apps/api/capabilities.py"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_pilot_scope.py",
                "--report",
                str(report),
                "--journeys",
                str(journeys),
                "--use-cases",
                str(use_cases),
                "--critical",
                str(critical),
                "--capabilities",
                str(caps),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, fixture_files, monkeypatch):
        report, journeys, use_cases, critical = fixture_files
        caps = scripts_dir.parent / "hub/apps/api/capabilities.py"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_pilot_scope.py",
                "--report",
                str(report),
                "--journeys",
                str(journeys),
                "--use-cases",
                str(use_cases),
                "--critical",
                str(critical),
                "--capabilities",
                str(caps),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 0
