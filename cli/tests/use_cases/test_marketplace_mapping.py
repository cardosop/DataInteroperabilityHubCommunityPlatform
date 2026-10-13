import pytest

pytestmark = pytest.mark.mvp

"""
End-to-end tests for marketplace mapping workflows.

These tests verify complete workflows from start to finish:
- List mappings → Get mapping → Delete mapping
- List with filters → Get details → Verify deletion
"""
import pytest

# Phase 215.4 review fix: this module imports from django/hub which are
# not on the CLI test PYTHONPATH (CLI pytest.ini sets ``-p no:django``).
# Skip the entire module gracefully when those packages are unavailable
# instead of crashing pytest collection.
django = pytest.importorskip("django")

hub = pytest.importorskip("hub")
# Phase U / U.3 — marketplace is paid/excluded from the public
# tree; the integrations guards were no-ops (integrations is core).
_marketplace = pytest.importorskip("hub.apps.marketplace")
# In the PUBLIC tree the core hub package still imports, but the paid
# apps above are excluded from publish_paths_exclude.txt — guarding the
# paid module itself (not just ``hub``) is what makes this file skip
# cleanly there instead of collection-erroring in the sdk-cli.yml
# ``cli`` job (D1-class).
import json
import uuid

from click.testing import CliRunner
from datahub_cli.config import config
from datahub_cli.main import cli
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceMapping, MarketplaceType

