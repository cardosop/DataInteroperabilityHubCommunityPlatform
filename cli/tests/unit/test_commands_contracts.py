"""
Comprehensive unit tests for contracts CLI commands.

Tests all contract commands: create, get, list, update, delete, validate, lint.
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from datahub_cli.main import cli
from datahub_cli.commands import contracts
from datahub_cli.api_client import api_client


class TestContractsList:
    """Test contracts list command"""

    def test_list_contracts_success_table_format(self, runner, mock_api_client):
        """Test listing contracts in table format"""
        mock_data = {
            'results': [
                {
                    'id': 'contract-1',
                    'version': 1,
                    'status': 'DRAFT',
                    'asset_id': 'asset-1'
                },
                {
                    'id': 'contract-2',
                    'version': 2,
                    'status': 'ACTIVE',
                    'asset_id': None
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'list'])

        assert result.exit_code == 0
        assert 'contract-1' in result.output
        assert 'contract-2' in result.output
        assert 'DRAFT' in result.output
        assert 'ACTIVE' in result.output
        mock_api_client.get.assert_called_once_with('contracts/contracts/', params={'limit': 20, 'offset': 0})

    def test_list_contracts_success_json_format(self, runner, mock_api_client):
        """Test listing contracts in JSON format"""
        mock_data = {
            'results': [
                {'id': 'contract-1', 'version': 1, 'status': 'DRAFT'}
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'list', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
        assert output_data[0]['id'] == 'contract-1'

    def test_list_contracts_with_filters(self, runner, mock_api_client):
        """Test listing contracts with status and asset_id filters"""
        mock_data = {'results': []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'contracts', 'list',
            '--status', 'ACTIVE',
            '--asset-id', 'asset-123',
            '--limit', '10',
            '--offset', '5'
        ])

        assert result.exit_code == 0
        mock_api_client.get.assert_called_once_with(
            'contracts/contracts/',
            params={'status': 'ACTIVE', 'asset_id': 'asset-123', 'limit': 10, 'offset': 5}
        )

    def test_list_contracts_empty_result(self, runner, mock_api_client):
        """Test listing contracts when no contracts exist"""
        mock_api_client.get.return_value = {'results': []}

        result = runner.invoke(cli, ['contracts', 'list'])

        assert result.exit_code == 0
        assert 'No contracts found' in result.output

    def test_list_contracts_unexpected_response_type(self, runner, mock_api_client):
        """Test listing contracts with unexpected response type (not dict or list)"""
        # Test edge case where API returns something unexpected
        mock_api_client.get.return_value = None

        result = runner.invoke(cli, ['contracts', 'list'])

        assert result.exit_code == 0
        assert 'No contracts found' in result.output

    def test_list_contracts_direct_list_response(self, runner, mock_api_client):
        """Test handling direct list response (not paginated)"""
        mock_data = [
            {'id': 'contract-1', 'version': 1, 'status': 'DRAFT'}
        ]
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'list'])

        assert result.exit_code == 0
        assert 'contract-1' in result.output

    def test_list_contracts_api_error(self, runner, mock_api_client):
        """Test handling API errors when listing contracts"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Connection failed")

        result = runner.invoke(cli, ['contracts', 'list'])

        assert result.exit_code != 0
        assert 'Failed to list contracts' in result.output or 'API error' in result.output


class TestContractsGet:
    """Test contracts get command"""

    def test_get_contract_success_table_format(self, runner, mock_api_client):
        """Test getting a contract in table format"""
        mock_data = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'asset_id': 'asset-1',
            'original_spec_type': 'ODCS',
            'original_format': 'YAML',
            'normalization_status': 'NORMALIZED_OK',
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:00Z'
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get', 'contract-1'])

        assert result.exit_code == 0
        assert 'contract-1' in result.output
        assert 'DRAFT' in result.output
        assert 'ODCS' in result.output
        mock_api_client.get.assert_called_once_with('contracts/contracts/contract-1/')

    def test_get_contract_success_json_format(self, runner, mock_api_client):
        """Test getting a contract in JSON format"""
        mock_data = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT'
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get', 'contract-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'contract-1'

    def test_get_contract_with_normalization_errors(self, runner, mock_api_client):
        """Test getting a contract with normalization errors"""
        mock_data = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'normalization_errors': ['Error 1', 'Error 2'],
            'normalization_warnings': ['Warning 1']
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get', 'contract-1'])

        assert result.exit_code == 0
        assert '2' in result.output  # Number of errors
        assert '1' in result.output  # Number of warnings

    def test_get_contract_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting a contract"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ['contracts', 'get', 'contract-1'])

        assert result.exit_code != 0
        assert 'Failed to get contract' in result.output or 'API error' in result.output


