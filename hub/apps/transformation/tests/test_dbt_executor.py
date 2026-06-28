"""
285.9.1.2 — Tests for DbtExecutor.

Tests profile resolution, dbt command execution, and log capture.
Uses the sample_dbt_project fixture and real file I/O (no mocks for
filesystem operations).
"""

import json
import os
import uuid
from pathlib import Path

import pytest
import yaml

# ── Fixture paths ─────────────────────────────────────────────────────

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_SAMPLE_PROJECT = _FIXTURES_DIR / "sample_dbt_project"
_SAMPLE_RUN_RESULTS = _FIXTURES_DIR / "sample_run_results.json"
_SAMPLE_DBT_LOG = _FIXTURES_DIR / "sample_dbt.log"


# ── Helpers ───────────────────────────────────────────────────────────


def _make_executor(tmp_path, **overrides):
    """Create a DbtExecutor with test-friendly defaults pointing work_dir
    into tmp_path (instead of /tmp) so tests don't leave artifacts."""
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


# ── Profile resolution tests (285.9.1.2.2) ────────────────────────────


@pytest.mark.unit
class TestProfileResolution:
    """Tests for _setup_profile() and _cleanup_profile()."""

    @pytest.mark.unit
    def test_setup_profile_writes_profiles_yml(self, tmp_path, monkeypatch):
        """_setup_profile writes a valid YAML profiles.yml to the work dir."""
        executor = _make_executor(tmp_path)
        # Bypass AWS SM — inject a fake secret so resolve_warehouse_credentials
        # works.  We patch _fetch_secret to return test credentials.
        fake_secret = {
            "type": "snowflake",
            "account": "test_account",
            "user": "test_user",
            "password": "test_pass",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )

        executor._setup_profile()

        profile_path = Path(executor.work_dir) / "profiles.yml"
        assert profile_path.exists()

        with open(profile_path) as f:
            data = yaml.safe_load(f)
        assert executor.profile_name in data
        out = data[executor.profile_name]["outputs"]["prod"]
        assert out["type"] == "snowflake"
        assert out["account"] == "test_account"

    @pytest.mark.unit
    def test_setup_profile_sets_env_var(self, tmp_path, monkeypatch):
        """_setup_profile sets DBT_PROFILES_DIR to the work dir."""
        executor = _make_executor(tmp_path)
        fake_secret = {
            "type": "snowflake",
            "account": "env_test",
            "user": "u",
            "password": "p",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )

        executor._setup_profile()
        assert os.environ.get("DBT_PROFILES_DIR") == executor.work_dir

    @pytest.mark.unit
    def test_cleanup_profile_removes_directory(self, tmp_path, monkeypatch):
        """_cleanup_profile deletes the work directory."""
        executor = _make_executor(tmp_path)
        fake_secret = {
            "type": "snowflake",
            "account": "cleanup_test",
            "user": "u",
            "password": "p",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )

        executor._setup_profile()
        work_dir = executor.work_dir
        assert os.path.isdir(work_dir)

        executor._cleanup_profile()
        assert not os.path.exists(work_dir)

    @pytest.mark.unit
    def test_run_context_cleanup_in_finally(self, tmp_path, monkeypatch):
        """Profile is cleaned up even when an exception is raised."""
        executor = _make_executor(tmp_path)
        fake_secret = {
            "type": "snowflake",
            "account": "finally_test",
            "user": "u",
            "password": "p",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )

        class TestError(Exception):
            pass

        try:
            with executor._profile_context():
                work_dir = executor.work_dir
                assert os.path.isdir(work_dir)
                raise TestError("simulated failure")
        except TestError:
            pass

        # Work dir must be cleaned up despite the exception
        assert not os.path.exists(work_dir)

    @pytest.mark.unit
    def test_profile_name_uses_tenant_slug_pipeline_id(self, tmp_path):
        """Profile name follows meshant_{tenant_slug}_{pipeline_id} convention."""
        executor = _make_executor(tmp_path, tenant_slug="acmecorp", pipeline_id="pipe-abc-123")
        assert executor.profile_name == "meshant_acmecorp_pipe-abc-123"

    @pytest.mark.unit
    def test_setup_profile_with_bigquery_credentials(self, tmp_path, monkeypatch):
        """BigQuery profile is written with keyfile_json (inline dict)."""
        executor = _make_executor(tmp_path)
        bq_secret = {
            "type": "bigquery",
            "project": "my-gcp",
            "dataset": "analytics_ds",
            "keyfile": {"private_key": "k", "client_email": "e@e.com"},
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: bq_secret,
        )

        executor._setup_profile()

        profile_path = Path(executor.work_dir) / "profiles.yml"
        with open(profile_path) as f:
            data = yaml.safe_load(f)
        out = data[executor.profile_name]["outputs"]["prod"]
        assert out["type"] == "bigquery"
        assert "keyfile_json" in out

    @pytest.mark.unit
    def test_work_dir_in_tmpfs(self):
        """Work dir is under /tmp by default (tmpfs for crash-safety)."""
        # Create executor WITHOUT work_dir_root override
        from hub.apps.transformation.dbt_executor import DbtExecutor

        executor = DbtExecutor(
            run_id="testrun123",
            tenant_slug="ts",
            pipeline_id="p1",
            warehouse_credential_ref="arn:...",
            git_credential_ref="arn:...",
        )
        assert executor.work_dir.startswith("/tmp/meshant_dbt_")
        assert "testrun123" in executor.work_dir

    @pytest.mark.unit
    def test_setup_profile_creates_nested_dirs(self, tmp_path, monkeypatch):
        """_setup_profile creates intermediate directories if needed."""
        # Use a deeply nested work_dir_root.
        from hub.apps.transformation.dbt_executor import DbtExecutor

        deep_root = str(tmp_path / "a" / "b")
        executor = DbtExecutor(
            run_id="deep",
            tenant_slug="x",
            pipeline_id="y",
            warehouse_credential_ref="arn:...",
            git_credential_ref="arn:...",
            work_dir_root=deep_root,
        )
        deep_dir = executor.work_dir

        fake_secret = {
            "type": "snowflake",
            "account": "deep",
            "user": "d",
            "password": "p",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )

        executor._setup_profile()
        assert os.path.isdir(deep_dir)
        assert os.path.isfile(os.path.join(deep_dir, "profiles.yml"))

        # Clean up
        executor._cleanup_profile()
        assert not os.path.exists(deep_dir)


