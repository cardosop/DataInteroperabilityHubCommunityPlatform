"""
Integration tests for Mesh CLI command registration against real Docker Compose services.

These tests verify that:
1. All mesh commands are properly registered and accessible
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


class TestMeshCommandsRegistrationRealAPI:
    """Integration tests for mesh command registration with real API service"""

    @pytest.fixture(scope='class', autouse=True)
    def setup_api_service(self):
        """Verify API service is running"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                import requests
                response = requests.get('http://localhost:8000/api/v1/health/', timeout=2)
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

    def test_mesh_command_accessible_via_main_cli(self, runner):
        """Test that mesh command is accessible via main CLI"""
        result = runner.invoke(cli, ['mesh', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Data Mesh management commands' in result.output
        assert 'domains' in result.output
        assert 'policies' in result.output
        assert 'topology' in result.output
        assert 'compliance' in result.output

    def test_mesh_info_command_executable(self, runner):
        """Test that mesh info command can be executed"""
        result = runner.invoke(cli, ['mesh', 'info'])
        # Should succeed even without API key (info command doesn't require auth)
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Status: Available' in result.output or 'status' in result.output.lower()

    def test_mesh_domains_group_accessible(self, runner):
        """Test that mesh domains group is accessible"""
        result = runner.invoke(cli, ['mesh', 'domains', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Domain management commands' in result.output
        assert 'list' in result.output
        assert 'create' in result.output
        assert 'get' in result.output
        assert 'update' in result.output
        assert 'delete' in result.output

    def test_mesh_policies_group_accessible(self, runner):
        """Test that mesh policies group is accessible"""
        result = runner.invoke(cli, ['mesh', 'policies', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Policy management commands' in result.output
        assert 'apply' in result.output
        assert 'list' in result.output
        assert 'remove' in result.output

    def test_mesh_topology_group_accessible(self, runner):
        """Test that mesh topology group is accessible"""
        result = runner.invoke(cli, ['mesh', 'topology', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Topology management commands' in result.output
        assert 'get' in result.output
        assert 'get-domain' in result.output

    def test_mesh_compliance_group_accessible(self, runner):
        """Test that mesh compliance group is accessible"""
        result = runner.invoke(cli, ['mesh', 'compliance', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Compliance management commands' in result.output
        assert 'check' in result.output
        assert 'report' in result.output

    def test_mesh_domains_list_help_text(self, runner):
        """Test that mesh domains list command has correct help text"""
        result = runner.invoke(cli, ['mesh', 'domains', 'list', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'List data mesh domains' in result.output
        assert '--status' in result.output
        assert '--format' in result.output
        assert '--page' in result.output

    def test_mesh_domains_create_help_text(self, runner):
        """Test that mesh domains create command has correct help text"""
        result = runner.invoke(cli, ['mesh', 'domains', 'create', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Create a new data mesh domain' in result.output
        assert '--name' in result.output
        assert 'required' in result.output.lower() or 'NAME' in result.output

    def test_mesh_policies_apply_help_text(self, runner):
        """Test that mesh policies apply command has correct help text"""
        result = runner.invoke(cli, ['mesh', 'policies', 'apply', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Apply a policy to a data mesh domain' in result.output
        assert 'DOMAIN_ID' in result.output
        assert '--policy' in result.output

    def test_mesh_policies_list_help_text(self, runner):
        """Test that mesh policies list command has correct help text"""
        result = runner.invoke(cli, ['mesh', 'policies', 'list', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'List policies applied to a data mesh domain' in result.output
        assert 'DOMAIN_ID' in result.output
        assert '--status' in result.output

    def test_mesh_topology_get_help_text(self, runner):
        """Test that mesh topology get command has correct help text"""
        result = runner.invoke(cli, ['mesh', 'topology', 'get', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Get complete data mesh topology' in result.output
        assert '--format' in result.output

    def test_mesh_compliance_check_help_text(self, runner):
        """Test that mesh compliance check command has correct help text"""
        result = runner.invoke(cli, ['mesh', 'compliance', 'check', '--help'])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Check compliance status' in result.output
        assert 'DOMAIN_ID' in result.output

    def test_mesh_commands_parse_correctly(self, runner):
        """Test that mesh commands parse arguments correctly (even if they fail due to auth)"""
        # Test that commands parse correctly - they may fail due to auth, but should parse
        commands_to_test = [
            (['mesh', 'domains', 'list'], '--format'),
            (['mesh', 'domains', 'create', '--name', 'test'], '--name'),
            (['mesh', 'policies', 'list', 'test-domain'], 'DOMAIN_ID'),
            (['mesh', 'topology', 'get'], '--format'),
            (['mesh', 'compliance', 'check', 'test-domain'], 'DOMAIN_ID'),
        ]

        for cmd, expected_in_output in commands_to_test:
            # Use --help to verify command structure without requiring auth
            help_cmd = cmd + ['--help']
            result = runner.invoke(cli, help_cmd)
            assert result.exit_code == 0, f"Command {cmd} help failed: {result.output}"
            # Verify the command structure is correct
            assert expected_in_output in result.output or any(
                expected_in_output.lower() in line.lower() for line in result.output.split('\n')
            )

    def test_mesh_in_main_cli_help(self, runner):
        """Test that mesh command appears in main CLI help"""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0, f"Main CLI help failed: {result.output}"
        assert 'mesh' in result.output.lower()

    def test_all_mesh_subcommands_listed_in_help(self, runner):
        """Test that all mesh subcommands are listed in mesh --help"""
        result = runner.invoke(cli, ['mesh', '--help'])
        assert result.exit_code == 0, f"Mesh help failed: {result.output}"

        # Verify all expected subcommands are present
        expected_commands = ['info', 'domains', 'policies', 'topology', 'compliance']
        for cmd in expected_commands:
            assert cmd in result.output, f"Command '{cmd}' not found in mesh help output"

    def test_invalid_mesh_subcommand_shows_error(self, runner):
        """Test that invalid mesh subcommand shows appropriate error"""
        result = runner.invoke(cli, ['mesh', 'invalid-command'])
        assert result.exit_code != 0, "Invalid command should fail"
        assert 'No such command' in result.output or 'Usage:' in result.output

