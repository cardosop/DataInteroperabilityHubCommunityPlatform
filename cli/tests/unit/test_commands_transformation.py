"""
Unit tests for Transformation CLI commands.

Tests: pipelines (list, get, create, update, delete, validate),
runs (list, get, submit, cancel), plan-limits.
"""

from datahub_cli.main import cli
from tests.fixtures.test_data import fresh_id

# Unique per test process (and per xdist worker) so a static literal
# can never collide across parallel runs — Phase 216.X.2.
ASSET_ID = fresh_id("asset")


class TestTransformationPipelineList:
    """Test transformation pipelines list command"""

    def test_list_pipelines(self, runner, mock_api_client):
        """Test listing transformation pipelines"""
        mock_api_client.get.return_value = {
            "results": [
                {
                    "id": "pipe-1",
                    "name": "dbt_daily",
                    "status": "ACTIVE",
                    "updated_at": "2026-06-14T00:00:00Z",
                }
            ]
        }

        result = runner.invoke(cli, ["transformation", "pipelines", "list"])

        assert result.exit_code == 0
        assert "dbt_daily" in result.output
        mock_api_client.get.assert_called_once_with(
            "transformation/pipelines/", params={"limit": 20, "offset": 0}
        )

    def test_list_pipelines_empty(self, runner, mock_api_client):
        """Test listing when no pipelines exist"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["transformation", "pipelines", "list"])

        assert result.exit_code == 0
        assert "No pipelines" in result.output

    def test_list_pipelines_with_filter(self, runner, mock_api_client):
        """Test listing with status filter"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["transformation", "pipelines", "list", "--status", "ERROR"])

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        assert call_args[1]["params"]["status"] == "ERROR"

    def test_list_pipelines_json(self, runner, mock_api_client):
        """Test listing in JSON format"""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["transformation", "pipelines", "list", "--format", "json"])

        assert result.exit_code == 0


class TestTransformationPipelineGet:
    """Test pipeline get command"""

    def test_get_pipeline(self, runner, mock_api_client):
        """Test getting pipeline details"""
        mock_api_client.get.return_value = {
            "id": "pipe-1",
            "name": "dbt_daily",
            "status": "ACTIVE",
            "dbt_project": "analytics",
        }

        result = runner.invoke(cli, ["transformation", "pipelines", "get", "pipe-1"])

        assert result.exit_code == 0
        assert "dbt_daily" in result.output


class TestTransformationPipelineCreate:
    """Test pipeline create command"""

    def test_create_pipeline(self, runner, mock_api_client):
        """Test creating a pipeline"""
        mock_api_client.post.return_value = {
            "id": "pipe-new",
            "name": "new_pipeline",
            "status": "DRAFT",
        }

        result = runner.invoke(
            cli,
            [
                "transformation",
                "pipelines",
                "create",
                "--name",
                "new_pipeline",
                "--config",
                '{"version": "1.0.0", "steps": [{"name": "clean", "type": "transform"}]}',
            ],
        )

        assert result.exit_code == 0
        assert "new_pipeline" in result.output
        mock_api_client.post.assert_called_once_with(
            "transformation/pipelines/",
            json_data={
                "name": "new_pipeline",
                "pipeline_definition": {
                    "version": "1.0.0",
                    "steps": [{"name": "clean", "type": "transform"}],
                },
            },
            timeout=120,
        )

    def test_create_pipeline_error(self, runner, mock_api_client):
        """Test create with validation error"""
        mock_api_client.post.side_effect = Exception("Name already exists")

        result = runner.invoke(
            cli,
            [
                "transformation",
                "pipelines",
                "create",
                "--name",
                "duplicate",
                "--config",
                '{"version": "1.0.0", "steps": [{"name": "clean", "type": "transform"}]}',
            ],
        )

        assert result.exit_code != 0