# ── Log capture tests (285.9.1.2.3) ───────────────────────────────────


@pytest.mark.unit
class TestLogCapture:
    """Tests for _parse_run_results() and _capture_error_logs()."""

    @pytest.mark.unit
    def test_parse_run_results_extracts_timing(self):
        """Parsed results include per-model execution_time_seconds."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        results = DbtExecutor._parse_run_results(str(_SAMPLE_RUN_RESULTS))
        assert len(results) == 3

        # Successful model
        customers = next(r for r in results if r["unique_id"] == "model.sample_dbt.customers")
        assert customers["status"] == "success"
        assert customers["execution_time_seconds"] == 3.3
        assert customers["rows_affected"] == 150

        # Another successful model
        orders = next(r for r in results if r["unique_id"] == "model.sample_dbt.orders")
        assert orders["status"] == "success"
        assert orders["execution_time_seconds"] == 3.7
        assert orders["rows_affected"] == 320

    @pytest.mark.unit
    def test_parse_run_results_handles_errors(self):
        """Failed model results are included with error metadata."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        results = DbtExecutor._parse_run_results(str(_SAMPLE_RUN_RESULTS))
        broken = next(r for r in results if r["unique_id"] == "model.sample_dbt.broken_model")
        assert broken["status"] == "error"
        assert broken["rows_affected"] == 0
        assert "Database Error" in broken["message"]

    @pytest.mark.unit
    def test_parse_run_results_extracts_elapsed_total(self):
        """Total elapsed_time is extracted from run_results."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        total = DbtExecutor._parse_elapsed_time(str(_SAMPLE_RUN_RESULTS))
        assert total == 11.1

    @pytest.mark.unit
    def test_parse_run_results_missing_file_returns_empty(self):
        """Missing run_results.json returns empty list."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        results = DbtExecutor._parse_run_results("/nonexistent/path/run_results.json")
        assert results == []

    @pytest.mark.unit
    def test_parse_run_results_malformed_json_returns_empty(self, tmp_path):
        """Malformed run_results.json returns empty list (no crash)."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        bad_path = str(tmp_path / "run_results.json")
        with open(bad_path, "w") as f:
            f.write("this is not valid json {{{")

        results = DbtExecutor._parse_run_results(bad_path)
        assert results == []

    @pytest.mark.unit
    def test_parse_run_results_missing_results_key_returns_empty(self, tmp_path):
        """run_results.json without 'results' key returns empty list."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        empty_path = str(tmp_path / "run_results.json")
        with open(empty_path, "w") as f:
            json.dump({"metadata": {"dbt_version": "1.9.0"}}, f)

        results = DbtExecutor._parse_run_results(empty_path)
        assert results == []

    @pytest.mark.unit
    def test_parse_elapsed_time_missing_file_returns_none(self):
        """Missing run_results.json returns None for elapsed time."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        total = DbtExecutor._parse_elapsed_time("/nonexistent/path/run_results.json")
        assert total is None

    @pytest.mark.unit
    def test_parse_elapsed_time_missing_key_returns_none(self, tmp_path):
        """run_results.json without elapsed_time returns None."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        no_elapsed_path = str(tmp_path / "run_results.json")
        with open(no_elapsed_path, "w") as f:
            json.dump({"metadata": {}, "results": []}, f)

        total = DbtExecutor._parse_elapsed_time(no_elapsed_path)
        assert total is None

    @pytest.mark.unit
    def test_capture_error_logs_extracts_error_lines(self):
        """ERROR lines are extracted from dbt.log."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        errors = DbtExecutor._capture_error_logs(str(_SAMPLE_DBT_LOG))
        assert len(errors) >= 1
        assert any("ERROR" in e for e in errors)
        assert any("customer_status" in e for e in errors)

    @pytest.mark.unit
    def test_capture_error_logs_missing_file_returns_empty(self):
        """Missing dbt.log returns empty list."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        errors = DbtExecutor._capture_error_logs("/nonexistent/dbt.log")
        assert errors == []

    @pytest.mark.unit
    def test_build_span_attributes(self):
        """_build_span_attributes returns a Prefect-span-compatible dict."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        results = DbtExecutor._parse_run_results(str(_SAMPLE_RUN_RESULTS))

        attrs = DbtExecutor._build_span_attributes(results, 11.1)
        assert attrs["dbt.models_run"] == 3
        assert attrs["dbt.models_success"] == 2
        assert attrs["dbt.models_error"] == 1
        assert attrs["dbt.total_elapsed_seconds"] == 11.1
        assert "dbt.total_rows_affected" in attrs
        # 150 + 320 + 0 = 470
        assert attrs["dbt.total_rows_affected"] == 470
        # Per-model breakdown
        assert "dbt.model_timing.model.sample_dbt.customers" in attrs
        assert attrs["dbt.model_timing.model.sample_dbt.customers"] == 3.3
        assert "dbt.model_rows.model.sample_dbt.customers" in attrs
        assert attrs["dbt.model_rows.model.sample_dbt.customers"] == 150


# ── Command construction tests (285.9.1.2.1) ──────────────────────────


@pytest.mark.unit
class TestCommandConstruction:
    """Tests for dbt CLI command building."""

    @pytest.mark.unit
    def test_dbt_parse_command(self, tmp_path):
        """dbt_parse builds the correct dbt parse command."""
        executor = _make_executor(tmp_path)
        cmd = executor._build_dbt_command("parse", project_path="/tmp/proj")
        assert cmd[0] == "dbt"
        assert "parse" in cmd
        assert "--project-dir" in cmd
        assert "/tmp/proj" in cmd

    @pytest.mark.unit
    def test_dbt_run_command_default(self, tmp_path):
        """dbt_run builds command with --target but no model selectors."""
        executor = _make_executor(tmp_path)
        cmd = executor._build_dbt_command("run", project_path="/tmp/proj")
        assert "run" in cmd
        assert "--target" in cmd
        assert "prod" in cmd
        # No --select when models is None
        assert "--select" not in cmd

    @pytest.mark.unit
    def test_dbt_run_command_with_models(self, tmp_path):
        """dbt_run with model list adds --select flag."""
        executor = _make_executor(tmp_path)
        cmd = executor._build_dbt_command(
            "run", project_path="/tmp/proj", models=["customers", "orders"]
        )
        assert "run" in cmd
        assert "--select" in cmd
        # Models are space-separated after --select
        select_idx = cmd.index("--select")
        assert cmd[select_idx + 1] == "customers"
        assert cmd[select_idx + 2] == "orders"

    @pytest.mark.unit
    def test_dbt_test_command(self, tmp_path):
        """dbt_test builds dbt test command."""
        executor = _make_executor(tmp_path)
        cmd = executor._build_dbt_command("test", project_path="/tmp/proj")
        assert "test" in cmd

    @pytest.mark.unit
    def test_dbt_docs_generate_command(self, tmp_path):
        """dbt_docs_generate builds dbt docs generate command."""
        executor = _make_executor(tmp_path)
        cmd = executor._build_dbt_command("docs-generate", project_path="/tmp/proj")
        # dbt docs generate is split into "docs" "generate"
        assert "docs" in cmd
        assert "generate" in cmd

    @pytest.mark.unit
    def test_dbt_deps_command(self, tmp_path):
        """dbt_deps builds dbt deps command."""
        executor = _make_executor(tmp_path)
        cmd = executor._build_dbt_command("deps", project_path="/tmp/proj")
        assert "deps" in cmd
        assert "--project-dir" in cmd

    @pytest.mark.unit
    def test_command_includes_profile_dir(self, tmp_path, monkeypatch):
        """Commands include --profiles-dir pointing to work dir."""
        executor = _make_executor(tmp_path)
        fake_secret = {
            "type": "snowflake",
            "account": "a",
            "user": "u",
            "password": "p",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )
        executor._setup_profile()

        cmd = executor._build_dbt_command("run", project_path="/tmp/proj")
        assert "--profiles-dir" in cmd
        profiles_idx = cmd.index("--profiles-dir")
        assert cmd[profiles_idx + 1] == executor.work_dir


# ── Integration tests with sample project ─────────────────────────────


@pytest.mark.unit
class TestWithSampleProject:
    """Tests that verify behaviour with the real sample_dbt_project fixture."""

    @pytest.mark.unit
    def test_project_yml_is_valid(self):
        """Sample project's dbt_project.yml is parsable and has required keys."""
        project_yml = _SAMPLE_PROJECT / "dbt_project.yml"
        with open(project_yml) as f:
            data = yaml.safe_load(f)
        assert data["name"] == "sample_dbt"
        assert data["profile"] == "meshant_dbt"
        assert "model-paths" in data
        assert data["model-paths"] == ["models"]

    @pytest.mark.unit
    def test_model_files_exist(self):
        """Sample project has at least 2 SQL models."""
        models_dir = _SAMPLE_PROJECT / "models"
        sql_files = list(models_dir.glob("*.sql"))
        assert len(sql_files) == 2, f"Expected 2 SQL models, got: {[f.name for f in sql_files]}"

    @pytest.mark.unit
    def test_schema_yml_exists(self):
        """Sample project has a schema.yml with model definitions."""
        schema_yml = _SAMPLE_PROJECT / "models" / "schema.yml"
        with open(schema_yml) as f:
            data = yaml.safe_load(f)
        assert "models" in data
        assert len(data["models"]) == 2

    @pytest.mark.unit
    def test_dbt_command_construction_with_sample_project(self, tmp_path, monkeypatch):
        """Verify dbt command construction and profile setup with sample project (no actual dbt exec)."""
        executor = _make_executor(tmp_path)
        fake_secret = {
            "type": "snowflake",
            "account": "sample_acct",
            "user": "sample_user",
            "password": "sample_pass",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )

        # Verify profile setup works with the sample project
        executor._setup_profile()
        assert os.path.isfile(os.path.join(executor.work_dir, "profiles.yml"))

        # Verify command construction with sample project path
        cmd = executor._build_dbt_command(
            "run", project_path=str(_SAMPLE_PROJECT), models=["customers"]
        )
        assert str(_SAMPLE_PROJECT) in cmd
        assert "customers" in cmd

        executor._cleanup_profile()


