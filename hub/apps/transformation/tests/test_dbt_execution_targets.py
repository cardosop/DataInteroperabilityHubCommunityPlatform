"""TDD pins for the P11 execution-target selection + the executor's
target modes (openspec run-transformation-on-databricks task 11.2) —
the D1 config-branch discipline: ``local`` stays the unchanged
DEFAULT, ``databricks_warehouse`` swaps ONLY the profiles.yml output
to the landed dbt-databricks shape (the 11.3-verified branch:
``type/host/http_path/token/catalog/schema/threads``), and
``databricks_job`` dispatches through the registered dispatcher
facade with ZERO local subprocess. An unknown target refuses with the
classified code — never a silent local fallback. Prefect orchestration
is untouched (no ``services/`` changes — the flow's config contract is
additive).

No mocks: real filesystem profile writes (tmpfs work dir, owner-only
chmod), real command construction, the REAL facade registry. The
sanctioned seams are the module-level profile-resolver symbol (the
0.8 factory convention — the executor pins the target MECHANICS; the
11.3 suite owns the real estate/M2M resolution) and a locally
registered test dispatcher (the facade's consumer side — the
databricks_admin suite owns the real dispatcher).
"""

from __future__ import annotations

import os
import uuid

import pytest
import yaml

from hub.apps.transformation.exceptions import TransformationExecutionError

pytestmark = pytest.mark.unit


def _make_executor(tmp_path, **overrides):
    from hub.apps.transformation.dbt_executor import DbtExecutor

    run_id = overrides.pop("run_id", uuid.uuid4().hex[:12])
    return DbtExecutor(
        run_id=run_id,
        tenant_slug=overrides.pop("tenant_slug", "testtenant"),
        pipeline_id=overrides.pop("pipeline_id", "pipe123"),
        warehouse_credential_ref=overrides.pop(
            "warehouse_credential_ref",
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:wh-test",
        ),
        git_credential_ref=overrides.pop(
            "git_credential_ref",
            "arn:aws:secretsmanager:us-east-1:123456789012:secret:git-test",
        ),
        work_dir_root=str(tmp_path),
        **overrides,
    )


# ── Target selection (D1) ─────────────────────────────────────────────


class TestResolveExecutionTarget:
    def test_local_is_the_unchanged_default(self):
        from hub.apps.transformation.execution_targets import (
            ExecutionTarget,
            resolve_execution_target,
        )

        assert resolve_execution_target(None) is ExecutionTarget.LOCAL
        assert resolve_execution_target("") is ExecutionTarget.LOCAL
        assert resolve_execution_target("local") is ExecutionTarget.LOCAL

    def test_the_databricks_vocabulary_resolves(self):
        from hub.apps.transformation.execution_targets import (
            ExecutionTarget,
            resolve_execution_target,
        )

        assert resolve_execution_target("databricks_warehouse") is (
            ExecutionTarget.DATABRICKS_WAREHOUSE
        )
        assert resolve_execution_target("databricks_job") is ExecutionTarget.DATABRICKS_JOB

    def test_an_unknown_target_refuses_never_falls_back(self):
        from hub.apps.transformation.execution_targets import resolve_execution_target

        with pytest.raises(TransformationExecutionError) as excinfo:
            resolve_execution_target("cassandra")
        assert excinfo.value.error_code == "DATABRICKS_EXECUTION_TARGET_INVALID"
        assert "cassandra" in str(excinfo.value)

    def test_the_executor_refuses_an_unknown_target_at_construction(self, tmp_path):
        with pytest.raises(TransformationExecutionError) as excinfo:
            _make_executor(tmp_path, execution_target="databricks_snowflake")
        assert excinfo.value.error_code == "DATABRICKS_EXECUTION_TARGET_INVALID"


class TestLocalTargetRegression:
    """D6 — the local path is byte-for-byte unchanged: the DEFAULT
    executor constructs with LOCAL and builds the same command the
    shipped 285.9 pins assert."""

    def test_default_construction_targets_local(self, tmp_path):
        from hub.apps.transformation.execution_targets import ExecutionTarget

        executor = _make_executor(tmp_path)
        assert executor.execution_target is ExecutionTarget.LOCAL

    def test_the_local_command_shape_is_unchanged(self, tmp_path):
        executor = _make_executor(tmp_path)
        cmd = executor._build_dbt_command("run", project_path="/srv/dbt", models=["m1"])
        assert cmd == [
            "dbt",
            "run",
            "--project-dir",
            "/srv/dbt",
            "--profiles-dir",
            executor.work_dir,
            "--target",
            "prod",
            "--select",
            "m1",
        ]


# ── Warehouse-direct mode (D3) ────────────────────────────────────────