# Import Django models
from hub.apps.tenants.models import Tenant

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestMarketplaceMappingWorkflowsE2E(LiveServerTestCase):
    """
    End-to-end tests for marketplace mapping workflows.

    Tests complete workflows using real API endpoints.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.runner = CliRunner()

        # The CLI's get_api_key() prefers env tokens over the config-file
        # key (DATAHUB_API_TOKEN etc.), and the batch runner exports one
        # bound to the DEFAULT tenant — the in-process CLI would auth as
        # that tenant and see none of this test's tenant-scoped rows.
        # Neutralize the env fallback for the duration of the test and
        # restore it in tearDown so other suites keep their batch token.
        import os as _os

        self._saved_env_token = _os.environ.pop("DATAHUB_API_TOKEN", None)

        # Seed the WHOLE fixture set (tenant + subscription + user + role +
        # key) through the stack's container: in-process ORM rows live
        # inside this TransactionTestCase's transaction while the live
        # server's request threads use separate connections that cannot
        # see uncommitted rows (intermittent 401 / "No active
        # subscription" 403 flakes).  The container commit makes every
        # row visible to every connection; re-read them here (READ
        # COMMITTED).
        from tests.use_cases.conftest import seed_marketplace_e2e_tenant_in_container

        _email = f"cli-mapping-e2e-{uuid.uuid4().hex[:8]}@example.com"
        seeded = seed_marketplace_e2e_tenant_in_container(
            slug=f"cli-mapping-e2e-test-tenant-{uuid.uuid4().hex[:8]}",
            name=f"CLI Mapping E2E Test Tenant {uuid.uuid4().hex[:8]}",
            email=_email,
            key_name="CLI Mapping E2E Test Key",
        )
        self.tenant = Tenant.objects.get(pk=seeded["tenant_id"])
        self.user = User.objects.get(email=_email)

        # Clear any auth left on the GLOBAL config by other tests (the
        # CLI prefers an access token over the API key — a stale JWT from
        # authenticated_config would make every call here "Invalid API key").
        config.clear_auth()
        # Set API base URL to live test server
        self.api_base_url = f"{self.live_server_url}/api/v1"
        config.set_api_base_url(self.api_base_url)
        config.set_api_key(seeded["api_key"])
        self.api_key = seeded["api_key"]

        # Create connection and assets for testing
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            name="E2E Test Connection",
            config={"base_url": "https://demo.ckan.org"},
            is_active=True,
        )

        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="e2e-test-asset-1",
            name="E2E Test Asset 1",
            status=AssetStatus.ACTIVE,
            source_type="HUB_NATIVE",
            created_by=self.user,
        )

        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="e2e-test-asset-2",
            name="E2E Test Asset 2",
            status=AssetStatus.ACTIVE,
            source_type="HUB_NATIVE",
            created_by=self.user,
        )

    @classmethod
    def _fixture_teardown(cls):
        """Never flush — the default TransactionTestCase flush TRUNCATEs
        tables in dependency order against the SHARED test DB
        (TEST_DB_SUFFIX=shared) until it raises NotSupportedError,
        wiping plans, seeded users and subscriptions along the way (the
        recurring seed-erasure mystery).  Fixture rows use per-run uuid
        suffixes, so skipping the flush is safe; manual cleanup lives in
        tearDown where needed.
        """

    def tearDown(self):
        """Clean up after tests"""
        super().tearDown()
        config.clear_auth()
        if getattr(self, "_saved_env_token", None) is not None:
            import os as _os

            _os.environ["DATAHUB_API_TOKEN"] = self._saved_env_token

    def test_complete_mapping_workflow_list_get_delete(self):
        """Test complete workflow: list → get → delete"""
        # Create a mapping
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset1,
            external_listing_id="E2E_TEST_LISTING_1",
            external_resource_ids=["RESOURCE_1", "RESOURCE_2"],
            sync_metadata={"last_sync_status": "SUCCESS", "last_sync_errors": []},
        )

        try:
            # Step 1: List mappings
            result = self.runner.invoke(
                cli, ["marketplace", "mappings", "list", "--format", "json"]
            )
            assert result.exit_code == 0, f"List failed: {result.output}"
            list_data = json.loads(result.output)

            # Verify mapping is in the list
            mappings = list_data.get("results", []) if isinstance(list_data, dict) else list_data

            mapping_ids = [m.get("id") for m in mappings]
            assert str(mapping.id) in mapping_ids, "Mapping not found in list"

            # Step 2: Get mapping details
            result = self.runner.invoke(
                cli, ["marketplace", "mappings", "get", str(mapping.id), "--format", "json"]
            )
            assert result.exit_code == 0, f"Get failed: {result.output}"
            get_data = json.loads(result.output)

            # Verify details — the backend serializer is FLAT
            # (hub_asset_id/hub_asset_name, connection_id/connection_name),
            # not nested envelopes.
            assert get_data["id"] == str(mapping.id)
            assert get_data["external_listing_id"] == "E2E_TEST_LISTING_1"
            assert get_data["hub_asset_id"] == str(self.asset1.id)
            assert get_data["hub_asset_name"] == "E2E Test Asset 1"
            assert get_data["connection_id"] == str(self.connection.id)
            assert len(get_data.get("external_resource_ids", [])) == 2

            # Step 3: Delete mapping
            result = self.runner.invoke(cli, ["marketplace", "mappings", "delete", str(mapping.id)])
            assert result.exit_code == 0, f"Delete failed: {result.output}"
            assert "deleted successfully" in result.output.lower()

            # Step 4: Verify mapping is deleted (get should fail)
            result = self.runner.invoke(cli, ["marketplace", "mappings", "get", str(mapping.id)])
            assert result.exit_code != 0, "Mapping should not exist after deletion"

        finally:
            # Clean up if mapping still exists
            if MarketplaceMapping.objects.filter(id=mapping.id).exists():
                MarketplaceMapping.objects.filter(id=mapping.id).delete()

    def test_mapping_workflow_with_filters(self):
        """Test mapping workflow with filters"""
        # Create multiple mappings
        mapping1 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset1,
            external_listing_id="FILTER_TEST_1",
            external_resource_ids=[],
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset2,
            external_listing_id="FILTER_TEST_2",
            external_resource_ids=[],
        )

        try:
            # Test filter by connection
            result = self.runner.invoke(
                cli,
                [
                    "marketplace",
                    "mappings",
                    "list",
                    "--connection-id",
                    str(self.connection.id),
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0
            list_data = json.loads(result.output)
            mappings = list_data.get("results", []) if isinstance(list_data, dict) else list_data
            mapping_ids = [m.get("id") for m in mappings]
            assert str(mapping1.id) in mapping_ids
            assert str(mapping2.id) in mapping_ids

            # Test filter by asset
            result = self.runner.invoke(
                cli,
                [
                    "marketplace",
                    "mappings",
                    "list",
                    "--asset-id",
                    str(self.asset1.id),
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0
            list_data = json.loads(result.output)
            mappings = list_data.get("results", []) if isinstance(list_data, dict) else list_data
            mapping_ids = [m.get("id") for m in mappings]
            assert str(mapping1.id) in mapping_ids
            assert str(mapping2.id) not in mapping_ids

            # Test pagination
            result = self.runner.invoke(
                cli,
                [
                    "marketplace",
                    "mappings",
                    "list",
                    "--limit",
                    "1",
                    "--offset",
                    "0",
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0
            list_data = json.loads(result.output)
            mappings = list_data.get("results", []) if isinstance(list_data, dict) else list_data
            assert len(mappings) <= 1

        finally:
            # Clean up
            MarketplaceMapping.objects.filter(id__in=[mapping1.id, mapping2.id]).delete()

    def test_mapping_workflow_table_output(self):
        """Test mapping commands with table output format"""
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset1,
            external_listing_id="TABLE_TEST_LISTING",
            external_resource_ids=[],
        )

        try:
            # Test list with table output
            result = self.runner.invoke(cli, ["marketplace", "mappings", "list"])
            assert result.exit_code == 0
            assert "TABLE_TEST_LISTING" in result.output or "No mappings found" in result.output

            # Test get with table output
            result = self.runner.invoke(cli, ["marketplace", "mappings", "get", str(mapping.id)])
            assert result.exit_code == 0
            assert str(mapping.id) in result.output
            assert "TABLE_TEST_LISTING" in result.output
            assert "E2E Test Asset 1" in result.output

            # Test delete with table output
            result = self.runner.invoke(cli, ["marketplace", "mappings", "delete", str(mapping.id)])
            assert result.exit_code == 0
            assert "deleted successfully" in result.output.lower()

        finally:
            # Clean up if mapping still exists
            if MarketplaceMapping.objects.filter(id=mapping.id).exists():
                MarketplaceMapping.objects.filter(id=mapping.id).delete()

    def test_mapping_workflow_error_handling(self):
        """Test error handling in mapping workflows"""
        # Test get with invalid ID
        result = self.runner.invoke(cli, ["marketplace", "mappings", "get", "invalid-uuid-format"])
        assert result.exit_code != 0

        # Test delete with invalid ID
        result = self.runner.invoke(
            cli, ["marketplace", "mappings", "delete", "invalid-uuid-format"]
        )
        assert result.exit_code != 0

        # Test list with invalid connection ID
        result = self.runner.invoke(
            cli, ["marketplace", "mappings", "list", "--connection-id", "invalid-uuid-format"]
        )
        assert result.exit_code != 0

        # Test list with invalid asset ID
        result = self.runner.invoke(
            cli, ["marketplace", "mappings", "list", "--asset-id", "invalid-uuid-format"]
        )
        assert result.exit_code != 0

        # Test list with invalid limit
        result = self.runner.invoke(cli, ["marketplace", "mappings", "list", "--limit", "0"])
        assert result.exit_code != 0

        # Test list with invalid offset
        result = self.runner.invoke(cli, ["marketplace", "mappings", "list", "--offset", "-1"])
        assert result.exit_code != 0
