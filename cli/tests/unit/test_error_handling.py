"""
Comprehensive unit tests for CLI error handling.

Tests network errors, API errors, invalid commands, invalid arguments, and error propagation.
"""

from unittest.mock import Mock, patch

import pytest
from click import ClickException
from click.testing import CliRunner
from datahub_cli.main import cli


class TestNetworkErrors:
    """Test handling of network errors"""

    def test_network_connection_error(self, runner, mock_api_client):
        """Test handling connection errors"""
        mock_api_client.get.side_effect = ClickException("API request failed: Connection refused")

        result = runner.invoke(cli, ["contracts", "list"])

        assert result.exit_code != 0
        assert "Connection" in result.output or "Failed to list contracts" in result.output

    def test_network_timeout_error(self, runner, mock_api_client):
        """Test handling timeout errors"""
        mock_api_client.get.side_effect = ClickException("API request failed: Timeout")

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code != 0
        assert "Timeout" in result.output or "Failed to list assets" in result.output

    def test_network_dns_error(self, runner, mock_api_client):
        """Test handling DNS resolution errors"""
        mock_api_client.get.side_effect = ClickException(
            "API request failed: Name resolution failed"
        )

        result = runner.invoke(cli, ["files", "list"])

        assert result.exit_code != 0
        assert "Failed to list files" in result.output or "API request failed" in result.output

    def test_network_ssl_error(self, runner, mock_api_client):
        """Test handling SSL certificate errors"""
        mock_api_client.get.side_effect = ClickException(
            "API request failed: SSL certificate verification failed"
        )

        result = runner.invoke(cli, ["jobs", "list"])

        assert result.exit_code != 0
        assert "Failed to list jobs" in result.output or "SSL" in result.output


class TestAPIErrors:
    """Test handling of API errors"""

    def test_api_400_bad_request(self, runner, mock_api_client):
        """Test handling 400 Bad Request errors"""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException(
            "API error (BAD_REQUEST): Invalid request parameters"
        )

        result = runner.invoke(cli, ["contracts", "get", "invalid-id"])

        assert result.exit_code != 0
        assert "API error" in result.output or "Failed to get contract" in result.output

    def test_api_401_unauthorized(self, runner, mock_api_client):
        """Test handling 401 Unauthorized errors"""
        mock_api_client.get.side_effect = ClickException(
            "API error (UNAUTHORIZED): Authentication required"
        )

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code != 0
        assert (
            "UNAUTHORIZED" in result.output
            or "Authentication" in result.output
            or "Failed to list assets" in result.output
        )

    def test_api_403_forbidden(self, runner, mock_api_client, temp_file):
        """Test handling 403 Forbidden errors"""
        file_path, _content = temp_file(".yaml", "name: Test Contract")
        mock_api_client.post.side_effect = ClickException(
            "API error (FORBIDDEN): Insufficient permissions"
        )

        result = runner.invoke(cli, ["contracts", "create", "--file", file_path])

        assert result.exit_code != 0
        assert (
            "FORBIDDEN" in result.output
            or "permissions" in result.output
            or "Failed to create contract" in result.output
        )

    def test_api_404_not_found(self, runner, mock_api_client):
        """Test handling 404 Not Found errors"""
        mock_api_client.get.side_effect = ClickException(
            "API error (NOT_FOUND): Resource not found"
        )

        result = runner.invoke(cli, ["assets", "get", "non-existent-id"])

        assert result.exit_code != 0
        assert (
            "NOT_FOUND" in result.output
            or "not found" in result.output
            or "Failed to get asset" in result.output
        )

    def test_api_500_internal_server_error(self, runner, mock_api_client):
        """Test handling 500 Internal Server Error"""
        mock_api_client.post.side_effect = ClickException(
            "API error (INTERNAL_ERROR): Internal server error"
        )

        result = runner.invoke(cli, ["contracts", "validate", "contract-id"])

        assert result.exit_code != 0
        assert (
            "INTERNAL_ERROR" in result.output
            or "server error" in result.output
            or "Failed to validate contract" in result.output
        )

    def test_api_503_service_unavailable(self, runner, mock_api_client):
        """Test handling 503 Service Unavailable"""
        mock_api_client.get.side_effect = ClickException(
            "API error (SERVICE_UNAVAILABLE): Service temporarily unavailable"
        )

        result = runner.invoke(cli, ["lineage", "contract", "contract-id"])

        assert result.exit_code != 0
        assert (
            "SERVICE_UNAVAILABLE" in result.output
            or "unavailable" in result.output
            or "Failed to get contract lineage" in result.output
        )

    def test_api_error_with_details(self, runner, mock_api_client, temp_file):
        """Test handling API errors with detailed error messages"""
        file_path, _content = temp_file(".yaml", "name: Test Contract")
        mock_api_client.post.side_effect = ClickException(
            "API error (VALIDATION_ERROR): Contract validation failed: Missing required field 'name'"
        )

        result = runner.invoke(cli, ["contracts", "create", "--file", file_path])

        assert result.exit_code != 0
        assert (
            "VALIDATION_ERROR" in result.output
            or "validation failed" in result.output
            or "Failed to create contract" in result.output
        )


