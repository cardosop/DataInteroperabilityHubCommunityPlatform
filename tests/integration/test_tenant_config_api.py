"""
Integration tests for TenantConfig API endpoints.

Tests the full API integration including authentication, authorization,
validation, and error handling.
"""
import pytest
from datetime import timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan, PlanTier
from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.tenants.validators import get_platform_defaults, PLATFORM_MAX_RATE_LIMITS

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantConfigAPIIntegrationTest(TestCase):
    """Integration tests for TenantConfig API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create plan and tenants (subscription required for PATCH by TenantSuspensionMiddleware)
        self.plan, _ = TenantPlan.objects.get_or_create(
            slug="free",
            defaults={
                "name": "Free Plan",
                "tier": PlanTier.FREE,
                "limits_json": {},
                "is_active": True,
            },
        )
        uid = uuid.uuid4().hex[:8]
        self.tenant1 = Tenant.objects.create(
            name=f"Test Tenant 1 {uid}",
            slug=f"test-tenant-1-{uid}",
        )
        self.tenant2 = Tenant.objects.create(
            name=f"Test Tenant 2 {uid}",
            slug=f"test-tenant-2-{uid}",
        )
        self._create_subscription(self.tenant1)
        self._create_subscription(self.tenant2)
        
        # Create roles
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant1,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant1,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        
        # Create users
        self.tenant1_admin = User.objects.create_user(
            email="admin1@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.tenant1_admin, role=self.admin_role)
        
        self.tenant1_provider = User.objects.create_user(
            email="provider1@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.tenant1_provider, role=self.provider_role)
        
        # Create platform admin
        self.platform_admin = User.objects.create_user(
            email="platform@example.com",
            password="testpass123",
            tenant=None,  # Platform admin has no tenant
            status=UserStatus.ACTIVE,
            is_platform_admin=True
        )
        
        self.platform_defaults = get_platform_defaults()

    def _create_subscription(self, tenant):
        """Create active subscription for tenant (required for write operations)."""
        Subscription.objects.create(
            tenant=tenant,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
    
    # GET /api/v1/tenants/{id}/config/ tests
    def test_get_config_success_tenant_admin_own_tenant(self):
        """Test GET success: TENANT_ADMIN accessing own tenant config"""
        self.client.force_authenticate(user=self.tenant1_admin)
        
        response = self.client.get(f"/api/v1/tenants/{self.tenant1.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("default_dq_profile", response.data)
        self.assertIn("allowed_compliance_regimes", response.data)
        self.assertIn("tenant_id", response.data)
    
    def test_get_config_success_platform_admin_any_tenant(self):
        """Test GET success: Platform Admin accessing any tenant config"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(f"/api/v1/tenants/{self.tenant1.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_config_returns_platform_defaults_when_no_config(self):
        """Test GET returns platform defaults when config doesn't exist"""
        self.client.force_authenticate(user=self.tenant1_admin)
        
        response = self.client.get(f"/api/v1/tenants/{self.tenant1.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["default_dq_profile"], self.platform_defaults["default_dq_profile"])
        self.assertEqual(response.data["allowed_compliance_regimes"], self.platform_defaults["allowed_compliance_regimes"])
    
    def test_get_config_returns_tenant_specific_when_exists(self):
        """Test GET returns tenant-specific config when exists"""
        config = TenantConfig.objects.create(
            tenant=self.tenant1,
            default_dq_profile="intake_basic_soda",
            allowed_compliance_regimes=["GDPR", "LGPD"]
        )
        
        self.client.force_authenticate(user=self.tenant1_admin)
        response = self.client.get(f"/api/v1/tenants/{self.tenant1.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["default_dq_profile"], "intake_basic_soda")
        self.assertEqual(response.data["allowed_compliance_regimes"], ["GDPR", "LGPD"])
    
    def test_get_config_404_tenant_not_found(self):
        """Test GET failure: 404 when tenant doesn't exist"""
        self.client.force_authenticate(user=self.tenant1_admin)
        fake_tenant_id = uuid.uuid4()
        
        response = self.client.get(f"/api/v1/tenants/{fake_tenant_id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_get_config_403_data_provider(self):
        """Test GET failure: 403 when user lacks TENANT_ADMIN role"""
        self.client.force_authenticate(user=self.tenant1_provider)
        
        response = self.client.get(f"/api/v1/tenants/{self.tenant1.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_get_config_403_tenant_admin_other_tenant(self):
        """Test GET failure: 403 when TENANT_ADMIN accesses other tenant"""
        self.client.force_authenticate(user=self.tenant1_admin)
        
        response = self.client.get(f"/api/v1/tenants/{self.tenant2.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_get_config_401_unauthenticated(self):
        """Test GET failure: 401 when unauthenticated"""
        response = self.client.get(f"/api/v1/tenants/{self.tenant1.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    # PATCH /api/v1/tenants/{id}/config tests
    def test_patch_update_single_field(self):
        """Test PATCH success: Update single field (default_dq_profile)"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"default_dq_profile": "intake_basic_soda"}
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["default_dq_profile"], "intake_basic_soda")
        
        # Verify persisted
        config = TenantConfig.objects.get(tenant=self.tenant1)
        self.assertEqual(config.default_dq_profile, "intake_basic_soda")
    
    def test_patch_update_multiple_fields(self):
        """Test PATCH success: Update multiple fields"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {
            "default_dq_profile": "intake_basic_soda",
            "data_retention_days": 1825,
            "allowed_compliance_regimes": ["GDPR", "LGPD", "CCPA"]
        }
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = TenantConfig.objects.get(tenant=self.tenant1)
        self.assertEqual(config.default_dq_profile, "intake_basic_soda")
        self.assertEqual(config.data_retention_days, 1825)
        self.assertEqual(config.allowed_compliance_regimes, ["GDPR", "LGPD", "CCPA"])
    
    def test_patch_partial_update(self):
        """Test PATCH success: Partial update (only provided fields)"""
        # Create config with initial values
        TenantConfig.objects.create(
            tenant=self.tenant1,
            default_dq_profile="intake_basic_gx",
            data_retention_days=2555
        )
        
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"default_dq_profile": "intake_basic_soda"}  # Only update this field
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = TenantConfig.objects.get(tenant=self.tenant1)
        self.assertEqual(config.default_dq_profile, "intake_basic_soda")
        self.assertEqual(config.data_retention_days, 2555)  # Unchanged
    
    def test_patch_update_rate_limits(self):
        """Test PATCH success: Update rate_limits structure"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {
            "rate_limits": {
                "dq_runs": {
                    "burst_per_10s": 20,
                    "sustained_per_min": 60,
                    "daily_cap": 10000
                }
            }
        }
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = TenantConfig.objects.get(tenant=self.tenant1)
        self.assertEqual(config.rate_limits["dq_runs"]["burst_per_10s"], 20)
    
    def test_patch_400_invalid_dq_profile(self):
        """Test PATCH failure: 400 with invalid DQ profile"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"default_dq_profile": "invalid_profile"}
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("default_dq_profile", str(response.data))
    
    def test_patch_400_invalid_compliance_regime(self):
        """Test PATCH failure: 400 with invalid compliance regime"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"allowed_compliance_regimes": ["INVALID_REGIME"]}
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_patch_400_invalid_data_retention_days_minimum(self):
        """Test PATCH failure: 400 with data retention days below minimum"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"data_retention_days": 89}  # Below minimum of 90
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_patch_400_invalid_data_retention_days_maximum(self):
        """Test PATCH failure: 400 with data retention days above maximum"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"data_retention_days": 3651}  # Above maximum of 3650
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_patch_400_rate_limits_exceed_platform_maximums(self):
        """Test PATCH failure: 400 with rate limits exceeding platform maximums"""
        self.client.force_authenticate(user=self.tenant1_admin)
        platform_max = PLATFORM_MAX_RATE_LIMITS["dq_runs"]
        data = {
            "rate_limits": {
                "dq_runs": {
                    "burst_per_10s": platform_max["burst_per_10s"] + 100  # Exceeds max
                }
            }
        }
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_patch_400_default_compliance_regimes_not_subset(self):
        """Test PATCH failure: 400 with default_compliance_regimes not subset of allowed"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {
            "allowed_compliance_regimes": ["GDPR", "LGPD"],
            "default_compliance_regimes": ["GDPR", "CCPA"]  # CCPA not in allowed
        }
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_patch_403_unauthorized_access(self):
        """Test PATCH failure: 403 unauthorized access"""
        self.client.force_authenticate(user=self.tenant1_provider)
        data = {"default_dq_profile": "intake_basic_soda"}
        
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant1.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_patch_404_tenant_not_found(self):
        """Test PATCH failure: 404 tenant not found"""
        self.client.force_authenticate(user=self.tenant1_admin)
        fake_tenant_id = uuid.uuid4()
        data = {"default_dq_profile": "intake_basic_soda"}
        
        response = self.client.patch(
            f"/api/v1/tenants/{fake_tenant_id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

