"""
Comprehensive E2E tests for Marketplace Connection Management Use Cases.

Tests complete workflows for marketplace connection management:
- Create connection
- List connections
- Get connection details
- Update connection
- Test connection
- Delete connection
"""
import json

import pytest

from datahub_cli.main import cli
from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = [pytest.mark.mvp, skip_if_mvp_mode]


@pytest.mark.e2e
class TestMarketplaceConnectionE2E:
    """
    E2E tests for marketplace connection management.

    Uses the shared ``authenticated_config`` fixture from conftest
    (persona-provisioned credentials) so these tests run under the
    same auth flow as every other use_cases test.
    """

    def test_complete_connection_lifecycle(
        self, runner, authenticated_config,
    ):
        """Test complete lifecycle: create -> list -> get ->
        update -> test -> delete"""
        # Step 1: Create connection
        connection_config = {
            'account': 'test_account',
            'user': 'test_user',
            'token': 'test_token',
            'warehouse': 'COMPUTE_WH',
            'role': 'ACCOUNTADMIN',
        }
        config_json = json.dumps(connection_config)

        result = runner.invoke(cli, [
            'marketplace', 'connections', 'create',
            '--marketplace-type', 'SNOWFLAKE_DATA_MARKETPLACE',
            '--name', 'E2E Test Snowflake Connection',
            '--config', config_json,
            '--format', 'json',
        ])
        assert result.exit_code == 0, (
            f"Create failed: {result.output}"
        )
        create_data = json.loads(result.output)
        connection_id = create_data['id']
        assert connection_id is not None
        assert (
            create_data['name']
            == 'E2E Test Snowflake Connection'
        )

        # Step 2: List connections
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'list',
            '--format', 'json',
        ])
        assert result.exit_code == 0, (
            f"List failed: {result.output}"
        )
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get('results', [])
        else:
            connections = list_data
        assert any(
            conn.get('id') == connection_id
            for conn in connections
        ), "Created connection not found in list"

        # Step 3: Get connection details
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'get',
            connection_id,
            '--format', 'json',
        ])
        assert result.exit_code == 0, (
            f"Get failed: {result.output}"
        )
        get_data = json.loads(result.output)
        assert get_data['id'] == connection_id
        assert (
            get_data['name']
            == 'E2E Test Snowflake Connection'
        )

        # Step 4: Update connection
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'update',
            connection_id,
            '--name', 'E2E Updated Snowflake Connection',
            '--no-is-active',
            '--format', 'json',
        ])
        assert result.exit_code == 0, (
            f"Update failed: {result.output}"
        )
        update_data = json.loads(result.output)
        assert (
            update_data['name']
            == 'E2E Updated Snowflake Connection'
        )
        assert update_data['is_active'] is False

        # Step 5: Test connection
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'test',
            connection_id,
            '--format', 'json',
        ])
        assert result.exit_code == 0, (
            f"Test failed: {result.output}"
        )
        test_data = json.loads(result.output)
        assert 'success' in test_data
        assert 'message' in test_data

        # Step 6: Delete connection
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'delete',
            connection_id,
        ])
        assert result.exit_code == 0, (
            f"Delete failed: {result.output}"
        )
        assert 'deleted successfully' in result.output.lower()

        # Verify deletion
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'get',
            connection_id,
        ])
        assert result.exit_code != 0, (
            "Connection should not exist after deletion"
        )

    def test_create_multiple_connections(
        self, runner, authenticated_config,
    ):
        """Test creating multiple connections with different
        marketplace types"""
        marketplace_configs = [
            (
                'SNOWFLAKE_DATA_MARKETPLACE',
                {
                    'account': 'test',
                    'user': 'test',
                    'token': 'test',
                },
            ),
            (
                'AWS_DATA_EXCHANGE',
                {'api_key': 'test', 'region': 'us-east-1'},
            ),
            (
                'CKAN_INSTANCE',
                {
                    'url': 'https://example.com',
                    'api_key': 'test',
                },
            ),
        ]

        connection_ids = []
        for mkt_type, config_data in marketplace_configs:
            config_json = json.dumps(config_data)
            result = runner.invoke(cli, [
                'marketplace', 'connections', 'create',
                '--marketplace-type', mkt_type,
                '--name', f'E2E Test {mkt_type} Connection',
                '--config', config_json,
                '--format', 'json',
            ])
            assert result.exit_code == 0, (
                f"Failed to create {mkt_type}: {result.output}"
            )
            cid = json.loads(result.output)['id']
            connection_ids.append(cid)

        # List all connections
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'list',
            '--format', 'json',
        ])
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get('results', [])
        else:
            connections = list_data

        for conn_id in connection_ids:
            assert any(
                conn.get('id') == conn_id
                for conn in connections
            ), f"Connection {conn_id} not found in list"

        # Clean up
        for conn_id in connection_ids:
            runner.invoke(cli, [
                'marketplace', 'connections', 'delete',
                conn_id,
            ])

    def test_connection_filtering(
        self, runner, authenticated_config,
    ):
        """Test filtering connections by marketplace type and
        active status"""
        connections_to_create = [
            (
                'SNOWFLAKE_DATA_MARKETPLACE',
                True,
                {
                    'account': 'test',
                    'user': 'test',
                    'token': 'test',
                },
            ),
            (
                'SNOWFLAKE_DATA_MARKETPLACE',
                False,
                {
                    'account': 'test2',
                    'user': 'test2',
                    'token': 'test2',
                },
            ),
            (
                'AWS_DATA_EXCHANGE',
                True,
                {'api_key': 'test', 'region': 'us-east-1'},
            ),
        ]

        connection_ids = []
        for mkt_type, is_active, config_data in connections_to_create:
            config_json = json.dumps(config_data)
            flag = '--is-active' if is_active else '--no-is-active'
            result = runner.invoke(cli, [
                'marketplace', 'connections', 'create',
                '--marketplace-type', mkt_type,
                '--name',
                f'E2E Filter Test {mkt_type} {is_active}',
                '--config', config_json,
                flag,
                '--format', 'json',
            ])
            assert result.exit_code == 0
            cid = json.loads(result.output)['id']
            connection_ids.append(cid)

        # Filter by marketplace type
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'list',
            '--marketplace-type',
            'SNOWFLAKE_DATA_MARKETPLACE',
            '--format', 'json',
        ])
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get('results', [])
        else:
            connections = list_data
        for conn in connections:
            assert (
                conn['marketplace_type']
                == 'SNOWFLAKE_DATA_MARKETPLACE'
            )

        # Filter by active status
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'list',
            '--is-active', 'true',
            '--format', 'json',
        ])
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get('results', [])
        else:
            connections = list_data
        for conn in connections:
            assert conn['is_active'] is True

        # Clean up
        for conn_id in connection_ids:
            runner.invoke(cli, [
                'marketplace', 'connections', 'delete',
                conn_id,
            ])