# ── Executor lifecycle tests ──────────────────────────────────────────


@pytest.mark.unit
class TestExecutorLifecycle:
    """Tests for DbtExecutor init, context manager, error paths."""

    @pytest.mark.unit
    def test_init_stores_attributes(self, tmp_path):
        """Executor init stores all constructor params correctly."""
        executor = _make_executor(
            tmp_path,
            tenant_slug="acme",
            pipeline_id="p99",
        )
        assert executor.tenant_slug == "acme"
        assert executor.pipeline_id == "p99"
        assert executor.profile_name == "meshant_acme_p99"
        assert executor.warehouse_credential_ref is not None
        assert executor.git_credential_ref is not None

    @pytest.mark.unit
    def test_profile_context_cleanup_on_success(self, tmp_path, monkeypatch):
        """After successful execution, profile is cleaned up."""
        executor = _make_executor(tmp_path)
        fake_secret = {
            "type": "snowflake",
            "account": "ctx_acct",
            "user": "ctx_user",
            "password": "ctx_pass",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )

        with executor._profile_context():
            assert os.path.isdir(executor.work_dir)
        assert not os.path.exists(executor.work_dir)

    @pytest.mark.unit
    def test_work_dir_permissions(self, tmp_path, monkeypatch):
        """Created work dir has owner read/write/execute permissions."""
        executor = _make_executor(tmp_path)
        fake_secret = {
            "type": "snowflake",
            "account": "perm_acct",
            "user": "p",
            "password": "p",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )
        executor._setup_profile()

        st = os.stat(executor.work_dir)
        # Owner has rwx
        assert st.st_mode & 0o700 == 0o700

        executor._cleanup_profile()

    @pytest.mark.unit
    def test_profiles_yml_restricted_permissions(self, tmp_path, monkeypatch):
        """profiles.yml is owner-only (0o600) to prevent credential exposure."""
        executor = _make_executor(tmp_path)
        fake_secret = {
            "type": "snowflake",
            "account": "sec_acct",
            "user": "s",
            "password": "s",
        }
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda arn: fake_secret,
        )
        executor._setup_profile()

        profile_path = os.path.join(executor.work_dir, "profiles.yml")
        st = os.stat(profile_path)
        # Owner read+write only, no group/other access
        assert (st.st_mode & 0o777) == 0o600

        executor._cleanup_profile()

    @pytest.mark.unit
    def test_cleanup_handles_missing_dir(self, tmp_path):
        """Cleanup of non-existent directory doesn't raise."""
        executor = _make_executor(tmp_path)
        # Don't call _setup_profile — work dir doesn't exist
        assert not os.path.exists(executor.work_dir)
        executor._cleanup_profile()  # Should not raise

    @pytest.mark.unit
    def test_sanitize_path_component(self):
        """Path components with special chars are sanitized."""
        from hub.apps.transformation.dbt_executor import DbtExecutor

        assert DbtExecutor._sanitize_path_component("hello") == "hello"
        assert DbtExecutor._sanitize_path_component("path/with/slashes") == "path_with_slashes"
        assert DbtExecutor._sanitize_path_component("a b c") == "a_b_c"
