"""
Phase 21 — Virtualization Federated Asset E2E Tests.

E2E tests for virtualization against real federated assets created from
demo.ckan.org (PULL → federated asset → virtual dataset → execute query).
No mocks or stubs; uses real CKAN API and real virtualization code paths.
"""
import unittest
import uuid

import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache

from hub.apps.tenants.models import Tenant, KYCStatus, TenantPlan, PlanTier
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.virtualization.models import (
    VirtualDataset,
    QueryType,
    VirtualDatasetStatus,
    QueryExecutionStatus,
    QueryExecutionMode,
)
from hub.apps.virtualization.services import VirtualizationService
from hub.apps.core.services.base import ValidationError

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

# CKAN instances to try for CSV row-count test (21.2)
CKAN_BASE_URLS = [
    "https://demo.ckan.org",
    "https://data.gov",
]


def _demo_ckan_reachable() -> bool:
    """Check if demo.ckan.org is reachable."""
    try:
        import httpx
        r = httpx.get("https://demo.ckan.org/api/3/action/status_show", timeout=10)
        return r.status_code == 200 and r.json().get("success") is True
    except Exception:
        return False


def _find_ckan_package_with_downloadable_csv():
    """
    Find a CKAN package with a CSV resource that can be downloaded.
    Returns (base_url, listing_id, resource_id) or (None, None, None).
    """
    from hub.apps.integrations.factory import MarketplaceConnectorFactory
    from hub.apps.integrations.base import MarketplaceType

    for base_url in CKAN_BASE_URLS:
        try:
            connector = MarketplaceConnectorFactory.create_connector(
                MarketplaceType.CKAN_INSTANCE,
                config={"base_url": base_url},
            )
            listings = connector.list_listings(limit=20)
            for listing in listings or []:
                try:
                    resources = connector.list_resources(listing.marketplace_id)
                except Exception:
                    continue
                for res in resources or []:
                    if not res.url or not str(res.format or "").upper().startswith("CSV"):
                        continue
                    # Try to download
                    try:
                        import tempfile
                        import os
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                            tmp_path = tmp.name
                        try:
                            connector.download_resource(res.resource_id, tmp_path)
                            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                                return (base_url, listing.marketplace_id, res.resource_id)
                        finally:
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                    except Exception:
                        continue
        except Exception:
            continue
    return (None, None, None)


