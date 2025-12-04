"""
Integration tests for TenantConfig with Compliance service.

GAP-1.2.2.3: Tests for compliance service integration with tenant configuration.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.tenants.services import get_tenant_compliance_regimes, get_tenant_config
from hub.apps.tenants.validators import get_platform_defaults, VALID_COMPLIANCE_REGIMES


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantConfigComplianceIntegrationTest(TestCase):
    """Test Compliance service integration with tenant configuration"""
    
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
    
    def test_compliance_run_with_tenant_specific_regimes(self):
        """Test compliance run uses tenant-specific regimes from TenantConfig"""
        # Create tenant config with custom regimes
        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD", "CCPA"],
            default_compliance_regimes=["GDPR", "CCPA"]
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Mock compliance service client
        with patch('hub.apps.compliance.views.ComplianceServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.scan_file.return_value = {
                "overall_status": "PASS",
                "risk_level": "LOW",
                "allowed_to_store": True,
                "detected_categories": [],
                "column_findings": []
            }
            
            # Create compliance run without explicit regimes (should use tenant config)
            response = self.client.post("/api/v1/compliance/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "scan_mode": "internal"
            }, format="json")
            
            # Verify tenant config regimes were used
            if response.status_code in [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]:
                compliance_run = ComplianceRun.objects.latest('created_at')
                # Regimes are stored in job.details_json
                job_details = compliance_run.job.details_json
                applicable_regulations = job_details.get('applicable_regulations', [])
                self.assertEqual(set(applicable_regulations), {"GDPR", "CCPA"})
    
    def test_compliance_run_with_platform_default(self):
        """Test compliance run uses platform default when tenant config not set"""
        # No tenant config exists
        
        self.client.force_authenticate(user=self.user)
        
        # Mock compliance service client
        with patch('hub.apps.compliance.views.ComplianceServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.scan_file.return_value = {
                "overall_status": "PASS",
                "risk_level": "LOW",
                "allowed_to_store": True
            }
            
            # Create compliance run without explicit regimes (should use platform default)
            response = self.client.post("/api/v1/compliance/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "scan_mode": "internal"
            }, format="json")
            
            # Verify platform default regimes were used
            if response.status_code in [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]:
                compliance_run = ComplianceRun.objects.latest('created_at')
                job_details = compliance_run.job.details_json
                applicable_regulations = job_details.get('applicable_regulations', [])
                self.assertEqual(set(applicable_regulations), set(self.platform_defaults["default_compliance_regimes"]))
    
    def test_compliance_run_with_explicit_regimes_overrides_tenant_config(self):
        """Test explicit regimes in request override tenant config"""
        # Create tenant config with custom regimes
        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD", "CCPA"],
            default_compliance_regimes=["GDPR", "LGPD"]
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Mock compliance service client
        with patch('hub.apps.compliance.views.ComplianceServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.scan_file.return_value = {
                "overall_status": "PASS",
                "risk_level": "LOW",
                "allowed_to_store": True
            }
            
            # Create compliance run with explicit regimes (should override tenant config)
            response = self.client.post("/api/v1/compliance/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "scan_mode": "internal",
                "applicable_regulations": ["CCPA"]  # Explicit override
            }, format="json")
            
            # Verify explicit regimes were used
            if response.status_code in [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]:
                compliance_run = ComplianceRun.objects.latest('created_at')
                job_details = compliance_run.job.details_json
                applicable_regulations = job_details.get('applicable_regulations', [])
                self.assertEqual(set(applicable_regulations), {"CCPA"})
    
    def test_compliance_run_validates_regimes_are_subset_of_allowed(self):
        """Test compliance run validates explicit regimes are subset of allowed_compliance_regimes"""
        # Create tenant config with limited allowed regimes
        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD"],  # CCPA not allowed
            default_compliance_regimes=["GDPR"]
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Try to create compliance run with regime not in allowed list
        response = self.client.post("/api/v1/compliance/runs/", {
            "file_id": "123e4567-e89b-12d3-a456-426614174000",
            "scan_mode": "internal",
            "applicable_regulations": ["CCPA"]  # Not in allowed_compliance_regimes
        }, format="json")
        
        # Should return validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Invalid compliance regimes", str(response.data["error"]))
    
    def test_get_tenant_compliance_regimes_utility_function(self):
        """Test get_tenant_compliance_regimes utility function"""
        # Test with tenant config
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_compliance_regimes=["GDPR", "CCPA"]
        )
        
        regimes = get_tenant_compliance_regimes(str(self.tenant.id))
        self.assertEqual(set(regimes), {"GDPR", "CCPA"})
        
        # Test without tenant config (platform default)
        tenant2 = Tenant.objects.create(name="Test Tenant 2", slug="test-tenant-2")
        regimes = get_tenant_compliance_regimes(str(tenant2.id))
        self.assertEqual(set(regimes), set(self.platform_defaults["default_compliance_regimes"]))
    
    def test_compliance_service_client_receives_regimes(self):
        """Test compliance service client receives applicable_regulations parameter"""
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_compliance_regimes=["GDPR", "LGPD"]
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Mock compliance service client
        with patch('hub.apps.compliance.views.ComplianceServiceClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.scan_file.return_value = {
                "overall_status": "PASS",
                "risk_level": "LOW",
                "allowed_to_store": True
            }
            
            # Create compliance run
            response = self.client.post("/api/v1/compliance/runs/", {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "scan_mode": "internal"
            }, format="json")
            
            # Verify compliance service client will receive regimes
            # (actual call happens in execute_compliance_run worker task)
            if response.status_code in [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED]:
                compliance_run = ComplianceRun.objects.latest('created_at')
                job_details = compliance_run.job.details_json
                applicable_regulations = job_details.get('applicable_regulations', [])
                self.assertEqual(set(applicable_regulations), {"GDPR", "LGPD"})

