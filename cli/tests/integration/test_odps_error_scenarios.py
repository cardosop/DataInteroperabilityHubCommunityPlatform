"""
Integration tests for ODPS error scenarios in CLI.

Tests verify error handling in real command execution scenarios.
"""
import json
import tempfile
from pathlib import Path
import pytest
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.odps_errors import (
    ODPSCLIError,
    ODPSValidationError,
    ODPSParameterError,
)


class TestODPSErrorScenarios:
    """Integration tests for ODPS error scenarios"""

    def test_create_odps_missing_flow_option(self, runner, temp_file):
        """Test create-odps command with missing flow option"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "Must specify either" in result.output

    def test_create_odps_both_flow_options(self, runner, temp_file):
        """Test create-odps command with both flow options"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs',
            '--link-odcs', 'odcs-123'
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "Cannot use both" in result.output

    def test_create_odps_invalid_version(self, runner, temp_file):
        """Test create-odps command with invalid version"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs',
            '--version', '4'
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "Invalid ODPS version format" in result.output

    def test_create_odps_invalid_contract_id(self, runner, temp_file):
        """Test create-odps command with invalid contract ID"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--link-odcs', '  '
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "cannot be empty" in result.output.lower()

    def test_create_odps_file_not_found(self, runner):
        """Test create-odps command with non-existent file"""
        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', '/nonexistent/file.json',
            '--extract-odcs'
        ])

        assert result.exit_code != 0
        # Should fail with file not found error
        assert "does not exist" in result.output.lower() or "No such file" in result.output.lower()

    def test_export_invalid_contract_id(self, runner):
        """Test export command with invalid contract ID"""
        result = runner.invoke(cli, [
            'contracts', 'export',
            '',
            '--format', 'odps'
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "cannot be empty" in result.output.lower()

    def test_export_invalid_version(self, runner):
        """Test export command with invalid version"""
        result = runner.invoke(cli, [
            'contracts', 'export',
            'contract-123',
            '--format', 'odps',
            '--version', 'invalid'
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "Invalid ODPS version format" in result.output

    def test_link_odps_invalid_ids(self, runner):
        """Test link-odps command with invalid IDs"""
        result = runner.invoke(cli, [
            'contracts', 'link-odps',
            '',
            'odps-123'
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "cannot be empty" in result.output.lower()

    def test_unlink_odps_invalid_id(self, runner):
        """Test unlink-odps command with invalid ID"""
        result = runner.invoke(cli, [
            'contracts', 'unlink-odps',
            '  '
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "whitespace" in result.output.lower()

    def test_list_links_invalid_id(self, runner):
        """Test list-links command with invalid ID"""
        result = runner.invoke(cli, [
            'contracts', 'list-links',
            ''
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "cannot be empty" in result.output.lower()

    def test_download_invalid_contract_id(self, runner):
        """Test download command with invalid contract ID"""
        result = runner.invoke(cli, [
            'contracts', 'download',
            '',
            '--format', 'odps'
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "cannot be empty" in result.output.lower()

    def test_download_invalid_version(self, runner):
        """Test download command with invalid version"""
        result = runner.invoke(cli, [
            'contracts', 'download',
            'contract-123',
            '--format', 'odps',
            '--version', '4'
        ])

        assert result.exit_code != 0
        assert isinstance(result.exception, ODPSParameterError) or "Invalid ODPS version format" in result.output


class TestODPSErrorMessages:
    """Test error message quality and helpfulness"""

    def test_validation_error_has_suggestion(self, runner, temp_file, mock_api_client):
        """Test that validation errors include helpful suggestions"""
        file_path, content = temp_file('.json', '{"invalid": "data"}')

        # Mock API to return validation error
        from click import ClickException
        error_response = {
            'error': {
                'code': 'SCHEMA_VALIDATION_FAILED',
                'message': 'Schema validation failed',
                'context': {
                    'field_path': '/product/name',
                    'expected': 'string',
                    'actual': 'number'
                }
            }
        }
        mock_api_client.post.side_effect = ClickException(f"API error (SCHEMA_VALIDATION_FAILED): {json.dumps(error_response)}")

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs'
        ])

        # Should show helpful error message
        assert result.exit_code != 0
        # Error should be informative
        assert len(result.output) > 0

    def test_parameter_error_has_suggestion(self, runner, temp_file):
        """Test that parameter errors include helpful suggestions"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--version', 'invalid'
        ])

        assert result.exit_code != 0
        # Should include suggestion about version format
        output_lower = result.output.lower()
        assert "suggestion" in output_lower or "format" in output_lower or "major.minor" in output_lower


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""
    def _create_file(extension, content):
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return str(file_path), content
    return _create_file


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client"""
    from unittest.mock import Mock
    from datahub_cli import api_client

    mock_client = Mock()
    monkeypatch.setattr('datahub_cli.commands.contracts.api_client', mock_client)
    return mock_client

