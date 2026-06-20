"""
Integration tests for ComplianceService integration in VirtualizationService.

Tests the full integration with ComplianceService without mocks/stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.core.services.base import ValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.marketplace.models import Entitlement, EntitlementStatus, Listing
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.virtualization.models import (
    QueryType,
)
from hub.apps.virtualization.services import VirtualizationService

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualizationComplianceIntegrationTest(TestCase):
    """Integration tests for compliance service integration"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        # Set up subscription/plan for both tenants
        for t in [self.tenant, self.other_tenant]:
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
            if t.plan_id != plan.id:
                t.plan = plan
                t.save(update_fields=["plan"])
            Subscription.objects.get_or_create(
                tenant=t,
                defaults={
                    "plan": plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "current_period_start": timezone.now(),
                    "current_period_end": timezone.now(),
                },
            )

        # Create DATA_PROVIDER role and assign to user
        from hub.apps.users.models import Role, UserRole

        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def test_compliance_integration_with_compliant_asset(self):
        """Test compliance integration with compliant asset source"""
        # Create asset with compliant dataset
        from hub.apps.assets.models import AssetSourceType

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="compliant-asset",
            name="Compliant Asset",
            source_type=AssetSourceType.FEDERATED,
            compliance_status="PASS",
        )

        # Create file and dataset
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="compliant.csv",
            storage_path="test/compliant.csv",
            size=100,
            content_type="text/csv",
            status="ACTIVE",
        )

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        # Create source with asset_id
        sources = [
            {"type": "federated_asset", "asset_id": str(asset.id), "name": "compliant-source"}
        ]

        # Note: This test requires ComplianceService to be running
        # In a real integration test environment, the service would be available
        # For now, we test the integration logic structure
        try:
            dataset = self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Compliant Integration Test",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                sources=sources,
            )

            # If service is available, dataset should be created
            self.assertIsNotNone(dataset)
        except ValidationError as e:
            # If ComplianceService is not available, the production code
            # skips the check gracefully (query_service.py:654-659).
            # Service-unavailability skips are expected; real compliance
            # violations on a compliant asset are test failures.
            err = str(e).lower()
            if "unavailable" in err:
                pass  # Service unavailable — skip gracefully
            else:
                self.fail(
                    f"Compliance validation failed unexpectedly on a compliant asset: {e}"
                )

    def test_cross_tenant_access_with_entitlement(self):
        """Test cross-tenant source access with proper entitlement"""
        # Create asset in other tenant
        from hub.apps.assets.models import AssetSourceType

        other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset",
            name="Other Asset",
            source_type=AssetSourceType.FEDERATED,
            compliance_status="PASS",
        )

        # Create listing and entitlement
        from hub.apps.assets.models import AssetStatus

        other_asset.status = AssetStatus.ACTIVE
        other_asset.save()

        listing = Listing.objects.create(
            tenant=self.other_tenant,
            asset=other_asset,
            status="PUBLISHED",
            metadata_json={"title": "Other Asset Listing"},
        )

        Entitlement.objects.create(
            tenant=self.tenant, listing=listing, asset=other_asset, status=EntitlementStatus.ACTIVE
        )

        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(other_asset.id),
                "name": "cross-tenant-source",
            }
        ]

        # Should allow creation with proper entitlement
        # (ComplianceService check may be skipped if unavailable)
        try:
            dataset = self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Cross-Tenant Integration Test",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                sources=sources,
            )

            # If service is available and all checks pass, dataset should be created
            self.assertIsNotNone(dataset)
        except ValidationError as e:
            # If ComplianceService is not available, it should skip gracefully
            err = str(e).lower()
            if "cross-tenant" in err and "denied" in err:
                # This should not happen if entitlement exists
                self.fail(f"Cross-tenant access denied despite entitlement: {e}")
            # Re-raise unexpected ValidationErrors so they surface as test failures
            raise

    def test_cross_tenant_access_without_entitlement_blocked(self):
        """Test that cross-tenant access without entitlement is blocked"""
        # Create asset in other tenant
        from hub.apps.assets.models import AssetSourceType

        other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset-no-access",
            name="Other Asset No Access",
            source_type=AssetSourceType.FEDERATED,
            compliance_status="PASS",
        )

        sources = [
            {
                "type": "federated_asset",
                "asset_id": str(other_asset.id),
                "name": "cross-tenant-source-no-access",
            }
        ]

        # Should block creation without entitlement
        with self.assertRaises(ValidationError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Cross-Tenant Blocked Test",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                sources=sources,
            )

        self.assertIn("entitlement", str(cm.exception).lower())

    def test_cross_tenant_execution_isolation(self):
        """Test that tenant B cannot access tenant A's virtual dataset executions.

        Creating a virtual dataset in one tenant should not expose its
        query executions or results to a user from a different tenant.
        """
        from hub.apps.core.services.base import NotFoundError
        from hub.apps.virtualization.models import (
            QueryExecution,
            QueryExecutionStatus,
        )

        # Create asset, file, dataset in self.tenant
        from hub.apps.assets.models import AssetSourceType

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="isolation-asset",
            name="Isolation Asset",
            source_type=AssetSourceType.FEDERATED,
            compliance_status="PASS",
        )
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="isolation.csv",
            storage_path="test/isolation.csv",
            size=100,
            content_type="text/csv",
            status="ACTIVE",
        )
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        sources = [
            {"type": "federated_asset", "asset_id": str(asset.id), "name": "isolation-source"}
        ]

        # Create virtual dataset as tenant user
        vd = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Isolation Test Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=sources,
        )

        # Create a query execution in tenant A
        execution = QueryExecution.objects.create(
            virtual_dataset=vd,
            query="SELECT * FROM source",
            status=QueryExecutionStatus.COMPLETED,
            parameters={},
        )

        # Try to retrieve execution result as other_tenant user
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
        )
        other_service = VirtualizationService(
            tenant_id=str(self.other_tenant.id),
            user_id=str(other_user.id),
        )

        # get_query_result should raise NotFoundError for cross-tenant access
        with self.assertRaises(NotFoundError):
            other_service.get_query_result(
                execution_id=str(execution.id),
                tenant_id=str(self.other_tenant.id),
                format="json",
            )

    def test_execute_query_against_inactive_dataset_raises_error(self):
        """Test that executing a query on an inactive dataset raises ValidationError.

        Production code: query_service.py:1180-1184 checks
        ``dataset.status != VirtualDatasetStatus.ACTIVE`` and raises
        ``ValidationError(code="DATASET_NOT_ACTIVE")``.
        """
        from hub.apps.virtualization.models import (
            QueryExecutionMode,
            VirtualDataset,
            VirtualDatasetStatus,
        )

        # Create an INACTIVE virtual dataset
        from hub.apps.assets.models import AssetSourceType

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="inactive-ds-asset",
            name="Inactive DS Asset",
            source_type=AssetSourceType.FEDERATED,
            compliance_status="PASS",
        )
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="inactive.csv",
            storage_path="test/inactive.csv",
            size=100,
            content_type="text/csv",
            status="ACTIVE",
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Inactive Dataset",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.INACTIVE,
            sources=[{"type": "federated_asset", "asset_id": str(asset.id)}],
        )

        with self.assertRaises(ValidationError) as cm:
            self.service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        self.assertIn("not active", str(cm.exception).lower())

    def test_duplicate_virtual_dataset_name_raises_conflict(self):
        """Test that creating a dataset with duplicate (tenant, name, version)
        raises ConflictError.

        Production code: dataset_service.py:356-362 checks for existing
        (tenant_id, name, version) and raises ConflictError on collision.
        """
        from hub.apps.core.services.base import ConflictError

        # Create a real asset so source validation passes
        from hub.apps.assets.models import AssetSourceType

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="dup-check-asset",
            name="Dup Check Asset",
            source_type=AssetSourceType.FEDERATED,
            compliance_status="PASS",
        )
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="dup-check.csv",
            storage_path="test/dup-check.csv",
            size=100,
            content_type="text/csv",
            status="ACTIVE",
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "integer"}]},
        )

        sources = [
            {"type": "federated_asset", "asset_id": str(asset.id),
             "name": "dup-source"}
        ]

        # First creation should succeed
        first = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Duplicate Name Test",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=sources,
        )
        self.assertIsNotNone(first)

        # Second creation with same name + tenant should raise ConflictError
        # (version defaults to "1.0.0", so same name+version collision)
        with self.assertRaises(ConflictError):
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Duplicate Name Test",
                query="SELECT * FROM other_source",
                query_type=QueryType.SQL,
                sources=sources,
            )
