"""
Unit tests for DataMeshService governance integration.

Tests verify:
1. User permission checks (TENANT_ADMIN role)
2. Resource quota validation via GovernanceService
3. ABAC policy checks for domain operations
4. Tenant-level resource limits enforcement
5. Integration with GovernanceService

Note: These tests use real services (no mocks) to ensure comprehensive integration testing.
"""
import uuid
from django.test import TestCase
from django.core.cache import cache

from hub.apps.mesh.services import DataMeshService
from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.core.services.base import PermissionError, ValidationError
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.tenants.models import Tenant
from hub.apps.governance.services import GovernanceService
from hub.apps.governance.abac import ABACEngine, PolicyEvaluationResult
from hub.apps.governance.models import AccessPolicy


class DataMeshGovernanceIntegrationTest(TestCase):
    """Test governance integration in DataMeshService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.tenant_id = str(self.tenant.id)

        # Get or create roles (may already exist from tenant signals)
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant admin role"}
        )
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )

        # Create tenant admin user
        self.tenant_admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(
            user=self.tenant_admin_user,
            role=self.tenant_admin_role
        )

        # Create regular user (without TENANT_ADMIN role)
        self.regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create platform admin user
        self.platform_admin_user = User.objects.create_user(
            email=f"platform-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
            is_platform_admin=True
        )

        # Create service with tenant admin user
        self.service = DataMeshService(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

        # ABAC: create_domain requires an ALLOW policy for DATA_MESH_DOMAIN when policies exist.
        # Default deny applies when no policy matches; add tenant-wide allow for domain creation.
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Domain Creation (Test Default)",
            defaults={
                "conditions": {
                    "user": {"tenant_id": self.tenant_id},
                    "resource": {"type": "DATA_MESH_DOMAIN"},
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by_id": self.tenant_admin_user.id,
            },
        )

        # Clear cache
        cache.clear()

    def test_create_domain_with_tenant_admin_role(self):
        """Test domain creation succeeds with TENANT_ADMIN role"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="Test Domain",
            description="Test domain description"
        )

        self.assertIsNotNone(domain)
        self.assertEqual(domain.name, "Test Domain")
        self.assertEqual(domain.tenant_id, uuid.UUID(self.tenant_id))

    def test_create_domain_with_platform_admin(self):
        """Test domain creation succeeds with platform admin"""
        platform_service = DataMeshService(
            tenant_id=self.tenant_id,
            user_id=str(self.platform_admin_user.id)
        )

        domain = platform_service.create_domain(
            tenant_id=self.tenant_id,
            name="Platform Admin Domain",
            description="Created by platform admin"
        )

        self.assertIsNotNone(domain)
        self.assertEqual(domain.name, "Platform Admin Domain")

    def test_create_domain_fails_without_tenant_admin_role(self):
        """Test domain creation fails for user without TENANT_ADMIN role"""
        regular_service = DataMeshService(
            tenant_id=self.tenant_id,
            user_id=str(self.regular_user.id)
        )

        with self.assertRaises(PermissionError) as cm:
            regular_service.create_domain(
                tenant_id=self.tenant_id,
                name="Unauthorized Domain",
                description="Should fail"
            )
        self.assertIn("TENANT_ADMIN", str(cm.exception))

    def test_create_domain_fails_with_wrong_tenant(self):
        """Test domain creation fails for user from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}"
        )
        other_role, _ = Role.objects.get_or_create(
            tenant=other_tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant admin role"}
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(
            user=other_user,
            role=other_role
        )

        other_service = DataMeshService(
            tenant_id=self.tenant_id,
            user_id=str(other_user.id)
        )

        with self.assertRaises(PermissionError) as cm:
            other_service.create_domain(
                tenant_id=self.tenant_id,
                name="Cross Tenant Domain",
                description="Should fail"
            )
        self.assertIn("does not belong to tenant", str(cm.exception))

    def test_validate_resource_quota_allocation_success(self):
        """Test resource quota validation succeeds when quota is available"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

        requested_quota = {
            "storage_gb": 100,
            "compute_hours": 50
        }

        validated_quota = governance_service.validate_resource_quota_allocation(
            tenant_id=self.tenant_id,
            requested_quota=requested_quota
        )

        self.assertEqual(validated_quota, requested_quota)

    def test_validate_resource_quota_allocation_invalid_structure(self):
        """Test resource quota validation fails with invalid structure"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

        with self.assertRaises(ValidationError) as cm:
            governance_service.validate_resource_quota_allocation(
                tenant_id=self.tenant_id,
                requested_quota="not a dict"
            )
        self.assertIn("must be a dictionary", str(cm.exception))

    def test_validate_resource_quota_allocation_negative_value(self):
        """Test resource quota validation fails with negative values"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

        with self.assertRaises(ValidationError) as cm:
            governance_service.validate_resource_quota_allocation(
                tenant_id=self.tenant_id,
                requested_quota={"storage_gb": -100}
            )
        self.assertIn("cannot be negative", str(cm.exception))

    def test_check_tenant_resource_limits_within_limit(self):
        """Test tenant resource limits check succeeds when within limit"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

        requested_quota = {
            "storage_gb": 100,
            "compute_hours": 50
        }

        # Should not raise
        governance_service.check_tenant_resource_limits(
            tenant_id=self.tenant_id,
            requested_quota=requested_quota
        )

    def test_check_tenant_resource_limits_exceeded(self):
        """Test tenant resource limits check fails when limit exceeded"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

        # Create existing domain with quota
        existing_domain = DataMeshDomain.objects.create(
            tenant_id=self.tenant_id,
            name="Existing Domain",
            status=DomainStatus.ACTIVE,
            resource_quota={"storage_gb": 9000}  # 9TB used
        )

        # Request quota that would exceed limit (10TB total)
        requested_quota = {
            "storage_gb": 2000  # Would make total 11TB, exceeding 10TB limit
        }

        with self.assertRaises(ValidationError) as cm:
            governance_service.check_tenant_resource_limits(
                tenant_id=self.tenant_id,
                requested_quota=requested_quota
            )
        self.assertIn("would exceed tenant limit", str(cm.exception))
        self.assertIn("storage_gb", str(cm.exception))

    def test_create_domain_with_resource_quota_validation(self):
        """Test domain creation with resource quota validation"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="Domain With Quota",
            description="Domain with resource quota",
            resource_quota={
                "storage_gb": 500,
                "compute_hours": 100
            }
        )

        self.assertIsNotNone(domain)
        self.assertEqual(domain.resource_quota["storage_gb"], 500)
        self.assertEqual(domain.resource_quota["compute_hours"], 100)

    def test_create_domain_with_abac_policy_allow(self):
        """Test domain creation succeeds when ABAC policy allows"""
        # Create ALLOW policy for domain creation
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Domain Creation",
            conditions={
                "user": {"tenant_id": self.tenant_id},
                "resource": {"type": "DATA_MESH_DOMAIN"}
            },
            effect="ALLOW",
            priority=100,
            enabled=True,
            created_by=self.tenant_admin_user
        )

        domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="ABAC Allowed Domain",
            description="Domain allowed by ABAC policy"
        )

        self.assertIsNotNone(domain)
        self.assertEqual(domain.name, "ABAC Allowed Domain")

    def test_create_domain_with_abac_policy_deny(self):
        """Test domain creation fails when ABAC policy denies"""
        # Create DENY policy for domain creation
        deny_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny Domain Creation",
            conditions={
                "user": {"tenant_id": self.tenant_id},
                "resource": {"type": "DATA_MESH_DOMAIN"}
            },
            effect="DENY",
            priority=50,  # Higher priority (lower number)
            enabled=True,
            created_by=self.tenant_admin_user
        )

        with self.assertRaises(PermissionError) as cm:
            self.service.create_domain(
                tenant_id=self.tenant_id,
                name="ABAC Denied Domain",
                description="Should be denied by ABAC policy"
            )
        self.assertIn("ABAC policy denied", str(cm.exception))

        # Clean up
        deny_policy.delete()

    def test_create_domain_integrates_all_governance_checks(self):
        """Test domain creation integrates all governance checks"""
        # Create ALLOW policy
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Domain Creation",
            conditions={
                "user": {"tenant_id": self.tenant_id}
            },
            effect="ALLOW",
            priority=100,
            enabled=True,
            created_by=self.tenant_admin_user
        )

        domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="Fully Validated Domain",
            description="Domain with all governance checks",
            resource_quota={
                "storage_gb": 200,
                "compute_hours": 50
            }
        )

        self.assertIsNotNone(domain)
        self.assertEqual(domain.name, "Fully Validated Domain")
        self.assertIn("storage_gb", domain.resource_quota)

    def test_governance_service_check_user_permissions_tenant_admin(self):
        """Test GovernanceService.check_user_permissions_for_domain_creation with TENANT_ADMIN"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

        # Should not raise
        governance_service.check_user_permissions_for_domain_creation(
            user_id=str(self.tenant_admin_user.id),
            tenant_id=self.tenant_id
        )

    def test_governance_service_check_user_permissions_platform_admin(self):
        """Test GovernanceService.check_user_permissions_for_domain_creation with platform admin"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.platform_admin_user.id)
        )

        # Should not raise (platform admins have all permissions)
        governance_service.check_user_permissions_for_domain_creation(
            user_id=str(self.platform_admin_user.id),
            tenant_id=self.tenant_id
        )

    def test_governance_service_check_user_permissions_regular_user(self):
        """Test GovernanceService.check_user_permissions_for_domain_creation fails for regular user"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.regular_user.id)
        )

        with self.assertRaises(PermissionError) as cm:
            governance_service.check_user_permissions_for_domain_creation(
                user_id=str(self.regular_user.id),
                tenant_id=self.tenant_id
            )
        self.assertIn("TENANT_ADMIN", str(cm.exception))

    def test_governance_service_check_user_permissions_user_not_found(self):
        """Test GovernanceService.check_user_permissions_for_domain_creation fails for non-existent user"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

        fake_user_id = str(uuid.uuid4())
        with self.assertRaises(PermissionError) as cm:
            governance_service.check_user_permissions_for_domain_creation(
                user_id=fake_user_id,
                tenant_id=self.tenant_id
            )
        self.assertIn("not found", str(cm.exception))


class DataMeshGovernanceIntegrationRealServicesTest(TestCase):
    """Integration tests using real services (no mocks)"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.tenant_id = str(self.tenant.id)

        # Create role and user
        self.role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant admin role"}
        )
        self.user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.user, role=self.role)

        self.service = DataMeshService(
            tenant_id=self.tenant_id,
            user_id=str(self.user.id)
        )

        # Create ABAC policy
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Domain Creation",
            defaults={
                "conditions": {
                    "user": {"tenant_id": self.tenant_id}
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": self.user
            }
        )

        # Clear cache
        cache.clear()

    def test_create_domain_with_real_governance_services(self):
        """Test create_domain with real GovernanceService and ABACEngine (no mocks)"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="Real Services Domain",
            description="Domain created with real services",
            resource_quota={
                "storage_gb": 100,
                "compute_hours": 50
            }
        )

        self.assertIsNotNone(domain)
        self.assertEqual(domain.name, "Real Services Domain")
        self.assertEqual(domain.tenant_id, uuid.UUID(self.tenant_id))

    def test_resource_quota_validation_with_real_governance_service(self):
        """Test resource quota validation uses real GovernanceService"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.user.id)
        )

        requested_quota = {
            "storage_gb": 100,
            "compute_hours": 50
        }

        # Should succeed with real service
        validated_quota = governance_service.validate_resource_quota_allocation(
            tenant_id=self.tenant_id,
            requested_quota=requested_quota
        )

        self.assertEqual(validated_quota, requested_quota)

    def test_tenant_resource_limits_with_real_service(self):
        """Test tenant resource limits check uses real GovernanceService"""
        governance_service = GovernanceService(
            tenant_id=self.tenant_id,
            user_id=str(self.user.id)
        )

        requested_quota = {
            "storage_gb": 100
        }

        # Should succeed when within limits
        governance_service.check_tenant_resource_limits(
            tenant_id=self.tenant_id,
            requested_quota=requested_quota
        )

    def test_abac_policy_check_with_real_abac_engine(self):
        """Test ABAC policy check uses real ABACEngine"""
        # Should succeed with real ABAC engine
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=self.tenant_id,
            resource_type="DATA_MESH_DOMAIN",
            resource_id=self.tenant_id,
            access_type="WRITE"
        )

        # Result may vary based on policies, but should not raise exception
        self.assertIsNotNone(result)
        self.assertIsInstance(result, PolicyEvaluationResult)

