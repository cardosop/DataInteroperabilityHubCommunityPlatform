"""
Unit tests for compliance CLI commands.

Tests command structure, argument validation, and help text.
These tests focus on CLI command registration and validation without API calls.
"""
import pytest
from click.testing import CliRunner
from click import ClickException
from datahub_cli.main import cli


@pytest.fixture
def runner():
    """Create a CLI runner"""
    return CliRunner()


class TestComplianceRunCommand:
    """Test compliance run command structure and validation"""

    def test_run_command_requires_resource_id(self, runner):
        """Test that run command requires at least one resource ID"""
        result = runner.invoke(cli, [
            'compliance', 'run',
            '--scan-mode', 'internal'
        ])

        assert result.exit_code != 0
        assert 'at least one' in result.output.lower() or 'required' in result.output.lower()

    def test_run_command_help_text(self, runner):
        """Test that run command has help text"""
        result = runner.invoke(cli, [
            'compliance', 'run', '--help'
        ])

        assert result.exit_code == 0
        assert 'Run a compliance check' in result.output
        assert '--asset-id' in result.output
        assert '--dataset-id' in result.output
        assert '--file-id' in result.output
        assert '--scan-mode' in result.output
        assert '--regulations' in result.output

    def test_run_command_scan_mode_validation(self, runner):
        """Test that scan-mode accepts only valid values"""
        # Valid values should be accepted (will fail on API call, but CLI validation passes)
        result = runner.invoke(cli, [
            'compliance', 'run',
            '--asset-id', 'test-id',
            '--scan-mode', 'internal'
        ])

        # Should pass CLI validation (may fail on API call, but that's OK)
        assert result.exit_code in [0, 1]

        # Invalid value should be rejected by Click
        result = runner.invoke(cli, [
            'compliance', 'run',
            '--asset-id', 'test-id',
            '--scan-mode', 'invalid-mode'
        ])

        assert result.exit_code != 0
        assert 'invalid' in result.output.lower() or 'choice' in result.output.lower()

    def test_run_command_output_format_validation(self, runner):
        """Test that output format accepts only valid values"""
        # Valid format should be accepted
        result = runner.invoke(cli, [
            'compliance', 'run',
            '--asset-id', 'test-id',
            '--format', 'json'
        ])

        # Should pass CLI validation
        assert result.exit_code in [0, 1]

        # Invalid format should be rejected by Click
        result = runner.invoke(cli, [
            'compliance', 'run',
            '--asset-id', 'test-id',
            '--format', 'invalid-format'
        ])

        assert result.exit_code != 0
        assert 'invalid' in result.output.lower() or 'choice' in result.output.lower()

    def test_run_command_with_all_options(self, runner):
        """Test run command accepts all options"""
        # Test that command accepts all options (validation happens in integration tests)
        result = runner.invoke(cli, [
            'compliance', 'run',
            '--asset-id', 'asset-123',
            '--dataset-id', 'dataset-123',
            '--file-id', 'file-123',
            '--scan-mode', 'external',
            '--regulations', 'GDPR,HIPAA',
            '--format', 'json'
        ])

        # Should pass CLI validation (may fail on API call, but that's OK)
        assert result.exit_code in [0, 1]


class TestComplianceGetCommand:
    """Test compliance get command structure"""

    def test_get_command_help_text(self, runner):
        """Test that get command has help text"""
        result = runner.invoke(cli, [
            'compliance', 'get', '--help'
        ])

        assert result.exit_code == 0
        assert 'Get compliance run details' in result.output
        assert 'compliance_run_id' in result.output or 'COMPLIANCE_RUN_ID' in result.output

    def test_get_command_requires_compliance_run_id(self, runner):
        """Test that get command requires compliance_run_id argument"""
        result = runner.invoke(cli, [
            'compliance', 'get'
        ])

        assert result.exit_code != 0
        assert 'missing' in result.output.lower() or 'required' in result.output.lower()

    def test_get_command_output_format_validation(self, runner):
        """Test that output format accepts only valid values"""
        # Valid format should be accepted
        result = runner.invoke(cli, [
            'compliance', 'get',
            'test-id',
            '--format', 'json'
        ])

        # Should pass CLI validation (may fail on API call, but that's OK)
        assert result.exit_code in [0, 1]

        # Invalid format should be rejected by Click
        result = runner.invoke(cli, [
            'compliance', 'get',
            'test-id',
            '--format', 'invalid-format'
        ])

        assert result.exit_code != 0
        assert 'invalid' in result.output.lower() or 'choice' in result.output.lower()


