"""
Unit tests for marketplace command parsing and output formatting.

These tests verify CLI command parsing, argument handling, and output formatting.
For integration tests with real API services, see test_commands_real_api.py
"""
import pytest
import json
import tempfile
import os
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from datahub_cli.commands import marketplace
from datahub_cli.marketplace_errors import (
    MarketplaceCLIError,
    MarketplaceValidationError,
    MarketplaceConnectionError,
)


class TestMarketplaceCommands:
    """Unit tests for marketplace command parsing and formatting"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_marketplace_help(self, runner):
        """Test marketplace command help"""
        result = runner.invoke(marketplace.marketplace, ['--help'])
        assert result.exit_code == 0
        assert 'Marketplace integration commands' in result.output

    def test_marketplace_connections_help(self, runner):
        """Test marketplace connections command help"""
        result = runner.invoke(marketplace.connections, ['--help'])
        assert result.exit_code == 0
        assert 'Marketplace connection management commands' in result.output

    def test_connections_create_help(self, runner):
        """Test connections create command help"""
        result = runner.invoke(marketplace.connections, ['create', '--help'])
        assert result.exit_code == 0
        assert 'Create a new marketplace connection' in result.output

    def test_connections_list_help(self, runner):
        """Test connections list command help"""
        result = runner.invoke(marketplace.connections, ['list', '--help'])
        assert result.exit_code == 0
        assert 'List marketplace connections' in result.output

    def test_connections_get_help(self, runner):
        """Test connections get command help"""
        result = runner.invoke(marketplace.connections, ['get', '--help'])
        assert result.exit_code == 0
        assert 'Get marketplace connection details' in result.output

    def test_connections_update_help(self, runner):
        """Test connections update command help"""
        result = runner.invoke(marketplace.connections, ['update', '--help'])
        assert result.exit_code == 0
        assert 'Update a marketplace connection' in result.output

    def test_connections_delete_help(self, runner):
        """Test connections delete command help"""
        result = runner.invoke(marketplace.connections, ['delete', '--help'])
        assert result.exit_code == 0
        assert 'Delete a marketplace connection' in result.output

    def test_connections_test_help(self, runner):
        """Test connections test command help"""
        result = runner.invoke(marketplace.connections, ['test', '--help'])
        assert result.exit_code == 0
        assert 'Test a marketplace connection' in result.output

    def test_connections_create_missing_required(self, runner):
        """Test connections create with missing required arguments"""
        result = runner.invoke(marketplace.connections, ['create'])
        assert result.exit_code != 0  # Should fail without required args

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_create_success(self, mock_api_client, runner):
        """Test connections create success"""
        mock_response = {
            'id': '550e8400-e29b-41d4-a716-446655440000',
            'name': 'Test Connection',
            'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE',
            'is_active': True,
            'created_at': '2026-01-10T10:00:00Z'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(marketplace.connections, [
            'create',
            '--marketplace-type', 'SNOWFLAKE_DATA_MARKETPLACE',
            '--name', 'Test Connection',
            '--config', '{"api_key": "test"}'
        ])
        assert result.exit_code == 0
        assert 'Connection created successfully!' in result.output
        assert '550e8400-e29b-41d4-a716-446655440000' in result.output
        mock_api_client.post.assert_called_once()

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_create_json_output(self, mock_api_client, runner):
        """Test connections create with JSON output"""
        mock_response = {
            'id': '550e8400-e29b-41d4-a716-446655440000',
            'name': 'Test Connection',
            'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE',
            'is_active': True
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(marketplace.connections, [
            'create',
            '--marketplace-type', 'SNOWFLAKE_DATA_MARKETPLACE',
            '--name', 'Test Connection',
            '--config', '{"api_key": "test"}',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        output_json = json.loads(result.output)
        assert output_json['id'] == '550e8400-e29b-41d4-a716-446655440000'

    def test_connections_create_invalid_marketplace_type(self, runner):
        """Test connections create with invalid marketplace type"""
        result = runner.invoke(marketplace.connections, [
            'create',
            '--marketplace-type', 'INVALID_TYPE',
            '--name', 'Test Connection',
            '--config', '{"api_key": "test"}'
        ])
        assert result.exit_code != 0

    def test_connections_create_config_from_file(self, runner):
        """Test connections create with config from file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {'api_key': 'test_key', 'endpoint': 'https://example.com'}
            json.dump(config_data, f)
            config_file = f.name

        try:
            with patch('datahub_cli.commands.marketplace.api_client') as mock_api_client:
                mock_response = {
                    'id': '550e8400-e29b-41d4-a716-446655440000',
                    'name': 'Test Connection',
                    'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE',
                    'is_active': True
                }
                mock_api_client.post.return_value = mock_response

                result = runner.invoke(marketplace.connections, [
                    'create',
                    '--marketplace-type', 'SNOWFLAKE_DATA_MARKETPLACE',
                    '--name', 'Test Connection',
                    '--config', config_file
                ])
                assert result.exit_code == 0
                # Verify config was parsed correctly
                call_args = mock_api_client.post.call_args
                assert call_args[1]['json_data']['config'] == config_data
        finally:
            os.unlink(config_file)

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_list_success(self, mock_api_client, runner):
        """Test connections list success"""
        mock_response = {
            'count': 2,
            'results': [
                {
                    'id': '550e8400-e29b-41d4-a716-446655440000',
                    'name': 'Connection 1',
                    'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE',
                    'is_active': True,
                    'created_at': '2026-01-10T10:00:00Z'
                },
                {
                    'id': '660e8400-e29b-41d4-a716-446655440001',
                    'name': 'Connection 2',
                    'marketplace_type': 'AWS_DATA_EXCHANGE',
                    'is_active': False,
                    'created_at': '2026-01-10T11:00:00Z'
                }
            ]
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connections, ['list'])
        assert result.exit_code == 0
        assert 'Connection 1' in result.output
        assert 'Connection 2' in result.output
        mock_api_client.get.assert_called_once()

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_list_empty(self, mock_api_client, runner):
        """Test connections list with no results"""
        mock_response = {'count': 0, 'results': []}
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connections, ['list'])
        assert result.exit_code == 0
        assert 'No connections found' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_get_success(self, mock_api_client, runner):
        """Test connections get success"""
        connection_id = '550e8400-e29b-41d4-a716-446655440000'
        mock_response = {
            'id': connection_id,
            'name': 'Test Connection',
            'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE',
            'is_active': True,
            'created_at': '2026-01-10T10:00:00Z',
            'updated_at': '2026-01-10T10:00:00Z'
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connections, ['get', connection_id])
        assert result.exit_code == 0
        assert connection_id in result.output
        assert 'Test Connection' in result.output
        # Check that get was called with the correct endpoint (params may or may not be passed)
        call_args = mock_api_client.get.call_args
        assert call_args[0][0] == f'integrations/marketplace/connections/{connection_id}/'

    def test_connections_get_invalid_id(self, runner):
        """Test connections get with invalid ID"""
        result = runner.invoke(marketplace.connections, ['get', 'invalid-id'])
        assert result.exit_code != 0

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_update_success(self, mock_api_client, runner):
        """Test connections update success"""
        connection_id = '550e8400-e29b-41d4-a716-446655440000'
        mock_response = {
            'id': connection_id,
            'name': 'Updated Connection',
            'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE',
            'is_active': False,
            'updated_at': '2026-01-10T11:00:00Z'
        }
        mock_api_client.patch.return_value = mock_response

        result = runner.invoke(marketplace.connections, [
            'update', connection_id,
            '--name', 'Updated Connection',
            '--no-is-active'
        ])
        assert result.exit_code == 0
        assert 'Connection updated successfully!' in result.output
        assert 'Updated Connection' in result.output
        mock_api_client.patch.assert_called_once()

    def test_connections_update_no_fields(self, runner):
        """Test connections update with no fields"""
        connection_id = '550e8400-e29b-41d4-a716-446655440000'
        result = runner.invoke(marketplace.connections, [
            'update', connection_id
        ])
        assert result.exit_code != 0

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_delete_success(self, mock_api_client, runner):
        """Test connections delete success"""
        connection_id = '550e8400-e29b-41d4-a716-446655440000'
        mock_api_client.delete.return_value = {}

        result = runner.invoke(marketplace.connections, [
            'delete', connection_id
        ])
        assert result.exit_code == 0
        assert 'Connection deleted successfully!' in result.output
        # Check that delete was called with the correct endpoint (json_data may or may not be passed)
        call_args = mock_api_client.delete.call_args
        assert call_args[0][0] == f'integrations/marketplace/connections/{connection_id}/'

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_test_success(self, mock_api_client, runner):
        """Test connections test success"""
        connection_id = '550e8400-e29b-41d4-a716-446655440000'
        mock_response = {
            'success': True,
            'message': 'Connection test successful',
            'tested_at': '2026-01-10T10:00:00Z',
            'details': {
                'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE',
                'response_time_ms': 245
            }
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(marketplace.connections, [
            'test', connection_id
        ])
        assert result.exit_code == 0
        assert 'Connection test successful!' in result.output
        assert '245' in result.output  # response_time_ms
        mock_api_client.post.assert_called_once()

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connections_test_failure(self, mock_api_client, runner):
        """Test connections test failure"""
        connection_id = '550e8400-e29b-41d4-a716-446655440000'
        mock_response = {
            'success': False,
            'message': 'Connection test failed: Invalid credentials',
            'tested_at': '2026-01-10T10:00:00Z',
            'error': 'Authentication failed'
        }
        mock_api_client.post.return_value = mock_response

        result = runner.invoke(marketplace.connections, [
            'test', connection_id
        ])
        assert result.exit_code == 0
        assert 'Connection test failed!' in result.output
        assert 'Invalid credentials' in result.output

    # Mapping commands tests
    def test_marketplace_mappings_help(self, runner):
        """Test marketplace mappings command help"""
        result = runner.invoke(marketplace.marketplace, ['mappings', '--help'])
        assert result.exit_code == 0
        assert 'Marketplace mapping management commands' in result.output

    def test_mappings_list_help(self, runner):
        """Test mappings list command help"""
        result = runner.invoke(marketplace.marketplace, ['mappings', 'list', '--help'])
        assert result.exit_code == 0
        assert 'List marketplace mappings' in result.output

    def test_mappings_get_help(self, runner):
        """Test mappings get command help"""
        result = runner.invoke(marketplace.marketplace, ['mappings', 'get', '--help'])
        assert result.exit_code == 0
        assert 'Get marketplace mapping details' in result.output

    def test_mappings_delete_help(self, runner):
        """Test mappings delete command help"""
        result = runner.invoke(marketplace.marketplace, ['mappings', 'delete', '--help'])
        assert result.exit_code == 0
        assert 'Delete a marketplace mapping' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_mappings_list_success(self, mock_api_client, runner):
        """Test mappings list success"""
        mock_response = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [
                {
                    'id': '770e8400-e29b-41d4-a716-446655440000',
                    'connection': {
                        'id': '550e8400-e29b-41d4-a716-446655440000',
                        'name': 'Snowflake Production',
                        'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE'
                    },
                    'hub_asset': {
                        'id': '880e8400-e29b-41d4-a716-446655440000',
                        'name': 'Sample Dataset',
                        'status': 'ACTIVE'
                    },
                    'external_listing_id': 'SNOWFLAKE_SAMPLE_DATA',
                    'external_resource_ids': ['SNOWFLAKE_SAMPLE_DATA.SCHEMA.TABLE1'],
                    'sync_metadata': {
                        'last_sync_status': 'SUCCESS',
                        'last_sync_errors': []
                    },
                    'last_synced_at': '2026-01-10T10:00:00Z',
                    'created_at': '2026-01-10T10:00:00Z',
                    'updated_at': '2026-01-10T10:00:00Z'
                },
                {
                    'id': '770e8400-e29b-41d4-a716-446655440001',
                    'connection': {
                        'id': '550e8400-e29b-41d4-a716-446655440001',
                        'name': 'AWS Production',
                        'marketplace_type': 'AWS_DATA_EXCHANGE'
                    },
                    'hub_asset': {
                        'id': '880e8400-e29b-41d4-a716-446655440001',
                        'name': 'Another Dataset',
                        'status': 'ACTIVE'
                    },
                    'external_listing_id': 'AWS_SAMPLE_DATA',
                    'external_resource_ids': [],
                    'sync_metadata': {
                        'last_sync_status': 'SUCCESS',
                        'last_sync_errors': []
                    },
                    'last_synced_at': '2026-01-10T11:00:00Z',
                    'created_at': '2026-01-10T11:00:00Z',
                    'updated_at': '2026-01-10T11:00:00Z'
                }
            ]
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.marketplace, ['mappings', 'list'])
        assert result.exit_code == 0
        assert 'Sample Dataset' in result.output
        assert 'Another Dataset' in result.output
        mock_api_client.get.assert_called_once()

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_mappings_list_empty(self, mock_api_client, runner):
        """Test mappings list with no results"""
        mock_response = {'count': 0, 'results': []}
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.marketplace, ['mappings', 'list'])
        assert result.exit_code == 0
        assert 'No mappings found' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_mappings_list_with_filters(self, mock_api_client, runner):
        """Test mappings list with filters"""
        connection_id = '550e8400-e29b-41d4-a716-446655440000'
        asset_id = '880e8400-e29b-41d4-a716-446655440000'
        mock_response = {'count': 1, 'results': []}
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'list',
            '--connection-id', connection_id,
            '--asset-id', asset_id,
            '--limit', '10',
            '--offset', '0'
        ])
        assert result.exit_code == 0
        # Verify filters were passed
        call_args = mock_api_client.get.call_args
        assert call_args[1]['params']['connection_id'] == connection_id
        assert call_args[1]['params']['hub_asset_id'] == asset_id
        # Implementation converts limit/offset to page_size/page for API
        assert call_args[1]['params']['page_size'] == 10
        assert call_args[1]['params']['page'] == 1  # offset 0 with limit 10 = page 1

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_mappings_list_json_output(self, mock_api_client, runner):
        """Test mappings list with JSON output"""
        mock_response = {
            'count': 1,
            'results': [{
                'id': '770e8400-e29b-41d4-a716-446655440000',
                'connection': {'id': '550e8400-e29b-41d4-a716-446655440000', 'name': 'Test'},
                'hub_asset': {'id': '880e8400-e29b-41d4-a716-446655440000', 'name': 'Test Asset'},
                'external_listing_id': 'TEST_LISTING'
            }]
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'list',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        output_json = json.loads(result.output)
        assert isinstance(output_json, list)
        assert len(output_json) == 1
        assert output_json[0]['id'] == '770e8400-e29b-41d4-a716-446655440000'

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_mappings_get_success(self, mock_api_client, runner):
        """Test mappings get success"""
        mapping_id = '770e8400-e29b-41d4-a716-446655440000'
        mock_response = {
            'id': mapping_id,
            'connection': {
                'id': '550e8400-e29b-41d4-a716-446655440000',
                'name': 'Snowflake Production',
                'marketplace_type': 'SNOWFLAKE_DATA_MARKETPLACE'
            },
            'hub_asset': {
                'id': '880e8400-e29b-41d4-a716-446655440000',
                'name': 'Sample Dataset',
                'status': 'ACTIVE'
            },
            'external_listing_id': 'SNOWFLAKE_SAMPLE_DATA',
            'external_resource_ids': ['SNOWFLAKE_SAMPLE_DATA.SCHEMA.TABLE1'],
            'sync_metadata': {
                'last_sync_status': 'SUCCESS',
                'last_sync_errors': []
            },
            'last_synced_at': '2026-01-10T10:00:00Z',
            'created_at': '2026-01-10T10:00:00Z',
            'updated_at': '2026-01-10T10:00:00Z'
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.marketplace, ['mappings', 'get', mapping_id])
        assert result.exit_code == 0
        assert mapping_id in result.output
        assert 'Sample Dataset' in result.output
        assert 'SNOWFLAKE_SAMPLE_DATA' in result.output
        call_args = mock_api_client.get.call_args
        assert call_args[0][0] == f'integrations/marketplace/mappings/{mapping_id}/'

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_mappings_get_json_output(self, mock_api_client, runner):
        """Test mappings get with JSON output"""
        mapping_id = '770e8400-e29b-41d4-a716-446655440000'
        mock_response = {
            'id': mapping_id,
            'connection': {'id': '550e8400-e29b-41d4-a716-446655440000', 'name': 'Test'},
            'hub_asset': {'id': '880e8400-e29b-41d4-a716-446655440000', 'name': 'Test Asset'},
            'external_listing_id': 'TEST_LISTING'
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'get', mapping_id,
            '--format', 'json'
        ])
        assert result.exit_code == 0
        output_json = json.loads(result.output)
        assert output_json['id'] == mapping_id

    def test_mappings_get_invalid_id(self, runner):
        """Test mappings get with invalid ID"""
        result = runner.invoke(marketplace.marketplace, ['mappings', 'get', 'invalid-id'])
        assert result.exit_code != 0

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_mappings_delete_success(self, mock_api_client, runner):
        """Test mappings delete success"""
        mapping_id = '770e8400-e29b-41d4-a716-446655440000'
        mock_api_client.delete.return_value = {}

        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'delete', mapping_id
        ])
        assert result.exit_code == 0
        assert 'Mapping deleted successfully' in result.output
        call_args = mock_api_client.delete.call_args
        assert call_args[0][0] == f'integrations/marketplace/mappings/{mapping_id}/'

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_mappings_delete_json_output(self, mock_api_client, runner):
        """Test mappings delete with JSON output"""
        mapping_id = '770e8400-e29b-41d4-a716-446655440000'
        mock_api_client.delete.return_value = {}

        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'delete', mapping_id,
            '--format', 'json'
        ])
        assert result.exit_code == 0
        output_json = json.loads(result.output)
        assert output_json['success'] is True
        assert 'deleted successfully' in output_json['message'].lower()

    def test_mappings_delete_invalid_id(self, runner):
        """Test mappings delete with invalid ID"""
        result = runner.invoke(marketplace.marketplace, ['mappings', 'delete', 'invalid-id'])
        assert result.exit_code != 0

    def test_mappings_list_invalid_connection_id(self, runner):
        """Test mappings list with invalid connection ID"""
        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'list',
            '--connection-id', 'invalid-id'
        ])
        assert result.exit_code != 0

    def test_mappings_list_invalid_asset_id(self, runner):
        """Test mappings list with invalid asset ID"""
        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'list',
            '--asset-id', 'invalid-id'
        ])
        assert result.exit_code != 0

    def test_mappings_list_invalid_limit(self, runner):
        """Test mappings list with invalid limit"""
        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'list',
            '--limit', '0'
        ])
        assert result.exit_code != 0

    def test_mappings_list_invalid_offset(self, runner):
        """Test mappings list with invalid offset"""
        result = runner.invoke(marketplace.marketplace, [
            'mappings', 'list',
            '--offset', '-1'
        ])
        assert result.exit_code != 0

    # ===== Connector Commands Tests =====

    def test_connectors_help(self, runner):
        """Test connectors command help"""
        result = runner.invoke(marketplace.connectors, ['--help'])
        assert result.exit_code == 0
        assert 'Marketplace connector management commands' in result.output

    def test_connectors_list_help(self, runner):
        """Test connectors list command help"""
        result = runner.invoke(marketplace.connectors, ['list', '--help'])
        assert result.exit_code == 0
        assert 'List available marketplace connector types' in result.output

    def test_connectors_info_help(self, runner):
        """Test connectors info command help"""
        result = runner.invoke(marketplace.connectors, ['info', '--help'])
        assert result.exit_code == 0
        assert 'Get detailed information about a marketplace connector type' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_list_success_table(self, mock_api_client, runner):
        """Test connectors list success with table format"""
        mock_response = {
            'connectors': [
                {
                    'type': 'SNOWFLAKE_DATA_MARKETPLACE',
                    'display_name': 'Snowflake Data Marketplace',
                    'supported_sync_directions': ['PULL'],
                    'status': 'available',
                    'description': 'Connector for Snowflake Data Marketplace'
                },
                {
                    'type': 'AWS_DATA_EXCHANGE',
                    'display_name': 'Aws Data Exchange',
                    'supported_sync_directions': ['PULL', 'PUSH'],
                    'status': 'available',
                    'description': 'Connector for AWS Data Exchange'
                }
            ]
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connectors, ['list'])
        assert result.exit_code == 0
        assert 'SNOWFLAKE_DATA_MARKETPLACE' in result.output
        assert 'AWS_DATA_EXCHANGE' in result.output
        assert 'PULL' in result.output
        assert 'available' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_list_success_json(self, mock_api_client, runner):
        """Test connectors list success with JSON format"""
        mock_response = {
            'connectors': [
                {
                    'type': 'SNOWFLAKE_DATA_MARKETPLACE',
                    'display_name': 'Snowflake Data Marketplace',
                    'supported_sync_directions': ['PULL'],
                    'status': 'available',
                    'description': 'Connector for Snowflake Data Marketplace'
                }
            ]
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connectors, ['list', '--format', 'json'])
        assert result.exit_code == 0
        output_json = json.loads(result.output)
        # JSON output is just the connectors array (consistent with other list commands)
        assert isinstance(output_json, list)
        assert len(output_json) == 1
        assert output_json[0]['type'] == 'SNOWFLAKE_DATA_MARKETPLACE'

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_list_empty(self, mock_api_client, runner):
        """Test connectors list with empty result"""
        mock_response = {'connectors': []}
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connectors, ['list'])
        assert result.exit_code == 0
        assert 'No connectors found' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_list_api_error(self, mock_api_client, runner):
        """Test connectors list with API error"""
        mock_api_client.get.side_effect = Exception("API connection failed")

        result = runner.invoke(marketplace.connectors, ['list'])
        assert result.exit_code != 0
        assert 'Failed to list connectors' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_info_success_table(self, mock_api_client, runner):
        """Test connectors info success with table format"""
        mock_response = {
            'type': 'SNOWFLAKE_DATA_MARKETPLACE',
            'display_name': 'Snowflake Data Marketplace',
            'supported_sync_directions': ['PULL'],
            'status': 'available',
            'description': 'Connector for Snowflake Data Marketplace',
            'capabilities': {
                'discovery': True,
                'harvest': True,
                'push': False,
                'pull': True,
                'bidirectional': False
            },
            'configuration_requirements': {
                'required': ['account', 'user', 'token'],
                'optional': ['warehouse', 'role', 'database']
            }
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connectors, ['info', 'SNOWFLAKE_DATA_MARKETPLACE'])
        assert result.exit_code == 0
        assert 'SNOWFLAKE_DATA_MARKETPLACE' in result.output
        assert 'Snowflake Data Marketplace' in result.output
        assert 'available' in result.output
        assert 'PULL' in result.output
        assert 'Capabilities:' in result.output
        assert 'Configuration Requirements:' in result.output
        assert 'account' in result.output
        assert 'warehouse' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_info_success_json(self, mock_api_client, runner):
        """Test connectors info success with JSON format"""
        mock_response = {
            'type': 'SNOWFLAKE_DATA_MARKETPLACE',
            'display_name': 'Snowflake Data Marketplace',
            'supported_sync_directions': ['PULL'],
            'status': 'available',
            'description': 'Connector for Snowflake Data Marketplace',
            'capabilities': {
                'discovery': True,
                'harvest': True,
                'push': False,
                'pull': True
            },
            'configuration_requirements': {
                'required': ['account', 'user', 'token'],
                'optional': ['warehouse']
            }
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connectors, ['info', 'SNOWFLAKE_DATA_MARKETPLACE', '--format', 'json'])
        assert result.exit_code == 0
        output_json = json.loads(result.output)
        assert output_json['type'] == 'SNOWFLAKE_DATA_MARKETPLACE'
        assert output_json['status'] == 'available'
        assert 'capabilities' in output_json
        assert 'configuration_requirements' in output_json

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_info_invalid_type(self, mock_api_client, runner):
        """Test connectors info with invalid connector type"""
        result = runner.invoke(marketplace.connectors, ['info', 'INVALID_TYPE'])
        assert result.exit_code != 0
        assert 'Invalid marketplace type' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_info_not_found(self, mock_api_client, runner):
        """Test connectors info with connector type not found"""
        # Use a valid marketplace type format but one that doesn't exist
        # The validation will pass, but API will return 404
        from click import ClickException
        mock_api_client.get.side_effect = ClickException("API error (404): Connector not found")

        result = runner.invoke(marketplace.connectors, ['info', 'SNOWFLAKE_DATA_MARKETPLACE'])
        # This will fail at API call, not validation
        assert result.exit_code != 0
        # Check for either "not found" or "404" in error message
        assert 'not found' in result.output.lower() or '404' in result.output.lower() or 'failed' in result.output.lower()

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_info_api_error(self, mock_api_client, runner):
        """Test connectors info with API error"""
        mock_api_client.get.side_effect = Exception("API connection failed")

        result = runner.invoke(marketplace.connectors, ['info', 'SNOWFLAKE_DATA_MARKETPLACE'])
        assert result.exit_code != 0
        assert 'Failed to get connector information' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_info_case_insensitive(self, mock_api_client, runner):
        """Test connectors info with case-insensitive connector type"""
        mock_response = {
            'type': 'SNOWFLAKE_DATA_MARKETPLACE',
            'display_name': 'Snowflake Data Marketplace',
            'supported_sync_directions': ['PULL'],
            'status': 'available',
            'description': 'Connector for Snowflake Data Marketplace',
            'capabilities': {},
            'configuration_requirements': {}
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connectors, ['info', 'snowflake_data_marketplace'])
        assert result.exit_code == 0
        assert 'SNOWFLAKE_DATA_MARKETPLACE' in result.output

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_info_with_all_capabilities(self, mock_api_client, runner):
        """Test connectors info with all capabilities enabled"""
        mock_response = {
            'type': 'AWS_DATA_EXCHANGE',
            'display_name': 'Aws Data Exchange',
            'supported_sync_directions': ['PULL', 'PUSH', 'BIDIRECTIONAL'],
            'status': 'available',
            'description': 'Connector for AWS Data Exchange',
            'capabilities': {
                'discovery': True,
                'harvest': True,
                'push': True,
                'pull': True,
                'bidirectional': True
            },
            'configuration_requirements': {
                'required': ['aws_access_key_id', 'aws_secret_access_key'],
                'optional': ['aws_session_token', 'region_name']
            }
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connectors, ['info', 'AWS_DATA_EXCHANGE'])
        assert result.exit_code == 0
        assert 'PULL' in result.output
        assert 'PUSH' in result.output
        assert 'BIDIRECTIONAL' in result.output
        assert '✓' in result.output  # Capability enabled indicator

    @patch('datahub_cli.commands.marketplace.api_client')
    def test_connectors_info_with_no_config_requirements(self, mock_api_client, runner):
        """Test connectors info with no configuration requirements"""
        mock_response = {
            'type': 'CKAN_INSTANCE',
            'display_name': 'Ckan Instance',
            'supported_sync_directions': ['PULL'],
            'status': 'available',
            'description': 'Connector for CKAN instances',
            'capabilities': {
                'discovery': True,
                'harvest': True,
                'push': False,
                'pull': True
            },
            'configuration_requirements': {
                'required': [],
                'optional': []
            }
        }
        mock_api_client.get.return_value = mock_response

        result = runner.invoke(marketplace.connectors, ['info', 'CKAN_INSTANCE'])
        assert result.exit_code == 0
        assert 'CKAN_INSTANCE' in result.output
