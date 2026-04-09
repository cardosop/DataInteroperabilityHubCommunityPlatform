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
import pytest
import json
import os
import requests
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import Config
from datahub_cli.auth import AuthManager


def setup_authentication_for_e2e(api_base_url: str, config: Config) -> bool:
    """
    Set up authentication for E2E tests.

    Tries multiple methods:
    1. Use TEST_API_KEY environment variable if available
    2. Use TEST_USER_EMAIL and TEST_USER_PASSWORD to login and create API key
    3. Try to register a test user and create API key

    Args:
        api_base_url: API base URL
        config: Config instance to set authentication

    Returns:
        True if authentication was set up successfully, False otherwise
    """
    # Method 1: Use API key from environment variable
    api_key = os.getenv("TEST_API_KEY")
    if api_key:
        config.set_api_key(api_key)
        # Verify it works
        try:
            response = requests.get(
                f"{api_base_url}/integrations/marketplace/connections/",
                headers={"Authorization": f"ApiKey {api_key}"},
                timeout=5
            )
            if response.status_code in [200, 401]:  # 401 is OK, means auth is working
                return True
        except Exception:
            pass

    # Method 2: Use credentials from environment to login and create API key
    email = os.getenv("TEST_USER_EMAIL", "e2e-marketplace-test@example.com")
    password = os.getenv("TEST_USER_PASSWORD", "TestPass123!")

    try:
        # Try to login first
        login_response = requests.post(
            f"{api_base_url}/auth/login/",
            json={"email": email, "password": password},
            timeout=5
        )

        access_token = None
        if login_response.status_code == 200:
            login_data = login_response.json()
            access_token = login_data.get("access_token")
        elif login_response.status_code in [401, 404]:
            # User doesn't exist, try to register
            register_response = requests.post(
                f"{api_base_url}/auth/register/",
                json={
                    "email": email,
                    "password": password,
                    "name": "E2E Marketplace Test User"
                },
                timeout=5
            )

            if register_response.status_code == 201:
                # Registration successful, try to login now
                login_response = requests.post(
                    f"{api_base_url}/auth/login/",
                    json={"email": email, "password": password},
                    timeout=5
                )

                if login_response.status_code == 200:
                    login_data = login_response.json()
                    access_token = login_data.get("access_token")

        if access_token:
            # Try to create API key
            api_key_response = requests.post(
                f"{api_base_url}/auth/api-keys/",
                json={"name": "E2E Marketplace Test API Key"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5
            )

            if api_key_response.status_code == 201:
                api_key_data = api_key_response.json()
                api_key = api_key_data.get("key")
                if api_key:
                    config.set_api_key(api_key)
                    return True

    except Exception:
        pass

    return False


@pytest.mark.e2e
class TestMarketplaceConnectionE2E:
    """
    E2E tests for marketplace connection management.

    These tests require a running API server. Set TEST_API_BASE_URL environment
    variable or use default http://localhost:8000.
    """

    @pytest.fixture(scope="class")
    def api_base_url(self):
        """Get API base URL from environment or use default"""
        return os.getenv("TEST_API_BASE_URL", "http://localhost:8000/api/v1")

    @pytest.fixture(scope="class")
    def config(self):
        """Get config instance"""
        return Config()

    @pytest.fixture(scope="class")
    def runner(self):
        """Get CLI runner"""
        return CliRunner()

    @pytest.fixture(scope="class", autouse=True)
    def setup_auth(self, api_base_url, config):
        """Set up authentication before tests"""
        # Set API base URL
        config.set_api_base_url(api_base_url)

        # Set up authentication
        authenticated = setup_authentication_for_e2e(api_base_url, config)
        if not authenticated:
            pytest.skip("Could not set up authentication for E2E tests. "
                       "Set TEST_API_KEY or TEST_USER_EMAIL/TEST_USER_PASSWORD environment variables.")

        yield

        # Cleanup
        config.clear_auth()

    def test_complete_connection_lifecycle(self, runner, api_base_url):
        """Test complete connection lifecycle: create → list → get → update → test → delete"""
        # Step 1: Create connection
        connection_config = {
            'account': 'test_account',
            'user': 'test_user',
            'token': 'test_token',
            'warehouse': 'COMPUTE_WH',
            'role': 'ACCOUNTADMIN'
        }
        config_json = json.dumps(connection_config)

        result = runner.invoke(cli, [
            'marketplace', 'connections', 'create',
            '--marketplace-type', 'SNOWFLAKE_DATA_MARKETPLACE',
            '--name', 'E2E Test Snowflake Connection',
            '--config', config_json,
            '--format', 'json'
        ])
        assert result.exit_code == 0, f"Create failed: {result.output}"
        create_data = json.loads(result.output)
        connection_id = create_data['id']
        assert connection_id is not None
        assert create_data['name'] == 'E2E Test Snowflake Connection'

        # Step 2: List connections
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'list',
            '--format', 'json'
        ])
        assert result.exit_code == 0, f"List failed: {result.output}"
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get('results', [])
        else:
            connections = list_data
        assert any(conn.get('id') == connection_id for conn in connections), \
            "Created connection not found in list"

        # Step 3: Get connection details
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'get',
            connection_id,
            '--format', 'json'
        ])
        assert result.exit_code == 0, f"Get failed: {result.output}"
        get_data = json.loads(result.output)
        assert get_data['id'] == connection_id
        assert get_data['name'] == 'E2E Test Snowflake Connection'

        # Step 4: Update connection
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'update',
            connection_id,
            '--name', 'E2E Updated Snowflake Connection',
            '--no-is-active',
            '--format', 'json'
        ])
        assert result.exit_code == 0, f"Update failed: {result.output}"
        update_data = json.loads(result.output)
        assert update_data['name'] == 'E2E Updated Snowflake Connection'
        assert update_data['is_active'] is False

        # Step 5: Test connection
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'test',
            connection_id,
            '--format', 'json'
        ])
        assert result.exit_code == 0, f"Test failed: {result.output}"
        test_data = json.loads(result.output)
        assert 'success' in test_data
        assert 'message' in test_data

        # Step 6: Delete connection
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'delete',
            connection_id
        ])
        assert result.exit_code == 0, f"Delete failed: {result.output}"
        assert 'deleted successfully' in result.output.lower()

        # Verify deletion
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'get',
            connection_id
        ])
        assert result.exit_code != 0, "Connection should not exist after deletion"

    def test_create_multiple_connections(self, runner):
        """Test creating multiple connections with different marketplace types"""
        marketplace_configs = [
            ('SNOWFLAKE_DATA_MARKETPLACE', {'account': 'test', 'user': 'test', 'token': 'test'}),
            ('AWS_DATA_EXCHANGE', {'api_key': 'test', 'region': 'us-east-1'}),
            ('CKAN_INSTANCE', {'url': 'https://example.com', 'api_key': 'test'}),
        ]

        connection_ids = []
        for marketplace_type, config_data in marketplace_configs:
            config_json = json.dumps(config_data)
            result = runner.invoke(cli, [
                'marketplace', 'connections', 'create',
                '--marketplace-type', marketplace_type,
                '--name', f'E2E Test {marketplace_type} Connection',
                '--config', config_json,
                '--format', 'json'
            ])
            assert result.exit_code == 0, f"Failed to create {marketplace_type}: {result.output}"
            connection_id = json.loads(result.output)['id']
            connection_ids.append(connection_id)

        # List all connections
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'list',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get('results', [])
        else:
            connections = list_data

        # Verify all created connections are in the list
        for conn_id in connection_ids:
            assert any(conn.get('id') == conn_id for conn in connections), \
                f"Connection {conn_id} not found in list"

        # Clean up
        for conn_id in connection_ids:
            runner.invoke(cli, [
                'marketplace', 'connections', 'delete', conn_id
            ])

    def test_connection_filtering(self, runner):
        """Test filtering connections by marketplace type and active status"""
        # Create connections with different types and statuses
        connections_to_create = [
            ('SNOWFLAKE_DATA_MARKETPLACE', True, {'account': 'test', 'user': 'test', 'token': 'test'}),
            ('SNOWFLAKE_DATA_MARKETPLACE', False, {'account': 'test2', 'user': 'test2', 'token': 'test2'}),
            ('AWS_DATA_EXCHANGE', True, {'api_key': 'test', 'region': 'us-east-1'}),
        ]

        connection_ids = []
        for marketplace_type, is_active, config_data in connections_to_create:
            config_json = json.dumps(config_data)
            is_active_flag = '--is-active' if is_active else '--no-is-active'
            result = runner.invoke(cli, [
                'marketplace', 'connections', 'create',
                '--marketplace-type', marketplace_type,
                '--name', f'E2E Filter Test {marketplace_type} {is_active}',
                '--config', config_json,
                is_active_flag,
                '--format', 'json'
            ])
            assert result.exit_code == 0
            connection_ids.append(json.loads(result.output)['id'])

        # Filter by marketplace type
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'list',
            '--marketplace-type', 'SNOWFLAKE_DATA_MARKETPLACE',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get('results', [])
        else:
            connections = list_data

        # Should only have Snowflake connections
        for conn in connections:
            assert conn['marketplace_type'] == 'SNOWFLAKE_DATA_MARKETPLACE'

        # Filter by active status
        result = runner.invoke(cli, [
            'marketplace', 'connections', 'list',
            '--is-active', 'true',
            '--format', 'json'
        ])
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get('results', [])
        else:
            connections = list_data

        # Should only have active connections
        for conn in connections:
            assert conn['is_active'] is True

        # Clean up
        for conn_id in connection_ids:
            runner.invoke(cli, [
                'marketplace', 'connections', 'delete', conn_id
            ])
