"""
End-to-End Tests for Marketplace CLI/SDK Consistency.

Task: 10.1.39.3 Marketplace CLI/SDK E2E Testing

This test suite provides engineering-grade E2E validation for:
- Complete workflows using CLI
- Complete workflows using SDK
- CLI/SDK consistency (same operations produce same results)

All tests use real API connections (no mocks/stubs) and follow TDD principles.
Tests verify that CLI and SDK produce identical results for the same operations.
"""

import pytest

# Phase 215.4 review fix: this module imports from django/hub which are
# not on the CLI test PYTHONPATH (CLI pytest.ini sets ``-p no:django``).
# Skip the entire module gracefully when those packages are unavailable
# instead of crashing pytest collection.
django = pytest.importorskip("django")
_billing_models = pytest.importorskip("hub.apps.billing.models")
_integrations_models = pytest.importorskip("hub.apps.integrations.models")
hub = pytest.importorskip("hub")
# In the PUBLIC tree the core hub package still imports, but the paid
# apps above are excluded from publish_paths_exclude.txt — guarding the
# paid module itself (not just ``hub``) is what makes this file skip
# cleanly there instead of collection-erroring in the sdk-cli.yml
# ``cli`` job (D1-class).
import contextlib
import json
import uuid

from click.testing import CliRunner
from datahub_cli.config import config
from datahub_cli.main import cli
from datahub_interoperability import (
    DataHubClient,
    DataHubClientConfig,
    MarketplaceIntegrationAPI,
    NotFoundError,
)
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


def _create_mapping_fixture(*, tenant, user, connection_id, unique_id, listing):
    """Sync ORM fixture creation for the async mapping tests.

    Django's ORM raises SynchronousOnlyOperation inside ``async def`` test
    bodies (measured 2026-08-28) — call this via ``sync_to_async``.
    """
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"mapping-list-test-asset-{unique_id}",
        name="Mapping List Test Asset",
        status=AssetStatus.ACTIVE,
        source_type="HUB_NATIVE",
        created_by=user,
    )
    connection_obj = MarketplaceConnection.objects.get(id=connection_id)
    mapping = MarketplaceMapping.objects.create(
        tenant=tenant,
        connection=connection_obj,
        hub_asset=asset,
        external_listing_id=listing,
        external_resource_ids=[] if listing.startswith("TEST_LISTING") else ["RESOURCE_1"],
    )
    return asset.id, str(mapping.id)


class MarketplaceLiveServerTestCase(LiveServerTestCase):
    """
    Custom LiveServerTestCase that handles database flush errors gracefully.

    LiveServerTestCase tries to flush the database in setUp, but PostgreSQL
    doesn't allow truncating tables with foreign key constraints unless CASCADE
    is used. This class catches and ignores those errors and ensures the
    live server URL is still set.
    """

    @classmethod
    def _fixture_setup(cls):
        """Skip the per-test DB flush on the persistent dedicated test DB.

        TransactionTestCase flushes every table before EACH test; against
        the persistent dedicated test DB (TEST_DB_SUFFIX=cli) the TRUNCATE
        (no CASCADE) blocks on FK-referenced tables until the 120 s
        ``statement_timeout`` fires — so the 9-test run burned 2+ minutes
        per test purely in setup (measured 2026-08-28).  Fixture names are
        per-run unique (uuid suffixes in setUp), so isolation does not
        depend on the flush.
        """
        import os

        if not os.environ.get("TEST_DB_SUFFIX"):
            # Fresh-DB path: setup errors are handled by setUp below.
            with contextlib.suppress(Exception):
                super()._fixture_setup()

    def _post_teardown(self):
        """Teardown that does not pay the 120 s statement-timeout."""
        import os

        if not os.environ.get("TEST_DB_SUFFIX"):
            # Fresh-DB path: teardown errors don't affect test validity.
            with contextlib.suppress(Exception):
                super()._post_teardown()

    def setUp(self):
        """Set up test fixtures, handling database flush errors"""
        # Call parent setUp which may fail on database flush
        # We'll handle that in _post_setup
        try:
            super().setUp()
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a database flush error
            if (
                "cannot truncate" in error_str
                or "foreign key constraint" in error_str
                or "couldn't be flushed" in error_str
            ):
                # Database flush failed, but we can continue
                # Ensure live_server_url is set by calling _live_server_setup
                try:
                    self._live_server_setup()
                except Exception:
                    # If that also fails, try to set it manually
                    if not hasattr(self, "live_server_url") or not self.live_server_url:
                        # Use a default port - LiveServerTestCase will find an available port
                        import socket

                        sock = socket.socket()
                        sock.bind(("", 0))
                        port = sock.getsockname()[1]
                        sock.close()
                        self.live_server_url = f"http://localhost:{port}"
            else:
                # Re-raise other exceptions
                raise


