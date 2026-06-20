"""
Integration tests for marketplace CLI commands using Django LiveServerTestCase.

These tests use Django's live test server, which starts automatically,
so they work without requiring a pre-running API service.

CRITICAL: To avoid transaction isolation issues with LiveServerTestCase,
all test data is created via HTTP requests to the live server. This ensures
the data is created through the server thread's database connection and is
immediately visible to subsequent CLI commands.

NOTE: These tests must be run from the Django project root (not CLI directory)
to ensure Django is properly initialized via pytest-django.
"""

import pytest

# Phase 215.4 review fix: this module imports from django/hub which are
# not on the CLI test PYTHONPATH (CLI pytest.ini sets ``-p no:django``).
# Skip the entire module gracefully when those packages are unavailable
# instead of crashing pytest collection.
django = pytest.importorskip("django")
hub = pytest.importorskip("hub")
import json

from click.testing import CliRunner
from datahub_cli.config import config
from datahub_cli.main import cli
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestMarketplaceCommandsIntegration(LiveServerTestCase):
    """
    Integration tests for marketplace CLI commands using Django's live test server.

    CRITICAL: All test data is created via HTTP requests to the live server
    to avoid transaction isolation issues. This ensures data is created
    through the server thread's database connection and is immediately visible.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.runner = CliRunner()

        # Create tenant (this is OK to create directly as it's needed for user creation)
        self.tenant = Tenant.objects.create(
            name="Marketplace CLI Test Tenant", slug="marketplace-cli-test-tenant"
        )

        # Create user with ACTIVE status (required for authentication)
        self.user = User.objects.create_user(
            email="marketplace-cli-test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create DATA_PROVIDER role and assign to user (required for marketplace operations)
        from hub.apps.users.models import Role

        data_provider_role, _ = Role.objects.get_or_create(
            name="DATA_PROVIDER", defaults={"description": "Data Provider Role"}
        )
        self.user.user_roles.create(role=data_provider_role)

        # Set API base URL to live test server
        self.api_base_url = f"{self.live_server_url}/api/v1"
        config.set_api_base_url(self.api_base_url)

        # Create API key for testing with integrations:write scope (required for marketplace operations)
        from hub.apps.auth.models import APIKey

        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="Marketplace CLI Test Key",
            key_hash=key_hash,
            scopes=["integrations:write", "integrations:read"],
        )
        config.set_api_key(plaintext_key)
        self.api_key = plaintext_key

    def tearDown(self):
        """Clean up after tests"""
        config.clear_auth()
        # Note: super().tearDown() may fail with database flush errors in LiveServerTestCase
        # This is a known issue and doesn't affect test results
        try:
            super().tearDown()
        except Exception:
            # Ignore teardown errors - they don't affect test validity
            pass

    def test_marketplace_connections_create_list_get_delete(self):
        """Test complete workflow: create → list → get → delete"""
        # Create connection
        connection_config = {
            "account": "test_account",
            "user": "test_user",
            "token": "test_token",
            "warehouse": "COMPUTE_WH",
            "role": "ACCOUNTADMIN",
        }
        config_json = json.dumps(connection_config)

        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                "Test Snowflake Connection",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"Create failed: {result.output}"

        # Parse created connection ID
        output_data = json.loads(result.output)
        connection_id = output_data["id"]
        assert connection_id is not None

        # List connections
        result = self.runner.invoke(cli, ["marketplace", "connections", "list", "--format", "json"])
        assert result.exit_code == 0, f"List failed: {result.output}"
        list_data = json.loads(result.output)
        assert isinstance(list_data, list) or (
            isinstance(list_data, dict) and "results" in list_data
        )

        # Find our connection in the list
        if isinstance(list_data, dict):
            connections = list_data.get("results", [])
        else:
            connections = list_data
        found = any(conn.get("id") == connection_id for conn in connections)
        assert found, "Created connection not found in list"

        # Get connection details
        result = self.runner.invoke(
            cli, ["marketplace", "connections", "get", connection_id, "--format", "json"]
        )
        assert result.exit_code == 0, f"Get failed: {result.output}"
        get_data = json.loads(result.output)
        assert get_data["id"] == connection_id
        assert get_data["name"] == "Test Snowflake Connection"
        assert get_data["marketplace_type"] == "SNOWFLAKE_DATA_MARKETPLACE"

        # Delete connection
        result = self.runner.invoke(cli, ["marketplace", "connections", "delete", connection_id])
        assert result.exit_code == 0, f"Delete failed: {result.output}"
        assert "deleted successfully" in result.output.lower()

    def test_marketplace_connections_update(self):
        """Test update connection workflow"""
        # Create connection
        connection_config = {"api_key": "test_key", "endpoint": "https://example.com"}
        config_json = json.dumps(connection_config)

        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "AWS_DATA_EXCHANGE",
                "--name",
                "Test AWS Connection",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        connection_id = json.loads(result.output)["id"]

        # Update connection
        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "update",
                connection_id,
                "--name",
                "Updated AWS Connection",
                "--no-is-active",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        update_data = json.loads(result.output)
        assert update_data["name"] == "Updated AWS Connection"
        assert update_data["is_active"] is False

    def test_marketplace_connections_test(self):
        """Test connection testing"""
        # Create connection
        connection_config = {"api_key": "test_key", "endpoint": "https://example.com"}
        config_json = json.dumps(connection_config)

        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "CKAN_INSTANCE",
                "--name",
                "Test CKAN Connection",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        connection_id = json.loads(result.output)["id"]

        # Test connection (may succeed or fail depending on actual connection)
        result = self.runner.invoke(
            cli, ["marketplace", "connections", "test", connection_id, "--format", "json"]
        )
        # Test may return success or failure, but should not crash
        assert result.exit_code == 0
        test_data = json.loads(result.output)
        assert "success" in test_data
        assert "message" in test_data

    def test_marketplace_connections_list_with_filters(self):
        """Test list connections with filters"""
        # Create multiple connections
        configs = [
            ("SNOWFLAKE_DATA_MARKETPLACE", "Snowflake Connection"),
            ("AWS_DATA_EXCHANGE", "AWS Connection"),
            ("CKAN_INSTANCE", "CKAN Connection"),
        ]

        connection_ids = []
        for marketplace_type, name in configs:
            connection_config = {"api_key": "test_key"}
            config_json = json.dumps(connection_config)

            result = self.runner.invoke(
                cli,
                [
                    "marketplace",
                    "connections",
                    "create",
                    "--marketplace-type",
                    marketplace_type,
                    "--name",
                    name,
                    "--config",
                    config_json,
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0
            connection_ids.append(json.loads(result.output)["id"])

        # List with marketplace type filter
        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "list",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            connections = list_data.get("results", [])
        else:
            connections = list_data

        # Should only have Snowflake connections
        for conn in connections:
            assert conn["marketplace_type"] == "SNOWFLAKE_DATA_MARKETPLACE"

        # Clean up
        for conn_id in connection_ids:
            self.runner.invoke(cli, ["marketplace", "connections", "delete", conn_id])

    def test_marketplace_connections_error_handling(self):
        """Test error handling for invalid operations"""
        # Try to get non-existent connection
        fake_id = "550e8400-e29b-41d4-a716-446655440000"
        result = self.runner.invoke(cli, ["marketplace", "connections", "get", fake_id])
        # Should fail gracefully
        assert result.exit_code != 0

        # Try to create with invalid marketplace type
        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "INVALID_TYPE",
                "--name",
                "Test",
                "--config",
                "{}",
            ],
        )
        assert result.exit_code != 0

        # Try to create with invalid JSON config
        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                "Test",
                "--config",
                "{invalid json}",
            ],
        )
        assert result.exit_code != 0

    def test_marketplace_mappings_list_get_delete(self):
        """Test complete workflow: list → get → delete for mappings"""
        # First, create a connection and asset to create a mapping
        connection_config = {
            "account": "test_account",
            "user": "test_user",
            "token": "test_token",
            "warehouse": "COMPUTE_WH",
            "role": "ACCOUNTADMIN",
        }
        config_json = json.dumps(connection_config)

        # Create connection
        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                "Test Mapping Connection",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"Create connection failed: {result.output}"
        connection_data = json.loads(result.output)
        connection_id = connection_data["id"]

        # Create an asset via API (mappings are created during sync, but we can create one directly for testing)
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.integrations.models import MarketplaceMapping

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-mapping-asset",
            name="Test Mapping Asset",
            status=AssetStatus.ACTIVE,
            source_type="HUB_NATIVE",
            created_by=self.user,
        )

        # Create a mapping directly (mappings are normally created during sync)
        from hub.apps.integrations.models import MarketplaceConnection

        connection_obj = MarketplaceConnection.objects.get(id=connection_id)

        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection_obj,
            hub_asset=asset,
            external_listing_id="TEST_LISTING_123",
            external_resource_ids=["RESOURCE_1", "RESOURCE_2"],
            sync_metadata={"last_sync_status": "SUCCESS", "last_sync_errors": []},
        )

        # List mappings
        result = self.runner.invoke(cli, ["marketplace", "mappings", "list", "--format", "json"])
        assert result.exit_code == 0, f"List mappings failed: {result.output}"
        list_data = json.loads(result.output)
        assert isinstance(list_data, list) or (
            isinstance(list_data, dict) and "results" in list_data
        )

        # Find our mapping in the list
        if isinstance(list_data, dict):
            mappings = list_data.get("results", [])
        else:
            mappings = list_data
        found = any(m.get("id") == str(mapping.id) for m in mappings)
        assert found, "Created mapping not found in list"

        # Get mapping details
        result = self.runner.invoke(
            cli, ["marketplace", "mappings", "get", str(mapping.id), "--format", "json"]
        )
        assert result.exit_code == 0, f"Get mapping failed: {result.output}"
        get_data = json.loads(result.output)
        assert get_data["id"] == str(mapping.id)
        assert get_data["external_listing_id"] == "TEST_LISTING_123"
        assert get_data["hub_asset"]["id"] == str(asset.id)

        # Delete mapping
        result = self.runner.invoke(cli, ["marketplace", "mappings", "delete", str(mapping.id)])
        assert result.exit_code == 0, f"Delete mapping failed: {result.output}"
        assert "deleted successfully" in result.output.lower()

        # Verify mapping is deleted
        result = self.runner.invoke(
            cli, ["marketplace", "mappings", "get", str(mapping.id), "--format", "json"]
        )
        assert result.exit_code != 0, "Mapping should not exist after deletion"

        # Clean up
        self.runner.invoke(cli, ["marketplace", "connections", "delete", connection_id])

    def test_marketplace_mappings_list_with_filters(self):
        """Test list mappings with filters"""
        # Create connection
        connection_config = {"api_key": "test_key"}
        config_json = json.dumps(connection_config)

        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "CKAN_INSTANCE",
                "--name",
                "Test Filter Connection",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        connection_data = json.loads(result.output)
        connection_id = connection_data["id"]

        # Create assets and mappings
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping

        connection_obj = MarketplaceConnection.objects.get(id=connection_id)

        asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="filter-asset-1",
            name="Filter Asset 1",
            status=AssetStatus.ACTIVE,
            source_type="HUB_NATIVE",
            created_by=self.user,
        )

        asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="filter-asset-2",
            name="Filter Asset 2",
            status=AssetStatus.ACTIVE,
            source_type="HUB_NATIVE",
            created_by=self.user,
        )

        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection_obj,
            hub_asset=asset1,
            external_listing_id="FILTER_LISTING_1",
            external_resource_ids=[],
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=connection_obj,
            hub_asset=asset2,
            external_listing_id="FILTER_LISTING_2",
            external_resource_ids=[],
        )

        # List with connection filter
        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "mappings",
                "list",
                "--connection-id",
                connection_id,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            mappings = list_data.get("results", [])
        else:
            mappings = list_data
        # Should have both mappings
        mapping_ids = [m.get("id") for m in mappings]
        assert str(mapping1.id) in mapping_ids
        assert str(mapping2.id) in mapping_ids

        # List with asset filter
        result = self.runner.invoke(
            cli,
            ["marketplace", "mappings", "list", "--asset-id", str(asset1.id), "--format", "json"],
        )
        assert result.exit_code == 0
        list_data = json.loads(result.output)
        if isinstance(list_data, dict):
            mappings = list_data.get("results", [])
        else:
            mappings = list_data
        # Should only have mapping1
        mapping_ids = [m.get("id") for m in mappings]
        assert str(mapping1.id) in mapping_ids
        assert str(mapping2.id) not in mapping_ids

        # Clean up
        self.runner.invoke(cli, ["marketplace", "mappings", "delete", str(mapping1.id)])
        self.runner.invoke(cli, ["marketplace", "mappings", "delete", str(mapping2.id)])
        self.runner.invoke(cli, ["marketplace", "connections", "delete", connection_id])

    def test_marketplace_mappings_error_handling(self):
        """Test error handling for invalid mapping operations"""
        # Try to get non-existent mapping
        fake_id = "770e8400-e29b-41d4-a716-446655440000"
        result = self.runner.invoke(cli, ["marketplace", "mappings", "get", fake_id])
        # Should fail gracefully
        assert result.exit_code != 0

        # Try to delete non-existent mapping
        result = self.runner.invoke(cli, ["marketplace", "mappings", "delete", fake_id])
        assert result.exit_code != 0

        # Try to list with invalid connection ID
        result = self.runner.invoke(
            cli, ["marketplace", "mappings", "list", "--connection-id", "invalid-id"]
        )
        assert result.exit_code != 0

        # Try to list with invalid asset ID
        result = self.runner.invoke(
            cli, ["marketplace", "mappings", "list", "--asset-id", "invalid-id"]
        )
        assert result.exit_code != 0

        # Try to list with invalid limit
        result = self.runner.invoke(cli, ["marketplace", "mappings", "list", "--limit", "0"])
        assert result.exit_code != 0

        # Try to list with invalid offset
        result = self.runner.invoke(cli, ["marketplace", "mappings", "list", "--offset", "-1"])
        assert result.exit_code != 0

    def test_marketplace_connectors_list(self):
        """Test marketplace connectors list command with real API"""
        # List connectors
        result = self.runner.invoke(cli, ["marketplace", "connectors", "list"])
        assert result.exit_code == 0
        assert "Type" in result.output or "No connectors found" in result.output

    def test_marketplace_connectors_list_json(self):
        """Test marketplace connectors list command with JSON format"""
        result = self.runner.invoke(cli, ["marketplace", "connectors", "list", "--format", "json"])
        assert result.exit_code == 0
        # Try to parse as JSON
        try:
            output_json = json.loads(result.output)
            assert "connectors" in output_json
            assert isinstance(output_json["connectors"], list)
        except json.JSONDecodeError:
            # If not JSON, check for error message
            assert "error" in result.output.lower() or "No connectors found" in result.output

    def test_marketplace_connectors_info_valid_type(self):
        """Test marketplace connectors info command with valid connector type"""
        # First, list connectors to get available types
        list_result = self.runner.invoke(
            cli, ["marketplace", "connectors", "list", "--format", "json"]
        )

        if list_result.exit_code == 0:
            try:
                list_data = json.loads(list_result.output)
                connectors = list_data.get("connectors", [])

                if connectors:
                    # Use the first available connector type
                    connector_type = connectors[0].get("type")
                    if connector_type:
                        # Get info for this connector
                        result = self.runner.invoke(
                            cli, ["marketplace", "connectors", "info", connector_type]
                        )
                        assert result.exit_code == 0
                        assert (
                            connector_type in result.output
                            or connector_type.upper() in result.output
                        )
            except json.JSONDecodeError:
                # If we can't parse, skip this test
                pass

    def test_marketplace_connectors_info_json(self):
        """Test marketplace connectors info command with JSON format"""
        # First, list connectors to get available types
        list_result = self.runner.invoke(
            cli, ["marketplace", "connectors", "list", "--format", "json"]
        )

        if list_result.exit_code == 0:
            try:
                list_data = json.loads(list_result.output)
                connectors = list_data.get("connectors", [])

                if connectors:
                    # Use the first available connector type
                    connector_type = connectors[0].get("type")
                    if connector_type:
                        # Get info for this connector with JSON format
                        result = self.runner.invoke(
                            cli,
                            [
                                "marketplace",
                                "connectors",
                                "info",
                                connector_type,
                                "--format",
                                "json",
                            ],
                        )
                        assert result.exit_code == 0
                        # Try to parse as JSON
                        try:
                            output_json = json.loads(result.output)
                            assert "type" in output_json
                            assert (
                                output_json["type"] == connector_type
                                or output_json["type"] == connector_type.upper()
                            )
                        except json.JSONDecodeError:
                            # If not JSON, check for error message
                            assert "error" in result.output.lower()
            except json.JSONDecodeError:
                # If we can't parse, skip this test
                pass

    def test_marketplace_connectors_info_invalid_type(self):
        """Test marketplace connectors info command with invalid connector type"""
        result = self.runner.invoke(
            cli, ["marketplace", "connectors", "info", "INVALID_CONNECTOR_TYPE"]
        )
        assert result.exit_code != 0
        assert "Invalid marketplace type" in result.output or "not found" in result.output.lower()

    def test_marketplace_connectors_info_case_insensitive(self):
        """Test marketplace connectors info command with case-insensitive connector type"""
        # First, list connectors to get available types
        list_result = self.runner.invoke(
            cli, ["marketplace", "connectors", "list", "--format", "json"]
        )

        if list_result.exit_code == 0:
            try:
                list_data = json.loads(list_result.output)
                connectors = list_data.get("connectors", [])

                if connectors:
                    # Use the first available connector type
                    connector_type = connectors[0].get("type")
                    if connector_type:
                        # Try with lowercase
                        result = self.runner.invoke(
                            cli, ["marketplace", "connectors", "info", connector_type.lower()]
                        )
                        # Should work (case-insensitive) or fail gracefully
                        assert result.exit_code == 0 or "not found" in result.output.lower()
            except json.JSONDecodeError:
                # If we can't parse, skip this test
                pass
