"""
Phase 23 — Marketplace demo.ckan.org fixture tests.

Tests that use get_or_create_demo_ckan_federated_asset fixture for marketplace
and virtualization flows. Uses real PULL from demo.ckan.org — no mocks or stubs.
"""
import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetSourceType
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.integrations.tests.utils.marketplace_fixtures import (
    get_or_create_demo_ckan_federated_asset,
)
from hub.apps.tenants.models import Tenant, KYCStatus

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


def _demo_ckan_reachable() -> bool:
    """Check if demo.ckan.org is reachable."""
    try:
        import httpx
        r = httpx.get("https://demo.ckan.org/api/3/action/status_show", timeout=10)
        return r.status_code == 200 and r.json().get("success") is True
    except Exception:
        return False


class MarketplaceDemoCkanFixtureTest(TestCase):
    """
    Phase 23.2: Tests using get_or_create_demo_ckan_federated_asset fixture.

    Verifies the fixture creates a federated asset from demo.ckan.org and
    that it can be reused in marketplace-related assertions.
    """

    def setUp(self):
        # Disconnect semantic signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.tenant = Tenant.objects.create(
            name="Demo CKAN Fixture Test Tenant",
            slug="demo-ckan-fixture-test-tenant",
            kyc_status=KYCStatus.VERIFIED,
        )
        from hub.apps.users.models import User, UserStatus

        self.user = User.objects.create_user(
            email="demockanfixture@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.real_virtualization_e2e
    def test_get_or_create_demo_ckan_federated_asset_creates_asset(self):
        """
        23.2 Marketplace: get_or_create_demo_ckan_federated_asset creates federated asset.
        """
        if not _demo_ckan_reachable():
            pytest.skip("demo.ckan.org unreachable")

        asset, connection = get_or_create_demo_ckan_federated_asset(
            tenant=self.tenant,
            user=self.user,
            listing_id="annakarenina",
        )

        self.assertIsNotNone(asset)
        self.assertIsNotNone(connection)
        self.assertEqual(asset.source_type, AssetSourceType.FEDERATED)
        self.assertIn("listing_id", asset.source_metadata or {})
        self.assertEqual(
            (asset.source_metadata or {}).get("listing_id"),
            "annakarenina",
        )
        self.assertEqual(connection.name, "Demo CKAN E2E Connection")

    @pytest.mark.real_virtualization_e2e
    def test_get_or_create_demo_ckan_federated_asset_reuses_existing(self):
        """
        23.2 Marketplace: get_or_create returns same asset on second call (get_or_create).
        """
        if not _demo_ckan_reachable():
            pytest.skip("demo.ckan.org unreachable")

        asset1, conn1 = get_or_create_demo_ckan_federated_asset(
            tenant=self.tenant,
            user=self.user,
            listing_id="annakarenina",
        )
        asset2, conn2 = get_or_create_demo_ckan_federated_asset(
            tenant=self.tenant,
            user=self.user,
            listing_id="annakarenina",
        )

        self.assertEqual(asset1.id, asset2.id)
        self.assertEqual(conn1.id, conn2.id)
