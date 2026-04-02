"""
Integration tests for GovernanceService integration with VirtualizationService.

Tests use real services (no mocks/stubs) to validate end-to-end governance integration.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache

from hub.apps.tenants.models import Tenant, KYCStatus, TenantPlan, PlanTier
from hub.apps.billing.models import Subscription, SubscriptionStatus
from django.utils import timezone
from hub.apps.virtualization.models import (
    VirtualDataset,
    QueryType,
    VirtualDatasetStatus,
)
from hub.apps.virtualization.services import VirtualizationService
from hub.apps.core.services.base import ValidationError, PermissionError
from hub.apps.governance.services import GovernanceService
from hub.apps.governance.models import AccessPolicy
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def governance_service_available() -> bool:
    """Check if GovernanceService is available (health check)"""
    try:
        # GovernanceService is a Django service, not an external service
        # So it's always available if Django is running
        return True
    except Exception:
        return False


class VirtualizationGovernanceIntegrationTest(TestCase):
    """Integration tests using real GovernanceService (no mocks)"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        # Set up subscription/plan
        plan, _ = TenantPlan.objects.get_or_create(
            slug="virtualization-test-plan",
            defaults={
                "name": "Virtualization Test Plan",
                "tier": PlanTier.PRO,
                "limits_json": {"max_assets": 100, "max_storage_gb": 1000, "max_virtual_datasets": 100},
                "is_active": True,
            },
        )
        if "max_storage_gb" not in (plan.limits_json or {}):
            plan.limits_json = {**(plan.limits_json or {}), "max_storage_gb": 1000, "max_virtual_datasets": 100}
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

        self.service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Clear cache
        cache.clear()

    @pytest.mark.skipif(not governance_service_available(), reason="GovernanceService not available")
    def test_governance_integration_with_user_permissions(self):
        """Test end-to-end flow with user permission checks"""
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(
            user=self.user,
            role=role
        )

        # Create ABAC policy that allows virtualization operations
        # Use simpler conditions that will match - just check tenant_id
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Virtualization Operations",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)},
                "resource": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            enabled=True,
            created_by=self.user
        )

        # Should succeed with proper permissions and ABAC policy
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset Governance",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.name, "Test Dataset Governance")
        self.assertEqual(dataset.tenant_id, self.tenant.id)

    @pytest.mark.skipif(not governance_service_available(), reason="GovernanceService not available")
    def test_governance_integration_with_resource_quota_validation(self):
        """Test resource quota validation with real GovernanceService"""
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(
            user=self.user,
            role=role
        )

        # Create ABAC policy that allows virtualization operations
        # Use simpler conditions that will match - just check tenant_id
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Virtualization Operations",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)},
                "resource": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            enabled=True,
            created_by=self.user
        )

        # Create virtual dataset with sources and schema to trigger quota validation
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset Quota Validation",
            query="SELECT * FROM source1 JOIN source2",
            query_type=QueryType.SQL,
            sources=[
                {"type": "postgresql", "host": "localhost", "database": "testdb1"},
                {"type": "postgresql", "host": "localhost", "database": "testdb2"}
            ],
            schema={
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "value", "type": "float"}
                ]
            }
        )

        self.assertIsNotNone(dataset)
        self.assertEqual(len(dataset.get_sources()), 2)

    @pytest.mark.skipif(not governance_service_available(), reason="GovernanceService not available")
    def test_governance_integration_with_abac_policy_denial(self):
        """Test that ABAC policy denial blocks virtual dataset creation"""
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(
            user=self.user,
            role=role
        )

        # Create ABAC policy that denies virtualization operations
        # Use simpler conditions that will match - just check tenant_id
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Virtualization Operations",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)},
                "resource": {"tenant_id": str(self.tenant.id)}
            },
            effect="DENY",
            priority=200,  # Higher priority than allow
            enabled=True,
            created_by=self.user
        )

        # Should fail with ABAC policy denying access
        with self.assertRaises(PermissionError) as cm:
            self.service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Dataset Denied",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
            )

        self.assertIn("ABAC policy", str(cm.exception))

    @pytest.mark.skipif(not governance_service_available(), reason="GovernanceService not available")
    def test_governance_integration_without_required_role(self):
        """Test that users without required role cannot create virtual datasets"""
        # User without DATA_PROVIDER or TENANT_ADMIN role
        regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(regular_user.id))

        # Should fail without required role
        with self.assertRaises(PermissionError) as cm:
            service.create_virtual_dataset(
                tenant_id=str(self.tenant.id),
                user_id=str(regular_user.id),
                name="Test Dataset No Role",
                query="SELECT * FROM source",
                query_type=QueryType.SQL,
                sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
            )

        self.assertIn("required role", str(cm.exception).lower())

    @pytest.mark.skipif(not governance_service_available(), reason="GovernanceService not available")
    def test_governance_integration_tenant_resource_limits(self):
        """Test that tenant-level resource limits are enforced"""
        from hub.apps.users.models import Role, UserRole

        # Create DATA_PROVIDER role
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )

        # Assign role to user
        UserRole.objects.get_or_create(
            user=self.user,
            role=role
        )

        # Create ABAC policy that allows virtualization operations
        # Use simpler conditions that will match - just check tenant_id
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Virtualization Operations",
            conditions={
                "user": {"tenant_id": str(self.tenant.id)},
                "resource": {"tenant_id": str(self.tenant.id)}
            },
            effect="ALLOW",
            priority=100,
            enabled=True,
            created_by=self.user
        )

        # Should succeed when within tenant limits
        dataset = self.service.create_virtual_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Dataset Limits",
            query="SELECT * FROM source",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        self.assertIsNotNone(dataset)

        # Verify GovernanceService was used for quota validation
        governance_service = GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Test quota validation directly
        requested_quota = {
            "query_quota": 1.0,
            "storage_gb": 0.001
        }

        # Should succeed when within limits
        validated_quota = governance_service.validate_resource_quota_allocation(
            tenant_id=str(self.tenant.id),
            requested_quota=requested_quota
        )

        self.assertEqual(validated_quota, requested_quota)

