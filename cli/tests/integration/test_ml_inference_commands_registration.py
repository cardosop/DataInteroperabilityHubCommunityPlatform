from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Integration tests for ML Inference CLI command registration against real Docker Compose services.

These tests verify that:
1. All inference commands are properly registered and accessible
2. Help text displays correctly for all commands
3. Commands can be invoked (even if they fail due to auth/validation, they should parse correctly)

These tests run against the real Docker Compose API service to ensure end-to-end CLI functionality.
"""
import os
import time

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


class TestMLInferenceCommandsRegistrationRealAPI:
    """Integration tests for ML inference command registration with real API service"""

    @pytest.fixture(scope="class", autouse=True)
    def setup_api_service(self):
        """Verify API service is running"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                import requests

                # Health endpoint is at /health/ not /api/v1/health/
                response = requests.get(
                    os.environ.get("MESHANT_API_URL", "http://localhost:8000").rstrip("/api/v1")
                    + "/health/",
                    timeout=2,
                )
                if response.status_code == 200:
                    break
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(1)  # noqa: sleep-needed — retry loop
                else:
                    pytest.skip("API service not available at http://localhost:8000")

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_inference_command_accessible_via_main_cli(self, runner):
        """Test that ML inference command is accessible via main CLI"""
        result = runner.invoke(cli, ["ml", "inference", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Inference deployment and prediction commands" in result.output

    def test_ml_inference_deploy_command_help(self, runner):
        """Test that ML inference deploy command has correct help text"""
        result = runner.invoke(cli, ["ml", "inference", "deploy", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Deploy a model for inference" in result.output
        assert "--model-id" in result.output
        assert "--config" in result.output
        assert "--format" in result.output

    def test_ml_inference_predict_command_help(self, runner):
        """Test that ML inference predict command has correct help text"""
        result = runner.invoke(cli, ["ml", "inference", "predict", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Run inference prediction" in result.output
        assert "--deployment-id" in result.output
        assert "--input-data" in result.output
        assert "--format" in result.output

    def test_ml_inference_list_command_help(self, runner):
        """Test that ML inference list command has correct help text"""
        result = runner.invoke(cli, ["ml", "inference", "list", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "List inference deployments" in result.output
        assert "--model-id" in result.output
        assert "--status" in result.output
        assert "--limit" in result.output
        assert "--offset" in result.output

    def test_ml_inference_get_command_help(self, runner):
        """Test that ML inference get command has correct help text"""
        result = runner.invoke(cli, ["ml", "inference", "get", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Get deployment details" in result.output
        assert "DEPLOYMENT_ID" in result.output
        assert "--format" in result.output

    def test_ml_inference_undeploy_command_help(self, runner):
        """Test that ML inference undeploy command has correct help text"""
        result = runner.invoke(cli, ["ml", "inference", "undeploy", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Undeploy a model" in result.output
        assert "DEPLOYMENT_ID" in result.output

    def test_ml_inference_metrics_command_help(self, runner):
        """Test that ML inference metrics command has correct help text"""
        result = runner.invoke(cli, ["ml", "inference", "metrics", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Get inference metrics" in result.output
        assert "DEPLOYMENT_ID" in result.output
        assert "--start-time" in result.output
        assert "--end-time" in result.output

    def test_ml_inference_in_main_cli_help(self, runner):
        """Test that ML inference command appears in main ML help"""
        result = runner.invoke(cli, ["ml", "--help"])
        assert result.exit_code == 0, f"ML help failed: {result.output}"
        assert "inference" in result.output.lower()

    def test_ml_inference_help_text_complete(self, runner):
        """Test that ML inference help text is complete"""
        result = runner.invoke(cli, ["ml", "inference", "--help"])
        assert result.exit_code == 0, f"Inference help failed: {result.output}"
        assert "Inference deployment and prediction commands" in result.output
        assert "deploy" in result.output
        assert "predict" in result.output
        assert "list" in result.output
        assert "get" in result.output
        assert "undeploy" in result.output
        assert "metrics" in result.output

    def test_invalid_ml_inference_subcommand_shows_error(self, runner):
        """Test that invalid ML inference subcommand shows appropriate error"""
        result = runner.invoke(cli, ["ml", "inference", "invalid-command"])
        assert result.exit_code != 0, "Invalid command should fail"
        assert "No such command" in result.output or "Usage:" in result.output

    def test_ml_inference_command_structure(self, runner):
        """Test that ML inference command has correct structure"""
        result = runner.invoke(cli, ["ml", "inference", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should list available commands
        assert "Commands:" in result.output
        assert "deploy" in result.output
        assert "predict" in result.output
        assert "list" in result.output
        assert "get" in result.output
        assert "undeploy" in result.output
        assert "metrics" in result.output

    def test_ml_inference_deploy_with_invalid_format(self, runner):
        """Test that ML inference deploy command rejects invalid format"""
        result = runner.invoke(
            cli, ["ml", "inference", "deploy", "--model-id", "test", "--format", "invalid"]
        )
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_inference_predict_with_invalid_format(self, runner):
        """Test that ML inference predict command rejects invalid format"""
        result = runner.invoke(
            cli,
            [
                "ml",
                "inference",
                "predict",
                "--deployment-id",
                "test",
                "--input",
                "{}",
                "--format",
                "invalid",
            ],
        )
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_inference_list_with_invalid_format(self, runner):
        """Test that ML inference list command rejects invalid format"""
        result = runner.invoke(cli, ["ml", "inference", "list", "--format", "invalid"])
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_all_ml_inference_commands_in_inference_help(self, runner):
        """Test that all ML inference subcommands appear in inference help"""
        result = runner.invoke(cli, ["ml", "inference", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Verify all commands are listed
        commands_section = (
            result.output.split("Commands:")[1] if "Commands:" in result.output else result.output
        )
        assert "deploy" in commands_section.lower()
        assert "predict" in commands_section.lower()
        assert "list" in commands_section.lower()
        assert "get" in commands_section.lower()
        assert "undeploy" in commands_section.lower()
        assert "metrics" in commands_section.lower()
