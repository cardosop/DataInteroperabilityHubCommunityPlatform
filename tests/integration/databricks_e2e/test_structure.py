"""Phase 9 (task 9.3) — the suite's OWN contract pins: the environment
gate, the leg order, the sandbox discovery, the workflow invocation, the
title coverage, and the report schema.

These pins run WITHOUT the sandbox (pure structure + the W16 gate
behavior — the gate helper driven with a controlled environment). The
live legs live in test_journey.py behind the session gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.integration.databricks_e2e import journey_plan

WORKFLOW_PATH = Path(REPO_ROOT) / ".github/workflows/databricks-e2e-nightly.yml"


class TestEnvironmentGate:
    """The W16 policy (the 9.4 conftest's shared contract): CI raises,
    local skips, never a silent pass."""

    def test_ci_raises_when_the_gate_is_unset(self, monkeypatch):
        from envpolicy import EnvironmentFailureError, skip_or_fail

        monkeypatch.delenv(journey_plan.E2E_GATE, raising=False)
        monkeypatch.setenv("CI", "true")
        with pytest.raises(EnvironmentFailureError, match=r"\[W16\]"):
            skip_or_fail(f"gate unset: {journey_plan.gate_reason()}")
        # The gate itself reports the reason — the W16 failure announces
        # the environment, never a silent pass.
        assert journey_plan.gate_reason() is not None

    def test_the_gate_requires_the_armed_value(self, monkeypatch):
        monkeypatch.setenv(journey_plan.E2E_GATE, "0")
        assert "DATABRICKS_E2E=1 is required" in (journey_plan.gate_reason() or "")

    def test_the_gate_requires_the_workspace_credentials(self, monkeypatch):
        monkeypatch.setenv(journey_plan.E2E_GATE, "1")
        monkeypatch.setenv(journey_plan.WORKSPACE_HOST_ENV, "adb-e2e.cloud.databricks.com")
        monkeypatch.delenv(journey_plan.WORKSPACE_TOKEN_ENV, raising=False)
        reason = journey_plan.gate_reason() or ""
        assert journey_plan.WORKSPACE_TOKEN_ENV in reason, (
            "the workspace token is part of the gate — the journey's legs authenticate with it"
        )

    def test_an_armed_environment_passes_the_gate(self, monkeypatch):
        monkeypatch.setenv(journey_plan.E2E_GATE, "1")
        monkeypatch.setenv(journey_plan.WORKSPACE_HOST_ENV, "adb-e2e.cloud.databricks.com")
        monkeypatch.setenv(journey_plan.WORKSPACE_TOKEN_ENV, "dapi-2")
        assert journey_plan.gate_reason() is None


class TestJourneyPlan:
    def test_the_legs_are_ordered_for_dependencies(self):
        expected = (
            "workspace_register",
            "warehouse_minimum",
            "uc_schema_table_grant",
            "uc_verify",
            "uc_destroy",
            "job_run_now",
            "dlt_pipeline_lifecycle",
            "budget_sync",
            "delta_sharing_reference_client",
        )
        assert expected == journey_plan.JOURNEY_LEGS, (
            "the registry pins the dependency-driven order — the warehouse "
            "precedes the SQL legs (schema/table + billing-usage need a "
            "RUNNING warehouse)"
        )

    def test_every_title_surface_maps_to_a_leg(self):
        # The 9.3 title's surfaces: register, schema/table/grant, verify,
        # destroy, warehouse min, job run-now, DLT create/start/stop,
        # budget sync, Delta Sharing vs reference client.
        title_surfaces = {
            "register": "workspace_register",
            "schema_table_grant": "uc_schema_table_grant",
            "verify": "uc_verify",
            "destroy": "uc_destroy",
            "warehouse_min": "warehouse_minimum",
            "job_run_now": "job_run_now",
            "dlt": "dlt_pipeline_lifecycle",
            "budget_sync": "budget_sync",
            "delta_sharing": "delta_sharing_reference_client",
        }
        legs = set(journey_plan.JOURNEY_LEGS)
        assert set(title_surfaces.values()) <= legs, (
            "no title surface may be missing from the registry"
        )

    def test_the_sandbox_discovery_selects_only_convention_rows(self):
        rows = [
            {"workspace_name": "meshant_e2e_123456", "workspace_id": "1"},
            {"workspace_name": "customer-prod-ws", "workspace_id": "2"},
            {"workspace_name": "meshant_e2e_654321", "workspace_id": "3"},
        ]
        owned = journey_plan.owned_sandbox_rows(rows)
        assert [r["workspace_id"] for r in owned] == ["1", "3"], (
            "only meshant_e2e_* workspaces are selected — never a real customer workspace"
        )

    def test_the_resolution_never_guesses(self):
        rows = [
            {"workspace_name": "meshant_e2e_123456", "workspace_id": "1"},
            {"workspace_name": "meshant_e2e_654321", "workspace_id": "2"},
        ]
        # No run-id match at all → fail.
        with pytest.raises(ValueError, match="expected exactly one sandbox"):
            journey_plan.resolve_sandbox(rows, "999999")
        # Multiple matches → fail (never pick one arbitrarily) — the
        # shared prefix substring matches BOTH rows.
        with pytest.raises(ValueError, match="expected exactly one sandbox"):
            journey_plan.resolve_sandbox(rows, "e2e")

    def test_the_report_schema_covers_every_leg(self):
        report = journey_plan.EMPTY_REPORT
        assert set(report["legs"]) == set(journey_plan.JOURNEY_LEGS)
        for entry in report["legs"].values():
            assert entry == {"status": "pending", "requests": 0, "evidence": []}
        serialized = journey_plan.report_json(report)
        assert '"schema_version": 1' in serialized
        assert '"outcome": null' in serialized


class TestWorkflowInvocation:
    def test_the_workflow_invokes_this_suite(self):
        import yaml

        workflow = yaml.safe_load(WORKFLOW_PATH.read_text())
        steps = list(workflow["jobs"]["databricks-e2e"]["steps"])
        suite_step = next(s for s in steps if "pytest" in str(s.get("run", "")))
        assert "tests/integration/databricks_e2e/" in suite_step["run"], (
            "the nightly workflow must point at THIS suite path"
        )
        assert "--timeout" in suite_step["run"], "the live suite needs the hard per-run timeout"

    def test_the_suite_directory_is_a_pytest_module(self):
        init = Path(__file__).resolve().parent / "__init__.py"
        assert init.is_file()