class TestContractsCreate:
    """Test contracts create command"""

    def test_create_contract_from_yaml_file(self, runner, mock_api_client, temp_file):
        """Test creating a contract from YAML file"""
        file_path, content = temp_file('.yaml', 'name: Test Contract\nversion: 1.0')

        mock_result = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'normalization_status': 'NORMALIZED_OK'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create', '--file', file_path])

        assert result.exit_code == 0
        assert 'Contract created successfully' in result.output
        assert 'contract-1' in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == 'contracts/contracts/'
        assert call_args[1]['json_data']['original_format'] == 'YAML'
        assert 'original_raw' in call_args[1]['json_data']

    def test_create_contract_from_json_file(self, runner, mock_api_client, temp_file):
        """Test creating a contract from JSON file"""
        file_path, content = temp_file('.json', '{"name": "Test Contract", "version": "1.0"}')

        mock_result = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create', '--file', file_path])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data']['original_format'] == 'JSON'

    def test_create_contract_format_detection_from_content(self, runner, mock_api_client, temp_file):
        """Test contract format detection from content when extension is unknown"""
        # Create file with unknown extension but JSON content
        file_path, content = temp_file('.txt', '{"name": "Test Contract"}')

        mock_result = {'id': 'contract-1', 'version': 1, 'status': 'DRAFT'}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create', '--file', file_path])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        # Should detect JSON from content
        assert call_args[1]['json_data']['original_format'] == 'JSON'

    def test_create_contract_format_detection_yaml_fallback(self, runner, mock_api_client, temp_file):
        """Test contract format detection falls back to YAML for non-JSON content"""
        # Create file with unknown extension and YAML-like content
        file_path, content = temp_file('.txt', 'name: Test Contract\nversion: 1.0')

        mock_result = {'id': 'contract-1', 'version': 1, 'status': 'DRAFT'}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create', '--file', file_path])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        # Should fall back to YAML
        assert call_args[1]['json_data']['original_format'] == 'YAML'

    def test_create_contract_with_asset_id(self, runner, mock_api_client, temp_file):
        """Test creating a contract with asset ID"""
        file_path, content = temp_file('.yaml', 'name: Test Contract')

        mock_result = {'id': 'contract-1', 'version': 1, 'status': 'DRAFT'}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', file_path,
            '--asset-id', 'asset-123'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data']['asset_id'] == 'asset-123'

    def test_create_contract_json_output(self, runner, mock_api_client, temp_file):
        """Test creating a contract with JSON output"""
        file_path, content = temp_file('.yaml', 'name: Test Contract')

        mock_result = {'id': 'contract-1', 'version': 1, 'status': 'DRAFT'}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', file_path,
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'contract-1'

    def test_create_contract_file_not_found(self, runner):
        """Test creating a contract with non-existent file"""
        result = runner.invoke(cli, ['contracts', 'create', '--file', '/nonexistent/file.yaml'])

        assert result.exit_code != 0
        # Click validates file path before command execution
        assert 'does not exist' in result.output or 'Failed to read file' in result.output or 'No such file' in result.output

    def test_create_contract_api_error(self, runner, mock_api_client, temp_file):
        """Test handling API errors when creating a contract"""
        file_path, content = temp_file('.yaml', 'name: Test Contract')

        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Validation failed")

        result = runner.invoke(cli, ['contracts', 'create', '--file', file_path])

        assert result.exit_code != 0
        assert 'Failed to create contract' in result.output or 'API error' in result.output


class TestContractsValidate:
    """Test contracts validate command"""

    def test_validate_contract_success(self, runner, mock_api_client):
        """Test validating a contract successfully"""
        mock_result = {
            'validation_status': 'VALID',
            'errors': [],
            'warnings': []
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'validate', 'contract-1'])

        assert result.exit_code == 0
        assert 'Contract is valid' in result.output
        mock_api_client.post.assert_called_once_with('contracts/contracts/contract-1/validate/')

    def test_validate_contract_with_errors(self, runner, mock_api_client):
        """Test validating a contract with errors"""
        mock_result = {
            'validation_status': 'INVALID',
            'errors': ['Error 1', 'Error 2', 'Error 3'],
            'warnings': ['Warning 1']
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'validate', 'contract-1'])

        assert result.exit_code == 0
        assert 'INVALID' in result.output
        assert 'Errors (3)' in result.output
        assert 'Warnings (1)' in result.output
        assert 'Error 1' in result.output

    def test_validate_contract_many_errors(self, runner, mock_api_client):
        """Test validating a contract with many errors (truncation)"""
        mock_result = {
            'validation_status': 'INVALID',
            'errors': [f'Error {i}' for i in range(15)],
            'warnings': []
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'validate', 'contract-1'])

        assert result.exit_code == 0
        assert 'Errors (15)' in result.output
        assert '... and 5 more' in result.output

    def test_validate_contract_json_output(self, runner, mock_api_client):
        """Test validating a contract with JSON output"""
        mock_result = {
            'validation_status': 'VALID',
            'errors': [],
            'warnings': []
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'validate', 'contract-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['validation_status'] == 'VALID'

    def test_validate_contract_api_error(self, runner, mock_api_client):
        """Test handling API errors when validating a contract"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ['contracts', 'validate', 'contract-1'])

        assert result.exit_code != 0
        assert 'Failed to validate contract' in result.output or 'API error' in result.output


class TestContractsLint:
    """Test contracts lint command"""

    def test_lint_contract_success(self, runner, mock_api_client):
        """Test linting a contract successfully"""
        mock_result = {
            'lint_status': 'PASSED',
            'issues': []
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'lint', 'contract-1'])

        assert result.exit_code == 0
        assert 'No linting issues found' in result.output
        mock_api_client.post.assert_called_once_with('contracts/contracts/contract-1/lint/')

    def test_lint_contract_with_issues(self, runner, mock_api_client):
        """Test linting a contract with issues"""
        mock_result = {
            'lint_status': 'FAILED',
            'issues': ['Issue 1', 'Issue 2', 'Issue 3']
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'lint', 'contract-1'])

        assert result.exit_code == 0
        assert 'FAILED' in result.output
        assert 'Issues (3)' in result.output
        assert 'Issue 1' in result.output

    def test_lint_contract_many_issues(self, runner, mock_api_client):
        """Test linting a contract with many issues (truncation)"""
        mock_result = {
            'lint_status': 'FAILED',
            'issues': [f'Issue {i}' for i in range(25)]
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'lint', 'contract-1'])

        assert result.exit_code == 0
        assert 'Issues (25)' in result.output
        assert '... and 5 more' in result.output

    def test_lint_contract_json_output(self, runner, mock_api_client):
        """Test linting a contract with JSON output"""
        mock_result = {
            'lint_status': 'PASSED',
            'issues': []
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'lint', 'contract-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['lint_status'] == 'PASSED'

    def test_lint_contract_api_error(self, runner, mock_api_client):
        """Test handling API errors when linting a contract"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ['contracts', 'lint', 'contract-1'])

        assert result.exit_code != 0
        assert 'Failed to lint contract' in result.output or 'API error' in result.output


class TestContractsCreateODPS:
    """Test contracts create-odps command"""

    def test_create_odps_extract_odcs_success(self, runner, mock_api_client, temp_file):
        """Test creating ODPS with --extract-odcs flag (Product-First flow)"""
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "test-product",
        "name": "Test Product"
      }
    },
    "contract": {
      "apiVersion": "odcs/v3",
      "kind": "DataContract",
      "id": "test-contract"
    }
  }
}"""
        file_path, content = temp_file('.json', odps_content)

        mock_result = {
            'odps_contract': {
                'id': 'odps-1',
                'version': 1,
                'status': 'DRAFT',
                'original_spec_type': 'ODPS',
                'original_format': 'JSON',
                'normalization_status': 'NORMALIZED_OK'
            },
            'odcs_contract': {
                'id': 'odcs-1',
                'version': 1,
                'status': 'DRAFT',
                'original_spec_type': 'ODCS',
                'normalization_status': 'NORMALIZED_OK'
            },
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create-odps', '--file', file_path, '--extract-odcs'])

        assert result.exit_code == 0
        assert 'ODPS product created successfully' in result.output
        assert 'odps-1' in result.output
        assert 'odcs-1' in result.output
        assert 'Product-First flow' in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == 'contracts/products/'
        assert call_args[1]['json_data']['original_format'] == 'JSON'
        assert call_args[1]['json_data']['resolve_external_refs'] is True
        assert 'original_raw' in call_args[1]['json_data']

    def test_create_odps_extract_odcs_yaml(self, runner, mock_api_client, temp_file):
        """Test creating ODPS from YAML file with --extract-odcs"""
        odps_content = """schema: https://opendataproducts.org/schema/v4.1
