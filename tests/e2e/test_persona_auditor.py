"""
E2E tests for AUDITOR persona.

Tests that AUDITOR:
- Cannot access tenant configuration
- Read-only access to most resources
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, Role, UserRole, UserStatus
from tests.e2e.conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
User = get_user_model()


class AuditorPersonaTest(E2ETestBase):
    """E2E tests for AUDITOR persona"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create AUDITOR role
        self.auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor"}
        )
        
        # Create auditor user
        self.auditor_user = User.objects.create_user(
            email="auditor@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.auditor_user, role=self.auditor_role)
        
        # Authenticate as auditor
        self.client.force_authenticate(user=self.auditor_user)
    
    def test_auditor_cannot_get_tenant_config(self):
        """Test AUDITOR cannot GET tenant configuration"""
        response = self.client.get(f"/api/v1/tenants/tenants/{self.tenant.id}/config/")
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)
    
    def test_auditor_cannot_patch_tenant_config(self):
        """Test AUDITOR cannot PATCH tenant configuration"""
        data = {"default_dq_profile": "intake_basic_gx"}
        
        response = self.client.patch(
            f"/api/v1/tenants/tenants/{self.tenant.id}/config/",
            data,
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_auditor_can_read_contracts(self):
        """Test AUDITOR can read contracts (read-only)"""
        response = self.client.get("/api/v1/contracts/contracts/")
        
        # Should be able to read
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_auditor_cannot_create_contracts(self):
        """Test AUDITOR cannot create contracts"""
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
        
        contract_data = ContractFactoryEnhanced.create_hub_contract_json()
        
        response = self.client.post(
            "/api/v1/contracts/contracts/",
            contract_data,
            format="json"
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_auditor_cannot_update_contracts(self):
        """Test AUDITOR cannot update contracts"""
        # Create a contract first (as another user)
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
        
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user  # Use different user
        )
        
        data = {"info": {"title": "Updated Title"}}
        response = self.client.patch(
            f"/api/v1/contracts/contracts/{contract.id}/",
            data,
            format="json"
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_auditor_cannot_delete_contracts(self):
        """Test AUDITOR cannot delete contracts"""
        from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
        
        contract = ContractFactoryEnhanced.create_contract_with_all_sections(
            tenant=self.tenant,
            created_by=self.user
        )
        
        response = self.client.delete(f"/api/v1/contracts/contracts/{contract.id}/")
        
        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_auditor_can_read_dq_runs(self):
        """Test AUDITOR can read DQ runs (read-only)"""
        response = self.client.get("/api/v1/dq/runs/")
        
        # Should be able to read
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_auditor_cannot_create_dq_runs(self):
        """Test AUDITOR cannot create DQ runs"""
        data = {"contract_id": "00000000-0000-0000-0000-000000000000"}
        
        response = self.client.post(
            "/api/v1/dq/runs/",
            data,
            format="json"
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_auditor_can_read_compliance_runs(self):
        """Test AUDITOR can read compliance runs (read-only)"""
        response = self.client.get("/api/v1/compliance/runs/")
        
        # Should be able to read
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_auditor_cannot_create_compliance_runs(self):
        """Test AUDITOR cannot create compliance runs"""
        data = {"contract_id": "00000000-0000-0000-0000-000000000000"}
        
        response = self.client.post(
            "/api/v1/compliance/runs/",
            data,
            format="json"
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_auditor_can_read_audit_logs(self):
        """Test AUDITOR can read audit logs (read-only)"""
        response = self.client.get("/api/v1/audit/events/")
        
        # Should be able to read audit logs
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
    
    def test_auditor_cannot_modify_audit_logs(self):
        """Test AUDITOR cannot modify audit logs"""
        # Audit logs should be immutable
        # Try to create one (should fail)
        data = {"action": "TEST_ACTION"}
        
        response = self.client.post(
            "/api/v1/audit/events/",
            data,
            format="json"
        )
        
        # Should be forbidden or not allowed
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_404_NOT_FOUND
        ])
    
    def test_auditor_read_only_access_summary(self):
        """Test AUDITOR has read-only access to most resources"""
        # Test various read operations
        read_endpoints = [
            "/api/v1/contracts/contracts/",
            "/api/v1/dq/runs/",
            "/api/v1/compliance/runs/",
            "/api/v1/audit/events/"
        ]
        
        for endpoint in read_endpoints:
            response = self.client.get(endpoint)
            # Should be able to read (may return empty list)
            self.assertIn(response.status_code, [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND
            ])

