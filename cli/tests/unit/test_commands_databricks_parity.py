"""Shared DoD gate (openspec add-databricks-control-plane — "CLI parity
commands shipped") — the CLI covers every databricks control-plane API
surface.

Mock-free by design (the test_commands_databricks convention): these
pins exercise ONLY offline behaviors — command registration, the
route↔command parity map, and click usage errors — which happen before
any HTTP request. The HTTP contract is pinned by the real-API suites
(cli/tests/integration/test_databricks_*_real_api.py).

The parity pin reads the REAL backend urlconf names and asserts a CLI
command path + the endpoint fragment it issues exist for each — a new
API route without CLI coverage (or a renamed endpoint) fails here.
"""

from pathlib import Path

from datahub_cli.main import cli

CLI_DIR = Path(__file__).resolve().parent.parent.parent / "datahub_cli"
DATABRICKS_CMD = CLI_DIR / "commands" / "databricks.py"

# One entry per databricks control-plane URL name the backend exposes:
# (url name in hub/apps/databricks_admin/urls.py, CLI command path,
#  endpoint fragment the command must issue).
PARITY_SURFACES = [
    # 2.8 — UC change-request approval pipeline
    ("databricks-uc-change-list", ["uc", "changes", "list"], "uc/changes/"),
    ("databricks-uc-change-inbox", ["uc", "changes", "inbox"], "uc/changes/pending-approvals/"),
    ("databricks-uc-change-detail", ["uc", "changes", "show"], "uc/changes/"),
    ("databricks-uc-change-submit", ["uc", "changes", "submit"], "/submit/"),
    ("databricks-uc-change-approve", ["uc", "changes", "approve"], "/approve/"),
    ("databricks-uc-change-reject", ["uc", "changes", "reject"], "/reject/"),
    ("databricks-uc-change-timeline", ["uc", "changes", "timeline"], "/timeline/"),
    ("databricks-uc-change-comments", ["uc", "changes", "comment"], "/comments/"),
    # 4.5 — job-fleet reads
    ("databricks-job-list", ["jobs", "list"], "/jobs/"),
    ("databricks-job-run-list", ["jobs", "runs"], "/jobs/"),
    # 7.6 — cost budgets
    ("databricks-budget-list", ["budgets", "list"], "databricks/budgets/"),
    # 8.x — account plane
    ("databricks-account", ["accounts", "list"], "databricks/accounts/"),
    ("databricks-account-estate", ["accounts", "estate"], "databricks/estate-summary/"),
    ("databricks-sso", ["sso", "workspaces"], "databricks/sso/"),
    # 12.x — ML assets
    ("ml-asset-models", ["ml", "models"], "ml-assets/models/"),
    ("ml-asset-model-versions", ["ml", "log-version"], "/versions/"),
    ("ml-asset-model-alias", ["ml", "alias"], "/aliases/"),
    ("ml-asset-feature-tables", ["ml", "feature-tables"], "ml-assets/feature-tables/"),
    ("ml-asset-feature-tag", ["ml", "feature-tag"], "/feature-tag/"),
    ("ml-asset-serving-endpoints", ["ml", "serving-endpoints"], "ml-assets/serving-endpoints/"),
    (
        "ml-asset-vector-search-endpoints",
        ["ml", "vector-endpoints"],
        "ml-assets/vector-search-endpoints/",
    ),
    # 1.3 — UC browse extras (external locations / storage credentials /
    # table detail ride the same mirror-first contract as `uc ls`)
    ("databricks-uc-external-locations", ["uc", "external-locations"], "uc/external-locations/"),
    ("databricks-uc-storage-credentials", ["uc", "storage-credentials"], "uc/storage-credentials/"),
    ("databricks-uc-table-detail", ["uc", "table"], "/uc/tables/"),
    # 0.x — workspace registry extras (credentials + soft-delete)
    ("databricks-credential-list", ["workspaces", "credentials"], "/credentials/"),
    ("databricks-workspace-detail", ["workspaces", "delete"], "databricks/workspaces/"),
    # 10.7 — DLT update/delete (the list/create/start/stop parity shipped
    # with task 10.7)
    ("dlt-pipeline-detail", ["dlt", "update"], "dlt-pipelines/"),
    ("dlt-pipeline-detail", ["dlt", "delete"], "dlt-pipelines/"),
]


class TestParityMap:
    """Every databricks API route family has a CLI command that issues
    the endpoint (the route↔command parity pin)."""

    def test_every_surface_has_a_registered_command(self, runner):
        source = DATABRICKS_CMD.read_text()
        for url_name, command_path, fragment in PARITY_SURFACES:
            result = runner.invoke(cli, ["databricks", *command_path, "--help"])
            assert result.exit_code == 0, (
                f"{url_name}: `databricks {' '.join(command_path)}` must exist "
                f"(exit {result.exit_code})"
            )
            assert fragment in source, (
                f"{url_name}: the CLI command must issue {fragment!r} "
                f"(endpoint drift — check {DATABRICKS_CMD.name})"
            )

    def test_new_groups_listed_in_databricks_help(self, runner):
        result = runner.invoke(cli, ["databricks", "--help"])
        assert result.exit_code == 0
        for group in ("jobs", "budgets", "ml", "accounts", "sso"):
            assert group in result.output, f"`databricks {group}` must be listed"

    def test_changes_subgroup_listed_under_uc(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "--help"])
        assert result.exit_code == 0
        assert "changes" in result.output

    def test_workspaces_credentials_subgroup_listed(self, runner):
        result = runner.invoke(cli, ["databricks", "workspaces", "--help"])
        assert result.exit_code == 0
        assert "credentials" in result.output


