"""
Minimal test to debug timeout issues during asset and contract creation.
"""

import json
import time
import uuid

from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, OriginalFormat
from hub.apps.semantic.signals import asset_saved, contract_saved
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.tenants.signals import create_default_roles
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import Role, UserRole
from tests.fixtures.test_data_factories import TenantFactory, UserFactory


class MinimalTimeoutTest(TestCase):
    """Minimal integration test for asset + contract creation workflow."""

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disconnect signals that trigger external service calls during test setup
        post_save.disconnect(contract_saved, sender=Contract)
        post_save.disconnect(asset_saved, sender=Asset)
        post_save.disconnect(create_default_roles, sender=Tenant)

    @classmethod
    def tearDownClass(cls):
        # Reconnect signals after all tests in this class complete
        post_save.connect(contract_saved, sender=Contract)
        post_save.connect(asset_saved, sender=Asset)
        post_save.connect(create_default_roles, sender=Tenant)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        unique_id = str(uuid.uuid4())[:8]
        self.tenant = TenantFactory.create_tenant(
            name=f"Minimal Test Tenant {unique_id}",
            slug=f"minimal-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )

        self.user = UserFactory.create_user(
            tenant=self.tenant, email=f"minimal-{unique_id}@test.com"
        )
        UserRole.objects.get_or_create(user=self.user, role=self.role)
        self.client.force_authenticate(user=self.user)
        ensure_user_has_data_provider_role(self.user)

    def test_minimal_asset_creation(self):
        """Test minimal asset creation and contract attachment."""
        start = time.time()

        # Create asset
        asset_data = {
            "key": "minimal-asset",
            "name": "Minimal Asset",
            "description": "Test",
            "domain": "sales",
        }
        asset_response = self.client.post(reverse("asset-list"), asset_data, format="json")
        elapsed = time.time() - start
        print(f"Asset creation took {elapsed:.3f}s, status: {asset_response.status_code}")

        self.assertEqual(asset_response.status_code, 201,
            f"Asset creation failed: {asset_response.data}")
        asset_id = asset_response.data["id"]
        self.assertIsNotNone(asset_id, "Asset ID should be present in response")
        print(f"Asset created: {asset_id}")

        # Create contract linked to the asset
        sample_contract = {
            "id": "orders",
            "info": {
                "name": "Customer Orders",
                "title": "Customer Orders",
                "owners": [{"name": "Data Platform Team", "email": "dataplatform@example.com"}],
                "tags": ["analytics", "sales"],
            },
            "schema": {
                "fields": [
                    {"name": "order_id", "type": "string", "required": True},
                ]
            },
        }
        contract_data = {
            "original_raw": json.dumps(sample_contract),
            "original_format": OriginalFormat.JSON.value,
            "asset_id": asset_id,
        }
        contract_start = time.time()
        contract_response = self.client.post(reverse("contract-list"), contract_data, format="json")
        contract_elapsed = time.time() - contract_start
        print(f"Contract creation took {contract_elapsed:.3f}s, status: {contract_response.status_code}")

        self.assertEqual(contract_response.status_code, 201,
            f"Contract creation failed: {contract_response.data}")
        contract_id = contract_response.data["id"]
        self.assertIsNotNone(contract_id, "Contract ID should be present in response")
        print(f"Contract created: {contract_id}")

        total_elapsed = time.time() - start
        print(f"Test complete in {total_elapsed:.3f}s")
