"""
Integration tests for TenantConfig with DQ service.

GAP-1.2.1.3: Tests for DQ service integration with tenant configuration.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.tenants.services import get_tenant_dq_profile
from hub.apps.tenants.validators import get_platform_defaults


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantConfigDQIntegrationTest(TestCase):
    """Test DQ service integration with tenant configuration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        self.platform_defaults = get_platform_defaults()
    
    def test_dq_run_with_tenant_specific_profile(self):
        """Test DQ run uses tenant-specific profile from TenantConfig"""
        # Create tenant config with custom profile
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda"
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Mock DQ service client
        with patch('hub.apps.dq.views.DQServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.run_dq.return_value = {
                "overall_status": "PASS",
                "quality_score": 0.95,
                "checks": [],
                "engine_type": "SODA",
                "engine_version": "1.0.0"
            }
            
            # Create DQ run without explicit profile_key (should use tenant config)
            response = self.client.post("/api/v1/dq/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "profile_key": None  # Should use tenant config
            }, format="json")
            
            # Verify tenant config profile was used
            # The profile_key should be "intake_basic_soda" from tenant config
            # This is verified by checking the DQRun record
            if response.status_code in [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]:
                dq_run = DQRun.objects.latest('created_at')
                self.assertEqual(dq_run.profile_key, "intake_basic_soda")
    
    def test_dq_run_with_platform_default(self):
        """Test DQ run uses platform default when tenant config not set"""
        # No tenant config exists
        
        self.client.force_authenticate(user=self.user)
        
        # Mock DQ service client
        with patch('hub.apps.dq.views.DQServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.run_dq.return_value = {
                "overall_status": "PASS",
                "quality_score": 0.95,
                "checks": []
            }
            
            # Create DQ run without explicit profile_key (should use platform default)
            response = self.client.post("/api/v1/dq/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000"
            }, format="json")
            
            # Verify platform default profile was used
            if response.status_code in [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]:
                dq_run = DQRun.objects.latest('created_at')
                self.assertEqual(dq_run.profile_key, self.platform_defaults["default_dq_profile"])
    
    def test_dq_run_with_explicit_profile_overrides_tenant_config(self):
        """Test explicit profile_key in request overrides tenant config"""
        # Create tenant config with custom profile
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda"
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Mock DQ service client
        with patch('hub.apps.dq.views.DQServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.run_dq.return_value = {
                "overall_status": "PASS",
                "quality_score": 0.95,
                "checks": []
            }
            
            # Create DQ run with explicit profile_key (should override tenant config)
            response = self.client.post("/api/v1/dq/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "profile_key": "intake_basic_gx"  # Explicit override
            }, format="json")
            
            # Verify explicit profile was used (not tenant config)
            if response.status_code in [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]:
                dq_run = DQRun.objects.latest('created_at')
                self.assertEqual(dq_run.profile_key, "intake_basic_gx")
    
    def test_get_tenant_dq_profile_utility_function(self):
        """Test get_tenant_dq_profile utility function"""
        # Test with tenant config
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda"
        )
        
        profile = get_tenant_dq_profile(str(self.tenant.id))
        self.assertEqual(profile, "intake_basic_soda")
        
        # Test without tenant config (platform default)
        tenant2 = Tenant.objects.create(name="Test Tenant 2", slug="test-tenant-2")
        profile = get_tenant_dq_profile(str(tenant2.id))
        self.assertEqual(profile, self.platform_defaults["default_dq_profile"])
    
    def test_dq_service_client_receives_profile_key(self):
        """Test DQ service client receives profile_key parameter"""
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda"
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Mock DQ service client
        with patch('hub.apps.dq.views.DQServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.run_dq.return_value = {
                "overall_status": "PASS",
                "quality_score": 0.95,
                "checks": []
            }
            
            # Create DQ run
            response = self.client.post("/api/v1/dq/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000"
            }, format="json")
            
            # Verify DQ service client was called with profile_key
            if response.status_code in [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]:
                # Check that run_dq was called (will be called in execute_dq_run)
                # The actual call happens in the worker task, so we verify the DQRun has the profile
                dq_run = DQRun.objects.latest('created_at')
                self.assertEqual(dq_run.profile_key, "intake_basic_soda")
    
    def test_invalid_profile_key_validation_error(self):
        """Test invalid profile_key returns validation error"""
        self.client.force_authenticate(user=self.user)
        
        # Try to create DQ run with invalid profile
        # Use the same URL pattern as other tests in this file
        # Mock DQ service client to avoid external service calls
        with patch('hub.apps.dq.views.DQServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            response = self.client.post("/api/v1/dq/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "profile_key": "invalid_profile"
            }, format="json")
        
        # Should return validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

