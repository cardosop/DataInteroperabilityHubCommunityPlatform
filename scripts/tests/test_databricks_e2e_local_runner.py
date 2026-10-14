"""TDD pins for ``scripts/databricks_e2e/local_runner.py`` — the gated
local driver behind ``make test-batch-13-8`` (close-test-coverage-gaps 0.4).

Pins the wrapper contract WITHOUT touching real Databricks infrastructure:

- the gate is pure: ``DATABRICKS_E2E=1`` + account credentials, else a
  SKIPPED exit 0 with the reason — and ZERO infrastructure calls;
- the sequence mirrors the nightly workflow ONE-FOR-ONE (budget → create →
  suite → always-destroy → always-audit), pinned by a real-file parity
  check against ``databricks-e2e-nightly.yml``;
- the failure paths run END-TO-END against a REAL local HTTP server (the
  8.3 RecordingHandler convention — no mocks): a refused budget still
  sweeps + audits; a failed create still sweeps + audits and the run
  exits with the step's failure code;
- the audit envelope lands next to the report with the convention-named
  sandbox identity.

No mocks anywhere: the driver spawns the REAL budget/sandbox/audit module
mains as subprocesses with a hermetic env; the only stand-in is the
scripted HTTP server the client talks to over real sockets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from scripts.databricks_e2e import local_runner as runner
from hub.apps.databricks_admin.e2e_tooling.sandbox import sandbox_name


def _armed_env(port: int | None = None, budget_dbus: str = "0") -> dict[str, str]:
    env: dict[str, str] = {
        runner.GATE_ENV: "1",
        runner.ACCOUNT_ID_ENV: "account-123",
        runner.ACCOUNT_TOKEN_ENV: "dapi-account-token",
        "DATABRICKS_E2E_BUDGET_DBUS": budget_dbus,
        runner.RUN_ID_ENV: "77",
    }
    if port is not None:
        env["DATABRICKS_E2E_ACCOUNT_BASE_URL"] = f"http://127.0.0.1:{port}"
    return env


class TestGatePure:
    def test_unarmed_gate_names_the_flag(self):
        reason = runner.gate_skip_reason({})
        assert reason is not None
        assert "DATABRICKS_E2E=1" in reason

    def test_armed_gate_names_each_missing_account_credential(self):
        reason = runner.gate_skip_reason({"DATABRICKS_E2E": "1"})
        assert reason is not None
        assert "DATABRICKS_E2E_ACCOUNT_ID" in reason
        assert "DATABRICKS_E2E_ACCOUNT_TOKEN" in reason

    def test_non_one_values_are_not_armed(self):
        for value in ("", "0", "true", "yes"):
            env = {"DATABRICKS_E2E": value}
            assert runner.gate_skip_reason(env) is not None

    def test_fully_armed_gate_passes(self):
        assert runner.gate_skip_reason(_armed_env()) is None


class TestRunId:
    def test_pinned_env_id_wins(self):
        assert runner.make_run_id({"DATABRICKS_E2E_RUN_ID": "abc123"}) == "abc123"

    def test_github_run_id_falls_back(self):
        assert runner.make_run_id({"GITHUB_RUN_ID": "424242"}) == "424242"

    def test_timestamp_shape_when_nothing_pinned(self):
        from datetime import UTC, datetime

        run_id = runner.make_run_id({}, now=datetime(2026, 9, 28, 13, 45, 6, tzinfo=UTC))
        assert run_id.isdigit()
        assert len(run_id) == 14
        assert run_id.startswith("20260928")


class TestSuiteArgv:
    def test_suite_argv_mirrors_the_nightly_step(self):
        argv = runner.suite_argv(Path("/tmp/report"))
        assert argv == [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/databricks_e2e/",
            "-q",
            "--timeout=1800",
            "--junitxml=/tmp/report/junit.xml",
        ]


class TestRunFailurePaths:
    """Real subprocesses, real module mains, real HTTP against a scripted
    local server — the 8.3 convention (no mocks)."""

    @pytest.fixture
    def local_account_server(self):
        import http.server
        import threading

        from hub.apps.databricks_admin.tests._http import RecordingHandler

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

    def test_unarmed_run_skips_without_any_step(self, capsys):
        rc = runner.run(env={}, cwd=REPO_ROOT)
        out = capsys.readouterr().out
        assert rc == 0
        assert "[13-8] SKIPPED" in out
        assert runner.BUDGET_MARKER not in out
        assert runner.CREATE_MARKER not in out
        assert runner.DESTROY_MARKER not in out

    def test_budget_refusal_stops_before_create_and_still_sweeps_and_audits(
        self, capsys, tmp_path, local_account_server
    ):
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        # Destroy will hit the account API once (list) — script a terminal
        # 401 so the sweep fails fast without retries.
        RecordingHandler.script = [401]
        env = _armed_env(local_account_server)  # BUDGET_DBUS=0 → refused
        rc = runner.run(env=env, cwd=tmp_path)
        captured = capsys.readouterr()
        assert rc == 1, "the budget refusal must fail the run"
        # budget.py reports the refusal on STDERR
        combined = captured.out + captured.err
        assert "BUDGET REFUSED" in combined
        assert runner.CREATE_MARKER not in combined, "a refused budget must die BEFORE any create"
        assert runner.DESTROY_MARKER in combined, "the always-sweep must run even on refusal"
        assert runner.AUDIT_MARKER in combined, "the audit bookend must run even on refusal"
        envelope = tmp_path / "tests/integration/databricks_e2e/report" / "e2e_audit_event.json"
        assert envelope.is_file()
        payload = json.loads(envelope.read_text())
        assert payload["event_type"] == "DATABRICKS_E2E_RUN_FAILED"
        assert payload["sandbox"]["workspace_name"] == sandbox_name("77")

    def test_create_failure_still_sweeps_and_audits(self, capsys, tmp_path, local_account_server):
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        # create POST → 401 (terminal, no retries); destroy GET → 401.
        RecordingHandler.script = [401, 401]
        env = _armed_env(local_account_server, budget_dbus="1000")
        rc = runner.run(env=env, cwd=tmp_path)
        out = capsys.readouterr().out
        assert rc == 1, "a failed create must fail the run"
        assert runner.CREATE_MARKER in out
        assert runner.SUITE_MARKER not in out, "the suite must not run when create failed"
        assert runner.DESTROY_MARKER in out, "the always-destroy must run on create failure"
        assert runner.AUDIT_MARKER in out, "the audit bookend must run on create failure"
        envelope = tmp_path / "tests/integration/databricks_e2e/report" / "e2e_audit_event.json"
        assert envelope.is_file()
        payload = json.loads(envelope.read_text())
        assert payload["event_type"] == "DATABRICKS_E2E_RUN_FAILED"
        assert payload["sandbox"]["workspace_name"] == sandbox_name("77")


class TestWorkflowParity:
    """The driver and the nightly workflow must sequence the SAME modules
    in the SAME order — drift between them silently changes what the
    local run proves.

    Occurrence-aware matching: the driver builds argv as lists, so the
    literal ``"sandbox destroy"`` pair never appears in its source — the
    FIRST ``hub.apps.databricks_admin.e2e_tooling.sandbox`` occurrence is the create
    step, the SECOND is the destroy step (the nightly spells both out).
    """

    STEPS = ("budget", "create", "suite", "destroy", "audit")

    def _positions(self, text: str) -> dict[str, int]:
        def idx_of(marker: str, occurrence: int = 1) -> int:
            pos = -1
            for _ in range(occurrence):
                pos = text.find(marker, pos + 1)
                assert pos >= 0, f"{marker!r} (occurrence {occurrence}) missing"
            return pos

        return {
            "budget": idx_of("scripts.databricks_e2e.budget"),
            "create": idx_of("hub.apps.databricks_admin.e2e_tooling.sandbox", 1),
            "suite": idx_of("pytest tests/integration/databricks_e2e"),
            "destroy": idx_of("hub.apps.databricks_admin.e2e_tooling.sandbox", 2),
            "audit": idx_of("hub.apps.databricks_admin.e2e_tooling.audit"),
        }

    def _ordered_steps(self, text: str) -> list[str]:
        positions = self._positions(text)
        return sorted(positions, key=positions.get)

    def test_driver_sequences_the_nightly_order(self):
        driver_text = (REPO_ROOT / "scripts" / "databricks_e2e" / "local_runner.py").read_text()
        assert self._ordered_steps(driver_text) == list(self.STEPS)

    def test_nightly_sequences_the_same_order(self):
        workflow = (REPO_ROOT / ".github/workflows/databricks-e2e-nightly.yml").read_text()
        assert self._ordered_steps(workflow) == list(self.STEPS)

    def test_driver_and_nightly_agree_on_the_order(self):
        driver_text = (REPO_ROOT / "scripts" / "databricks_e2e" / "local_runner.py").read_text()
        workflow = (REPO_ROOT / ".github/workflows/databricks-e2e-nightly.yml").read_text()
        assert self._ordered_steps(driver_text) == self._ordered_steps(workflow)
