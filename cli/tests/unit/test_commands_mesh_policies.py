from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive unit tests for Mesh Policy CLI commands.

Tests all policy commands: apply, list, remove.
"""
import pytest
import json
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from datahub_cli.main import cli
from datahub_cli.commands import mesh
from datahub_cli.api_client import api_client


@pytest.fixture
def runner():
    """Create CLI runner"""
    return CliRunner()


@pytest.fixture
def mock_api_client():
    """Mock API client for testing"""
    with patch('datahub_cli.commands.mesh.api_client') as mock_client:
        yield mock_client


class TestMeshPoliciesApply:
    """Test mesh policies apply command"""

    def test_apply_policy_success_table_format(self, runner, mock_api_client):
        """Test applying a policy successfully in table format"""
        mock_response = {
            'id': 'policy-app-1',
            'policy_id': 'policy-1',
            'domain_id': 'domain-1',
            'status': 'APPLIED',
            'overrides': {},
            'applied_at': '2025-01-01T00:00:00Z',
            'applied_by': 'user-1'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'mesh', 'policies', 'apply', 'domain-1',
            '--policy', 'policy-1'
        ])

        assert result.exit_code == 0
        assert 'Policy applied successfully' in result.output
        assert 'policy-app-1' in result.output
        assert 'policy-1' in result.output
        assert 'domain-1' in result.output
        assert 'APPLIED' in result.output
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert call_args[0][0] == 'mesh/domains/domain-1/policies/apply/'
        json_data = call_args[1]['json_data']
        assert json_data['policy_id'] == 'policy-1'
        assert 'overrides' not in json_data

    def test_apply_policy_success_json_format(self, runner, mock_api_client):
        """Test applying a policy successfully in JSON format"""
        mock_response = {
            'id': 'policy-app-1',
            'policy_id': 'policy-1',
            'domain_id': 'domain-1',
            'status': 'APPLIED'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(cli, [
            'mesh', 'policies', 'apply', 'domain-1',
            '--policy', 'policy-1',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'policy-app-1'
        assert output_data['policy_id'] == 'policy-1'

    def test_apply_policy_with_overrides(self, runner, mock_api_client):
        """Test applying a policy with overrides"""
        mock_response = {
            'id': 'policy-app-1',
            'policy_id': 'policy-1',
            'domain_id': 'domain-1',
            'status': 'APPLIED',
            'overrides': {'priority': 50, 'effect': 'ALLOW'}
        }
        mock_api_client.post.return_value = mock_response

        overrides = '{"priority": 50, "effect": "ALLOW"}'
        result = runner.invoke(cli, [
            'mesh', 'policies', 'apply', 'domain-1',
            '--policy', 'policy-1',
            '--overrides', overrides
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.post.call_args
        json_data = call_args[1]['json_data']
        assert json_data['policy_id'] == 'policy-1'
        assert json_data['overrides'] == {'priority': 50, 'effect': 'ALLOW'}

    def test_apply_policy_missing_policy_id(self, runner):
        """Test applying a policy without required policy ID"""
        result = runner.invoke(cli, [
            'mesh', 'policies', 'apply', 'domain-1'
        ])

        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()

    def test_apply_policy_invalid_json_overrides(self, runner):
        """Test applying a policy with invalid JSON in overrides"""
        result = runner.invoke(cli, [
            'mesh', 'policies', 'apply', 'domain-1',
            '--policy', 'policy-1',
            '--overrides', 'invalid json'
        ])

        assert result.exit_code != 0
        assert 'Invalid JSON' in result.output

    def test_apply_policy_overrides_not_dict(self, runner):
        """Test applying a policy with overrides that is not a dict"""
        result = runner.invoke(cli, [
            'mesh', 'policies', 'apply', 'domain-1',
            '--policy', 'policy-1',
            '--overrides', '["not", "a", "dict"]'
        ])

        assert result.exit_code != 0
        assert 'must be a JSON object' in result.output

    def test_apply_policy_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.post.side_effect = Exception("API connection error")

        result = runner.invoke(cli, [
            'mesh', 'policies', 'apply', 'domain-1',
            '--policy', 'policy-1'
        ])

        assert result.exit_code != 0
        assert 'Failed to apply policy' in result.output


class TestMeshPoliciesList:
    """Test mesh policies list command"""

    def test_list_policies_success_table_format(self, runner, mock_api_client):
        """Test listing policies in table format"""
        mock_data = {
            'count': 2,
            'page': 1,
            'page_size': 20,
            'total_pages': 1,
            'results': [
                {
                    'id': 'policy-app-1',
                    'policy_id': 'policy-1',
                    'policy_name': 'Test Policy 1',
                    'domain_id': 'domain-1',
                    'status': 'APPLIED',
                    'applied_at': '2025-01-01T00:00:00Z',
                    'applied_by': 'user-1'
                },
                {
                    'id': 'policy-app-2',
                    'policy_id': 'policy-2',
                    'policy_name': 'Test Policy 2',
                    'domain_id': 'domain-1',
                    'status': 'PENDING',
                    'applied_at': '2025-01-01T01:00:00Z',
                    'applied_by': 'user-2'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['mesh', 'policies', 'list', 'domain-1'])

        assert result.exit_code == 0
        assert 'policy-1' in result.output
        assert 'policy-2' in result.output
        assert 'Test Policy 1' in result.output
        assert 'APPLIED' in result.output
        assert 'PENDING' in result.output
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args
        assert call_args[0][0] == 'mesh/domains/domain-1/policies/'
        assert call_args[1]['params']['page'] == 1
        assert call_args[1]['params']['page_size'] == 20

    def test_list_policies_success_json_format(self, runner, mock_api_client):
        """Test listing policies in JSON format"""
        mock_data = {
            'count': 1,
            'page': 1,
            'page_size': 20,
            'total_pages': 1,
            'results': [
                {
                    'id': 'policy-app-1',
                    'policy_id': 'policy-1',
                    'policy_name': 'Test Policy',
                    'status': 'APPLIED'
                }
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'mesh', 'policies', 'list', 'domain-1',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert 'count' in output_data
        assert 'results' in output_data
        assert len(output_data['results']) == 1
        assert output_data['results'][0]['policy_id'] == 'policy-1'

    def test_list_policies_with_filters(self, runner, mock_api_client):
        """Test listing policies with filters"""
        mock_data = {'count': 0, 'page': 1, 'page_size': 20, 'total_pages': 0, 'results': []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, [
            'mesh', 'policies', 'list', 'domain-1',
            '--status', 'APPLIED',
            '--page', '2',
            '--page-size', '50'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.get.call_args
        params = call_args[1]['params']
        assert params['status'] == 'APPLIED'
        assert params['page'] == 2
        assert params['page_size'] == 50

    def test_list_policies_empty_result(self, runner, mock_api_client):
        """Test listing policies with no results"""
        mock_data = {'count': 0, 'page': 1, 'page_size': 20, 'total_pages': 0, 'results': []}
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['mesh', 'policies', 'list', 'domain-1'])

        assert result.exit_code == 0
        assert 'No policies found' in result.output

    def test_list_policies_pagination_info(self, runner, mock_api_client):
        """Test pagination info display"""
        mock_data = {
            'count': 50,
            'page': 1,
            'page_size': 20,
            'total_pages': 3,
            'results': [
                {
                    'id': f'policy-app-{i}',
                    'policy_id': f'policy-{i}',
                    'policy_name': f'Policy {i}',
                    'status': 'APPLIED',
                    'applied_at': '2025-01-01T00:00:00Z',
                    'applied_by': 'user-1'
                } for i in range(20)
            ]
        }
        mock_api_client.get.return_value = mock_data

        result = runner.invoke(cli, ['mesh', 'policies', 'list', 'domain-1'])

        assert result.exit_code == 0
        assert 'Showing 20 of 50 policies' in result.output
        assert 'Page 1 of 3' in result.output
        assert 'Next page: --page 2' in result.output

    def test_list_policies_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.get.side_effect = Exception("API connection error")

        result = runner.invoke(cli, ['mesh', 'policies', 'list', 'domain-1'])

        assert result.exit_code != 0
        assert 'Failed to list policies' in result.output


class TestMeshPoliciesRemove:
    """Test mesh policies remove command"""

    def test_remove_policy_success_table_format(self, runner, mock_api_client):
        """Test removing a policy successfully in table format"""
        mock_response = {
            'id': 'policy-app-1',
            'policy_id': 'policy-1',
            'domain_id': 'domain-1',
            'status': 'REVOKED'
        }
        mock_api_client.delete.return_value = mock_response

        result = runner.invoke(cli, [
            'mesh', 'policies', 'remove', 'domain-1', 'policy-1'
        ])

        assert result.exit_code == 0
        assert 'Policy removed successfully' in result.output
        assert 'policy-app-1' in result.output
        assert 'policy-1' in result.output
        assert 'REVOKED' in result.output
        mock_api_client.delete.assert_called_once()
        call_args = mock_api_client.delete.call_args
        assert call_args[0][0] == 'mesh/domains/domain-1/policies/policy-1/'
        # Check if json_data was passed (should be None if no reason)
        assert call_args[1].get('json_data') is None

    def test_remove_policy_success_json_format(self, runner, mock_api_client):
        """Test removing a policy successfully in JSON format"""
        mock_response = {
            'id': 'policy-app-1',
            'policy_id': 'policy-1',
            'domain_id': 'domain-1',
            'status': 'REVOKED'
        }
        mock_api_client.delete.return_value = mock_response

        result = runner.invoke(cli, [
            'mesh', 'policies', 'remove', 'domain-1', 'policy-1',
            '--format', 'json'
        ])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data['id'] == 'policy-app-1'
        assert output_data['policy_id'] == 'policy-1'

    def test_remove_policy_with_reason(self, runner, mock_api_client):
        """Test removing a policy with a reason"""
        mock_response = {
            'id': 'policy-app-1',
            'policy_id': 'policy-1',
            'domain_id': 'domain-1',
            'status': 'REVOKED'
        }
        mock_api_client.delete.return_value = mock_response

        result = runner.invoke(cli, [
            'mesh', 'policies', 'remove', 'domain-1', 'policy-1',
            '--reason', 'Policy no longer needed'
        ])

        assert result.exit_code == 0
        call_args = mock_api_client.delete.call_args
        json_data = call_args[1].get('json_data')
        assert json_data is not None
        assert json_data['reason'] == 'Policy no longer needed'

    def test_remove_policy_missing_arguments(self, runner):
        """Test removing a policy without required arguments"""
        result = runner.invoke(cli, ['mesh', 'policies', 'remove', 'domain-1'])

        assert result.exit_code != 0
        assert 'Missing argument' in result.output or 'required' in result.output.lower()

    def test_remove_policy_api_error(self, runner, mock_api_client):
        """Test handling API errors"""
        mock_api_client.delete.side_effect = Exception("API connection error")

        result = runner.invoke(cli, [
            'mesh', 'policies', 'remove', 'domain-1', 'policy-1'
        ])

        assert result.exit_code != 0
        assert 'Failed to remove policy' in result.output

    def test_remove_policy_empty_response(self, runner, mock_api_client):
        """Test removing a policy with empty response"""
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, [
            'mesh', 'policies', 'remove', 'domain-1', 'policy-1'
        ])

        assert result.exit_code == 0
        assert 'Policy removed successfully' in result.output
        assert 'Policy policy-1 removed from domain domain-1' in result.output


class TestMeshPoliciesCommandStructure:
    """Test mesh policies command group structure"""

    def test_policies_command_group_exists(self, runner):
        """Test that policies command group exists"""
        result = runner.invoke(cli, ['mesh', 'policies', '--help'])
        assert result.exit_code == 0
        assert 'Policy management commands' in result.output

    def test_policies_apply_command_exists(self, runner):
        """Test that policies apply command exists"""
        result = runner.invoke(cli, ['mesh', 'policies', 'apply', '--help'])
        assert result.exit_code == 0

    def test_policies_list_command_exists(self, runner):
        """Test that policies list command exists"""
        result = runner.invoke(cli, ['mesh', 'policies', 'list', '--help'])
        assert result.exit_code == 0

    def test_policies_remove_command_exists(self, runner):
        """Test that policies remove command exists"""
        result = runner.invoke(cli, ['mesh', 'policies', 'remove', '--help'])
        assert result.exit_code == 0

