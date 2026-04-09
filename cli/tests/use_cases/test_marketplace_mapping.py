"""
End-to-end tests for marketplace mapping workflows.

These tests verify complete workflows from start to finish:
- List mappings → Get mapping → Delete mapping
- List with filters → Get details → Verify deletion
"""
import pytest
import json
from click.testing import CliRunner
from django.test import LiveServerTestCase
from django.contrib.auth import get_user_model
from datahub_cli.main import cli
from datahub_cli.config import config

# Import Django models
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceType
)

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

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="CLI Mapping E2E Test Tenant",
            slug="cli-mapping-e2e-test-tenant"
        )

        # Create user with ACTIVE status
        self.user = User.objects.create_user(
            email="cli-mapping-e2e@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create DATA_PROVIDER role and assign to user
        from hub.apps.users.models import Role, UserRole
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"}
        )
        UserRole.objects.create(
            user=self.user,
            role=data_provider_role
        )

        # Set API base URL to live test server
        self.api_base_url = f'{self.live_server_url}/api/v1'
        config.set_api_base_url(self.api_base_url)

        # Create API key for testing with required scopes
        from hub.apps.auth.models import APIKey
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        api_key_obj = APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="CLI Mapping E2E Test Key",
            key_hash=key_hash,
            scopes=["integrations:write", "integrations:read"]
        )
        config.set_api_key(plaintext_key)
        self.api_key = plaintext_key

        # Create connection and assets for testing
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            name="E2E Test Connection",
            config={"base_url": "https://demo.ckan.org"},
            is_active=True,
            created_by=self.user
        )

        self.asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="e2e-test-asset-1",
            name="E2E Test Asset 1",
            status=AssetStatus.ACTIVE,
            source_type="HUB_NATIVE",
            created_by=self.user
        )

        self.asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="e2e-test-asset-2",
            name="E2E Test Asset 2",
            status=AssetStatus.ACTIVE,
            source_type="HUB_NATIVE",
            created_by=self.user
        )

    def tearDown(self):
        """Clean up after tests"""
        super().tearDown()
        config.clear_auth()

    def test_complete_mapping_workflow_list_get_delete(self):
        """Test complete workflow: list → get → delete"""
        # Create a mapping
        mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset1,
            external_listing_id="E2E_TEST_LISTING_1",
            external_resource_ids=["RESOURCE_1", "RESOURCE_2"],
            sync_metadata={
                "last_sync_status": "SUCCESS",
                "last_sync_errors": []
            }
        )

        try:
            # Step 1: List mappings
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'list',
                '--format', 'json'
            ])
            assert result.exit_code == 0, f"List failed: {result.output}"
            list_data = json.loads(result.output)

            # Verify mapping is in the list
            if isinstance(list_data, dict):
                mappings = list_data.get('results', [])
            else:
                mappings = list_data

            mapping_ids = [m.get('id') for m in mappings]
            assert str(mapping.id) in mapping_ids, "Mapping not found in list"

            # Step 2: Get mapping details
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'get',
                str(mapping.id),
                '--format', 'json'
            ])
            assert result.exit_code == 0, f"Get failed: {result.output}"
            get_data = json.loads(result.output)

            # Verify details
            assert get_data['id'] == str(mapping.id)
            assert get_data['external_listing_id'] == "E2E_TEST_LISTING_1"
            assert get_data['hub_asset']['id'] == str(self.asset1.id)
            assert get_data['hub_asset']['name'] == "E2E Test Asset 1"
            assert get_data['connection']['id'] == str(self.connection.id)
            assert len(get_data.get('external_resource_ids', [])) == 2

            # Step 3: Delete mapping
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'delete',
                str(mapping.id)
            ])
            assert result.exit_code == 0, f"Delete failed: {result.output}"
            assert 'deleted successfully' in result.output.lower()

            # Step 4: Verify mapping is deleted (get should fail)
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'get',
                str(mapping.id)
            ])
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
            external_resource_ids=[]
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset2,
            external_listing_id="FILTER_TEST_2",
            external_resource_ids=[]
        )

        try:
            # Test filter by connection
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'list',
                '--connection-id', str(self.connection.id),
                '--format', 'json'
            ])
            assert result.exit_code == 0
            list_data = json.loads(result.output)
            if isinstance(list_data, dict):
                mappings = list_data.get('results', [])
            else:
                mappings = list_data
            mapping_ids = [m.get('id') for m in mappings]
            assert str(mapping1.id) in mapping_ids
            assert str(mapping2.id) in mapping_ids

            # Test filter by asset
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'list',
                '--asset-id', str(self.asset1.id),
                '--format', 'json'
            ])
            assert result.exit_code == 0
            list_data = json.loads(result.output)
            if isinstance(list_data, dict):
                mappings = list_data.get('results', [])
            else:
                mappings = list_data
            mapping_ids = [m.get('id') for m in mappings]
            assert str(mapping1.id) in mapping_ids
            assert str(mapping2.id) not in mapping_ids

            # Test pagination
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'list',
                '--limit', '1',
                '--offset', '0',
                '--format', 'json'
            ])
            assert result.exit_code == 0
            list_data = json.loads(result.output)
            if isinstance(list_data, dict):
                mappings = list_data.get('results', [])
            else:
                mappings = list_data
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
            external_resource_ids=[]
        )

        try:
            # Test list with table output
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'list'
            ])
            assert result.exit_code == 0
            assert 'TABLE_TEST_LISTING' in result.output or 'No mappings found' in result.output

            # Test get with table output
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'get',
                str(mapping.id)
            ])
            assert result.exit_code == 0
            assert str(mapping.id) in result.output
            assert 'TABLE_TEST_LISTING' in result.output
            assert 'E2E Test Asset 1' in result.output

            # Test delete with table output
            result = self.runner.invoke(cli, [
                'marketplace', 'mappings', 'delete',
                str(mapping.id)
            ])
            assert result.exit_code == 0
            assert 'deleted successfully' in result.output.lower()

        finally:
            # Clean up if mapping still exists
            if MarketplaceMapping.objects.filter(id=mapping.id).exists():
                MarketplaceMapping.objects.filter(id=mapping.id).delete()

    def test_mapping_workflow_error_handling(self):
        """Test error handling in mapping workflows"""
        # Test get with invalid ID
        result = self.runner.invoke(cli, [
            'marketplace', 'mappings', 'get',
            'invalid-uuid-format'
        ])
        assert result.exit_code != 0

        # Test delete with invalid ID
        result = self.runner.invoke(cli, [
            'marketplace', 'mappings', 'delete',
            'invalid-uuid-format'
        ])
        assert result.exit_code != 0

        # Test list with invalid connection ID
        result = self.runner.invoke(cli, [
            'marketplace', 'mappings', 'list',
            '--connection-id', 'invalid-uuid-format'
        ])
        assert result.exit_code != 0

        # Test list with invalid asset ID
        result = self.runner.invoke(cli, [
            'marketplace', 'mappings', 'list',
            '--asset-id', 'invalid-uuid-format'
        ])
        assert result.exit_code != 0

        # Test list with invalid limit
        result = self.runner.invoke(cli, [
            'marketplace', 'mappings', 'list',
            '--limit', '0'
        ])
        assert result.exit_code != 0

        # Test list with invalid offset
        result = self.runner.invoke(cli, [
            'marketplace', 'mappings', 'list',
            '--offset', '-1'
        ])
        assert result.exit_code != 0