class TestTransformationPipelineDelete:
    """Test pipeline delete command"""

    def test_delete_pipeline(self, runner, mock_api_client):
        """Test deleting a pipeline with confirmation"""
        result = runner.invoke(
            cli, ["transformation", "pipelines", "delete", "pipe-1", "--confirm"]
        )

        assert result.exit_code == 0
        mock_api_client.delete.assert_called()


class TestTransformationPipelineValidate:
    """Test pipeline validate command"""

    def test_validate_pipeline_success(self, runner, mock_api_client):
        """Test validating a pipeline successfully"""
        mock_api_client.post.return_value = {"valid": True, "errors": []}

        result = runner.invoke(cli, ["transformation", "pipelines", "validate", "pipe-1"])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_pipeline_with_errors(self, runner, mock_api_client):
        """Test validating a pipeline with errors"""
        mock_api_client.post.return_value = {
            "valid": False,
            "errors": ["Missing model definition", "Invalid YAML"],
        }

        result = runner.invoke(cli, ["transformation", "pipelines", "validate", "pipe-1"])

        assert result.exit_code == 0
        assert "Invalid YAML" in result.output


class TestTransformationRuns:
    """Test runs subcommands"""

    def test_list_runs(self, runner, mock_api_client):
        """Test listing pipeline runs"""
        mock_api_client.get.return_value = {
            "results": [{"id": "run-1", "status": "COMPLETED", "pipeline_id": "pipe-1"}]
        }

        result = runner.invoke(cli, ["transformation", "runs", "list", "--pipeline-id", "pipe-1"])

        assert result.exit_code == 0
        assert "COMPLETED" in result.output

    def test_get_run(self, runner, mock_api_client):
        """Test getting run details"""
        mock_api_client.get.return_value = {
            "id": "run-1",
            "status": "COMPLETED",
            "duration_seconds": 45,
        }

        result = runner.invoke(cli, ["transformation", "runs", "get", "run-1"])

        assert result.exit_code == 0
        assert "COMPLETED" in result.output

    def test_submit_run(self, runner, mock_api_client):
        """Test submitting a pipeline run"""
        mock_api_client.post.return_value = {
            "execution_id": "run-new",
            "status": "PENDING",
            "pipeline_id": "pipe-1",
            "asset_id": ASSET_ID,
        }

        result = runner.invoke(
            cli,
            [
                "transformation",
                "runs",
                "submit",
                "--pipeline-id",
                "pipe-1",
                "--asset-id",
                ASSET_ID,
            ],
        )

        assert result.exit_code == 0
        assert "PENDING" in result.output
        mock_api_client.post.assert_called_once_with(
            "transformation/pipelines/pipe-1/execute/",
            json_data={"asset_id": ASSET_ID, "execution_mode": "ASYNC"},
            timeout=120,
        )

    def test_cancel_run(self, runner, mock_api_client):
        """Test cancelling a run"""
        mock_api_client.post.return_value = {
            "execution_id": "run-1",
            "status": "CANCELLED",
            "message": "Execution cancelled successfully",
        }

        result = runner.invoke(cli, ["transformation", "runs", "cancel", "run-1"])

        assert result.exit_code == 0
        assert "CANCELLED" in result.output


class TestTransformationPlanLimits:
    """Test plan-limits command"""

    def test_plan_limits(self, runner, mock_api_client):
        """Test viewing transformation plan limits"""
        # ``billing/subscription/current/`` returns ``limits`` populated from
        # the plan's ``limits_json``; transformation keys are
        # ``max_transformation_pipelines`` / ``max_transformation_runs_per_month``.
        mock_api_client.get.return_value = {
            "plan_name": "Pro",
            "plan_slug": "pro",
            "limits": {
                "max_transformation_pipelines": 10,
                "max_transformation_runs_per_month": 50,
                "max_ml_models": 3,
            },
        }

        result = runner.invoke(cli, ["transformation", "plan-limits"])

        assert result.exit_code == 0
        assert "10" in result.output
        mock_api_client.get.assert_called_once_with("billing/subscription/current/")