class TestWarehouseDirectTarget:
    def _install_resolver(self, monkeypatch, *, profile_output=None):
        """The sanctioned seam: redirect the executor's module-level
        profile-resolver symbol (the 0.8 factory convention)."""
        from hub.apps.transformation import dbt_executor

        def _resolver(**kwargs):
            captured["kwargs"] = kwargs
            return {
                "meshant_testtenant_pipe123": {
                    "target": "prod",
                    "outputs": {
                        "prod": profile_output
                        or {
                            "type": "databricks",
                            "host": "dbc-abc.cloud.databricks.com",
                            "http_path": "/sql/1.0/warehouses/wh1",
                            "token": "dapi-test",
                            "catalog": "meshant",
                            "schema": "gold",
                            "threads": 4,
                        }
                    },
                }
            }

        captured: dict = {}
        monkeypatch.setattr(dbt_executor, "_resolve_databricks_warehouse_profile", _resolver)
        return captured

    def test_the_profile_output_swaps_to_the_databricks_shape(self, tmp_path, monkeypatch):
        """The tmpfs profiles.yml discipline stays; ONLY the target
        output changes to the landed dbt-databricks adapter shape."""
        captured = self._install_resolver(monkeypatch)
        executor = _make_executor(tmp_path, execution_target="databricks_warehouse")

        executor._setup_profile()
        try:
            profiles_path = os.path.join(executor.work_dir, "profiles.yml")
            assert os.path.isfile(profiles_path), "the profiles.yml discipline is unchanged"
            mode = os.stat(profiles_path).st_mode
            assert mode & 0o077 == 0, "credentials stay owner-only"
            with open(profiles_path) as f:
                profile = yaml.safe_load(f)
            output = profile["meshant_testtenant_pipe123"]["outputs"]["prod"]
            assert output == {
                "type": "databricks",
                "host": "dbc-abc.cloud.databricks.com",
                "http_path": "/sql/1.0/warehouses/wh1",
                "token": "dapi-test",
                "catalog": "meshant",
                "schema": "gold",
                "threads": 4,
            }
            # The resolver receives the executor's profile name — the
            # same per-run isolation contract the SM path carries.
            assert captured["kwargs"]["profile_name"] == "meshant_testtenant_pipe123"
        finally:
            executor._cleanup_profile()

    def test_the_dbt_command_shape_is_target_agnostic(self, tmp_path):
        """`run_results.json` parsing is target-agnostic (D3) — the
        CLI invocation is byte-identical to the local path's (same
        run identity, only the target differs)."""
        run_id = uuid.uuid4().hex[:12]
        executor = _make_executor(tmp_path, run_id=run_id, execution_target="databricks_warehouse")
        cmd = executor._build_dbt_command("run", project_path="/srv/dbt")
        local = _make_executor(tmp_path, run_id=run_id)
        assert cmd == local._build_dbt_command("run", project_path="/srv/dbt")

    def test_a_resolver_failure_refuses_before_any_subprocess(self, tmp_path, monkeypatch):
        """A resolution failure surfaces the classified error and the
        run NEVER reaches the subprocess stage (the profile context
        refuses first)."""
        from hub.apps.transformation import dbt_executor

        def _boom(**_kwargs):
            raise TransformationExecutionError(
                "masked credential failure", error_code="DATABRICKS_DBT_PROFILE_RESOLUTION_FAILED"
            )

        monkeypatch.setattr(dbt_executor, "_resolve_databricks_warehouse_profile", _boom)
        executor = _make_executor(tmp_path, execution_target="databricks_warehouse")
        with pytest.raises(TransformationExecutionError) as excinfo:
            executor.dbt_run("/srv/dbt")
        assert excinfo.value.error_code == "DATABRICKS_DBT_PROFILE_RESOLUTION_FAILED"
        assert not os.path.isdir(executor.work_dir), (
            "the refusal happens before the work dir is ever created"
        )


# ── Job mode (D1) ─────────────────────────────────────────────────────


