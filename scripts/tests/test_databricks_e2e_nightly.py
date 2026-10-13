"""TDD suite for Phase 9 task 9.2 — the Databricks E2E nightly workflow.

Pins the workflow CONTRACT without executing it (the workflow is env-gated
and inert everywhere): the `DATABRICKS_E2E=1` gate, the OIDC permissions
posture, the `meshant_e2e_*` sandbox naming, the `always()` auto-destroy,
and the hard-budget pre-flight ordered BEFORE any create call. The helper
scripts are pinned against their real behavior — the budget arithmetic
(pure) and the sandbox lifecycle driven through the PRODUCTION
``DatabricksAccountClient`` over a REAL local HTTP server (the 8.3
RecordingHandler convention; no mocks).

The empty-200-delete pin guards the real root-cause class: the account
API's delete endpoints answer EMPTY bodies — a JSON parse would
misclassify a successful destroy as a transport error.
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

import pytest
import yaml

REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from hub.apps.databricks_admin.account_client import DatabricksAccountClient
from hub.apps.databricks_admin.tests._http import RecordingHandler
from scripts.databricks_e2e import budget, sandbox

WORKFLOW_PATH = Path(REPO_ROOT) / ".github/workflows/databricks-e2e-nightly.yml"

_SECRET_PATTERN = re.compile(r"(dapi[0-9a-f]{20,}|-----BEGIN|client_secret\s*[:=])", re.I)


class TestWorkflowContract:
    """The YAML pins the design D1 + spec scenarios: gate, OIDC, naming,
    auto-destroy, hard budget — asserted structurally, never executed."""

    @pytest.fixture
    def workflow(self):
        if not WORKFLOW_PATH.exists():
            pytest.fail("RED: .github/workflows/databricks-e2e-nightly.yml does not exist")
        return yaml.safe_load(WORKFLOW_PATH.read_text())

    def _job(self, workflow, name):
        for job_id, job in workflow["jobs"].items():
            if job_id == name:
                return job
        pytest.fail(f"job {name!r} not found")

    def _steps(self, job):
        return list(job["steps"])

    def test_triggers_are_nightly_schedule_and_dispatch(self, workflow):
        assert "schedule" in workflow.get(True, {})
        cron = workflow[True]["schedule"][0].get("cron", "")
        assert re.match(r"^[\d ,*/#?\-]+$", cron), "the schedule must carry a cron expression"
        assert any(c.isdigit() for c in cron), "the cron expression must carry concrete digits"
        assert "workflow_dispatch" in workflow.get(True, {})

    def test_the_env_gate_keeps_everything_inert_without_the_flag(self, workflow):
        job = self._job(workflow, "databricks-e2e")
        gate = str(job.get("if", ""))
        assert "DATABRICKS_E2E" in gate, (
            "the sandbox job must be gated on the DATABRICKS_E2E variable"
        )
        assert "1" in gate, (
            "the gate must require the armed value — ZERO real-infrastructure operations without it"
        )
        # The gated job is the ONLY job — nothing sandbox-touching lives outside.
        assert list(workflow["jobs"]) == ["databricks-e2e"]

    def test_oidc_permissions_posture(self, workflow):
        permissions = workflow.get("permissions", {})
        assert permissions.get("id-token") == "write", "OIDC federation requires id-token: write"
        assert permissions.get("contents") == "read"
        for key, value in permissions.items():
            if key not in ("contents", "id-token"):
                assert value != "write", f"no write permissions beyond OIDC ({key})"

    def test_no_secret_material_in_the_workflow_file(self):
        text = WORKFLOW_PATH.read_text()
        assert not _SECRET_PATTERN.search(text), (
            "no token material in the workflow — credentials come from "
            "environment secrets via the OIDC posture"
        )
        secret_refs = re.findall(r"\${{ secrets\.(\w+) }}", text)
        for name in secret_refs:
            assert name.startswith("DATABRICKS_E2E_"), (
                f"the workflow only references DATABRICKS_E2E_* secrets, got {name}"
            )

    def test_budget_preflight_runs_before_the_create_step(self, workflow):
        steps = self._steps(self._job(workflow, "databricks-e2e"))
        budget_idx = next(
            i for i, s in enumerate(steps) if "budget" in str(s.get("name", "")).lower()
        )
        create_idx = next(
            i
            for i, s in enumerate(steps)
            if "sandbox" in str(s.get("run", "")) and "create" in str(s.get("run", ""))
        )
        assert budget_idx < create_idx, "the hard-budget pre-flight MUST run BEFORE any create call"

    def test_autodestroy_is_always_and_after_the_suite(self, workflow):
        steps = self._steps(self._job(workflow, "databricks-e2e"))
        destroy_idx = next(i for i, s in enumerate(steps) if "destroy" in str(s.get("run", "")))
        destroy_step = steps[destroy_idx]
        assert "always()" in str(destroy_step.get("if", "")), (
            "the auto-destroy MUST run in always() — a failed run never leaves a sandbox behind"
        )
        suite_idx = next(i for i, s in enumerate(steps) if "pytest" in str(s.get("run", "")))
        assert destroy_idx > suite_idx, "destroy follows the suite"

    def test_the_sandbox_naming_convention_is_wired(self, workflow):
        # The convention lives ONLY in scripts/databricks_e2e/sandbox.py —
        # no workflow step may hardcode the prefix in a command (the doc
        # header may NAME the convention; a run value may not).
        run_values = " ".join(
            str(step.get("run", "")) for step in self._steps(self._job(workflow, "databricks-e2e"))
        )
        assert "sandbox" in run_values, "the workflow delegates to the sandbox module"
        assert "meshant_e2e_" not in run_values, (
            "no step hardcodes the sandbox prefix — the naming convention "
            "lives in ONE place (sandbox.py)"
        )


class TestBudgetArithmetic:
    """The hard-budget pre-flight is pure arithmetic — pinned exactly."""

    def test_projected_run_cost_sums_the_leg_table_times_the_multiplier(self):
        cost = budget.projected_run_cost(
            legs=["journey", "contracts"],
            dbu_table={"journey": 10, "contracts": 2, "overhead": 1},
            multiplier=1.5,
        )
        assert cost == 18, "only the REQUESTED legs sum, then the multiplier applies"

    def test_unknown_leg_is_refused(self):
        with pytest.raises(ValueError, match="unknown"):
            budget.projected_run_cost(
                legs=["journey", "bogus"], dbu_table={"journey": 10}, multiplier=1.0
            )

    def test_check_budget_refuses_above_the_ceiling_with_the_numbers(self):
        with pytest.raises(budget.BudgetExceeded) as excinfo:
            budget.check_budget(projected=51, ceiling=50)
        assert "51" in str(excinfo.value)
        assert "50" in str(excinfo.value)

    def test_check_budget_passes_at_or_under_the_ceiling(self):
        budget.check_budget(projected=50, ceiling=50)
        budget.check_budget(projected=49, ceiling=50)

    def test_a_zero_ceiling_refuses_any_positive_projection(self):
        with pytest.raises(budget.BudgetExceeded):
            budget.check_budget(projected=1, ceiling=0)


class TestSandboxNaming:
    """The meshant_e2e_* convention — unique, bounded, one place."""

    def test_names_carry_the_convention_and_the_run_identity(self):
        name = sandbox.sandbox_name("987654321")
        assert name.startswith("meshant_e2e_")
        assert "987654321" in name
        assert len(name) <= 255

    def test_distinct_runs_never_collide(self):
        assert sandbox.sandbox_name("1") != sandbox.sandbox_name("2")

    def test_selector_matches_only_the_convention(self):
        rows = [
            {"workspace_name": "meshant_e2e_42", "workspace_id": 1},
            {"workspace_name": "prod-workspace", "workspace_id": 2},
            {"workspace_name": "meshant_e2e_43", "workspace_id": 3},
        ]
        assert [r["workspace_id"] for r in sandbox.owned_sandboxes(rows)] == [1, 3]


class TestSandboxLifecycleOverRealHTTP:
    """The create/destroy scripts drive the PRODUCTION client over a REAL
    local account-API server (no mocks — the 8.3 convention)."""

    @pytest.fixture
    def local_account_server(self):
        import http.server
        import threading

        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield port
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def _client(self, port, account_id=None):
        self._account_id = str(account_id or uuid.uuid4())
        return DatabricksAccountClient(
            self._account_id,
            {"token": "dapi-account-token"},
            base_url=f"http://127.0.0.1:{port}",
        )

    def test_destroy_is_idempotent_when_no_sandboxes_exist(self, local_account_server):
        import json

        RecordingHandler.json_script = [json.dumps({"workspaces": []})]
        sandbox.destroy_sandbox(self._client(local_account_server))
        assert len(RecordingHandler.requests) == 1, (
            "a list with no matches issues the list call and ZERO deletes"
        )

    def test_destroy_deletes_every_convention_match(self, local_account_server):
        import json

        account_id = uuid.uuid4()
        RecordingHandler.json_script = [
            json.dumps(
                {
                    "workspaces": [
                        {"workspace_name": "meshant_e2e_1", "workspace_id": 101},
                        {"workspace_name": "other", "workspace_id": 202},
                        {"workspace_name": "meshant_e2e_2", "workspace_id": 303},
                    ]
                }
            ),
            "",  # delete 101 — the account API answers an EMPTY 200 body
            "",  # delete 303
        ]
        sandbox.destroy_sandbox(self._client(local_account_server, account_id))
        paths = [req["path"] for req in RecordingHandler.requests]
        base = f"/api/2.0/accounts/{account_id}/workspaces"
        assert paths == [base, f"{base}/101", f"{base}/303"]
        assert [req["method"] for req in RecordingHandler.requests] == ["GET", "DELETE", "DELETE"]

    def test_create_builds_the_convention_named_workspace(self, local_account_server):
        import json

        RecordingHandler.json_script = [
            json.dumps({"workspace_name": "meshant_e2e_77", "deployment_name": "d-77"})
        ]
        envelope = sandbox.create_sandbox(self._client(local_account_server), run_id="77")
        assert envelope["workspace_name"] == "meshant_e2e_77"
        (request,) = RecordingHandler.requests
        assert request["method"] == "POST"
        body = json.loads(request["body"])
        assert body["workspace_name"].startswith("meshant_e2e_")
        assert "77" in body["workspace_name"]