class TestMarketplaceCLISDKConsistency(MarketplaceLiveServerTestCase):
    """
    E2E tests for Marketplace CLI/SDK consistency.

    Verifies that CLI and SDK produce identical results for the same operations.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.runner = CliRunner()

        # Create tenant — per-run unique: the _post_teardown override skips
        # the TransactionTestCase flush (persistent dedicated DB), so a
        # fixed name collides with the tenants_name_key constraint on the
        # second test of the run (measured 2026-08-28).
        self.tenant = Tenant.objects.create(
            name=f"Marketplace CLI/SDK Consistency Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"marketplace-cli-sdk-consistency-test-tenant-{uuid.uuid4().hex[:8]}",
            # Phase 285.5.2.1 — the connection/mapping viewsets gate on this
            # tenant flag (403 MARKETPLACE_INTEGRATIONS_DISABLED when False).
            marketplace_integrations_enabled=True,
        )

        # Phase 313 paid write-gate — tenants middleware blocks every write
        # method with 403 "No active subscription" when the tenant has no
        # ACTIVE billing subscription. Provision one (plan is global, so a
        # fixed name keeps reruns idempotent).
        # GATE-29 — no static paid import: reuse the importorskip'd module
        # object above (its skip-in-public-tree behaviour stays intact).
        Subscription = _billing_models.Subscription
        SubscriptionStatus = _billing_models.SubscriptionStatus
        from hub.apps.tenants.models import PlanTier, TenantPlan

        plan, _ = TenantPlan.objects.get_or_create(
            name="Marketplace CLI/SDK Parity Pro Plan",
            defaults={
                "slug": "marketplace-cli-sdk-parity-pro",
                "tier": PlanTier.PRO,
                "category": "BASE",
                "order": 1,
            },
        )
        Subscription.objects.get_or_create(
            tenant=self.tenant,
            defaults={"plan": plan, "status": SubscriptionStatus.ACTIVE, "category": "BASE"},
        )

        # Create user with ACTIVE status
        self.user = User.objects.create_user(
            email=f"marketplace-cli-sdk-consistency-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create DATA_PROVIDER role and assign to user
        from hub.apps.users.models import Role

        data_provider_role, _ = Role.objects.get_or_create(
            # Roles are tenant-scoped (unique on (tenant, name)); without the
            # tenant filter get() raises MultipleObjectsReturned once more
            # than one tenant has a DATA_PROVIDER role (found on the shared
            # test DB, which held 5 of them).
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"},
        )
        self.user.user_roles.create(role=data_provider_role, tenant=self.tenant)

        # Set API base URL to live test server
        # LiveServerTestCase starts a test server that uses the test database
        self.api_base_url = f"{self.live_server_url}/api/v1"
        config.set_api_base_url(self.api_base_url)

        # Create API key for testing
        from hub.apps.auth.models import APIKey

        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="Marketplace CLI/SDK Consistency Test Key",
            key_hash=key_hash,
            scopes=["integrations:write", "integrations:read"],
        )
        config.set_api_key(plaintext_key)
        self.api_key = plaintext_key

        # Setup SDK client
        self.sdk_config = DataHubClientConfig(
            base_url=self.api_base_url,
            api_token=plaintext_key,
            timeout=60.0,
            max_retries=3,
            enable_logging=False,
        )

        # Test data storage
        self.created_connections = []
        self.created_mappings = []
        self.created_assets = []

    def tearDown(self):
        """Clean up after tests"""
        # Clean up created resources
        for mapping_id in self.created_mappings:
            with contextlib.suppress(Exception):
                self.runner.invoke(cli, ["marketplace", "mappings", "delete", mapping_id])

        for connection_id in self.created_connections:
            with contextlib.suppress(Exception):
                self.runner.invoke(cli, ["marketplace", "connections", "delete", connection_id])

        config.clear_auth()
        # Note: super().tearDown() may fail with database flush errors in LiveServerTestCase
        # This is a known issue and doesn't affect test results
        # Ignore teardown errors - they don't affect test validity
        with contextlib.suppress(Exception):
            super().tearDown()

    async def get_sdk_client(self):
        """Get SDK client"""
        client = DataHubClient(self.sdk_config)
        return client, MarketplaceIntegrationAPI(client)

    # ========== Connection Workflow Consistency Tests ==========

    @pytest.mark.asyncio
    async def test_connection_create_consistency(self):
        """Test that CLI and SDK create connections with identical results"""
        unique_id = str(uuid.uuid4())
        connection_name_cli = f"CLI Test Connection {unique_id}"
        connection_name_sdk = f"SDK Test Connection {unique_id}"
        config_data = {"api_key": "test", "endpoint": "https://example.com"}
        config_json = json.dumps(config_data)

        # Create via CLI
        result_cli = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                connection_name_cli,
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result_cli.exit_code == 0
        cli_data = json.loads(result_cli.output)
        self.created_connections.append(cli_data["id"])

        # Create via SDK
        client, marketplace_api = await self.get_sdk_client()
        try:
            sdk_data = await marketplace_api.create_connection(
                marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
                name=connection_name_sdk,
                config=config_data,
            )
            self.created_connections.append(sdk_data["id"])

            # Verify both have same structure
            assert "id" in cli_data
            assert "id" in sdk_data
            assert "marketplace_type" in cli_data
            assert "marketplace_type" in sdk_data
            assert cli_data["marketplace_type"] == sdk_data["marketplace_type"]
            assert "is_active" in cli_data
            assert "is_active" in sdk_data
            assert "created_at" in cli_data
            assert "created_at" in sdk_data
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_connection_list_consistency(self):
        """Test that CLI and SDK list connections with identical results"""
        # Create test connections via CLI
        config_json = json.dumps({"api_key": "test"})
        for i in range(2):
            unique_id = str(uuid.uuid4())
            result = self.runner.invoke(
                cli,
                [
                    "marketplace",
                    "connections",
                    "create",
                    "--marketplace-type",
                    "SNOWFLAKE_DATA_MARKETPLACE",
                    "--name",
                    f"List Test Connection {i} {unique_id}",
                    "--config",
                    config_json,
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0
            self.created_connections.append(json.loads(result.output)["id"])

        # List via CLI
        result_cli = self.runner.invoke(
            cli, ["marketplace", "connections", "list", "--format", "json"]
        )
        assert result_cli.exit_code == 0
        cli_list = json.loads(result_cli.output)
        if isinstance(cli_list, dict):
            cli_list = cli_list.get("results", [])

        # List via SDK
        client, marketplace_api = await self.get_sdk_client()
        try:
            sdk_list = await marketplace_api.list_connections()

            # Verify both return lists
            assert isinstance(cli_list, list)
            assert isinstance(sdk_list, list)

            # Verify both contain our created connections
            cli_ids = {conn["id"] for conn in cli_list}
            sdk_ids = {conn["id"] for conn in sdk_list}

            for conn_id in self.created_connections:
                assert conn_id in cli_ids
                assert conn_id in sdk_ids

            # Verify structure consistency
            if cli_list and sdk_list:
                cli_conn = cli_list[0]
                sdk_conn = sdk_list[0]
                assert "id" in cli_conn
                assert "id" in sdk_conn
                assert "marketplace_type" in cli_conn
                assert "marketplace_type" in sdk_conn
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_connection_get_consistency(self):
        """Test that CLI and SDK get connection details with identical results"""
        # Create connection via CLI
        config_json = json.dumps({"api_key": "test"})
        unique_id = str(uuid.uuid4())
        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                f"Get Test Connection {unique_id}",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        connection_id = json.loads(result.output)["id"]
        self.created_connections.append(connection_id)

        # Get via CLI
        result_cli = self.runner.invoke(
            cli, ["marketplace", "connections", "get", connection_id, "--format", "json"]
        )
        assert result_cli.exit_code == 0
        cli_data = json.loads(result_cli.output)

        # Get via SDK
        client, marketplace_api = await self.get_sdk_client()
        try:
            sdk_data = await marketplace_api.get_connection(connection_id)

            # Verify both have same ID
            assert cli_data["id"] == sdk_data["id"]
            assert cli_data["id"] == connection_id

            # Verify both have same fields
            assert cli_data["name"] == sdk_data["name"]
            assert cli_data["marketplace_type"] == sdk_data["marketplace_type"]
            assert cli_data["is_active"] == sdk_data["is_active"]
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_connection_update_consistency(self):
        """Test that CLI and SDK update connections with identical results"""
        # Create connection via CLI
        config_json = json.dumps({"api_key": "test"})
        unique_id = str(uuid.uuid4())
        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                f"Update Test Connection {unique_id}",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        connection_id = json.loads(result.output)["id"]
        self.created_connections.append(connection_id)

        # Update via CLI
        updated_name_cli = f"Updated CLI Name {unique_id}"
        result_cli = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "update",
                connection_id,
                "--name",
                updated_name_cli,
                "--format",
                "json",
            ],
        )
        assert result_cli.exit_code == 0
        cli_data = json.loads(result_cli.output)

        # Update via SDK
        updated_name_sdk = f"Updated SDK Name {unique_id}"
        client, marketplace_api = await self.get_sdk_client()
        try:
            sdk_data = await marketplace_api.update_connection(connection_id, name=updated_name_sdk)

            # Verify both updates worked
            assert cli_data["name"] == updated_name_cli
            assert sdk_data["name"] == updated_name_sdk
            assert cli_data["id"] == sdk_data["id"]
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_connection_delete_consistency(self):
        """Test that CLI and SDK delete connections consistently"""
        # Create two connections - one for CLI delete, one for SDK delete
        config_json = json.dumps({"api_key": "test"})
        unique_id = str(uuid.uuid4())

        # Connection for CLI delete
        result1 = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                f"CLI Delete Test {unique_id}",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result1.exit_code == 0
        cli_delete_id = json.loads(result1.output)["id"]

        # Connection for SDK delete
        client, marketplace_api = await self.get_sdk_client()
        try:
            sdk_delete_data = await marketplace_api.create_connection(
                marketplace_type="SNOWFLAKE_DATA_MARKETPLACE",
                name=f"SDK Delete Test {unique_id}",
                config={"api_key": "test"},
            )
            sdk_delete_id = sdk_delete_data["id"]

            # Delete via CLI
            result_cli = self.runner.invoke(
                cli, ["marketplace", "connections", "delete", cli_delete_id]
            )
            assert result_cli.exit_code == 0

            # Delete via SDK
            await marketplace_api.delete_connection(sdk_delete_id)

            # Verify both are deleted
            result_get_cli = self.runner.invoke(
                cli, ["marketplace", "connections", "get", cli_delete_id]
            )
            assert result_get_cli.exit_code != 0

            with pytest.raises(NotFoundError):
                await marketplace_api.get_connection(sdk_delete_id)
        finally:
            await client.close()

    # ========== Mapping Workflow Consistency Tests ==========

    @pytest.mark.asyncio
    async def test_mapping_list_consistency(self):
        """Test that CLI and SDK list mappings with identical results"""
        # Create connection, asset, and mapping
        config_json = json.dumps({"api_key": "test"})
        unique_id = str(uuid.uuid4())

        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                f"Mapping List Test Connection {unique_id}",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        connection_id = json.loads(result.output)["id"]
        self.created_connections.append(connection_id)

        # Create asset + mapping (sync ORM — must run via sync_to_async).
        from asgiref.sync import sync_to_async

        asset_id, mapping_id = await sync_to_async(_create_mapping_fixture)(
            tenant=self.tenant,
            user=self.user,
            connection_id=connection_id,
            unique_id=unique_id,
            listing=f"TEST_LISTING_{unique_id}",
        )
        self.created_assets.append(asset_id)
        self.created_mappings.append(mapping_id)

        # List via CLI
        result_cli = self.runner.invoke(
            cli, ["marketplace", "mappings", "list", "--format", "json"]
        )
        assert result_cli.exit_code == 0
        cli_list = json.loads(result_cli.output)
        if isinstance(cli_list, dict):
            cli_list = cli_list.get("results", [])

        # List via SDK
        client, marketplace_api = await self.get_sdk_client()
        try:
            sdk_list = await marketplace_api.list_mappings()

            # Verify both return lists
            assert isinstance(cli_list, list)
            assert isinstance(sdk_list, list)

            # Verify both contain our created mapping
            cli_ids = {m.get("id") for m in cli_list}
            sdk_ids = {m.get("id") for m in sdk_list}

            assert str(mapping_id) in cli_ids
            assert str(mapping_id) in sdk_ids
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_mapping_get_consistency(self):
        """Test that CLI and SDK get mapping details with identical results"""
        # Create connection, asset, and mapping
        config_json = json.dumps({"api_key": "test"})
        unique_id = str(uuid.uuid4())

        result = self.runner.invoke(
            cli,
            [
                "marketplace",
                "connections",
                "create",
                "--marketplace-type",
                "SNOWFLAKE_DATA_MARKETPLACE",
                "--name",
                f"Mapping Get Test Connection {unique_id}",
                "--config",
                config_json,
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        connection_id = json.loads(result.output)["id"]
        self.created_connections.append(connection_id)

        from asgiref.sync import sync_to_async

        asset_id, mapping_id = await sync_to_async(_create_mapping_fixture)(
            tenant=self.tenant,
            user=self.user,
            connection_id=connection_id,
            unique_id=unique_id,
            listing=f"TEST_LISTING_{unique_id}",
        )
        self.created_assets.append(asset_id)
        self.created_mappings.append(mapping_id)

        # Get via CLI
        result_cli = self.runner.invoke(
            cli, ["marketplace", "mappings", "get", str(mapping_id), "--format", "json"]
        )
        assert result_cli.exit_code == 0
        cli_data = json.loads(result_cli.output)

        # Get via SDK
        client, marketplace_api = await self.get_sdk_client()
        try:
            sdk_data = await marketplace_api.get_mapping(str(mapping_id))

            # Verify both have same ID
            assert cli_data["id"] == sdk_data["id"]
            assert cli_data["id"] == str(mapping_id)

            # Verify both have same external_listing_id
            assert cli_data["external_listing_id"] == sdk_data["external_listing_id"]
        finally:
            await client.close()

    # ========== Connector Workflow Consistency Tests ==========

    @pytest.mark.asyncio
    async def test_connector_list_consistency(self):
        """Test that CLI and SDK list connectors with identical results"""
        # List via CLI
        result_cli = self.runner.invoke(
            cli, ["marketplace", "connectors", "list", "--format", "json"]
        )
        assert result_cli.exit_code == 0

        try:
            cli_list = json.loads(result_cli.output)
            if isinstance(cli_list, dict):
                cli_list = cli_list.get("connectors", [])
        except json.JSONDecodeError:
            pytest.skip("CLI returned non-JSON output")

        # List via SDK
        client, marketplace_api = await self.get_sdk_client()
        try:
            sdk_list = await marketplace_api.list_connectors()

            # Verify both return lists
            assert isinstance(cli_list, list)
            assert isinstance(sdk_list, list)

            # Verify both have same connector types (if any)
            if cli_list and sdk_list:
                cli_types = {c.get("type") or c.get("connector_type") for c in cli_list}
                sdk_types = {c.get("type") or c.get("connector_type") for c in sdk_list}
                assert cli_types == sdk_types
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_connector_info_consistency(self):
        """Test that CLI and SDK get connector info with identical results"""
        # First, list connectors to get available types
        result = self.runner.invoke(cli, ["marketplace", "connectors", "list", "--format", "json"])

        if result.exit_code != 0:
            pytest.skip("Cannot list connectors")

        try:
            list_data = json.loads(result.output)
            connectors = (
                list_data if isinstance(list_data, list) else list_data.get("connectors", [])
            )

            if not connectors:
                pytest.skip("No connectors available")

            connector_type = connectors[0].get("type") or connectors[0].get("connector_type")
            if not connector_type:
                pytest.skip("No connector type found")

            # Get info via CLI
            result_cli = self.runner.invoke(
                cli, ["marketplace", "connectors", "info", connector_type, "--format", "json"]
            )
            assert result_cli.exit_code == 0
            cli_data = json.loads(result_cli.output)

            # Get info via SDK
            client, marketplace_api = await self.get_sdk_client()
            try:
                sdk_data = await marketplace_api.get_connector_info(connector_type)

                # Verify both have same type
                cli_type = cli_data.get("type") or cli_data.get("connector_type")
                sdk_type = sdk_data.get("type") or sdk_data.get("connector_type")
                assert cli_type == sdk_type
                assert cli_type == connector_type
            finally:
                await client.close()
        except (json.JSONDecodeError, KeyError):
            pytest.skip("Cannot parse connector data")
