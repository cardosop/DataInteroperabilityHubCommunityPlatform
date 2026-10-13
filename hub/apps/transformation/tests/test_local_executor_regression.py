"""TDD pins for the P11 local-executor regression contract (openspec
run-transformation-on-databricks task 11.5, design D6) — the LOCAL
execution path stays the shipped dbt-native default while the 11.2/11.3
Databricks branches land alongside: the profile resolution remains the
SM path BYTE-FOR-BYTE (the pre-11.2 contract), the estate profile seam
is NEVER called on the local path (the branch is inert), the run-family
command shapes are unchanged, and the deprecated DuckDB/Polars engine's
remaining surface (the legacy migration command) keeps its contract.

Vocabulary note (the 11.5 landing reconciliation): the roadmap's "local
DuckDB/Polars executors" wording predates the dbt-native migration —
the LANDED local path is the dbt-native executor (the SM-path secret
profiles); DuckDB/Polars exist only as the deprecated legacy engine
under `migrate_legacy_transformation_pipelines` (the deep behavior is
pinned by the existing management-command suite; the surface contract
is pinned here).

No mocks: real filesystem profile writes (tmpfs work dir, owner-only
chmod), the REAL executor construction + command family, the REAL
resolver over a patched SM fetch (the 285.9 suite's convention), and
an AST pin for the import boundary (the 0.11 convention).
"""

from __future__ import annotations

import pathlib
import uuid

import pytest
import yaml

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


class TestLocalPathProfileResolution:
    """The local profile output is BYTE-FOR-BYTE the shipped SM shape —
    the 11.2 target branch changed nothing on the default path."""

    def _setup_with_secret(self, tmp_path, monkeypatch, secret):
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda _arn: secret,
        )
        executor = _make_executor(tmp_path)
        executor._setup_profile()
        with open(pathlib.Path(executor.work_dir) / "profiles.yml") as f:
            return executor, yaml.safe_load(f)

    def test_the_local_profile_output_is_byte_for_byte_the_sm_shape(self, tmp_path, monkeypatch):
        executor, data = self._setup_with_secret(
            tmp_path,
            monkeypatch,
            {
                "type": "snowflake",
                "account": "test_account",
                "user": "test_user",
                "password": "test_pass",
            },
        )
        # FULL-dict equality — a drifted key, default, or nesting fails.
        assert data == {
            executor.profile_name: {
                "target": "prod",
                "outputs": {
                    "prod": {
                        "type": "snowflake",
                        "account": "test_account",
                        "user": "test_user",
                        "password": "test_pass",
                        "role": "transform",
                        "database": "analytics",
                        "warehouse": "compute_wh",
                        "schema": "public",
                        "threads": 4,
                        "client_session_keep_alive": False,
                    }
                },
            }
        }

    def test_the_sm_databricks_secret_is_the_local_paths_only_databricks_surface(
        self, tmp_path, monkeypatch
    ):
        # The estate seam + the production exchange must NEVER fire for a
        # databricks SM secret — the local path's databricks branch is
        # the secret-based `_databricks_output`, nothing else.
        from hub.apps.transformation import dbt_executor

        monkeypatch.setattr(
            dbt_executor,
            "_resolve_databricks_warehouse_profile",
            lambda **_kwargs: pytest.fail("the estate seam fired on the local path"),
        )
        monkeypatch.setattr(
            "hub.apps.warehouses.connectors.databricks.resolve_access_token",
            lambda *_a, **_kw: pytest.fail("the production exchange fired on the local path"),
        )

        executor, data = self._setup_with_secret(
            tmp_path,
            monkeypatch,
            {
                "type": "databricks",
                "host": "dbc-test.cloud.databricks.com",
                "http_path": "/sql/1.0/warehouses/wh-1",
                "token": "dapi-sm-token",
            },
        )
        assert data == {
            executor.profile_name: {
                "target": "prod",
                "outputs": {
                    "prod": {
                        "type": "databricks",
                        "host": "dbc-test.cloud.databricks.com",
                        "http_path": "/sql/1.0/warehouses/wh-1",
                        "token": "dapi-sm-token",
                        "catalog": "main",
                        "schema": "public",
                        "threads": 4,
                    }
                },
            }
        }


class TestTheDatabricksBranchIsInertOnTheLocalPath:
    """A LOCAL-target executor never touches the estate machinery."""

    def test_the_local_path_never_calls_the_estate_profile_seam(self, tmp_path, monkeypatch):
        from hub.apps.transformation import dbt_executor

        monkeypatch.setattr(
            dbt_executor,
            "_resolve_databricks_warehouse_profile",
            lambda **_kwargs: pytest.fail("the estate seam fired on the local path"),
        )
        monkeypatch.setattr(
            "hub.apps.transformation.credential_resolver._fetch_secret",
            lambda _arn: {
                "type": "snowflake",
                "account": "a",
                "user": "u",
                "password": "p",
            },
        )
        executor = _make_executor(tmp_path)  # default → LOCAL
        executor._setup_profile()
        assert (pathlib.Path(executor.work_dir) / "profiles.yml").exists()

    def test_the_local_run_family_commands_are_unchanged(self, tmp_path):
        executor = _make_executor(tmp_path)

        def shape(subcommand_parts, *tail):
            # Compound actions split on "-" (the shipped builder): the
            # command family is byte-for-byte the 285.9 contract.
            cmd = ["dbt", *subcommand_parts]
            cmd.extend(
                [
                    "--project-dir",
                    "/srv/dbt",
                    "--profiles-dir",
                    executor.work_dir,
                    "--target",
                    "prod",
                ]
            )
            cmd.extend(tail)
            return cmd

        assert executor._build_dbt_command("parse", project_path="/srv/dbt") == shape(["parse"])
        assert executor._build_dbt_command("run", project_path="/srv/dbt", models=["m1"]) == shape(
            ["run"], "--select", "m1"
        )
        assert executor._build_dbt_command("test", project_path="/srv/dbt") == shape(["test"])
        assert executor._build_dbt_command("docs-generate", project_path="/srv/dbt") == shape(
            ["docs", "generate"]
        )
        assert executor._build_dbt_command("deps", project_path="/srv/dbt") == shape(["deps"])


class TestTheLocalDefaultAndTheLegacySurface:
    """The vocabulary marks local the default; the deprecated engine's
    remaining surface keeps its contract."""

    def test_the_vocabulary_marks_local_the_default(self):
        from hub.apps.transformation.execution_targets import (
            ExecutionTarget,
            resolve_execution_target,
        )

        assert resolve_execution_target(None) is ExecutionTarget.LOCAL
        assert resolve_execution_target("") is ExecutionTarget.LOCAL
        assert ExecutionTarget.LOCAL.value == "local"

    def test_the_legacy_engine_migration_surface_is_unchanged(self):
        from django.core.management import get_commands

        # The deprecated DuckDB/Polars engine's remaining surface is the
        # migration command (the deep behavior is the existing
        # management-command suite's).
        assert "migrate_legacy_transformation_pipelines" in get_commands()

    def test_the_local_executor_imports_no_estate_symbols(self):
        # AST pin (the 0.11 convention): the local path's module cannot
        # touch the databricks_admin estate even accidentally.
        from hub.apps.transformation import dbt_executor

        source = pathlib.Path(dbt_executor.__file__).read_text()
        assert "hub.apps.databricks_admin" not in source