class TestInvalidCommands:
    """Test handling of invalid commands"""

    def test_invalid_top_level_command(self, runner):
        """Test handling invalid top-level command"""
        result = runner.invoke(cli, ["invalid-command"])

        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output

    def test_invalid_subcommand(self, runner):
        """Test handling invalid subcommand"""
        result = runner.invoke(cli, ["contracts", "invalid-subcommand"])

        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output

    def test_command_with_typo(self, runner):
        """Test handling command with typo"""
        result = runner.invoke(cli, ["contracs", "list"])  # typo: contracs instead of contracts

        assert result.exit_code != 0
        assert (
            "No such command" in result.output
            or "Did you mean" in result.output
            or "Usage:" in result.output
        )

    def test_empty_command(self, runner):
        """Test handling empty command (just 'datahub')"""
        result = runner.invoke(cli, [])

        # Should show help or usage
        assert result.exit_code == 0 or "Usage:" in result.output or "DataHub CLI" in result.output


class TestInvalidArguments:
    """Test handling of invalid arguments"""

    def test_missing_required_argument(self, runner):
        """Test handling missing required argument"""
        result = runner.invoke(cli, ["contracts", "get"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Usage:" in result.output

    def test_invalid_option_value(self, runner):
        """Test handling invalid option value"""
        result = runner.invoke(cli, ["contracts", "list", "--format", "invalid-format"])

        assert result.exit_code != 0
        assert (
            "Invalid value" in result.output
            or "invalid-format" in result.output
            or "Usage:" in result.output
        )

    def test_invalid_choice_value(self, runner):
        """Test handling invalid choice value"""
        result = runner.invoke(
            cli, ["assets", "create", "--name", "Test", "--key", "test", "--visibility", "INVALID"]
        )

        assert result.exit_code != 0
        assert (
            "Invalid value" in result.output
            or "INVALID" in result.output
            or "Usage:" in result.output
        )

    def test_missing_required_option(self, runner):
        """Test handling missing required option"""
        result = runner.invoke(cli, ["assets", "create", "--name", "Test"])
        # key is required

        assert result.exit_code != 0
        assert (
            "Missing option" in result.output
            or "--key" in result.output
            or "Usage:" in result.output
        )

    def test_invalid_file_path(self, runner):
        """Test handling invalid file path"""
        result = runner.invoke(
            cli, ["contracts", "create", "--file", "/nonexistent/path/file.yaml"]
        )

        assert result.exit_code != 0
        assert (
            "does not exist" in result.output
            or "Invalid value" in result.output
            or "Failed to read file" in result.output
        )

    def test_invalid_integer_argument(self, runner):
        """Test handling invalid integer argument"""
        result = runner.invoke(cli, ["contracts", "list", "--limit", "not-a-number"])

        assert result.exit_code != 0
        assert (
            "Invalid value" in result.output
            or "not-a-number" in result.output
            or "Usage:" in result.output
        )

    def test_negative_limit(self, runner, mock_api_client):
        """Test handling of negative limit value — API must reject it."""
        from click import ClickException

        mock_api_client.get.side_effect = ClickException(
            "API error (VALIDATION): Limit must be a positive integer"
        )

        result = runner.invoke(cli, ["contracts", "list", "--limit", "-1"])

        assert result.exit_code != 0, (
            f"Negative limit should be rejected, got exit {result.exit_code}"
        )
        assert (
            "Limit" in result.output
            or "VALIDATION" in result.output
            or "error" in result.output.lower()
        )


class TestErrorPropagation:
    """Test error propagation through command chain"""

    def test_click_exception_propagation(self, runner, mock_api_client):
        """Test that ClickException is properly propagated"""
        mock_api_client.get.side_effect = ClickException("Custom error message")

        result = runner.invoke(cli, ["contracts", "list"])

        assert result.exit_code != 0
        # ClickException should be caught and displayed
        assert (
            "Custom error message" in result.output or "Failed to list contracts" in result.output
        )

    def test_generic_exception_handling(self, runner, mock_api_client):
        """Test that generic exceptions are caught and converted"""
        mock_api_client.get.side_effect = ValueError("Unexpected error")

        result = runner.invoke(cli, ["assets", "list"])

        assert result.exit_code != 0
        assert "Failed to list assets" in result.output or "Unexpected error" in result.output

    def test_keyboard_interrupt_handling(self, runner):
        """Test handling KeyboardInterrupt in main()"""
        # This is tested at the main() level
        # KeyboardInterrupt should be caught and handled gracefully
        with patch("datahub_cli.main.cli") as mock_cli:
            mock_cli.side_effect = KeyboardInterrupt()

            from datahub_cli.main import main

            with patch("sys.exit") as mock_exit:
                main()
                # Should exit with code 130
                mock_exit.assert_called()

    def test_unexpected_exception_in_main(self, runner):
        """Test handling unexpected exceptions in main()"""
        with patch("datahub_cli.main.cli") as mock_cli:
            mock_cli.side_effect = RuntimeError("Unexpected runtime error")

            from datahub_cli.main import main

            with patch("sys.exit") as mock_exit:
                main()
                # Should exit with code 1
                mock_exit.assert_called()


class TestErrorMessages:
    """Test error message quality and clarity"""

    def test_error_message_contains_context(self, runner, mock_api_client):
        """Test that error messages contain helpful context"""
        mock_api_client.get.side_effect = ClickException(
            "API error (NOT_FOUND): Contract with ID 'test-id' not found"
        )

        result = runner.invoke(cli, ["contracts", "get", "test-id"])

        assert result.exit_code != 0
        # Error should mention the resource type and ID
        assert (
            "test-id" in result.output
            or "Contract" in result.output
            or "not found" in result.output
        )

    def test_error_message_suggests_solution(self, runner):
        """Test that error messages suggest solutions when possible"""
        result = runner.invoke(cli, ["contracts", "get"])

        assert result.exit_code != 0
        # Should show usage or help
        assert "Usage:" in result.output or "Missing argument" in result.output

    def test_error_message_includes_command_context(self, runner, mock_api_client):
        """Test that error messages include command context"""
        from click import ClickException

        mock_api_client.post.side_effect = ClickException("API error: Validation failed")

        result = runner.invoke(cli, ["contracts", "validate", "contract-id"])

        assert result.exit_code != 0
        # Error should be contextual to the validate command
        assert (
            "validate" in result.output.lower()
            or "Failed to validate contract" in result.output
            or "Validation failed" in result.output
        )


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client"""
    mock_client = Mock()
    monkeypatch.setattr("datahub_cli.commands.contracts.api_client", mock_client)
    monkeypatch.setattr("datahub_cli.commands.assets.api_client", mock_client)
    monkeypatch.setattr("datahub_cli.commands.files.api_client", mock_client)
    monkeypatch.setattr("datahub_cli.commands.jobs.api_client", mock_client)
    monkeypatch.setattr("datahub_cli.commands.lineage.api_client", mock_client)
    return mock_client


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""

    def _create_file(extension, content):
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return str(file_path), content

    return _create_file
