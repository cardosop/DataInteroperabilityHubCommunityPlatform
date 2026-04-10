from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Unit tests for Mesh CLI commands.

Tests command group registration, help text, and basic command structure.
"""
import pytest
from click.testing import CliRunner
from datahub_cli.commands import mesh
from datahub_cli.main import cli


class TestMeshCommandGroup:
    """Test mesh command group registration and structure"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_mesh_command_group_registered(self, runner):
        """Test that mesh command group is registered in main CLI"""
        result = runner.invoke(cli, ['mesh', '--help'])
        assert result.exit_code == 0
        assert 'Data Mesh management commands' in result.output

    def test_mesh_command_group_help(self, runner):
        """Test mesh command group help text"""
        result = runner.invoke(mesh.mesh, ['--help'])
        assert result.exit_code == 0
        assert 'Data Mesh management commands' in result.output

    def test_mesh_info_command_exists(self, runner):
        """Test that mesh info command exists"""
        result = runner.invoke(mesh.mesh, ['info', '--help'])
        assert result.exit_code == 0

    def test_mesh_info_command_output_table(self, runner):
        """Test mesh info command with table output format"""
        result = runner.invoke(mesh.mesh, ['info', '--format', 'table'])
        assert result.exit_code == 0
        assert 'Status: Available' in result.output
        assert 'Mesh command module is registered and functional' in result.output

    def test_mesh_info_command_output_json(self, runner):
        """Test mesh info command with JSON output format"""
        result = runner.invoke(mesh.mesh, ['info', '--format', 'json'])
        assert result.exit_code == 0
        assert 'status' in result.output
        assert 'available' in result.output.lower()
        assert 'message' in result.output

    def test_mesh_command_group_importable(self):
        """Test that mesh command group can be imported"""
        from datahub_cli.commands.mesh import mesh as mesh_group
        assert mesh_group is not None
        assert callable(mesh_group)

    def test_mesh_command_group_in_main_cli(self):
        """Test that mesh command group is available in main CLI"""
        from datahub_cli.main import cli as main_cli

        # Check that mesh command is registered
        commands = [cmd.name for cmd in main_cli.commands.values()]
        assert 'mesh' in commands

    def test_mesh_command_group_in_commands_init(self):
        """Test that mesh is exported from commands __init__"""
        from datahub_cli.commands import mesh as mesh_module
        assert mesh_module is not None
        assert hasattr(mesh_module, 'mesh')

    def test_mesh_invalid_subcommand(self, runner):
        """Test handling invalid mesh subcommand"""
        result = runner.invoke(mesh.mesh, ['invalid-subcommand'])
        assert result.exit_code != 0
        assert 'No such command' in result.output or 'Usage:' in result.output

    def test_mesh_command_group_structure(self):
        """Test that mesh command group has correct structure"""
        from datahub_cli.commands.mesh import mesh as mesh_group

        # Should be a Click group
        assert hasattr(mesh_group, 'commands')
        assert 'info' in mesh_group.commands
        assert 'domains' in mesh_group.commands
        assert 'policies' in mesh_group.commands
        assert 'topology' in mesh_group.commands
        assert 'compliance' in mesh_group.commands

    def test_mesh_domains_group_help(self, runner):
        """Test mesh domains command group help text"""
        result = runner.invoke(cli, ['mesh', 'domains', '--help'])
        assert result.exit_code == 0
        assert 'Domain management commands' in result.output
        assert 'list' in result.output
        assert 'create' in result.output
        assert 'get' in result.output
        assert 'update' in result.output
        assert 'delete' in result.output

    def test_mesh_policies_group_help(self, runner):
        """Test mesh policies command group help text"""
        result = runner.invoke(cli, ['mesh', 'policies', '--help'])
        assert result.exit_code == 0
        assert 'Policy management commands for data mesh domains' in result.output
        assert 'apply' in result.output
        assert 'list' in result.output
        assert 'remove' in result.output

    def test_mesh_topology_group_help(self, runner):
        """Test mesh topology command group help text"""
        result = runner.invoke(cli, ['mesh', 'topology', '--help'])
        assert result.exit_code == 0
        assert 'Topology management commands' in result.output
        assert 'get' in result.output
        assert 'get-domain' in result.output

    def test_mesh_compliance_group_help(self, runner):
        """Test mesh compliance command group help text"""
        result = runner.invoke(cli, ['mesh', 'compliance', '--help'])
        assert result.exit_code == 0
        assert 'Compliance management commands for data mesh domains' in result.output
        assert 'check' in result.output
        assert 'report' in result.output

    def test_mesh_domains_list_help(self, runner):
        """Test mesh domains list command help text"""
        result = runner.invoke(cli, ['mesh', 'domains', 'list', '--help'])
        assert result.exit_code == 0
        assert 'List data mesh domains' in result.output
        assert '--status' in result.output
        assert '--format' in result.output

    def test_mesh_domains_create_help(self, runner):
        """Test mesh domains create command help text"""
        result = runner.invoke(cli, ['mesh', 'domains', 'create', '--help'])
        assert result.exit_code == 0
        assert 'Create a new data mesh domain' in result.output
        assert '--name' in result.output

    def test_mesh_domains_get_help(self, runner):
        """Test mesh domains get command help text"""
        result = runner.invoke(cli, ['mesh', 'domains', 'get', '--help'])
        assert result.exit_code == 0
        assert 'Get domain details by ID' in result.output
        assert 'DOMAIN_ID' in result.output

    def test_mesh_domains_update_help(self, runner):
        """Test mesh domains update command help text"""
        result = runner.invoke(cli, ['mesh', 'domains', 'update', '--help'])
        assert result.exit_code == 0
        assert 'Update an existing data mesh domain' in result.output
        assert 'DOMAIN_ID' in result.output

    def test_mesh_domains_delete_help(self, runner):
        """Test mesh domains delete command help text"""
        result = runner.invoke(cli, ['mesh', 'domains', 'delete', '--help'])
        assert result.exit_code == 0
        assert 'Delete a data mesh domain' in result.output
        assert 'DOMAIN_ID' in result.output

    def test_mesh_policies_apply_help(self, runner):
        """Test mesh policies apply command help text"""
        result = runner.invoke(cli, ['mesh', 'policies', 'apply', '--help'])
        assert result.exit_code == 0
        assert 'Apply a policy to a data mesh domain' in result.output
        assert 'DOMAIN_ID' in result.output
        assert '--policy' in result.output

    def test_mesh_policies_list_help(self, runner):
        """Test mesh policies list command help text"""
        result = runner.invoke(cli, ['mesh', 'policies', 'list', '--help'])
        assert result.exit_code == 0
        assert 'List policies applied to a data mesh domain' in result.output
        assert 'DOMAIN_ID' in result.output
        assert '--status' in result.output

    def test_mesh_policies_remove_help(self, runner):
        """Test mesh policies remove command help text"""
        result = runner.invoke(cli, ['mesh', 'policies', 'remove', '--help'])
        assert result.exit_code == 0
        assert 'Remove a policy from a data mesh domain' in result.output
        assert 'DOMAIN_ID' in result.output
        assert 'POLICY_ID' in result.output

    def test_mesh_topology_get_help(self, runner):
        """Test mesh topology get command help text"""
        result = runner.invoke(cli, ['mesh', 'topology', 'get', '--help'])
        assert result.exit_code == 0
        assert 'Get complete data mesh topology' in result.output

    def test_mesh_topology_get_domain_help(self, runner):
        """Test mesh topology get-domain command help text"""
        result = runner.invoke(cli, ['mesh', 'topology', 'get-domain', '--help'])
        assert result.exit_code == 0
        assert 'Get topology view for a specific domain' in result.output
        assert 'DOMAIN_ID' in result.output

    def test_mesh_compliance_check_help(self, runner):
        """Test mesh compliance check command help text"""
        result = runner.invoke(cli, ['mesh', 'compliance', 'check', '--help'])
        assert result.exit_code == 0
        assert 'Check compliance status for a data mesh domain' in result.output
        assert 'DOMAIN_ID' in result.output

    def test_mesh_compliance_report_help(self, runner):
        """Test mesh compliance report command help text"""
        result = runner.invoke(cli, ['mesh', 'compliance', 'report', '--help'])
        assert result.exit_code == 0
        assert 'Get compliance report' in result.output
        assert 'DOMAIN_ID' in result.output

    def test_mesh_all_commands_accessible_via_main_cli(self, runner):
        """Test that all mesh commands are accessible via main CLI"""
        commands_to_test = [
            ['mesh', '--help'],
            ['mesh', 'info', '--help'],
            ['mesh', 'domains', '--help'],
            ['mesh', 'domains', 'list', '--help'],
            ['mesh', 'domains', 'create', '--help'],
            ['mesh', 'domains', 'get', '--help'],
            ['mesh', 'domains', 'update', '--help'],
            ['mesh', 'domains', 'delete', '--help'],
            ['mesh', 'policies', '--help'],
            ['mesh', 'policies', 'apply', '--help'],
            ['mesh', 'policies', 'list', '--help'],
            ['mesh', 'policies', 'remove', '--help'],
            ['mesh', 'topology', '--help'],
            ['mesh', 'topology', 'get', '--help'],
            ['mesh', 'topology', 'get-domain', '--help'],
            ['mesh', 'compliance', '--help'],
            ['mesh', 'compliance', 'check', '--help'],
            ['mesh', 'compliance', 'report', '--help'],
        ]

        for cmd in commands_to_test:
            result = runner.invoke(cli, cmd)
            assert result.exit_code == 0, f"Command {cmd} failed with exit code {result.exit_code}"

    def test_mesh_commands_in_main_cli_help(self, runner):
        """Test that mesh command appears in main CLI help"""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'mesh' in result.output
        assert 'Data Mesh' in result.output or 'Mesh' in result.output

    def test_mesh_module_exported_correctly(self):
        """Test that mesh module is correctly exported from commands package"""
        from datahub_cli.commands import mesh
        from datahub_cli.commands.__init__ import __all__

        assert mesh is not None
        assert hasattr(mesh, 'mesh')
        assert 'mesh' in __all__

    def test_mesh_registered_in_main_py(self):
        """Test that mesh command is registered in main.py"""
        from datahub_cli.main import cli as main_cli

        # Verify mesh command is in the main CLI
        assert 'mesh' in main_cli.commands
        mesh_cmd = main_cli.commands['mesh']
        assert mesh_cmd is not None
        assert callable(mesh_cmd)

