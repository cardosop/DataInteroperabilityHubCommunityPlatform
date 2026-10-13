"""
Unit tests for the Databricks workspace CLI commands (openspec
add-databricks-control-plane task 0.15).

Mock-free by design: every test here exercises only offline behaviors —
click usage errors and command registration — which happen BEFORE any
HTTP request. API-contract behavior is pinned by the real-API suite at
cli/tests/integration/test_databricks_workspaces_real_api.py.
"""

from datahub_cli.main import cli


class TestDatabricksGroupRegistration:
    """The ``databricks`` group is wired onto the root CLI."""

    def test_databricks_group_listed_in_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "databricks" in result.output

    def test_workspaces_subgroup_listed_in_help(self, runner):
        result = runner.invoke(cli, ["databricks", "--help"])
        assert result.exit_code == 0
        assert "workspaces" in result.output


class TestRegisterUsageGuards:
    """register enforces its options locally (click UsageError, exit 2)."""

    def test_register_requires_name(self, runner):
        result = runner.invoke(
            cli,
            [
                "databricks",
                "workspaces",
                "register",
                "--host",
                "h.cloud.databricks.com",
                "--cloud",
                "AWS",
            ],
        )
        assert result.exit_code == 2
        assert "name" in result.output.lower()

    def test_register_requires_host(self, runner):
        result = runner.invoke(
            cli,
            ["databricks", "workspaces", "register", "--name", "n1", "--cloud", "AWS"],
        )
        assert result.exit_code == 2
        assert "host" in result.output.lower()

    def test_register_requires_cloud(self, runner):
        result = runner.invoke(
            cli,
            [
                "databricks",
                "workspaces",
                "register",
                "--name",
                "n1",
                "--host",
                "h.cloud.databricks.com",
            ],
        )
        assert result.exit_code == 2
        assert "cloud" in result.output.lower()

    def test_register_requires_region(self, runner):
        # region is REQUIRED — the backend serializer requires it and
        # residency validation consumes it; the CLI mirrors that contract.
        result = runner.invoke(
            cli,
            [
                "databricks",
                "workspaces",
                "register",
                "--name",
                "n1",
                "--host",
                "h.cloud.databricks.com",
                "--cloud",
                "AWS",
            ],
        )
        assert result.exit_code == 2
        assert "region" in result.output.lower()

    def test_register_rejects_unknown_cloud(self, runner):
        result = runner.invoke(
            cli,
            [
                "databricks",
                "workspaces",
                "register",
                "--name",
                "n1",
                "--host",
                "h.cloud.databricks.com",
                "--cloud",
                "ORACLE",
            ],
        )
        assert result.exit_code == 2
        assert "AWS" in result.output  # the Choice lists the valid values


class TestListUsageGuards:
    def test_list_rejects_unknown_format(self, runner):
        result = runner.invoke(cli, ["databricks", "workspaces", "list", "--format", "yaml"])
        assert result.exit_code == 2


class TestTestUsageGuards:
    def test_test_requires_workspace_id(self, runner):
        result = runner.invoke(cli, ["databricks", "workspaces", "test"])
        assert result.exit_code == 2


class TestRotateUsageGuards:
    def test_rotate_requires_workspace_and_credential_ids(self, runner):
        result = runner.invoke(cli, ["databricks", "workspaces", "rotate"])
        assert result.exit_code == 2


class TestUcGroupRegistration:
    """The ``databricks uc`` group is wired (task 1.9 — UC mirror browsing)."""

    def test_uc_subgroup_listed_in_help(self, runner):
        result = runner.invoke(cli, ["databricks", "--help"])
        assert result.exit_code == 0
        assert "uc" in result.output

    def test_uc_ls_listed_in_uc_help(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "--help"])
        assert result.exit_code == 0
        assert "ls" in result.output


class TestUcLsUsageGuards:
    """``uc ls`` enforces its options locally (click UsageError, exit 2)
    — offline behavior only; the API contract lives in the real-API suite."""

    def test_uc_ls_requires_workspace(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "ls"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

    def test_uc_ls_rejects_unknown_kind(self, runner):
        result = runner.invoke(
            cli,
            [
                "databricks",
                "uc",
                "ls",
                "--workspace",
                "00000000-0000-0000-0000-000000000001",
                "--schema",
                "00000000-0000-0000-0000-000000000002",
                "--kind",
                "not-a-kind",
            ],
        )
        assert result.exit_code == 2
        assert "kind" in result.output.lower()

    def test_uc_ls_catalog_and_schema_are_mutually_scoped(self, runner):
        """--schema implies the tables listing; --catalog and --schema
        together are accepted (schema wins — it is the deeper drill), but
        the usage surface must accept both flags."""
        result = runner.invoke(
            cli,
            [
                "databricks",
                "uc",
                "ls",
                "--workspace",
                "00000000-0000-0000-0000-000000000001",
                "--catalog",
                "00000000-0000-0000-0000-000000000003",
                "--schema",
                "00000000-0000-0000-0000-000000000004",
                "--help",
            ],
        )
        assert result.exit_code == 0


class TestWarehousesGroupRegistration:
    """The ``databricks warehouses`` group is wired onto the CLI."""

    def test_warehouses_subgroup_listed_in_help(self, runner):
        result = runner.invoke(cli, ["databricks", "--help"])
        assert result.exit_code == 0
        assert "warehouses" in result.output


class TestWarehousesUsageGuards:
    """The lifecycle commands enforce their options locally (click
    UsageError, exit 2) — before any HTTP request."""

    def test_ls_requires_workspace(self, runner):
        result = runner.invoke(cli, ["databricks", "warehouses", "ls"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

    def test_start_requires_workspace_and_warehouse(self, runner):
        result = runner.invoke(cli, ["databricks", "warehouses", "start"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

        result = runner.invoke(cli, ["databricks", "warehouses", "start", "--workspace", "w-1"])
        assert result.exit_code == 2
        assert "warehouse" in result.output.lower()

    def test_stop_requires_workspace_and_warehouse(self, runner):
        result = runner.invoke(cli, ["databricks", "warehouses", "stop"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

        result = runner.invoke(cli, ["databricks", "warehouses", "stop", "--workspace", "w-1"])
        assert result.exit_code == 2
        assert "warehouse" in result.output.lower()
