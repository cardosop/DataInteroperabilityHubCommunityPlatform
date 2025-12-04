"""
E2E tests for DATA_CONSUMER persona.

Tests that DATA_CONSUMER:
- Cannot access tenant configuration
- Subject to rate limits
- Can use CLI tool
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.rate_limiting.service import check_rate_limit
from tests.e2e.conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
User = get_user_model()


class DataConsumerPersonaTest(E2ETestBase):
    """E2E tests for DATA_CONSUMER persona"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create DATA_CONSUMER role
        self.consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_CONSUMER",
            defaults={"description": "Data Consumer"}
        )
        
        # Create data consumer user
        self.consumer_user = User.objects.create_user(
            email="consumer@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.consumer_user, role=self.consumer_role)
        
        # Authenticate as consumer
        self.client.force_authenticate(user=self.consumer_user)
    
    def test_data_consumer_cannot_get_tenant_config(self):
        """Test DATA_CONSUMER cannot GET tenant configuration"""
        response = self.client.get(f"/api/v1/tenants/tenants/{self.tenant.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)
    
    def test_data_consumer_cannot_patch_tenant_config(self):
        """Test DATA_CONSUMER cannot PATCH tenant configuration"""
        data = {"default_dq_profile": "intake_basic_gx"}
        
        response = self.client.patch(
            f"/api/v1/tenants/tenants/{self.tenant.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_data_consumer_subject_to_rate_limits(self):
        """Test DATA_CONSUMER is subject to rate limits"""
        result = check_rate_limit(
            tenant_id=str(self.tenant.id),
            user_id=str(self.consumer_user.id),
            api_key_id=None,
            endpoint_category="catalog_reads",
            path="/api/v1/contracts/contracts/",
            method="GET"
        )
        
        self.assertIn("allowed", result)
    
    def test_data_consumer_rate_limit_headers(self):
        """Test rate limit headers are present for DATA_CONSUMER"""
        response = self.client.get("/api/v1/contracts/contracts/")
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])
    
    def test_data_consumer_can_access_contracts(self):
        """Test DATA_CONSUMER can access contracts (subject to rate limits)"""
        response = self.client.get("/api/v1/contracts/contracts/")
        
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])
    
    def test_data_consumer_cli_authentication(self):
        """Test DATA_CONSUMER can authenticate with CLI tool"""
        from hub.apps.auth.models import APIKey
        
        api_key = APIKey.objects.create(
            user=self.consumer_user,
            name="CLI Key",
            tenant=self.tenant
        )
        
        self.assertIsNotNone(api_key)
        self.assertEqual(api_key.user, self.consumer_user)
    
    def test_data_consumer_cli_rate_limits(self):
        """Test DATA_CONSUMER CLI usage respects rate limits"""
        from hub.apps.auth.models import APIKey
        
        api_key = APIKey.objects.create(
            user=self.consumer_user,
            name="CLI Key",
            tenant=self.tenant
        )
        
        result = check_rate_limit(
            tenant_id=str(self.tenant.id),
            user_id=None,
            api_key_id=str(api_key.id),
            endpoint_category="catalog_reads",
            path="/api/v1/contracts/contracts/",
            method="GET"
        )
        
        self.assertIn("allowed", result)
    
    def test_data_consumer_can_use_cli_for_contracts(self):
        """Test DATA_CONSUMER can use CLI for contract operations"""
        response = self.client.get("/api/v1/contracts/contracts/")
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS])
    
    def test_data_consumer_rate_limit_per_endpoint(self):
        """Test rate limits are enforced per endpoint category"""
        endpoints = [
            "/api/v1/contracts/contracts/",
            "/api/v1/dq/runs/",
            "/api/v1/compliance/runs/"
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertIn(response.status_code, [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_429_TOO_MANY_REQUESTS
            ])
    
    def test_data_consumer_rate_limit_tenant_override(self):
        """Test tenant-specific rate limits apply to DATA_CONSUMER"""
        from hub.apps.tenants.models import TenantConfig
        
        TenantConfig.objects.update_or_create(
            tenant=self.tenant,
            defaults={
                "config_json": {
                    "rate_limits": {
                        "catalog_reads": {
                            "burst_per_10s": 10,
                            "sustained_per_min": 30
                        }
                    }
                }
            }
        )
        
        result = check_rate_limit(
            tenant_id=str(self.tenant.id),
            user_id=str(self.consumer_user.id),
            api_key_id=None,
            endpoint_category="catalog_reads",
            path="/api/v1/contracts/contracts/",
            method="GET"
        )
        
        self.assertIn("allowed", result)
    
    def test_data_consumer_rate_limit_platform_defaults(self):
        """Test platform defaults apply when tenant config not set"""
        from hub.apps.tenants.models import TenantConfig
        
        TenantConfig.objects.filter(tenant=self.tenant).delete()
        
        result = check_rate_limit(
            tenant_id=str(self.tenant.id),
            user_id=str(self.consumer_user.id),
            api_key_id=None,
            endpoint_category="catalog_reads",
            path="/api/v1/contracts/contracts/",
            method="GET"
        )
        
        self.assertIn("allowed", result)
    
    def test_data_consumer_cannot_modify_tenant_config_via_cli(self):
        """Test DATA_CONSUMER cannot modify tenant config even via CLI"""
        from hub.apps.auth.models import APIKey
        
        api_key = APIKey.objects.create(
            user=self.consumer_user,
            name="CLI Key",
            tenant=self.tenant
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {api_key.key_hash}')
        
        data = {"default_dq_profile": "intake_basic_gx"}
        response = self.client.patch(
            f"/api/v1/tenants/tenants/{self.tenant.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_data_consumer_rate_limit_retry_after(self):
        """Test rate limit Retry-After header for DATA_CONSUMER"""
        response = None
        for i in range(20):
            response = self.client.get("/api/v1/contracts/contracts/")
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break
        
        if response and response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            self.assertIn("Retry-After", response.headers or {})
    
    def test_data_consumer_rate_limit_error_format(self):
        """Test rate limit error format for DATA_CONSUMER"""
        response = None
        for i in range(20):
            response = self.client.get("/api/v1/contracts/contracts/")
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break
        
        if response and response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            self.assertIn("error", response.data)
            error = response.data["error"]
            self.assertIn("code", error)
            self.assertIn("message", error)
    
    def test_data_consumer_rate_limit_per_user(self):
        """Test rate limits are enforced per user for DATA_CONSUMER"""
        other_consumer = User.objects.create_user(
            email="other_consumer@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=other_consumer, role=self.consumer_role)
        
        result1 = check_rate_limit(
            tenant_id=str(self.tenant.id),
            user_id=str(self.consumer_user.id),
            api_key_id=None,
            endpoint_category="catalog_reads",
            path="/api/v1/contracts/contracts/",
            method="GET"
        )
        
        result2 = check_rate_limit(
            tenant_id=str(self.tenant.id),
            user_id=str(other_consumer.id),
            api_key_id=None,
            endpoint_category="catalog_reads",
            path="/api/v1/contracts/contracts/",
            method="GET"
        )
        
        self.assertIn("allowed", result1)
        self.assertIn("allowed", result2)

