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

