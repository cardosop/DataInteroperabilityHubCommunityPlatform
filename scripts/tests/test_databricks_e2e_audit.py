"""TDD suite for Phase 9 task 9.6 — the run bookend audit + report artifact.

Pins three layers against the landed reality:

1. The VOCABULARY — `DATABRICKS_E2E_RUN_PASSED` / `DATABRICKS_E2E_RUN_FAILED`
   are real constants in `hub.apps/audit/event_types.py` (name == value
   convention) AND ride `__all__` (the vocabulary catalogue every emit
   site's tests pin against).
2. The EMITTER (`scripts/databricks_e2e/audit.py`) — real behavior, no
   mocks: one envelope per run with the run outcome, the sandbox identity
   (derived through the ONE naming convention in `sandbox.py`, never
   hardcoded), and the duration; best-effort — a missing or corrupt
   report still yields a FAILED envelope with the evidence, and the
   emitter never raises (the report artifact must never be blocked —
   the Phase 273 discipline).
3. The WORKFLOW — the suite step carries `--junitxml`, the audit
   emission and the `always()` report publish steps exist and follow the
   destroy backstop, and the 9.2 contract still holds (single job, no
   hardcoded sandbox prefix in run values).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.databricks_e2e import audit, sandbox

WORKFLOW_PATH = REPO_ROOT / ".github/workflows/databricks-e2e-nightly.yml"

TOKEN_PATTERN = re.compile(r"(dapi[0-9a-f]{20,}|client_secret|bearer[ ]?token)", re.I)


class TestVocabulary:
    """The audit vocabulary registers both run-bookend events."""

    def test_constants_exist_and_follow_the_name_equals_value_convention(self):
        from hub.apps.audit import event_types

        for name in ("DATABRICKS_E2E_RUN_PASSED", "DATABRICKS_E2E_RUN_FAILED"):
            assert hasattr(event_types, name), f"event_types.{name} missing"
            value = getattr(event_types, name)
            assert isinstance(value, str), f"{name} must be str, got {type(value)}"
            assert value == name, (
                f"convention: constant value matches the constant name ({name} != {value})"
            )

    def test_constants_ride_the_all_registry(self):
        from hub.apps.audit import event_types

        for name in ("DATABRICKS_E2E_RUN_PASSED", "DATABRICKS_E2E_RUN_FAILED"):
            assert name in event_types.__all__, (
                f"{name} must ride __all__ — the vocabulary catalogue the "
                "emit-site tests pin against"
            )


class TestEmitterBehavior:
    """The emitter's real behavior — driven with real report dicts and
    real files in tmp_path, never a mock."""

    def _report(self, outcome: str) -> dict:
        return {
            "schema_version": 1,
            "run_id": "1234567890",
            "sandbox": None,
            "legs": {
                "workspace_register": {"status": "passed", "requests": 1, "evidence": []},
                "warehouse_minimum": {"status": "passed", "requests": 2, "evidence": []},
            },
            "outcome": outcome,
        }

    def test_a_passed_report_composes_the_passed_envelope(self):
        envelope = audit.compose_event(
            self._report("PASSED"),
            run_id="1234567890",
            duration_seconds=42.5,
            workspace_host="https://adb-e2e.cloud.databricks.com",
        )
        assert envelope["event_type"] == "DATABRICKS_E2E_RUN_PASSED"
        assert envelope["outcome"] == "PASSED"
        assert envelope["run_id"] == "1234567890"
        assert envelope["duration_seconds"] == 42.5
        assert envelope["sandbox"]["workspace_name"] == sandbox.sandbox_name("1234567890"), (
            "the sandbox identity derives through the ONE naming convention "
            "(sandbox.py), never a hardcoded prefix"
        )
        assert envelope["sandbox"]["workspace_host"] == "https://adb-e2e.cloud.databricks.com"

    def test_a_failed_report_composes_the_failed_envelope(self):
        report = self._report("PASSED")
        report["legs"]["warehouse_minimum"]["status"] = "failed"
        report["outcome"] = "FAILED"
        envelope = audit.compose_event(
            report, run_id="1234567890", duration_seconds=None, workspace_host=None
        )
        assert envelope["event_type"] == "DATABRICKS_E2E_RUN_FAILED"
        assert envelope["outcome"] == "FAILED"
        assert envelope["sandbox"]["workspace_host"] is None

    def test_main_writes_the_envelope_next_to_the_report(self, tmp_path):
        report_path = tmp_path / "e2e_report.json"
        report_path.write_text(json.dumps(self._report("PASSED")))
        audit.main(
            [
                "--report",
                str(report_path),
                "--run-id",
                "1234567890",
                "--run-started-at",
                "2026-09-14T20:01:05Z",
            ]
        )
        envelope_path = tmp_path / "e2e_audit_event.json"
        assert envelope_path.is_file(), "the envelope must land next to the report"
        envelope = json.loads(envelope_path.read_text())
        assert envelope["event_type"] == "DATABRICKS_E2E_RUN_PASSED"
        assert isinstance(envelope["duration_seconds"], (int, float)), (
            "the duration is the run's elapsed seconds (never fabricated)"
        )
        assert not TOKEN_PATTERN.search(envelope_path.read_text()), (
            "the envelope never carries credential material"
        )

    def test_a_missing_report_still_yields_a_failed_envelope(self, tmp_path):
        audit.main(
            [
                "--report",
                str(tmp_path / "e2e_report.json"),
                "--run-id",
                "1234567890",
                "--run-started-at",
                "2026-09-14T20:01:05Z",
            ]
        )
        envelope_path = tmp_path / "e2e_audit_event.json"
        assert envelope_path.is_file()
        envelope = json.loads(envelope_path.read_text())
        assert envelope["event_type"] == "DATABRICKS_E2E_RUN_FAILED", (
            "no report means no evidence of a pass — the envelope fails closed"
        )
        assert envelope["evidence"]["report"] == "missing"

    def test_a_corrupt_report_still_yields_a_failed_envelope(self, tmp_path):
        report_path = tmp_path / "e2e_report.json"
        report_path.write_text("{not json")
        audit.main(
            [
                "--report",
                str(report_path),
                "--run-id",
                "1234567890",
                "--run-started-at",
                "2026-09-14T20:01:05Z",
            ]
        )
        envelope = json.loads((tmp_path / "e2e_audit_event.json").read_text())
        assert envelope["event_type"] == "DATABRICKS_E2E_RUN_FAILED"
        assert envelope["evidence"]["report"] == "unparseable"

    def test_an_unparseable_started_at_never_crashes(self, tmp_path):
        report_path = tmp_path / "e2e_report.json"
        report_path.write_text(json.dumps(self._report("PASSED")))
        audit.main(
            [
                "--report",
                str(report_path),
                "--run-id",
                "1234567890",
                "--run-started-at",
                "garbage",
            ]
        )
        envelope = json.loads((tmp_path / "e2e_audit_event.json").read_text())
        assert envelope["event_type"] == "DATABRICKS_E2E_RUN_PASSED", (
            "a broken timestamp must not flip the outcome — only the duration degrades"
        )
        assert envelope["duration_seconds"] is None


class TestWorkflowSteps:
    """The workflow's 9.6 steps — inert everywhere until the gate is armed."""

    @pytest.fixture
    def steps(self):
        if not WORKFLOW_PATH.exists():
            pytest.fail("RED: .github/workflows/databricks-e2e-nightly.yml does not exist")
        workflow = yaml.safe_load(WORKFLOW_PATH.read_text())
        job = workflow["jobs"]["databricks-e2e"]
        return list(job["steps"])

    def _step(self, steps, needle):
        for step in steps:
            if needle in str(step.get("run", "")) or needle in str(step.get("uses", "")):
                return step
        pytest.fail(f"step containing {needle!r} not found")

    def test_the_suite_step_carries_the_junit_output(self, steps):
        suite = self._step(steps, "pytest")
        assert "--junitxml" in str(suite.get("run", "")), (
            "the suite must produce the JUnit XML for the report artifact"
        )

    def test_the_audit_emission_step_runs_always(self, steps):
        emission = self._step(steps, "scripts.databricks_e2e.audit")
        assert "always()" in str(emission.get("if", "")), (
            "the audit envelope is best-effort on every path — a failed run "
            "still emits the FAILED event"
        )
        assert "${{ github.run_started_at }}" in str(emission.get("run", "")), (
            "the emitter receives the run's started-at for the duration"
        )

    def test_the_report_publish_step_is_always_and_after_the_emission(self, steps):
        publish = self._step(steps, "upload-artifact")
        assert "always()" in str(publish.get("if", "")), "no failure path loses the report evidence"
        publish_paths = str(publish.get("with", {}).get("path", ""))
        assert "databricks_e2e/report" in publish_paths, (
            "the artifact carries the report directory (journey report + audit envelope + JUnit)"
        )
        emission_idx = next(
            i
            for i, s in enumerate(steps)
            if "scripts.databricks_e2e.audit" in str(s.get("run", ""))
        )
        publish_idx = next(
            i for i, s in enumerate(steps) if "upload-artifact" in str(s.get("uses", ""))
        )
        assert publish_idx > emission_idx, "the envelope must exist before the publish"

    def test_the_destroy_backstop_still_precedes_the_bookend_steps(self, steps):
        destroy_idx = next(i for i, s in enumerate(steps) if "destroy" in str(s.get("run", "")))
        emission_idx = next(
            i
            for i, s in enumerate(steps)
            if "scripts.databricks_e2e.audit" in str(s.get("run", ""))
        )
        assert destroy_idx > 0
        assert emission_idx > destroy_idx, (
            "the auto-destroy keeps its always() position before the bookends"
        )

    def test_no_step_hardcodes_the_sandbox_prefix(self, steps):
        run_values = " ".join(str(s.get("run", "")) for s in steps)
        assert "meshant_e2e_" not in run_values, (
            "the 9.2 contract holds: the naming convention lives ONLY in sandbox.py"
        )


class TestReportArtifactPath:
    """The generated report directory never reaches git."""

    def test_the_report_path_is_gitignored(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text()
        assert "tests/integration/databricks_e2e/report/" in gitignore
