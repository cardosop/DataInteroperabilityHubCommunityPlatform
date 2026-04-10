from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Integration tests for Virtualization CLI command registration against real Docker Compose services.

These tests verify that:
1. All virtualization commands are properly registered and accessible
2. Help text displays correctly for all commands
3. Commands can be invoked (even if they fail due to auth/validation, they should parse correctly)

These tests run against the real Docker Compose API service to ensure end-to-end CLI functionality.
"""
import pytest
import os
import subprocess
import time
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import config


class TestVirtualizationCommandsRegistrationRealAPI:
    """Integration tests for virtualization command registration with real API service"""

    @pytest.fixture(scope='class', autouse=True)
    def setup_api_service(self):
        """Verify API service is running"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                import requests
                response = requests.get(os.environ.get('MESHANT_API_URL', 'http://localhost:8000/api/v1') + '/health/', timeout=2)
                if response.status_code == 200:
                    break
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    pytest.skip("API service not available at http://localhost:8000")

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_virtualization_command_accessible_via_main_cli(self, runner):
        """Test that virtualization command is accessible via main CLI"""
        result = runner.invoke(cli, ['virtualization', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Virtualization management commands' in result.output

    def test_virtualization_info_command_executable(self, runner):
        """Test that virtualization info command can be executed"""
        result = runner.invoke(cli, ['virtualization', 'info'])
        # Should succeed even without API key (info command doesn't require auth)
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Status: Available' in result.output or 'status' in result.output.lower()

    def test_virtualization_info_command_json_format(self, runner):
        """Test that virtualization info command works with JSON format"""
        result = runner.invoke(cli, ['virtualization', 'info', '--format', 'json'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should output valid JSON
        import json
        try:
            output_data = json.loads(result.output)
            assert 'status' in output_data
            assert 'message' in output_data
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {result.output}")

    def test_virtualization_info_command_table_format(self, runner):
        """Test that virtualization info command works with table format"""
        result = runner.invoke(cli, ['virtualization', 'info', '--format', 'table'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Status:' in result.output
        assert 'Message:' in result.output

    def test_virtualization_info_command_default_format(self, runner):
        """Test that virtualization info command uses table format by default"""
        result = runner.invoke(cli, ['virtualization', 'info'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Default should be table format
        assert 'Status:' in result.output
        assert 'Message:' in result.output

    def test_virtualization_in_main_cli_help(self, runner):
        """Test that virtualization command appears in main CLI help"""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0, f"Main CLI help failed: {result.output}"
        assert 'virtualization' in result.output.lower()

    def test_virtualization_help_text_complete(self, runner):
        """Test that virtualization help text is complete"""
        result = runner.invoke(cli, ['virtualization', '--help'])
        assert result.exit_code == 0, f"Virtualization help failed: {result.output}"
        assert 'Virtualization management commands' in result.output
        assert 'info' in result.output

    def test_virtualization_info_help_text(self, runner):
        """Test that virtualization info command has correct help text"""
        result = runner.invoke(cli, ['virtualization', 'info', '--help'])
        assert result.exit_code == 0, f"Info help failed: {result.output}"
        assert 'Get virtualization information' in result.output
        assert '--format' in result.output
        assert 'json' in result.output or 'table' in result.output

    def test_invalid_virtualization_subcommand_shows_error(self, runner):
        """Test that invalid virtualization subcommand shows appropriate error"""
        result = runner.invoke(cli, ['virtualization', 'invalid-command'])
        assert result.exit_code != 0, "Invalid command should fail"
        assert 'No such command' in result.output or 'Usage:' in result.output

    def test_virtualization_command_structure(self, runner):
        """Test that virtualization command has correct structure"""
        result = runner.invoke(cli, ['virtualization', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should list available commands
        assert 'Commands:' in result.output
        assert 'info' in result.output
        assert 'datasets' in result.output
        assert 'queries' in result.output
        assert 'topology' in result.output

    def test_virtualization_info_with_invalid_format(self, runner):
        """Test that virtualization info command rejects invalid format"""
        # Note: Click should handle this, but let's verify
        result = runner.invoke(cli, ['virtualization', 'info', '--format', 'invalid'])
        # Click should validate the choice and show error
        assert result.exit_code != 0 or 'invalid' not in result.output.lower()

    def test_virtualization_datasets_command_accessible(self, runner):
        """Test that virtualization datasets command is accessible"""
        result = runner.invoke(cli, ['virtualization', 'datasets', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Virtual dataset management commands' in result.output
        assert 'list' in result.output
        assert 'create' in result.output
        assert 'get' in result.output
        assert 'update' in result.output
        assert 'delete' in result.output

    def test_virtualization_queries_command_accessible(self, runner):
        """Test that virtualization queries command is accessible"""
        result = runner.invoke(cli, ['virtualization', 'queries', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Query execution management commands' in result.output
        assert 'execute' in result.output
        assert 'list' in result.output
        assert 'get' in result.output
        assert 'cancel' in result.output
        assert 'result' in result.output

    def test_virtualization_topology_command_accessible(self, runner):
        """Test that virtualization topology command is accessible"""
        result = runner.invoke(cli, ['virtualization', 'topology', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Virtualization topology management commands' in result.output
        assert 'get' in result.output
        assert 'get-dataset' in result.output

    def test_virtualization_topology_get_help_text(self, runner):
        """Test that virtualization topology get command has correct help text"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Get complete virtualization topology' in result.output
        assert '--include-health-metrics' in result.output or '--no-include-health-metrics' in result.output
        assert '--format' in result.output

    def test_virtualization_topology_get_dataset_help_text(self, runner):
        """Test that virtualization topology get-dataset command has correct help text"""
        result = runner.invoke(cli, ['virtualization', 'topology', 'get-dataset', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Get topology view for a specific virtual dataset' in result.output
        assert 'DATASET_ID' in result.output
        assert '--format' in result.output

    def test_virtualization_datasets_list_help_text(self, runner):
        """Test that virtualization datasets list command has correct help text"""
        result = runner.invoke(cli, ['virtualization', 'datasets', 'list', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'List virtual datasets' in result.output
        assert '--format' in result.output
        assert '--page' in result.output
        assert '--page-size' in result.output

    def test_virtualization_queries_execute_help_text(self, runner):
        """Test that virtualization queries execute command has correct help text"""
        result = runner.invoke(cli, ['virtualization', 'queries', 'execute', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Execute a query on a virtual dataset' in result.output
        assert 'DATASET_ID' in result.output
        assert '--format' in result.output

    def test_all_virtualization_commands_in_main_help(self, runner):
        """Test that all virtualization subcommands appear in main virtualization help"""
        result = runner.invoke(cli, ['virtualization', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Verify all major command groups are listed
        commands_section = result.output.split('Commands:')[1] if 'Commands:' in result.output else result.output
        assert 'datasets' in commands_section.lower()
        assert 'queries' in commands_section.lower()
        assert 'topology' in commands_section.lower()
        assert 'info' in commands_section.lower()

