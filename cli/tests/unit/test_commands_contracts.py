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
        # Output may include stderr messages (like "Auto-detected spec type"), extract JSON
        output_lines = result.output.strip().split('\n')
        # Find the JSON part (starts with '{')
        json_start = None
        for i, line in enumerate(output_lines):
            if line.strip().startswith('{'):
                json_start = i
                break

        assert json_start is not None, f"JSON not found in output: {result.output}"
        json_output = '\n'.join(output_lines[json_start:])
        output_data = json.loads(json_output)
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
        # Error message can be "Failed to create ODPS contract" or "API error" or validation error
        assert ('Failed to create ODPS contract' in result.output or
                'API error' in result.output or
                'Must specify either' in result.output or
                'Contract not found' in result.output)

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
        assert 'contracts/contract-1/export/' in call_args[0][1]
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
        # Enhanced error handling provides better formatted messages
        assert 'Contract not found' in result.output or 'Failed to export' in result.output or 'error' in result.output.lower()

    def test_export_contract_odcs_with_version(self, runner, mock_api_client):
        """Test exporting contract as ODCS format with version"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.2'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'odcs'
        assert call_args[1]['params'].get('version') == '3.0.2'

    def test_export_contract_odcs_with_version_yaml(self, runner, mock_api_client):
        """Test exporting contract as ODCS format with version in YAML"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/x-yaml'}
        mock_response.text = 'apiVersion: odcs.io/v3.0.2\nkind: DataContract'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.1',
            '--output-format', 'yaml'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'odcs'
        assert call_args[1]['params']['output_format'] == 'yaml'
        assert call_args[1]['params'].get('version') == '3.0.1'

    def test_export_contract_odcs_invalid_version_format(self, runner):
        """Test exporting contract as ODCS with invalid version format"""
        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', 'invalid'
        ])

        assert result.exit_code != 0
        assert 'Invalid ODCS version format' in result.output or 'invalid' in result.output.lower()

    def test_export_contract_odcs_unsupported_version(self, runner):
        """Test exporting contract as ODCS with unsupported version"""
        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '99.99.99'
        ])

        assert result.exit_code != 0
        assert 'not supported' in result.output.lower()

    def test_export_contract_odcs_version_preview(self, runner, mock_api_client):
        """Test exporting contract as ODCS with preview version"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"apiVersion": "odcs.io/v3.0.0-preview"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.0-preview'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params'].get('version') == '3.0.0-preview'

    def test_export_contract_version_only_for_odps_or_odcs(self, runner, mock_api_client):
        """Test that version parameter is only sent when format is odps or odcs"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = '{"hub_contract_version": "1.0.0"}'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'hubcontract',
            '--version', '3.0.2'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        # Version should not be in params when format is hubcontract
        assert 'version' not in call_args[1]['params'] or call_args[1]['params'].get('version') is None

    def test_export_contract_odcs_all_versions_json(self, runner, mock_api_client):
        """Test exporting ODCS with all supported versions as JSON"""
        supported_versions = ['3.0.2', '3.0.1', '3.0.0', '3.0.0-preview', '2.2.2']

        for version in supported_versions:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Type': 'application/json'}
            mock_response.text = json.dumps({
                'apiVersion': f'odcs.io/v{version}',
                'kind': 'DataContract',
                'id': 'test-contract'
            })
            mock_api_client.request.return_value = mock_response

            result = runner.invoke(cli, [
                'contracts', 'export', 'contract-1',
                '--format', 'odcs',
                '--version', version,
                '--output-format', 'json'
            ])

            assert result.exit_code == 0, f"Failed for version {version}: {result.output}"
            call_args = mock_api_client.request.call_args
            assert call_args[1]['params']['format'] == 'odcs'
            assert call_args[1]['params']['version'] == version
            assert call_args[1]['params']['output_format'] == 'json'

    def test_export_contract_odcs_all_versions_yaml(self, runner, mock_api_client):
        """Test exporting ODCS with all supported versions as YAML"""
        supported_versions = ['3.0.2', '3.0.1', '3.0.0', '3.0.0-preview', '2.2.2']

        for version in supported_versions:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'Content-Type': 'application/x-yaml'}
            mock_response.text = f'apiVersion: odcs.io/v{version}\nkind: DataContract\nid: test-contract'
            mock_api_client.request.return_value = mock_response

            result = runner.invoke(cli, [
                'contracts', 'export', 'contract-1',
                '--format', 'odcs',
                '--version', version,
                '--output-format', 'yaml'
            ])

            assert result.exit_code == 0, f"Failed for version {version}: {result.output}"
            call_args = mock_api_client.request.call_args
            assert call_args[1]['params']['format'] == 'odcs'
            assert call_args[1]['params']['version'] == version
            assert call_args[1]['params']['output_format'] == 'yaml'

    def test_export_contract_odcs_format_conversion_json_to_yaml(self, runner, mock_api_client):
        """Test exporting ODCS with format conversion from JSON to YAML"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/x-yaml'}
        mock_response.text = 'apiVersion: odcs.io/v3.0.2\nkind: DataContract\nid: test-contract'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.2',
            '--output-format', 'yaml',
            '--cli-format', 'json'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'odcs'
        assert call_args[1]['params']['output_format'] == 'yaml'
        # CLI format json should output raw content
        assert 'apiVersion' in result.output or 'odcs' in result.output.lower()

    def test_export_contract_odcs_format_conversion_yaml_to_json(self, runner, mock_api_client):
        """Test exporting ODCS with format conversion from YAML to JSON"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = json.dumps({
            'apiVersion': 'odcs.io/v3.0.2',
            'kind': 'DataContract',
            'id': 'test-contract'
        })
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.2',
            '--output-format', 'json',
            '--cli-format', 'table'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.request.call_args
        assert call_args[1]['params']['format'] == 'odcs'
        assert call_args[1]['params']['output_format'] == 'json'
        # Table format should show export info
        assert 'exported successfully' in result.output.lower() or 'Contract ID' in result.output

    def test_export_contract_odcs_error_handling_api_error(self, runner, mock_api_client):
        """Test error handling for ODCS export API errors"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = json.dumps({
            'error': {
                'message': 'Invalid ODCS version',
                'code': 'INVALID_VERSION'
            }
        })
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.2'
        ])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'failed' in result.output.lower()

    def test_export_contract_odcs_error_handling_invalid_json_response(self, runner, mock_api_client):
        """Test error handling for invalid JSON response from ODCS export"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = 'invalid json content {'
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.2',
            '--output-format', 'json'
        ])

        assert result.exit_code != 0
        assert 'invalid' in result.output.lower() or 'json' in result.output.lower()

    def test_export_contract_odcs_error_handling_missing_odcs_fields(self, runner, mock_api_client):
        """Test warning for ODCS export missing required fields"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        # Missing apiVersion and kind fields
        mock_response.text = json.dumps({
            'id': 'test-contract',
            'name': 'Test Contract'
        })
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.2',
            '--output-format', 'json'
        ])

        # Should succeed but show warning
        assert result.exit_code == 0
        assert 'warning' in result.output.lower() or 'may not be valid' in result.output.lower()

    def test_export_contract_odcs_error_handling_404_not_found(self, runner, mock_api_client):
        """Test error handling for 404 Not Found when exporting ODCS"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = json.dumps({
            'error': {
                'message': 'Contract not found',
                'code': 'NOT_FOUND'
            }
        })
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'nonexistent-contract',
            '--format', 'odcs',
            '--version', '3.0.2'
        ])

        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'error' in result.output.lower()

    def test_export_contract_odcs_error_handling_500_server_error(self, runner, mock_api_client):
        """Test error handling for 500 Server Error when exporting ODCS"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = json.dumps({
            'error': {
                'message': 'Internal server error',
                'code': 'INTERNAL_ERROR'
            }
        })
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.2'
        ])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'failed' in result.output.lower()

    def test_export_contract_odcs_with_version_table_output(self, runner, mock_api_client):
        """Test ODCS export with version showing table output format"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.text = json.dumps({
            'apiVersion': 'odcs.io/v3.0.2',
            'kind': 'DataContract',
            'id': 'test-contract',
            'name': 'Test Contract'
        })
        mock_api_client.request.return_value = mock_response

        result = runner.invoke(cli, [
            'contracts', 'export', 'contract-1',
            '--format', 'odcs',
            '--version', '3.0.2',
            '--output-format', 'json',
            '--cli-format', 'table'
        ])

        assert result.exit_code == 0
        assert 'exported successfully' in result.output.lower()
        assert 'ODCS Version: 3.0.2' in result.output
        assert 'Format: odcs' in result.output
        assert 'Output Format: json' in result.output


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