class TestDatabricksJobTarget:
    def _install_dispatcher(self, monkeypatch):
        from hub.apps.transformation import execution_targets

        calls: list[dict] = []

        def _dispatcher(**kwargs):
            calls.append(kwargs)
            return {
                "job_id": "job-123",
                "status": "SUCCEEDED",
                "run_id": 42,
                "resource_type": "DATABRICKS_JOB",
            }

        monkeypatch.setattr(execution_targets, "_JOB_DISPATCHERS", [_dispatcher])
        return calls

    def test_dbt_run_dispatches_with_zero_local_execution(self, tmp_path, monkeypatch):
        """The job target never writes a profiles.yml and never builds
        a local command — the run rides the registered dispatcher with
        the exact run context."""
        calls = self._install_dispatcher(monkeypatch)
        executor = _make_executor(
            tmp_path,
            execution_target="databricks_job",
            tenant_id="t-1",
            workspace_id="ws-1",
            runner_job_id="runner-1",
        )

        result = executor.dbt_run("/srv/dbt", models=["stg_orders", "marts_revenue"])

        assert len(calls) == 1
        assert calls[0]["tenant_id"] == "t-1"
        assert calls[0]["workspace_id"] == "ws-1"
        assert calls[0]["runner_job_id"] == "runner-1"
        assert calls[0]["select"] == ["stg_orders", "marts_revenue"]
        assert calls[0]["target"] == "prod"
        assert result["job_dispatch"]["job_id"] == "job-123"
        assert result["job_dispatch"]["status"] == "SUCCEEDED"
        assert not os.path.isdir(executor.work_dir), (
            "the job path never creates the local work dir — zero local execution"
        )

    def test_dbt_test_dispatches_through_the_same_facade(self, tmp_path, monkeypatch):
        calls = self._install_dispatcher(monkeypatch)
        executor = _make_executor(
            tmp_path,
            execution_target="databricks_job",
            tenant_id="t-1",
            workspace_id="ws-1",
            runner_job_id="runner-1",
        )
        executor.dbt_test("/srv/dbt")
        assert calls[0]["select"] is None

    def test_a_missing_dispatch_context_refuses(self, tmp_path, monkeypatch):
        self._install_dispatcher(monkeypatch)
        executor = _make_executor(tmp_path, execution_target="databricks_job", tenant_id="t-1")
        with pytest.raises(TransformationExecutionError) as excinfo:
            executor.dbt_run("/srv/dbt")
        assert excinfo.value.error_code == "DATABRICKS_DBT_RUNNER_JOB_MISSING"

    def test_an_unregistered_dispatcher_refuses(self, tmp_path):
        """The facade refuses classified when NO provider dispatcher is
        registered — the unregistered state is simulated by emptying the
        facade registry (the provider registers at app-ready; the real
        registration is pinned by the databricks_admin suite)."""
        from hub.apps.transformation import execution_targets

        registered = execution_targets._JOB_DISPATCHERS[:]
        execution_targets._JOB_DISPATCHERS[:] = []
        try:
            executor = _make_executor(
                tmp_path,
                execution_target="databricks_job",
                tenant_id="t-1",
                workspace_id="ws-1",
                runner_job_id="runner-1",
            )
            with pytest.raises(TransformationExecutionError) as excinfo:
                executor.dbt_run("/srv/dbt")
            assert excinfo.value.error_code == "DATABRICKS_DBT_JOB_DISPATCH_UNAVAILABLE"
        finally:
            execution_targets._JOB_DISPATCHERS[:] = registered

    def test_the_dispatchers_classified_code_rides_through(self, tmp_path, monkeypatch):
        """The facade converts the provider's classified code into the
        transformation error family (D3 — the executor's failure
        classification is unchanged). Boundary-clean: the stand-in
        dispatcher carries a plain ``code`` attribute, exactly like the
        provider's ``DatabricksDbtDispatchError``."""
        from hub.apps.transformation import execution_targets

        class _ProviderRefusal(Exception):
            def __init__(self, code: str, message: str):
                super().__init__(message)
                self.code = code

        def _refusing_dispatcher(**_kwargs):
            raise _ProviderRefusal("DATABRICKS_DBT_RUNNER_JOB_MISSING", "runner job not mirrored")

        monkeypatch.setattr(execution_targets, "_JOB_DISPATCHERS", [_refusing_dispatcher])
        executor = _make_executor(
            tmp_path,
            execution_target="databricks_job",
            tenant_id="t-1",
            workspace_id="ws-1",
            runner_job_id="runner-1",
        )
        with pytest.raises(TransformationExecutionError) as excinfo:
            executor.dbt_run("/srv/dbt")
        assert excinfo.value.error_code == "DATABRICKS_DBT_RUNNER_JOB_MISSING"

    def test_docs_generate_and_parse_stay_local_even_on_job_targets(self, tmp_path, monkeypatch):
        """Project validation (parse/docs) stays local — only run/test
        dispatch (the D3/D4 contract: compile locally, execute remote)."""
        self._install_dispatcher(monkeypatch)
        executor = _make_executor(
            tmp_path,
            execution_target="databricks_job",
            tenant_id="t-1",
            workspace_id="ws-1",
            runner_job_id="runner-1",
        )
        # parse/docs still build the local command — no dispatch.
        cmd = executor._build_dbt_command("parse", project_path="/srv/dbt")
        assert cmd[1] == "parse"
