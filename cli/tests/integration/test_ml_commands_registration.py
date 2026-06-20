from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Integration tests for ML CLI command registration against real Docker Compose services.

These tests verify that:
1. All ML commands are properly registered and accessible
2. Help text displays correctly for all commands
3. Commands can be invoked (even if they fail due to auth/validation, they should parse correctly)

These tests run against the real Docker Compose API service to ensure end-to-end CLI functionality.
"""
import os
import time

import pytest
from click.testing import CliRunner
from datahub_cli.main import cli


class TestMLCommandsRegistrationRealAPI:
    """Integration tests for ML command registration with real API service"""

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

    def test_ml_command_accessible_via_main_cli(self, runner):
        """Test that ML command is accessible via main CLI"""
        result = runner.invoke(cli, ["ml", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "ML Model Registry management commands" in result.output

    def test_ml_models_command_group_accessible(self, runner):
        """Test that ML models command group is accessible"""
        result = runner.invoke(cli, ["ml", "models", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Model registry commands" in result.output

    def test_ml_models_list_command_help(self, runner):
        """Test that ML models list command has correct help text"""
        result = runner.invoke(cli, ["ml", "models", "list", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "List ML models" in result.output
        assert "--asset-id" in result.output
        assert "--status" in result.output
        assert "--limit" in result.output
        assert "--offset" in result.output
        assert "--format" in result.output

    def test_ml_models_get_command_help(self, runner):
        """Test that ML models get command has correct help text"""
        result = runner.invoke(cli, ["ml", "models", "get", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Get model details" in result.output
        assert "MODEL_ID" in result.output
        assert "--format" in result.output

    def test_ml_models_create_command_help(self, runner):
        """Test that ML models create command has correct help text"""
        result = runner.invoke(cli, ["ml", "models", "create", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Create a new ML model link" in result.output
        assert "--odh-model-id" in result.output
        assert "--odh-model-name" in result.output
        assert "--odh-model-version" in result.output
        assert "--model-type" in result.output
        assert "--asset-id" in result.output
        assert "--contract-id" in result.output

    def test_ml_models_update_command_help(self, runner):
        """Test that ML models update command has correct help text"""
        result = runner.invoke(cli, ["ml", "models", "update", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Update ML model" in result.output
        assert "MODEL_ID" in result.output
        assert "--asset-id" in result.output
        assert "--contract-id" in result.output
        assert "--status" in result.output

    def test_ml_models_delete_command_help(self, runner):
        """Test that ML models delete command has correct help text"""
        result = runner.invoke(cli, ["ml", "models", "delete", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Delete ML model" in result.output
        assert "MODEL_ID" in result.output

    def test_ml_models_versions_command_help(self, runner):
        """Test that ML models versions command has correct help text"""
        result = runner.invoke(cli, ["ml", "models", "versions", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "List all versions of a model" in result.output
        assert "MODEL_ID" in result.output
        assert "--format" in result.output

    def test_ml_in_main_cli_help(self, runner):
        """Test that ML command appears in main CLI help"""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0, f"Main CLI help failed: {result.output}"
        assert "ml" in result.output.lower()

    def test_ml_help_text_complete(self, runner):
        """Test that ML help text is complete"""
        result = runner.invoke(cli, ["ml", "--help"])
        assert result.exit_code == 0, f"ML help failed: {result.output}"
        assert "ML Model Registry management commands" in result.output
        assert "models" in result.output

    def test_invalid_ml_subcommand_shows_error(self, runner):
        """Test that invalid ML subcommand shows appropriate error"""
        result = runner.invoke(cli, ["ml", "invalid-command"])
        assert result.exit_code != 0, "Invalid command should fail"
        assert "No such command" in result.output or "Usage:" in result.output

    def test_ml_command_structure(self, runner):
        """Test that ML command has correct structure"""
        result = runner.invoke(cli, ["ml", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should list available commands
        assert "Commands:" in result.output
        assert "models" in result.output

    def test_ml_models_command_structure(self, runner):
        """Test that ML models command has correct structure"""
        result = runner.invoke(cli, ["ml", "models", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should list available commands
        assert "Commands:" in result.output
        assert "list" in result.output
        assert "get" in result.output
        assert "create" in result.output
        assert "update" in result.output
        assert "delete" in result.output
        assert "versions" in result.output

    def test_ml_models_list_with_invalid_format(self, runner):
        """Test that ML models list command rejects invalid format"""
        result = runner.invoke(cli, ["ml", "models", "list", "--format", "invalid"])
        # Click should validate the choice and show error
        assert result.exit_code != 0 or "invalid" not in result.output.lower()

    def test_ml_models_list_with_invalid_status(self, runner):
        """Test that ML models list command rejects invalid status"""
        result = runner.invoke(cli, ["ml", "models", "list", "--status", "INVALID_STATUS"])
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_models_create_with_invalid_model_type(self, runner):
        """Test that ML models create command rejects invalid model type"""
        result = runner.invoke(
            cli,
            [
                "ml",
                "models",
                "create",
                "--odh-model-id",
                "test-id",
                "--odh-model-name",
                "test-name",
                "--odh-model-version",
                "1.0.0",
                "--model-type",
                "INVALID_TYPE",
            ],
        )
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_models_update_with_invalid_status(self, runner):
        """Test that ML models update command rejects invalid status"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli, ["ml", "models", "update", valid_uuid, "--status", "INVALID_STATUS"]
        )
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_all_ml_commands_in_main_help(self, runner):
        """Test that all ML subcommands appear in main ML help"""
        result = runner.invoke(cli, ["ml", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Verify all major command groups are listed
        commands_section = (
            result.output.split("Commands:")[1] if "Commands:" in result.output else result.output
        )
        assert "models" in commands_section.lower()

    def test_all_ml_models_commands_in_models_help(self, runner):
        """Test that all ML models subcommands appear in models help"""
        result = runner.invoke(cli, ["ml", "models", "--help"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Verify all commands are listed
        commands_section = (
            result.output.split("Commands:")[1] if "Commands:" in result.output else result.output
        )
        assert "list" in commands_section.lower()
        assert "get" in commands_section.lower()
        assert "create" in commands_section.lower()
        assert "update" in commands_section.lower()
        assert "delete" in commands_section.lower()
        assert "versions" in commands_section.lower()