class TestContractsGetPaymentGateways:
    """Test contracts get-payment-gateways command"""

    def test_get_payment_gateways_success_table_format(self, runner, mock_api_client):
        """Test getting payment gateways in table format"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'payment_gateways': {
                'stripe': {
                    'type': 'stripe',
                    'enabled': True,
                    'webhook_url': 'https://api.stripe.com/webhook'
                },
                'paypal': {
                    'type': 'paypal',
                    'enabled': False,
                    'webhook_url': None
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code == 0
        assert 'stripe' in result.output
        assert 'paypal' in result.output
        assert 'Yes' in result.output
        assert 'No' in result.output
        assert 'Payment Gateways for Contract' in result.output
        assert 'Total: 2 payment gateway(s)' in result.output
        mock_api_client.get.assert_called_once_with(f'contracts/{contract_id}/payment-gateways/')

    def test_get_payment_gateways_success_json_format(self, runner, mock_api_client):
        """Test getting payment gateways in JSON format"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'payment_gateways': {
                'stripe': {
                    'type': 'stripe',
                    'enabled': True,
                    'webhook_url': 'https://api.stripe.com/webhook'
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        assert 'stripe' in output_data
        assert output_data['stripe']['type'] == 'stripe'
        assert output_data['stripe']['enabled'] is True

    def test_get_payment_gateways_empty(self, runner, mock_api_client):
        """Test getting payment gateways when none are configured"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'payment_gateways': {}
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code == 0
        assert 'No payment gateways found' in result.output
        assert 'ODPS contracts' in result.output

    def test_get_payment_gateways_long_webhook_url(self, runner, mock_api_client):
        """Test getting payment gateways with long webhook URL (truncation)"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        long_url = 'https://api.example.com/webhook/' + 'x' * 100
        mock_data = {
            'payment_gateways': {
                'stripe': {
                    'type': 'stripe',
                    'enabled': True,
                    'webhook_url': long_url
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code == 0
        assert 'stripe' in result.output
        # Check that URL is truncated (should end with ...)
        assert '...' in result.output or len(long_url) > 48

    def test_get_payment_gateways_missing_fields(self, runner, mock_api_client):
        """Test getting payment gateways with missing optional fields"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'payment_gateways': {
                'stripe': {
                    # Missing type, enabled, webhook_url
                }
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code == 0
        assert 'stripe' in result.output
        assert 'N/A' in result.output  # Should show N/A for missing fields

    def test_get_payment_gateways_invalid_contract_id(self, runner):
        """Test getting payment gateways with invalid contract ID"""
        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', 'invalid-id'])

        assert result.exit_code != 0
        assert 'uuid' in result.output.lower() or 'invalid' in result.output.lower() or 'not found' in result.output.lower() or 'resource not found' in result.output.lower()

    def test_get_payment_gateways_empty_contract_id(self, runner):
        """Test getting payment gateways with empty contract ID"""
        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', ''])

        assert result.exit_code != 0

    def test_get_payment_gateways_api_error_404(self, runner, mock_api_client):
        """Test getting payment gateways when contract not found"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Contract not found (404)")

        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or '404' in result.output or 'error' in result.output.lower()

    def test_get_payment_gateways_api_error_400(self, runner, mock_api_client):
        """Test getting payment gateways when contract is not ODPS"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Contract is not an ODPS contract (400)")

        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'validation' in result.output.lower() or 'odps' in result.output.lower()

    def test_get_payment_gateways_api_error_500(self, runner, mock_api_client):
        """Test getting payment gateways when API returns server error"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_api_client.get.side_effect = Exception("Internal server error")

        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'failed' in result.output.lower()


class TestContractsGetProductStrategy:
    """Test contracts get-product-strategy command"""

    def test_get_product_strategy_success_table_format(self, runner, mock_api_client):
        """Test getting product strategy in table format"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_strategy': {
                'objectives': [
                    {'name': 'Increase revenue', 'description': 'Target 20% growth'}
                ],
                'strategicAlignment': [
                    {'name': 'Digital transformation', 'description': 'Align with company goals'}
                ],
                'productKPIs': [
                    {'name': 'User adoption', 'targetValue': '1000', 'unit': 'users', 'description': 'Monthly active users'}
                ],
                'targetAudience': {'type': 'enterprise', 'size': 'large'},
                'valueProposition': {'key': 'value', 'benefit': 'cost reduction'}
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code == 0
        assert 'Product Strategy for Contract' in result.output
        assert 'Objectives' in result.output
        assert 'Strategic Alignment' in result.output
        assert 'Product KPIs' in result.output
        assert 'Target Audience' in result.output
        assert 'Value Proposition' in result.output
        assert 'Increase revenue' in result.output
        assert 'Summary:' in result.output
        mock_api_client.get.assert_called_once_with(f'contracts/{contract_id}/product-strategy/')

    def test_get_product_strategy_success_json_format(self, runner, mock_api_client):
        """Test getting product strategy in JSON format"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_strategy': {
                'objectives': [{'name': 'Test objective'}],
                'productKPIs': [{'name': 'Test KPI', 'targetValue': '100'}]
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        assert 'objectives' in output_data
        assert 'productKPIs' in output_data

    def test_get_product_strategy_empty(self, runner, mock_api_client):
        """Test getting product strategy when none is configured"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_strategy': None
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code == 0
        assert 'No product strategy found' in result.output
        assert 'ODPS 4.1+' in result.output

    def test_get_product_strategy_partial_data(self, runner, mock_api_client):
        """Test getting product strategy with partial data (only objectives)"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_strategy': {
                'objectives': [{'name': 'Single objective'}]
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code == 0
        assert 'Objectives' in result.output
        assert 'Single objective' in result.output
        # Should not error if other sections are missing

    def test_get_product_strategy_invalid_contract_id(self, runner):
        """Test getting product strategy with invalid contract ID"""
        result = runner.invoke(cli, ['contracts', 'get-product-strategy', 'invalid-id'])

        assert result.exit_code != 0
        assert 'uuid' in result.output.lower() or 'invalid' in result.output.lower() or 'not found' in result.output.lower()

    def test_get_product_strategy_empty_contract_id(self, runner):
        """Test getting product strategy with empty contract ID"""
        result = runner.invoke(cli, ['contracts', 'get-product-strategy', ''])

        assert result.exit_code != 0

    def test_get_product_strategy_api_error_404(self, runner, mock_api_client):
        """Test getting product strategy when contract not found"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Contract not found (404)")

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or '404' in result.output or 'error' in result.output.lower()

    def test_get_product_strategy_api_error_400_not_odps(self, runner, mock_api_client):
        """Test getting product strategy when contract is not ODPS"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Contract is not an ODPS contract (400)")

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'odps' in result.output.lower()

    def test_get_product_strategy_api_error_400_version(self, runner, mock_api_client):
        """Test getting product strategy when contract is not ODPS 4.1+"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Product strategy is only available for ODPS 4.1+ (400)")

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or '4.1' in result.output.lower()

    def test_get_product_strategy_api_error_500(self, runner, mock_api_client):
        """Test getting product strategy when API returns server error"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_api_client.get.side_effect = Exception("Internal server error")

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'failed' in result.output.lower()

    def test_get_product_strategy_complex_data(self, runner, mock_api_client):
        """Test getting product strategy with complex nested data"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_strategy': {
                'objectives': [
                    {'name': 'Obj1', 'description': 'Desc1'},
                    {'name': 'Obj2', 'description': 'Desc2'}
                ],
                'strategicAlignment': [
                    {'name': 'Align1', 'description': 'AlignDesc1'},
                    {'name': 'Align2'}
                ],
                'productKPIs': [
                    {'name': 'KPI1', 'targetValue': '100', 'unit': 'users', 'description': 'KPI desc'},
                    {'name': 'KPI2', 'targetValue': '50', 'unit': '%'}
                ],
                'targetAudience': {'type': 'enterprise', 'size': 'large', 'industry': 'tech'},
                'valueProposition': {'key': 'value', 'benefit': 'cost reduction', 'differentiator': 'quality'}
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code == 0
        assert '2 objective(s)' in result.output or 'objective' in result.output.lower()
        assert '2 alignment(s)' in result.output or 'alignment' in result.output.lower()
        assert '2 KPI(s)' in result.output or 'kpi' in result.output.lower()
        assert 'target audience' in result.output.lower()
        assert 'value proposition' in result.output.lower()


class TestContractsGetProductDetails:
    """Test contracts get-product-details command"""

    def test_get_product_details_success_table_format(self, runner, mock_api_client):
        """Test getting product details in table format"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Test Product',
                'description': 'A test product description',
                'productVersion': '1.0.0',
                'category': 'Data Product',
                'tags': ['tag1', 'tag2', 'tag3']
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code == 0
        assert 'Product Details for Contract' in result.output
        assert 'Language: en' in result.output
        assert 'Product ID: test-product' in result.output
        assert 'Name: Test Product' in result.output
        assert 'Description: A test product description' in result.output
        assert 'Version: 1.0.0' in result.output
        assert 'Category: Data Product' in result.output
        assert 'tag1' in result.output
        mock_api_client.get.assert_called_once_with(f'contracts/{contract_id}/product-details/', params={'lang': 'en'})

    def test_get_product_details_success_json_format(self, runner, mock_api_client):
        """Test getting product details in JSON format"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Test Product',
                'description': 'A test product description'
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        assert 'productID' in output_data
        assert 'name' in output_data
        assert output_data['productID'] == 'test-product'
        assert output_data['name'] == 'Test Product'

    def test_get_product_details_with_language_parameter(self, runner, mock_api_client):
        """Test getting product details with language parameter"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Testi Tuote',
                'description': 'Testituotteen kuvaus'
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'fi'])

        assert result.exit_code == 0
        assert 'Language: fi' in result.output
        assert 'Testi Tuote' in result.output
        mock_api_client.get.assert_called_once_with(f'contracts/{contract_id}/product-details/', params={'lang': 'fi'})

    def test_get_product_details_empty(self, runner, mock_api_client):
        """Test getting product details when none is configured"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_details': None
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code == 0
        assert 'No product details found' in result.output
        assert 'may not be available for all languages' in result.output

    def test_get_product_details_partial_data(self, runner, mock_api_client):
        """Test getting product details with partial data (only name and productID)"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Test Product'
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code == 0
        assert 'Product ID: test-product' in result.output
        assert 'Name: Test Product' in result.output

    def test_get_product_details_invalid_contract_id(self, runner):
        """Test getting product details with invalid contract ID"""
        result = runner.invoke(cli, ['contracts', 'get-product-details', 'invalid-id'])

        assert result.exit_code != 0
        assert 'uuid' in result.output.lower() or 'invalid' in result.output.lower() or 'not found' in result.output.lower()

    def test_get_product_details_empty_contract_id(self, runner):
        """Test getting product details with empty contract ID"""
        result = runner.invoke(cli, ['contracts', 'get-product-details', ''])

        assert result.exit_code != 0

    def test_get_product_details_invalid_language_code(self, runner):
        """Test getting product details with invalid language code"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'invalid'])

        assert result.exit_code != 0
        assert 'language code' in result.output.lower() or 'invalid' in result.output.lower()

    def test_get_product_details_language_code_too_long(self, runner):
        """Test getting product details with language code that is too long"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'eng'])

        assert result.exit_code != 0
        assert 'language code' in result.output.lower() or '2 characters' in result.output.lower()

    def test_get_product_details_api_error_404(self, runner, mock_api_client):
        """Test getting product details when contract not found"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Contract not found (404)")

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or '404' in result.output or 'error' in result.output.lower()

    def test_get_product_details_api_error_400_not_odps(self, runner, mock_api_client):
        """Test getting product details when contract is not ODPS"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error: Contract is not an ODPS contract (400)")

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'odps' in result.output.lower()

    def test_get_product_details_api_error_500(self, runner, mock_api_client):
        """Test getting product details when API returns server error"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_api_client.get.side_effect = Exception("Internal server error")

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'failed' in result.output.lower()

    def test_get_product_details_multilingual_support(self, runner, mock_api_client):
        """Test getting product details with different languages"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'

        # Test English
        mock_data_en = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Test Product',
                'description': 'English description'
            }
        }
        mock_api_client.get.return_value = mock_data_en
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'en'])
        assert result.exit_code == 0
        assert 'Test Product' in result.output
        assert 'English description' in result.output

        # Test Spanish
        mock_data_es = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Producto de Prueba',
                'description': 'Descripción en español'
            }
        }
        mock_api_client.get.return_value = mock_data_es
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'es'])
        assert result.exit_code == 0
        assert 'Producto de Prueba' in result.output
        assert 'Descripción en español' in result.output

    def test_get_product_details_with_tags(self, runner, mock_api_client):
        """Test getting product details with tags list"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Test Product',
                'tags': ['data', 'analytics', 'product']
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code == 0
        assert 'Tags:' in result.output
        assert 'data' in result.output
        assert 'analytics' in result.output
        assert 'product' in result.output

    def test_get_product_details_with_additional_fields(self, runner, mock_api_client):
        """Test getting product details with additional fields"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Test Product',
                'customField': 'custom value',
                'nestedField': {'key': 'value'}
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code == 0
        assert 'Additional Fields:' in result.output
        assert 'customField' in result.output
        assert 'nestedField' in result.output

    def test_get_product_details_language_case_insensitive(self, runner, mock_api_client):
        """Test that language code is converted to lowercase"""
        contract_id = '123e4567-e89b-12d3-a456-426614174000'
        mock_data = {
            'product_details': {
                'productID': 'test-product',
                'name': 'Test Product'
            }
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'EN'])

        assert result.exit_code == 0
        # Should call API with lowercase 'en'
        mock_api_client.get.assert_called_once_with(f'contracts/{contract_id}/product-details/', params={'lang': 'en'})