class VirtualizationFederatedAssetE2ETest(TestCase):
    """
    Phase 21 E2E: PULL from demo.ckan.org → federated asset → virtual dataset → execute query.

    Skip conditions:
    - demo.ckan.org unreachable
    - No CKAN package with downloadable CSV (for 21.2 only)
    """

    def setUp(self):
        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Federated E2E Test Tenant {_uid}",
            slug=f"federated-e2e-test-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"federatede2e-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        from hub.apps.users.models import Role, UserRole

        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        # Set up subscription/plan
        from django.utils import timezone
        plan, _ = TenantPlan.objects.get_or_create(
            slug="virtualization-test-plan",
            defaults={
                "name": "Virtualization Test Plan",
                "tier": PlanTier.PRO,
                "limits_json": {
                    "max_assets": 100,
                    "max_storage_gb": 1000,
                    "max_virtual_datasets": 100,
                },
                "is_active": True,
            },
        )
        if "max_storage_gb" not in (plan.limits_json or {}):
            plan.limits_json = {
                **(plan.limits_json or {}),
                "max_storage_gb": 1000,
                "max_virtual_datasets": 100,
            }
            plan.save(update_fields=["limits_json"])
        if self.tenant.plan_id != plan.id:
            self.tenant.plan = plan
            self.tenant.save(update_fields=["plan"])
        Subscription.objects.get_or_create(
            tenant=self.tenant,
            defaults={
                "plan": plan,
                "status": SubscriptionStatus.ACTIVE,
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now(),
            },
        )

        self.virt_service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        cache.clear()

    @pytest.mark.integration
    @pytest.mark.real_virtualization_e2e
    def test_e2e_pull_from_demo_ckan_create_federated_asset_virtual_dataset_execute_query(self):
        """
        21.1 E2E: PULL from demo.ckan.org → create federated asset → create virtual dataset → execute query.

        Flow:
        1. Create marketplace connection to demo.ckan.org
        2. Get listing via connector.get_listing()
        3. Map to hub asset via connector.map_to_hub_asset()
        4. Create federated asset via create_federated_asset_with_contracts()
        5. Create virtual dataset with federated_asset source
        6. Execute query via VirtualizationService
        7. Assert execution COMPLETED and result has expected structure
        """
        if not _demo_ckan_reachable():
            raise unittest.SkipTest("demo.ckan.org unreachable")

        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.base import MarketplaceType
        from hub.apps.integrations.models import MarketplaceConnection
        from hub.apps.integrations.services import MarketplaceIntegrationService

        # 1. Create marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            name="Demo CKAN E2E Connection",
            config={"base_url": "https://demo.ckan.org"},
            is_active=True,
        )

        # 2. Get listing (use annakarenina - known package on demo.ckan.org)
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config={"base_url": "https://demo.ckan.org"},
        )
        try:
            listing = connector.get_listing("annakarenina")
        except Exception as e:
            # Fallback: get any listing from package_list
            try:
                listings = connector.list_listings(limit=5)
                if not listings:
                    raise unittest.SkipTest(f"No listings from demo.ckan.org: {e}")
                listing = connector.get_listing(listings[0].marketplace_id)
            except Exception as e2:
                raise unittest.SkipTest(f"Cannot get listing from demo.ckan.org: {e2}")

        # 3. Map to hub asset
        mapping = connector.map_to_hub_asset(listing)

        # 4. Create federated asset (METADATA_ONLY - no download)
        integration_service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        asset = integration_service.create_federated_asset_with_contracts(
            asset_mapping=mapping,
            connection=connection,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="METADATA_ONLY",
        )

        # 5. Create virtual dataset with federated_asset source
        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Federated E2E Virtual Dataset",
            query="SELECT * FROM metadata",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[
                {
                    "type": "federated_asset",
                    "asset_id": str(asset.id),
                    "query": "SELECT * FROM metadata",
                }
            ],
        )

        # 6. Execute query
        try:
            execution = self.virt_service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except ValidationError as e:
            pytest.fail(f"Query execution failed: {e}")

        # 7. Assert
        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, vd.id)
        self.assertEqual(
            execution.status,
            QueryExecutionStatus.COMPLETED,
            f"Expected COMPLETED, got {execution.status}. Log: {getattr(execution, 'execution_log', '')}",
        )

        result = self.virt_service.get_query_result(
            execution_id=str(execution.id), format="json"
        )
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertGreaterEqual(len(result["data"]), 1)
        self.assertIn("total_count", result)
        self.assertGreaterEqual(result["total_count"], 1)

    @pytest.mark.integration
    @pytest.mark.real_virtualization_e2e
    def test_e2e_using_demo_ckan_fixture_virtual_dataset_execute_query(self):
        """
        23.2 Virtualization: Use get_or_create_demo_ckan_federated_asset fixture → virtual dataset → execute query.

        Uses the shared marketplace fixture from tests/fixtures/marketplace/ to create
        a federated asset from demo.ckan.org (annakarenina), then runs virtualization E2E.
        """
        if not _demo_ckan_reachable():
            raise unittest.SkipTest("demo.ckan.org unreachable")

        from hub.apps.integrations.tests.utils.marketplace_fixtures import (
            get_or_create_demo_ckan_federated_asset,
        )

        asset, _ = get_or_create_demo_ckan_federated_asset(
            tenant=self.tenant,
            user=self.user,
            listing_id="annakarenina",
        )

        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Fixture Federated E2E Virtual Dataset",
            query="SELECT * FROM metadata",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[
                {
                    "type": "federated_asset",
                    "asset_id": str(asset.id),
                    "query": "SELECT * FROM metadata",
                }
            ],
        )

        try:
            execution = self.virt_service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except ValidationError as e:
            pytest.fail(f"Query execution failed: {e}")

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, vd.id)
        self.assertEqual(
            execution.status,
            QueryExecutionStatus.COMPLETED,
            f"Expected COMPLETED, got {execution.status}. Log: {getattr(execution, 'execution_log', '')}",
        )

        result = self.virt_service.get_query_result(
            execution_id=str(execution.id), format="json"
        )
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertGreaterEqual(len(result["data"]), 1)
        self.assertIn("total_count", result)
        self.assertGreaterEqual(result["total_count"], 1)

    @pytest.mark.integration
    @pytest.mark.real_virtualization_e2e
    def test_ckan_package_csv_row_count(self):
        """
        21.2 Use CKAN package with real CSV resource; assert row count in virtualization result.

        Tries demo.ckan.org and data.gov for a package with downloadable CSV.
        Creates federated asset with DOWNLOAD_SELECTIVE, virtual dataset, executes query,
        asserts row_count > 0.

        Skip conditions:
        - No CKAN package with downloadable CSV resource found
        - CKAN service not reachable
        """
        # Check if CKAN is reachable before attempting the slow search
        try:
            import httpx
            resp = httpx.get(
                "https://demo.ckan.org/api/3/action/status_show",
                timeout=5,
            )
            if resp.status_code != 200:
                raise unittest.SkipTest("CKAN service not reachable")
        except Exception:
            raise unittest.SkipTest("CKAN service not reachable")

        base_url, listing_id, resource_id = _find_ckan_package_with_downloadable_csv()
        if not base_url or not listing_id or not resource_id:
            raise unittest.SkipTest(
                "No CKAN package with downloadable CSV resource found "
                f"(tried: {', '.join(CKAN_BASE_URLS)})"
            )

        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.base import MarketplaceType
        from hub.apps.integrations.models import MarketplaceConnection
        from hub.apps.integrations.services import MarketplaceIntegrationService

        # Create connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            name="CKAN CSV E2E Connection",
            config={"base_url": base_url},
            is_active=True,
        )

        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config={"base_url": base_url},
        )
        listing = connector.get_listing(listing_id)
        mapping = connector.map_to_hub_asset(listing)

        integration_service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        asset = integration_service.create_federated_asset_with_contracts(
            asset_mapping=mapping,
            connection=connection,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            data_strategy="DOWNLOAD_SELECTIVE",
            download_resources=[resource_id],
            skip_semantic_mapping=True,
        )

        # Virtual dataset with resource_id to target the CSV.
        # "SELECT * FROM data" returns all CSV rows via virtualization file-content path.
        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="CKAN CSV Row Count Dataset",
            query="SELECT * FROM data",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[
                {
                    "type": "federated_asset",
                    "asset_id": str(asset.id),
                    "resource_id": resource_id,
                    "query": "SELECT * FROM data",
                }
            ],
        )

        try:
            execution = self.virt_service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except ValidationError as e:
            pytest.fail(f"Query execution failed: {e}")

        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)

        result = self.virt_service.get_query_result(
            execution_id=str(execution.id), format="json"
        )
        self.assertIn("total_count", result)
        self.assertGreater(
            result["total_count"],
            0,
            f"Expected total_count > 0, got {result.get('total_count')}. "
            "Virtualization should return actual CSV rows when DOWNLOAD_SELECTIVE and resource is downloadable.",
        )
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertGreater(len(result["data"]), 0)