class TestComplianceListCommand:
    """Test compliance list command structure"""

    def test_list_command_help_text(self, runner):
        """Test that list command has help text"""
        result = runner.invoke(cli, [
            'compliance', 'list', '--help'
        ])

        assert result.exit_code == 0
        assert 'List compliance runs' in result.output
        assert '--asset-id' in result.output
        assert '--status' in result.output
        assert '--limit' in result.output
        assert '--offset' in result.output

    def test_list_command_status_validation(self, runner):
        """Test that status accepts only valid values"""
        # Valid status should be accepted
        result = runner.invoke(cli, [
            'compliance', 'list',
            '--status', 'SUCCEEDED'
        ])

        # Should pass CLI validation (may fail on API call, but that's OK)
        assert result.exit_code in [0, 1]

        # Invalid status should be rejected by Click
        result = runner.invoke(cli, [
            'compliance', 'list',
            '--status', 'INVALID_STATUS'
        ])

        assert result.exit_code != 0
        assert 'invalid' in result.output.lower() or 'choice' in result.output.lower()

    def test_list_command_with_all_options(self, runner):
        """Test list command accepts all options"""
        result = runner.invoke(cli, [
            'compliance', 'list',
            '--asset-id', 'asset-123',
            '--status', 'PENDING',
            '--limit', '10',
            '--offset', '5',
            '--format', 'json'
        ])

        # Should pass CLI validation (may fail on API call, but that's OK)
        assert result.exit_code in [0, 1]


class TestComplianceReportCommand:
    """Test compliance report command structure"""

    def test_report_command_help_text(self, runner):
        """Test that report command has help text"""
        result = runner.invoke(cli, [
            'compliance', 'report', '--help'
        ])

        assert result.exit_code == 0
        assert 'Generate a compliance report' in result.output
        assert '--asset-id' in result.output
        assert '--regulation' in result.output

    def test_report_command_requires_asset_id(self, runner):
        """Test that report command requires asset_id"""
        result = runner.invoke(cli, [
            'compliance', 'report',
            '--regulation', 'GDPR'
        ])

        assert result.exit_code != 0
        assert 'required' in result.output.lower() or 'asset-id' in result.output.lower()

    def test_report_command_requires_regulation(self, runner):
        """Test that report command requires regulation"""
        result = runner.invoke(cli, [
            'compliance', 'report',
            '--asset-id', 'asset-123'
        ])

        assert result.exit_code != 0
        assert 'required' in result.output.lower() or 'regulation' in result.output.lower()

    def test_report_command_regulation_validation(self, runner):
        """Test that regulation accepts only valid values"""
        # Valid regulation should be accepted
        result = runner.invoke(cli, [
            'compliance', 'report',
            '--asset-id', 'asset-123',
            '--regulation', 'GDPR'
        ])

        # Should pass CLI validation (may fail on API call, but that's OK)
        assert result.exit_code in [0, 1]

        # Invalid regulation should be rejected by Click
        result = runner.invoke(cli, [
            'compliance', 'report',
            '--asset-id', 'asset-123',
            '--regulation', 'INVALID_REGULATION'
        ])

        assert result.exit_code != 0
        assert 'invalid' in result.output.lower() or 'choice' in result.output.lower()


class TestComplianceCommandRegistration:
    """Test that compliance commands are properly registered"""

    def test_compliance_group_registered(self, runner):
        """Test that compliance command group is registered"""
        result = runner.invoke(cli, ['compliance', '--help'])

        assert result.exit_code == 0
        assert 'Compliance management commands' in result.output

    def test_all_compliance_commands_listed(self, runner):
        """Test that all compliance commands are listed in help"""
        result = runner.invoke(cli, ['compliance', '--help'])

        assert result.exit_code == 0
        assert 'run' in result.output
        assert 'get' in result.output
        assert 'list' in result.output
        assert 'report' in result.output