class TestUcChangesUsageGuards:
    """The 2.8 approval-pipeline commands enforce their options locally
    (click UsageError, exit 2) — before any HTTP request."""

    def test_list_requires_workspace(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "changes", "list"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

    def test_inbox_takes_no_required_args(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "changes", "inbox", "--help"])
        assert result.exit_code == 0

    def test_show_requires_workspace_and_change(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "changes", "show"])
        assert result.exit_code == 2
        result = runner.invoke(cli, ["databricks", "uc", "changes", "show", "--workspace", "w-1"])
        assert result.exit_code == 2
        assert "change" in result.output.lower()

    def test_approve_requires_workspace_and_change(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "changes", "approve"])
        assert result.exit_code == 2
        result = runner.invoke(
            cli, ["databricks", "uc", "changes", "approve", "--workspace", "w-1"]
        )
        assert result.exit_code == 2
        assert "change" in result.output.lower()

    def test_comment_requires_text(self, runner):
        result = runner.invoke(
            cli,
            [
                "databricks",
                "uc",
                "changes",
                "comment",
                "--workspace",
                "w-1",
                "--change",
                "00000000-0000-0000-0000-000000000002",
            ],
        )
        assert result.exit_code == 2
        assert "text" in result.output.lower()

    def test_create_requires_workspace_and_file(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "changes", "create"])
        assert result.exit_code == 2
        result = runner.invoke(cli, ["databricks", "uc", "changes", "create", "--workspace", "w-1"])
        assert result.exit_code == 2
        assert "file" in result.output.lower()


class TestJobsUsageGuards:
    """The 4.5 job-fleet reads enforce their options locally."""

    def test_list_requires_workspace(self, runner):
        result = runner.invoke(cli, ["databricks", "jobs", "list"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

    def test_runs_requires_workspace_and_job(self, runner):
        result = runner.invoke(cli, ["databricks", "jobs", "runs"])
        assert result.exit_code == 2
        result = runner.invoke(cli, ["databricks", "jobs", "runs", "--workspace", "w-1"])
        assert result.exit_code == 2
        assert "job" in result.output.lower()


class TestBudgetsUsageGuards:
    """The 7.6 budget read is tenant-scoped — no required args."""

    def test_list_takes_no_required_args(self, runner):
        result = runner.invoke(cli, ["databricks", "budgets", "list", "--help"])
        assert result.exit_code == 0


class TestMlAssetsUsageGuards:
    """The 12.x ML-asset commands enforce their options locally."""

    def test_models_requires_workspace(self, runner):
        result = runner.invoke(cli, ["databricks", "ml", "models"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

    def test_register_model_requires_workspace_and_file(self, runner):
        result = runner.invoke(cli, ["databricks", "ml", "register-model"])
        assert result.exit_code == 2
        result = runner.invoke(cli, ["databricks", "ml", "register-model", "--workspace", "w-1"])
        assert result.exit_code == 2
        assert "file" in result.output.lower()

    def test_alias_set_requires_version_num(self, runner):
        result = runner.invoke(
            cli,
            [
                "databricks",
                "ml",
                "alias",
                "set",
                "--workspace",
                "w-1",
                "--model",
                "00000000-0000-0000-0000-000000000002",
                "--alias",
                "champion",
            ],
        )
        assert result.exit_code == 2
        assert "version-num" in result.output.lower()

    def test_feature_tag_requires_table(self, runner):
        result = runner.invoke(cli, ["databricks", "ml", "feature-tag", "mark"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

        result = runner.invoke(
            cli, ["databricks", "ml", "feature-tag", "mark", "--workspace", "w-1"]
        )
        assert result.exit_code == 2
        assert "table" in result.output.lower()


class TestAccountsUsageGuards:
    """The 8.x account-plane commands enforce their options locally."""

    def test_create_requires_file(self, runner):
        result = runner.invoke(cli, ["databricks", "accounts", "create"])
        assert result.exit_code == 2
        assert "file" in result.output.lower()

    def test_metastores_requires_account(self, runner):
        result = runner.invoke(cli, ["databricks", "accounts", "metastores"])
        assert result.exit_code == 2
        assert "account" in result.output.lower()


class TestUcBrowseExtrasUsageGuards:
    """The 1.3 browse extras enforce --workspace locally."""

    def test_external_locations_requires_workspace(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "external-locations"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

    def test_storage_credentials_requires_workspace(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "storage-credentials"])
        assert result.exit_code == 2
        assert "workspace" in result.output.lower()

    def test_table_detail_requires_workspace_and_table(self, runner):
        result = runner.invoke(cli, ["databricks", "uc", "table"])
        assert result.exit_code == 2
        result = runner.invoke(cli, ["databricks", "uc", "table", "--workspace", "w-1"])
        assert result.exit_code == 2
        assert "table" in result.output.lower()
