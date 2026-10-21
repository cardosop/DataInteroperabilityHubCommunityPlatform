from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Unit tests for Virtualization CLI commands.

Tests command group registration, help text, and basic command structure.
"""
import json

import pytest
from click.testing import CliRunner
from datahub_cli.commands import virtualization
from datahub_cli.main import cli


class TestVirtualizationCommandGroup:
    """Test virtualization command group registration and structure"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_virtualization_command_group_registered(self, runner):
        """Test that virtualization command group is registered in main CLI"""
        result = runner.invoke(cli, ["virtualization", "--help"])
        assert result.exit_code == 0
        assert "Virtualization management commands" in result.output

    def test_virtualization_command_group_help(self, runner):
        """Test virtualization command group help text"""
        result = runner.invoke(virtualization.virtualization, ["--help"])
        assert result.exit_code == 0
        assert "Virtualization management commands" in result.output

    def test_virtualization_command_group_importable(self):
        """Test that virtualization command group can be imported"""
        from datahub_cli.commands.virtualization import virtualization as virtualization_group

        assert virtualization_group is not None
        assert callable(virtualization_group)

    def test_virtualization_command_group_in_main_cli(self):
        """Test that virtualization command group is available in main CLI"""
        from datahub_cli.main import cli as main_cli

        # Check that virtualization command is registered
        commands = [cmd.name for cmd in main_cli.commands.values()]
        assert "virtualization" in commands

    def test_virtualization_command_group_in_commands_init(self):
        """Test that virtualization is exported from commands __init__"""
        from datahub_cli.commands import virtualization as virtualization_module

        assert virtualization_module is not None
        assert hasattr(virtualization_module, "virtualization")

    def test_virtualization_invalid_subcommand(self, runner):
        """Test handling invalid virtualization subcommand"""
        result = runner.invoke(virtualization.virtualization, ["invalid-subcommand"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output

    def test_virtualization_command_group_structure(self):
        """Test that virtualization command group has correct structure"""
        from datahub_cli.commands.virtualization import virtualization as virtualization_group

        # Should be a Click group
        assert hasattr(virtualization_group, "commands")
        # Initially empty, but structure is correct
        assert isinstance(virtualization_group.commands, dict)

    def test_virtualization_commands_in_main_cli_help(self, runner):
        """Test that virtualization command appears in main CLI help"""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "virtualization" in result.output
        assert "Virtualization" in result.output

    def test_virtualization_module_exported_correctly(self):
        """Test that virtualization module is correctly exported from commands package"""
        from datahub_cli.commands import virtualization as virtualization_module

        assert hasattr(virtualization_module, "virtualization")
        virtualization_cmd = virtualization_module.virtualization
        assert virtualization_cmd is not None
        assert callable(virtualization_cmd)

    def test_virtualization_info_command(self, runner):
        """Test virtualization info command"""
        result = runner.invoke(virtualization.virtualization, ["info"])
        assert result.exit_code == 0
        assert "Status: Available" in result.output or "available" in result.output.lower()

    def test_virtualization_info_command_json_format(self, runner):
        """Test virtualization info command with JSON output"""
        result = runner.invoke(virtualization.virtualization, ["info", "--format", "json"])
        assert result.exit_code == 0
        try:
            output_data = json.loads(result.output)
            assert "status" in output_data
            assert "message" in output_data
            assert output_data["status"] == "available"
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {result.output}")

    def test_virtualization_info_command_table_format(self, runner):
        """Test virtualization info command with table output (default)"""
        result = runner.invoke(virtualization.virtualization, ["info", "--format", "table"])
        assert result.exit_code == 0
        assert "Status:" in result.output
        assert "Message:" in result.output
