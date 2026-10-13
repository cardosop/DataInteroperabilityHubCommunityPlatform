"""validate_openspec_change.py tests — TDD fixtures, no mocks.

Synthetic change dirs exercise each rule; the baseline mechanics use the
same real-file round-trip as the GATE-29 ratchet (working set vs baseline,
net growth fails, shrink passes).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validate_openspec_change import collect_violations, main

VALID_PROPOSAL = "## Why\n\n## What Changes\n\n## Impact\n"
VALID_SPEC = (
    "# Test Spec\n\n"
    "## ADDED Requirements\n\n"
    "### Requirement: The system SHALL do the thing\n\n"
    "#### Scenario: It works\n"
    "- **WHEN** the thing happens\n"
    "- **THEN** the result SHALL be correct\n"
)


def _write_change(
    tmp_path: Path, proposal: str = VALID_PROPOSAL, specs: dict[str, str] | None = None
) -> Path:
    change = tmp_path / "change"
    (change / "specs").mkdir(parents=True)
    (change / "proposal.md").write_text(proposal)
    (change / "tasks.md").write_text("## Phase 1\n")
    for name, content in (specs or {"test-spec/spec.md": VALID_SPEC}).items():
        path = change / "specs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return change


class TestRules:
    def test_valid_change_has_no_violations(self, tmp_path):
        change = _write_change(tmp_path)
        assert collect_violations(change) == []

    def test_missing_proposal(self, tmp_path):
        change = _write_change(tmp_path)
        (change / "proposal.md").unlink()
        assert "proposal.md::missing" in collect_violations(change)

    def test_missing_impact_section(self, tmp_path):
        change = _write_change(tmp_path, proposal="## Why\n\n## What Changes\n")
        assert any("missing-section::## Impact" in v for v in collect_violations(change))

    def test_spec_without_title(self, tmp_path):
        change = _write_change(tmp_path, specs={"bad/spec.md": "## ADDED Requirements\n"})
        assert any(v.endswith("::no-title") for v in collect_violations(change))

    def test_requirement_without_shall(self, tmp_path):
        spec = VALID_SPEC.replace("SHALL do the thing", "does the thing").replace(
            "SHALL be correct", "be correct"
        )
        change = _write_change(tmp_path, specs={"bad/spec.md": spec})
        assert any("::requirement-no-shall::" in v for v in collect_violations(change))

    def test_requirement_without_scenario(self, tmp_path):
        spec = "# T\n\n## ADDED Requirements\n\n### Requirement: SHALL x\n"
        change = _write_change(tmp_path, specs={"bad/spec.md": spec})
        assert any("::requirement-no-scenario::" in v for v in collect_violations(change))

    def test_scenario_without_then(self, tmp_path):
        spec = VALID_SPEC.replace("- **THEN** the result SHALL be correct", "- **AND** whatever")
        change = _write_change(tmp_path, specs={"bad/spec.md": spec})
        assert any("::scenario-no-then::" in v for v in collect_violations(change))

    def test_scenario_without_when(self, tmp_path):
        spec = VALID_SPEC.replace("- **WHEN** the thing happens", "- **GIVEN** the thing")
        change = _write_change(tmp_path, specs={"bad/spec.md": spec})
        assert any("::scenario-no-when::" in v for v in collect_violations(change))

    def test_duplicate_requirement_title(self, tmp_path):
        spec = VALID_SPEC + "\n### Requirement: The system SHALL do the thing\n"
        change = _write_change(tmp_path, specs={"bad/spec.md": spec})
        assert any("::duplicate-requirement::" in v for v in collect_violations(change))


class TestBaselineMechanics:
    def test_new_violation_fails_with_baseline(self, tmp_path):
        change = _write_change(tmp_path)
        baseline = tmp_path / "baseline.txt"
        baseline.write_text("# empty baseline\n")
        assert main(["--change", str(change), "--baseline", str(baseline)]) == 0
        # introduce a new violation (strip SHALL from title AND body)
        (change / "specs" / "test-spec" / "spec.md").write_text(
            VALID_SPEC.replace("SHALL do the thing", "does the thing").replace(
                "SHALL be correct", "be correct"
            )
        )
        assert main(["--change", str(change), "--baseline", str(baseline)]) == 1

    def test_baselined_violation_passes(self, tmp_path):
        spec = VALID_SPEC.replace("SHALL do the thing", "does the thing").replace(
            "SHALL be correct", "be correct"
        )
        change = _write_change(tmp_path, specs={"bad/spec.md": spec})
        assert collect_violations(change), "fixture must produce a real violation"
        baseline = tmp_path / "baseline.txt"
        baseline.write_text("\n".join(collect_violations(change)) + "\n")
        assert main(["--change", str(change), "--baseline", str(baseline)]) == 0

    def test_emit_baseline_round_trips(self, tmp_path):
        spec = VALID_SPEC.replace("SHALL do the thing", "does the thing").replace(
            "SHALL be correct", "be correct"
        )
        change = _write_change(tmp_path, specs={"bad/spec.md": spec})
        emitted = subprocess.run(
            [
                sys.executable,
                "-m",
                "validate_openspec_change",
                "--change",
                str(change),
                "--emit-baseline",
            ],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONPATH": str(Path(__file__).resolve().parent.parent)},
        )
        baseline = tmp_path / "baseline.txt"
        baseline.write_text(emitted.stdout)
        assert main(["--change", str(change), "--baseline", str(baseline)]) == 0


class TestChurnStability:
    def test_blank_line_insertion_does_not_change_keys(self, tmp_path):
        """Line-number-free keys: inserting blank lines must not churn the
        violation set (the ratchet must not false-fail on formatting churn)."""
        spec = VALID_SPEC.replace("SHALL do the thing", "does the thing").replace(
            "SHALL be correct", "be correct"
        )
        change = _write_change(tmp_path, specs={"bad/spec.md": spec})
        before = collect_violations(change)
        assert before, "fixture must produce a real violation"
        (change / "specs" / "bad" / "spec.md").write_text("\n\n" + spec + "\n\n\n")
        assert collect_violations(change) == before


class TestWrapperScript:
    def test_wrapper_strict_on_baselined_change(self, tmp_path):
        """The wrapper: a baselined change with a NEW violation exits 1."""
        repo = _fake_repo_with_changes(tmp_path)
        change = repo / "openspec" / "changes" / "good"
        baseline = repo / "scripts" / "openspec_validation_baseline_good.txt"
        baseline.write_text("# empty\n")
        result = subprocess.run(
            [
                "bash",
                str(Path(__file__).resolve().parent.parent / "validate_openspec_changes.sh"),
                str(repo),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        # introduce a new violation in the baselined change
        (change / "specs" / "test-spec" / "spec.md").write_text(
            VALID_SPEC.replace("SHALL do the thing", "does the thing").replace(
                "SHALL be correct", "be correct"
            )
        )
        result = subprocess.run(
            [
                "bash",
                str(Path(__file__).resolve().parent.parent / "validate_openspec_changes.sh"),
                str(repo),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert "good" in result.stdout + result.stderr

    def test_wrapper_report_only_without_baseline(self, tmp_path):
        """A change WITHOUT a baseline is report-only: never blocks."""
        repo = _fake_repo_with_changes(tmp_path)
        change = repo / "openspec" / "changes" / "reportme"
        (change / "specs" / "bad").mkdir(parents=True)
        (change / "specs" / "bad" / "spec.md").write_text(
            VALID_SPEC.replace("SHALL do the thing", "does the thing").replace(
                "SHALL be correct", "be correct"
            )
        )
        result = subprocess.run(
            [
                "bash",
                str(Path(__file__).resolve().parent.parent / "validate_openspec_changes.sh"),
                str(repo),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "report-only" in result.stdout

    def test_wrapper_fails_when_no_change_dirs(self, tmp_path):
        repo = tmp_path / "empty"
        (repo / "openspec" / "changes").mkdir(parents=True)
        result = subprocess.run(
            [
                "bash",
                str(Path(__file__).resolve().parent.parent / "validate_openspec_changes.sh"),
                str(repo),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert "no active change dirs" in result.stdout


def _fake_repo_with_changes(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    good = repo / "openspec" / "changes" / "good"
    (good / "specs" / "test-spec").mkdir(parents=True)
    (good / "proposal.md").write_text(VALID_PROPOSAL)
    (good / "tasks.md").write_text("## Phase 1\n")
    (good / "specs" / "test-spec" / "spec.md").write_text(VALID_SPEC)
    reportme = repo / "openspec" / "changes" / "reportme"
    (reportme / "specs").mkdir(parents=True)
    (reportme / "proposal.md").write_text(VALID_PROPOSAL)
    (reportme / "tasks.md").write_text("## Phase 1\n")
    return repo


class TestRealChange:
    def test_real_preprod01_is_clean_with_baseline(self):
        """The executed Phase 1 delta must add ZERO new violations beyond the
        recorded baseline for the pre-existing specs."""
        repo = Path(__file__).resolve().parent.parent.parent
        change = repo / "openspec" / "changes" / "preprod01"
        baseline = repo / "scripts" / "openspec_validation_baseline.txt"
        rc = main(["--change", str(change), "--baseline", str(baseline)])
        assert rc == 0, "new structural violations vs the recorded baseline"