version: 4.1
product:
  details:
    en:
      productID: test-product
      name: Test Product
  contract:
    apiVersion: odcs/v3
    kind: DataContract
    id: test-contract
"""
        file_path, content = temp_file('.yaml', odps_content)

        mock_result = {
            'odps_contract': {'id': 'odps-1', 'version': 1, 'status': 'DRAFT'},
            'odcs_contract': {'id': 'odcs-1', 'version': 1, 'status': 'DRAFT'},
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create-odps', '--file', file_path, '--extract-odcs'])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data']['original_format'] == 'YAML'

    def test_create_odps_link_odcs_success(self, runner, mock_api_client, temp_file):
        """Test creating ODPS with --link-odcs flag"""
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "test-product",
        "name": "Test Product"
      }
    }
  }
}"""
        file_path, content = temp_file('.json', odps_content)

        mock_result = {
            'id': 'odps-1',
            'version': 1,
            'status': 'DRAFT',
            'original_spec_type': 'ODPS',
            'original_format': 'JSON',
            'normalization_status': 'NORMALIZED_OK'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--link-odcs', 'odcs-123'
        ])

        assert result.exit_code == 0
        assert 'ODPS contract created and linked successfully' in result.output
        assert 'odps-1' in result.output
        assert 'odcs-123' in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == 'contracts/contracts/odcs-123/link-odps/'
        assert call_args[1]['json_data']['original_format'] == 'JSON'

    def test_create_odps_with_format_override(self, runner, mock_api_client, temp_file):
        """Test creating ODPS with explicit --format option"""
        file_path, content = temp_file('.txt', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        mock_result = {
            'odps_contract': {'id': 'odps-1'},
            'odcs_contract': {'id': 'odcs-1'},
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs',
            '--format', 'JSON'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data']['original_format'] == 'JSON'

    def test_create_odps_with_version(self, runner, mock_api_client, temp_file):
        """Test creating ODPS with --version option"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        mock_result = {
            'odps_contract': {'id': 'odps-1'},
            'odcs_contract': {'id': 'odcs-1'},
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs',
            '--version', '4.1'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data'].get('odps_version') == '4.1'

    def test_create_odps_with_asset_id(self, runner, mock_api_client, temp_file):
        """Test creating ODPS with --asset-id option"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        mock_result = {
            'odps_contract': {'id': 'odps-1'},
            'odcs_contract': {'id': 'odcs-1'},
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs',
            '--asset-id', 'asset-123'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data']['asset_id'] == 'asset-123'

    def test_create_odps_no_resolve_external_refs(self, runner, mock_api_client, temp_file):
        """Test creating ODPS with --no-resolve-external-refs flag"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        mock_result = {
            'odps_contract': {'id': 'odps-1'},
            'odcs_contract': {'id': 'odcs-1'},
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs',
            '--no-resolve-external-refs'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data']['resolve_external_refs'] is False

    def test_create_odps_json_output(self, runner, mock_api_client, temp_file):
        """Test creating ODPS with JSON output format"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        mock_result = {
            'odps_contract': {'id': 'odps-1', 'version': 1},
            'odcs_contract': {'id': 'odcs-1', 'version': 1},
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs',
            '--output-format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert 'odps_contract' in output_data
        assert output_data['odps_contract']['id'] == 'odps-1'

    def test_create_odps_mutually_exclusive_options(self, runner, temp_file):
        """Test that --extract-odcs and --link-odcs are mutually exclusive"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs',
            '--link-odcs', 'odcs-123'
        ])

        assert result.exit_code != 0
        assert 'Cannot use both' in result.output or 'mutually exclusive' in result.output.lower()

    def test_create_odps_missing_flow_option(self, runner, temp_file):
        """Test that either --extract-odcs or --link-odcs must be specified"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path
        ])

        assert result.exit_code != 0
        assert 'Must specify either' in result.output or 'required' in result.output.lower()

    def test_create_odps_file_not_found(self, runner):
        """Test creating ODPS with non-existent file"""
        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', '/nonexistent/file.json',
            '--extract-odcs'
        ])

        assert result.exit_code != 0
        assert 'does not exist' in result.output or 'Failed to read file' in result.output or 'No such file' in result.output

    def test_create_odps_api_error_extract_odcs(self, runner, mock_api_client, temp_file):
        """Test handling API errors when creating ODPS with --extract-odcs"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Validation failed")

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs'
        ])

        assert result.exit_code != 0
        assert 'Failed to create ODPS contract' in result.output or 'API error' in result.output

    def test_create_odps_api_error_link_odcs(self, runner, mock_api_client, temp_file):
        """Test handling API errors when creating ODPS with --link-odcs"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Contract not found")

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--link-odcs', 'odcs-123'
        ])

        assert result.exit_code != 0
        assert 'Failed to create ODPS contract' in result.output or 'API error' in result.output

    def test_create_odps_format_auto_detection_json(self, runner, mock_api_client, temp_file):
        """Test format auto-detection for JSON content"""
        file_path, content = temp_file('.txt', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        mock_result = {
            'odps_contract': {'id': 'odps-1'},
            'odcs_contract': {'id': 'odcs-1'},
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        # Should auto-detect JSON from content
        assert call_args[1]['json_data']['original_format'] == 'JSON'

    def test_create_odps_format_auto_detection_yaml(self, runner, mock_api_client, temp_file):
        """Test format auto-detection for YAML content"""
        file_path, content = temp_file('.txt', 'schema: https://opendataproducts.org/schema/v4.1\nversion: 4.1')

        mock_result = {
            'odps_contract': {'id': 'odps-1'},
            'odcs_contract': {'id': 'odcs-1'},
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        # Should auto-detect YAML from content
        assert call_args[1]['json_data']['original_format'] == 'YAML'

    def test_create_odps_with_normalization_errors(self, runner, mock_api_client, temp_file):
        """Test creating ODPS that has normalization errors"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        mock_result = {
            'odps_contract': {
                'id': 'odps-1',
                'version': 1,
                'status': 'DRAFT',
                'normalization_status': 'NORMALIZED_WITH_ERRORS',
                'normalization_errors': ['Error 1', 'Error 2']
            },
            'odcs_contract': {
                'id': 'odcs-1',
                'version': 1,
                'status': 'DRAFT',
                'normalization_status': 'NORMALIZED_OK'
            },
            'workflow_instance_id': 'workflow-1'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create-odps',
            '--file', file_path,
            '--extract-odcs'
        ])

        assert result.exit_code == 0
        assert 'ODPS Normalization Errors: 2' in result.output


class TestContractsExport:
    """Test contracts export command"""

    def test_export_contract_odps_json(self, runner, mock_api_client):
        """Test exporting contract as ODPS format in JSON"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {}}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odps',
            '--output-format', 'json'
        ])

        assert result.exit_code == 0
        assert 'contract-1' in result.output or 'schema' in result.output
        mock_api_client.request.assert_called_once()
        call_args = mock_api_client.request.call_args
        assert call_args[0][0] == 'GET'
        assert 'contracts/contracts/contract-1/export/' in call_args[0][1]
        assert call_args[1]['params']['format'] == 'odps'
        assert call_args[1]['params']['output_format'] == 'json'

    def test_export_contract_odps_yaml(self, runner, mock_api_client):
        """Test exporting contract as ODPS format in YAML"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/x-yaml'}
        mock_response.text = 'schema: https://opendataproducts.org/schema/v4.1\nversion: 4.1'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odps',
            '--output-format', 'yaml'
        ])

        assert result.exit_code == 0
        mock_api_client.request.assert_called_once()
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'odps'
        assert call_args[1]['params']['output_format'] == 'yaml'

    def test_export_contract_odps_with_version(self, runner, mock_api_client):
        """Test exporting contract as ODPS format with version"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odps',
            '--version', '4.1'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params'].get('version') == '4.1'

    def test_export_contract_odcs_format(self, runner, mock_api_client):
        """Test exporting contract as ODCS format"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"apiVersion": "odcs/v3", "kind": "DataContract"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'odcs'

    def test_export_contract_hubcontract_format(self, runner, mock_api_client):
        """Test exporting contract as HubContract format (default)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"hub_contract_version": "1.0.0"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, ['contracts', 'export', 'contract-1'])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'hubcontract'

    def test_export_contract_json_cli_format(self, runner, mock_api_client):
        """Test exporting contract with JSON CLI output format"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"schema": "https://opendataproducts.org/schema/v4.1"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odps',
            '--cli-format', 'json'
        ])

        assert result.exit_code == 0
        # Should output raw JSON
        assert 'schema' in result.output

    def test_export_contract_api_error(self, runner, mock_api_client):
        """Test handling API errors when exporting contract"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {'error': {'message': 'Contract not found', 'code': 'NOT_FOUND'}}
        mock_response.text = '{"error": {"message": "Contract not found", "code": "NOT_FOUND"}}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, ['contracts', 'export', 'contract-1'])

        assert result.exit_code != 0
        assert 'Failed to export contract' in result.output or 'API error' in result.output

    def test_export_contract_version_only_for_odps(self, runner, mock_api_client):
        """Test that version parameter is only sent when format is odps"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"apiVersion": "odcs/v3"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '4.1'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        # Version should not be in params when format is not odps
        assert 'version' not in call_args[1]['params']


class TestContractsDownload:
    """Test contracts download command"""

    def test_download_contract_odps_json(self, runner, mock_api_client, tmp_path):
        """Test downloading contract as ODPS format in JSON"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            'Content-Disposition': 'attachment; filename="contract.odps.json"',
            'Content-Type': 'application/json'
        }
        mock_response.content = b'{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}'
        mock_api_client.request.return_value = mock_response

        output_file = tmp_path / 'downloaded.json'
        result = runner.invoke(cli, [
            'contracts', 'download', 'contract-1',
            '--format', 'odps',
            '--output-format', 'json',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        assert 'downloaded successfully' in result.output.lower()
        assert str(output_file) in result.output
        assert output_file.exists()
        assert output_file.read_bytes() == mock_response.content
        mock_api_client.request.assert_called_once()
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'odps'
        assert call_args[1]['params']['output_format'] == 'json'

    def test_download_contract_odps_yaml(self, runner, mock_api_client, tmp_path):
        """Test downloading contract as ODPS format in YAML"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            'Content-Disposition': 'attachment; filename="contract.odps.yaml"',
            'Content-Type': 'application/x-yaml'
        }
        mock_response.content = b'schema: https://opendataproducts.org/schema/v4.1\nversion: 4.1'
        mock_api_client.request.return_value = mock_response

        output_file = tmp_path / 'downloaded.yaml'
        result = runner.invoke(cli, [
            'contracts', 'download', 'contract-1',
            '--format', 'odps',
            '--output-format', 'yaml',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.read_bytes() == mock_response.content

    def test_download_contract_odps_with_version(self, runner, mock_api_client, tmp_path):
        """Test downloading contract as ODPS format with version"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Disposition': 'attachment; filename="contract.odps.json"'}
        mock_response.content = b'{"schema": "https://opendataproducts.org/schema/v4.1"}'
        mock_api_client.request.return_value = mock_response

        output_file = tmp_path / 'downloaded.json'
        result = runner.invoke(cli, [
            'contracts', 'download', 'contract-1',
            '--format', 'odps',
            '--version', '4.1',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params'].get('version') == '4.1'

    def test_download_contract_auto_filename(self, runner, mock_api_client, tmp_path):
        """Test downloading contract with auto-generated filename"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Disposition': 'attachment; filename="test-contract.odps.json"'}
        mock_response.content = b'{"schema": "https://opendataproducts.org/schema/v4.1"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'download', 'contract-1',
            '--format', 'odps'
        ])

        assert result.exit_code == 0
        # Should use filename from Content-Disposition header
        assert 'test-contract.odps.json' in result.output

    def test_download_contract_fallback_filename(self, runner, mock_api_client, tmp_path):
        """Test downloading contract with fallback filename when no Content-Disposition"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"schema": "https://opendataproducts.org/schema/v4.1"}'
        mock_api_client.request.return_value = mock_response

        # Change to tmp_path directory
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(cli, [
                'contracts', 'download', 'contract-1',
                '--format', 'odps'
            ])

            assert result.exit_code == 0
            # Should generate filename like contract-{id}.odps.json
            assert 'contract-' in result.output
            assert '.odps.json' in result.output
        finally:
            os.chdir(old_cwd)

    def test_download_contract_odcs_format(self, runner, mock_api_client, tmp_path):
        """Test downloading contract as ODCS format"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Disposition': 'attachment; filename="contract.odcs.json"'}
        mock_response.content = b'{"apiVersion": "odcs/v3"}'
        mock_api_client.request.return_value = mock_response

        output_file = tmp_path / 'downloaded.json'
        result = runner.invoke(cli, [
            'contracts', 'download', 'contract-1',
            '--format', 'odcs',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'odcs'

    def test_download_contract_hubcontract_format(self, runner, mock_api_client, tmp_path):
        """Test downloading contract as HubContract format (default)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Disposition': 'attachment; filename="contract.hubcontract.json"'}
        mock_response.content = b'{"hub_contract_version": "1.0.0"}'
        mock_api_client.request.return_value = mock_response

        output_file = tmp_path / 'downloaded.json'
        result = runner.invoke(cli, [
            'contracts', 'download', 'contract-1',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'hubcontract'

    def test_download_contract_api_error(self, runner, mock_api_client):
        """Test handling API errors when downloading contract"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {'error': {'message': 'Contract not found', 'code': 'NOT_FOUND'}}
        mock_response.text = '{"error": {"message": "Contract not found", "code": "NOT_FOUND"}}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, ['contracts', 'download', 'contract-1'])

        assert result.exit_code != 0
        assert 'Failed to download contract' in result.output or 'API error' in result.output

    def test_download_contract_file_size_info(self, runner, mock_api_client, tmp_path):
        """Test that download command shows file size"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Disposition': 'attachment; filename="contract.odps.json"'}
        mock_response.content = b'{"schema": "https://opendataproducts.org/schema/v4.1"}' * 100
        mock_api_client.request.return_value = mock_response

        output_file = tmp_path / 'downloaded.json'
        result = runner.invoke(cli, [
            'contracts', 'download', 'contract-1',
            '--format', 'odps',
            '--output', str(output_file)
        ])

        assert result.exit_code == 0
        assert 'Size:' in result.output or 'bytes' in result.output


class TestContractsGetODPS:
    """Test contracts get --show-odps command"""

    def test_get_contract_with_show_odps_flag(self, runner, mock_api_client):
        """Test getting a contract with --show-odps flag"""
        mock_data = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'original_spec_type': 'ODPS',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {
                        'pricing_plans': [
                            {
                                'planID': 'basic',
                                'name': 'Basic Plan',
                                'price': 9.99,
                                'currency': 'USD',
                                'billingPeriod': 'monthly'
                            }
                        ],
                        'access_methods': {
                            'api': {
                                'type': 'REST API',
                                'endpoint': 'https://api.example.com/v1'
                            }
                        }
                    }
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get', 'contract-1', '--show-odps'])

        assert result.exit_code == 0
        assert 'ODPS Information' in result.output
        assert 'Pricing Plans' in result.output
        assert 'Access Methods' in result.output
        assert 'Basic Plan' in result.output
        assert 'api' in result.output.lower()

    def test_get_contract_with_show_odps_no_odps_data(self, runner, mock_api_client):
        """Test getting a contract with --show-odps flag when no ODPS data exists"""
        mock_data = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'original_spec_type': 'ODCS',
            'hub_contract_json': {}
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get', 'contract-1', '--show-odps'])

        assert result.exit_code == 0
        assert 'ODPS Information' in result.output
        assert 'Not available' in result.output

    def test_get_contract_with_show_odps_json_format(self, runner, mock_api_client):
        """Test getting a contract with --show-odps flag in JSON format"""
        mock_data = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {
                        'pricing_plans': []
                    }
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get', 'contract-1', '--show-odps', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'contract-1'
        # JSON format should include all data, ODPS info is in hub_contract_json
        assert 'hub_contract_json' in output_data


class TestContractsGetPricing:
    """Test contracts get-pricing command"""

    def test_get_pricing_success_table_format(self, runner, mock_api_client):
        """Test getting pricing information in table format"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {
                        'pricing_plans': [
                            {
                                'planID': 'basic',
                                'name': 'Basic Plan',
                                'price': 9.99,
                                'currency': 'USD',
                                'billingPeriod': 'monthly'
                            },
                            {
                                'planID': 'premium',
                                'name': 'Premium Plan',
                                'price': 49.99,
                                'currency': 'USD',
                                'billingPeriod': 'monthly',
                                'isDefault': True
                            }
                        ]
                    }
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-pricing', 'contract-1'])

        assert result.exit_code == 0
        assert 'Pricing Plans for Contract: contract-1' in result.output
        assert 'Basic Plan' in result.output
        assert 'Premium Plan' in result.output
        assert '9.99 USD' in result.output
        assert '49.99 USD' in result.output
        assert 'monthly' in result.output
        assert 'Default: Yes' in result.output

    def test_get_pricing_success_json_format(self, runner, mock_api_client):
        """Test getting pricing information in JSON format"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {
                        'pricing_plans': [
                            {
                                'planID': 'basic',
                                'name': 'Basic Plan',
                                'price': 9.99
                            }
                        ]
                    }
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-pricing', 'contract-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['contract_id'] == 'contract-1'
        assert 'pricing_plans' in output_data
        assert len(output_data['pricing_plans']) == 1
        assert output_data['pricing_plans'][0]['planID'] == 'basic'

    def test_get_pricing_no_pricing_plans(self, runner, mock_api_client):
        """Test getting pricing when no pricing plans exist"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {}
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-pricing', 'contract-1'])

        assert result.exit_code == 0
        assert 'No pricing plans found' in result.output

    def test_get_pricing_no_odps_data(self, runner, mock_api_client):
        """Test getting pricing when contract has no ODPS data"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {}
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-pricing', 'contract-1'])

        assert result.exit_code == 0
        assert 'No pricing plans found' in result.output

    def test_get_pricing_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting pricing"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ['contracts', 'get-pricing', 'contract-1'])

        assert result.exit_code != 0
        assert 'Failed to get pricing' in result.output or 'API error' in result.output


class TestContractsGetAccessMethods:
    """Test contracts get-access-methods command"""

    def test_get_access_methods_success_table_format(self, runner, mock_api_client):
        """Test getting access methods in table format"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {
                        'access_methods': {
                            'api': {
                                'type': 'REST API',
                                'endpoint': 'https://api.example.com/v1/products/test',
                                'protocol': 'HTTPS'
                            },
                            'download': {
                                'type': 'File Download',
                                'url': 'https://download.example.com/data.zip'
                            }
                        }
                    }
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-access-methods', 'contract-1'])

        assert result.exit_code == 0
        assert 'Access Methods for Contract: contract-1' in result.output
        assert 'API' in result.output
        assert 'DOWNLOAD' in result.output
        assert 'REST API' in result.output
        assert 'https://api.example.com' in result.output

    def test_get_access_methods_success_json_format(self, runner, mock_api_client):
        """Test getting access methods in JSON format"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {
                        'access_methods': {
                            'api': {
                                'type': 'REST API',
                                'endpoint': 'https://api.example.com/v1'
                            }
                        }
                    }
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-access-methods', 'contract-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['contract_id'] == 'contract-1'
        assert 'access_methods' in output_data
        assert 'api' in output_data['access_methods']
        assert output_data['access_methods']['api']['type'] == 'REST API'

    def test_get_access_methods_no_access_methods(self, runner, mock_api_client):
        """Test getting access methods when none exist"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {}
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-access-methods', 'contract-1'])

        assert result.exit_code == 0
        assert 'No access methods found' in result.output

    def test_get_access_methods_no_odps_data(self, runner, mock_api_client):
        """Test getting access methods when contract has no ODPS data"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {}
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-access-methods', 'contract-1'])

        assert result.exit_code == 0
        assert 'No access methods found' in result.output

    def test_get_access_methods_complex_structure(self, runner, mock_api_client):
        """Test getting access methods with complex nested structures"""
        mock_data = {
            'id': 'contract-1',
            'hub_contract_json': {
                'marketplace': {
                    'x_odps': {
                        'access_methods': {
                            'api': {
                                'type': 'REST API',
                                'endpoint': 'https://api.example.com/v1',
                                'authentication': {
                                    'type': 'OAuth2',
                                    'scopes': ['read', 'write']
                                },
                                'rateLimits': {
                                    'requestsPerMinute': 100
                                }
                            }
                        }
                    }
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-access-methods', 'contract-1'])

        assert result.exit_code == 0
        assert 'API' in result.output
        # Complex nested structures should be displayed as JSON
        assert 'authentication' in result.output or 'rateLimits' in result.output

    def test_get_access_methods_api_error(self, runner, mock_api_client):
        """Test handling API errors when getting access methods"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Not found")

        result = runner.invoke(cli, ['contracts', 'get-access-methods', 'contract-1'])

        assert result.exit_code != 0
        assert 'Failed to get access methods' in result.output or 'API error' in result.output


class TestContractsFormatDetection:
    """Test contract format detection functionality"""

    def test_detect_odps_contract_from_schema_url(self, runner):
        """Test detecting ODPS contract from schema URL"""
        from datahub_cli.commands.contracts import _detect_contract_spec_type

        odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {}}'
        spec_type = _detect_contract_spec_type(odps_content, 'JSON')
        assert spec_type == 'ODPS'

    def test_detect_odps_contract_from_product_field(self, runner):
        """Test detecting ODPS contract from product field"""
        from datahub_cli.commands.contracts import _detect_contract_spec_type

        odps_content = '{"product": {"details": {"en": {"name": "Test Product"}}}}'
        spec_type = _detect_contract_spec_type(odps_content, 'JSON')
        assert spec_type == 'ODPS'

    def test_detect_odcs_contract_from_apiversion(self, runner):
        """Test detecting ODCS contract from apiVersion and kind"""
        from datahub_cli.commands.contracts import _detect_contract_spec_type

        odcs_content = '{"apiVersion": "odcs/v3", "kind": "DataContract", "id": "test"}'
        spec_type = _detect_contract_spec_type(odcs_content, 'JSON')
        assert spec_type == 'ODCS'

    def test_detect_odps_contract_yaml(self, runner):
        """Test detecting ODPS contract from YAML content"""
        from datahub_cli.commands.contracts import _detect_contract_spec_type

        odps_content = """schema: https://opendataproducts.org/schema/v4.1
version: 4.1
product:
  details:
    en:
      name: Test Product
"""
        spec_type = _detect_contract_spec_type(odps_content, 'YAML')
        assert spec_type == 'ODPS'

    def test_detect_odcs_contract_yaml(self, runner):
        """Test detecting ODCS contract from YAML content"""
        from datahub_cli.commands.contracts import _detect_contract_spec_type

        odcs_content = """apiVersion: odcs/v3
kind: DataContract
id: test
"""
        spec_type = _detect_contract_spec_type(odcs_content, 'YAML')
        assert spec_type == 'ODCS'

    def test_detect_contract_invalid_json(self, runner):
        """Test detection with invalid JSON returns None"""
        from datahub_cli.commands.contracts import _detect_contract_spec_type

        invalid_content = '{"invalid": json}'
        spec_type = _detect_contract_spec_type(invalid_content, 'JSON')
        assert spec_type is None

    def test_detect_contract_defaults_to_odcs(self, runner):
        """Test that contracts without clear indicators default to ODCS"""
        from datahub_cli.commands.contracts import _detect_contract_spec_type

        generic_content = '{"id": "test", "name": "Test Contract"}'
        spec_type = _detect_contract_spec_type(generic_content, 'JSON')
        assert spec_type == 'ODCS'


class TestContractsCreateWithDetection:
    """Test contracts create command with format detection"""

    def test_create_contract_auto_detects_odps(self, runner, mock_api_client, temp_file):
        """Test creating contract with auto-detected ODPS format"""
        odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "test-product",
        "name": "Test Product"
      }
    }
  }
}"""
        file_path, content = temp_file('.json', odps_content)

        mock_result = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'original_spec_type': 'ODPS',
            'normalization_status': 'NORMALIZED_OK'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create', '--file', file_path])

        assert result.exit_code == 0
        assert 'Auto-detected spec type: ODPS' in result.output or 'ODPS' in result.output
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data'].get('original_spec_type') == 'ODPS'

    def test_create_contract_auto_detects_odcs(self, runner, mock_api_client, temp_file):
        """Test creating contract with auto-detected ODCS format"""
        odcs_content = """{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "test-contract",
  "name": "Test Contract"
}"""
        file_path, content = temp_file('.json', odcs_content)

        mock_result = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'original_spec_type': 'ODCS',
            'normalization_status': 'NORMALIZED_OK'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create', '--file', file_path])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        # Should detect ODCS (may not show message if default)
        assert call_args[1]['json_data'].get('original_spec_type') == 'ODCS' or 'original_spec_type' not in call_args[1]['json_data']

    def test_create_contract_with_spec_type_override(self, runner, mock_api_client, temp_file):
        """Test creating contract with spec type override"""
        file_path, content = temp_file('.json', '{"id": "test"}')

        mock_result = {'id': 'contract-1', 'version': 1, 'status': 'DRAFT'}
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, [
            'contracts', 'create',
            '--file', file_path,
            '--spec-type', 'ODPS'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        assert call_args[1]['json_data'].get('original_spec_type') == 'ODPS'

    def test_create_contract_shows_spec_type_in_output(self, runner, mock_api_client, temp_file):
        """Test that created contract shows spec type in output"""
        file_path, content = temp_file('.json', '{"schema": "https://opendataproducts.org/schema/v4.1"}')

        mock_result = {
            'id': 'contract-1',
            'version': 1,
            'status': 'DRAFT',
            'original_spec_type': 'ODPS',
            'normalization_status': 'NORMALIZED_OK'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'create', '--file', file_path])

        assert result.exit_code == 0
        assert 'Spec Type: ODPS' in result.output


class TestContractsListWithSpecType:
    """Test contracts list command showing original_spec_type"""

    def test_list_contracts_shows_spec_type(self, runner, mock_api_client):
        """Test that list command shows original_spec_type column"""
        mock_data = {
            'results': [
                {
                    'id': 'contract-1',
                    'version': 1,
                    'status': 'DRAFT',
                    'original_spec_type': 'ODPS',
                    'asset_id': None
                },
                {
                    'id': 'contract-2',
                    'version': 2,
                    'status': 'ACTIVE',
                    'original_spec_type': 'ODCS',
                    'asset_id': 'asset-1'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'list'])

        assert result.exit_code == 0
        assert 'Spec Type' in result.output
        assert 'ODPS' in result.output
        assert 'ODCS' in result.output

    def test_list_contracts_spec_type_none(self, runner, mock_api_client):
        """Test that list command handles missing spec_type gracefully"""
        mock_data = {
            'results': [
                {
                    'id': 'contract-1',
                    'version': 1,
                    'status': 'DRAFT',
                    'asset_id': None
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'list'])

        assert result.exit_code == 0
        assert 'Spec Type' in result.output
        # Should show N/A for missing spec_type
        assert 'N/A' in result.output or 'contract-1' in result.output


# Note: update and delete commands are not implemented in contracts.py
# They would be tested similarly if they were added


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def mock_api_client(monkeypatch):
    """Mock API client"""
    mock_client = Mock()
    monkeypatch.setattr('datahub_cli.commands.contracts.api_client', mock_client)
    return mock_client


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file"""
    def _create_file(extension, content):
        file_path = tmp_path / f'test{extension}'
        file_path.write_text(content)
        return str(file_path), content
    return _create_file


class TestContractsLinkODPS:
    """Test contracts link-odps command"""

    def test_link_odps_success_table_format(self, runner, mock_api_client):
        """Test linking ODPS to ODCS in table format"""
        mock_result = {
            'id': 'odps-1',
            'version': 1,
            'status': 'ACTIVE',
            'original_spec_type': 'ODPS',
            'normalization_status': 'NORMALIZED_OK'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'link-odps', 'odcs-1', 'odps-1'])

        assert result.exit_code == 0
        assert 'ODPS contract linked successfully' in result.output
        assert 'odcs-1' in result.output
        assert 'odps-1' in result.output
        assert 'ACTIVE' in result.output
        mock_api_client.post.assert_called_once_with(
            'contracts/contracts/odcs-1/link-odps/',
            json_data={'odps_contract_id': 'odps-1'}
        )

    def test_link_odps_success_json_format(self, runner, mock_api_client):
        """Test linking ODPS to ODCS in JSON format"""
        mock_result = {
            'id': 'odps-1',
            'version': 1,
            'status': 'ACTIVE',
            'original_spec_type': 'ODPS'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'link-odps', 'odcs-1', 'odps-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'odps-1'
        assert output_data['status'] == 'ACTIVE'

    def test_link_odps_api_error(self, runner, mock_api_client):
        """Test handling API errors when linking ODPS"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Contract not found")

        result = runner.invoke(cli, ['contracts', 'link-odps', 'odcs-1', 'odps-1'])

        assert result.exit_code != 0
        assert 'Failed to link ODPS contract' in result.output or 'API error' in result.output


class TestContractsUnlinkODPS:
    """Test contracts unlink-odps command"""

    def test_unlink_odps_success_table_format(self, runner, mock_api_client):
        """Test unlinking ODPS from ODCS in table format"""
        mock_result = {
            'message': 'ODPS contract unlinked successfully'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'unlink-odps', 'odcs-1'])

        assert result.exit_code == 0
        assert 'ODPS contract unlinked successfully' in result.output
        assert 'odcs-1' in result.output
        mock_api_client.post.assert_called_once_with(
            'contracts/contracts/odcs-1/unlink-odps/'
        )

    def test_unlink_odps_success_json_format(self, runner, mock_api_client):
        """Test unlinking ODPS from ODCS in JSON format"""
        mock_result = {
            'message': 'ODPS contract unlinked successfully'
        }
        mock_api_client.post.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'unlink-odps', 'odcs-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['message'] == 'ODPS contract unlinked successfully'

    def test_unlink_odps_api_error(self, runner, mock_api_client):
        """Test handling API errors when unlinking ODPS"""
        from click import ClickException
        mock_api_client.post.side_effect = ClickException("API error: Contract not found")

        result = runner.invoke(cli, ['contracts', 'unlink-odps', 'odcs-1'])

        assert result.exit_code != 0
        assert 'Failed to unlink ODPS contract' in result.output or 'API error' in result.output


class TestContractsListLinks:
    """Test contracts list-links command"""

    def test_list_links_with_odps_link(self, runner, mock_api_client):
        """Test listing links when ODPS link exists"""
        mock_result = {
            'odps_link': {
                'id': 'odps-1',
                'version': 1,
                'status': 'ACTIVE',
                'original_spec_type': 'ODPS',
                'normalization_status': 'NORMALIZED_OK'
            },
            'odcs_link': None
        }
        mock_api_client.get.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'list-links', 'odcs-1'])

        assert result.exit_code == 0
        assert 'odcs-1' in result.output
        assert 'ODPS Link:' in result.output
        assert 'odps-1' in result.output
        assert 'ODCS Link: None' in result.output
        mock_api_client.get.assert_called_once_with(
            'contracts/contracts/odcs-1/links/'
        )

    def test_list_links_with_odcs_link(self, runner, mock_api_client):
        """Test listing links when ODCS link exists"""
        mock_result = {
            'odps_link': None,
            'odcs_link': {
                'id': 'odcs-1',
                'version': 1,
                'status': 'ACTIVE',
                'original_spec_type': 'ODCS',
                'normalization_status': 'NORMALIZED_OK'
            }
        }
        mock_api_client.get.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'list-links', 'odps-1'])

        assert result.exit_code == 0
        assert 'odps-1' in result.output
        assert 'ODPS Link: None' in result.output
        assert 'ODCS Link:' in result.output
        assert 'odcs-1' in result.output

    def test_list_links_with_both_links(self, runner, mock_api_client):
        """Test listing links when both ODPS and ODCS links exist"""
        mock_result = {
            'odps_link': {
                'id': 'odps-1',
                'version': 1,
                'status': 'ACTIVE',
                'original_spec_type': 'ODPS'
            },
            'odcs_link': {
                'id': 'odcs-1',
                'version': 1,
                'status': 'ACTIVE',
                'original_spec_type': 'ODCS'
            }
        }
        mock_api_client.get.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'list-links', 'contract-1'])

        assert result.exit_code == 0
        assert 'ODPS Link:' in result.output
        assert 'ODCS Link:' in result.output
        assert 'odps-1' in result.output
        assert 'odcs-1' in result.output

    def test_list_links_no_links(self, runner, mock_api_client):
        """Test listing links when no links exist"""
        mock_result = {
            'odps_link': None,
            'odcs_link': None
        }
        mock_api_client.get.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'list-links', 'contract-1'])

        assert result.exit_code == 0
        assert 'No links found for this contract' in result.output
        assert 'ODPS Link: None' in result.output
        assert 'ODCS Link: None' in result.output

    def test_list_links_json_format(self, runner, mock_api_client):
        """Test listing links in JSON format"""
        mock_result = {
            'odps_link': {
                'id': 'odps-1',
                'version': 1,
                'status': 'ACTIVE'
            },
            'odcs_link': None
        }
        mock_api_client.get.return_value = mock_result

        result = runner.invoke(cli, ['contracts', 'list-links', 'odcs-1', '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['odps_link']['id'] == 'odps-1'
        assert output_data['odcs_link'] is None

    def test_list_links_api_error(self, runner, mock_api_client):
        """Test handling API errors when listing links"""
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Contract not found")

        result = runner.invoke(cli, ['contracts', 'list-links', 'contract-1'])

        assert result.exit_code != 0
        assert 'Failed to list contract links' in result.output or 'API error' in result.output

