"""
Unit tests for contract status lifecycle rules.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    ValidationStatus,
    NormalizationStatus,
    OriginalSpecType,
    OriginalFormat
)
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class ContractStatusRulesTest(TestCase):
    """Test contract status lifecycle rules"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_contract_can_activate_with_valid_status(self):
        """Test that contract can be activated with VALID validation status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        can_activate, reason = contract.can_activate()
        self.assertTrue(can_activate)
        self.assertEqual(reason, "")
    
    def test_contract_can_activate_with_warning_only(self):
        """Test that contract can be activated with WARNING_ONLY validation status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            created_by=self.user
        )
        
        can_activate, reason = contract.can_activate()
        self.assertTrue(can_activate)
    
    def test_contract_cannot_activate_with_invalid_validation(self):
        """Test that contract cannot be activated with INVALID validation status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("validation_status", reason)
    
    def test_contract_cannot_activate_with_failed_normalization(self):
        """Test that contract cannot be activated with failed normalization"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZATION_FAILED,
            created_by=self.user
        )
        
        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("normalization_status", reason)
    
    def test_activate_contract_via_api_success(self):
        """Test activating a contract via API when requirements are met"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        data = {"status": ContractStatus.ACTIVE}
        response = self.client.patch(f"/api/v1/contracts/contracts/{contract.id}/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ContractStatus.ACTIVE)
        
        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.ACTIVE)
    
    def test_activate_contract_via_api_failure(self):
        """Test activating a contract via API when requirements are not met"""
        self.client.force_authenticate(user=self.user)
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        data = {"status": ContractStatus.ACTIVE}
        response = self.client.patch(f"/api/v1/contracts/contracts/{contract.id}/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("validation_status", response.data["error"])
        
        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.DRAFT)  # Status unchanged
    
    def test_draft_contract_can_have_any_validation_status(self):
        """Test that DRAFT contracts can have any validation status"""
        # DRAFT with null validation_status
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=None,
            created_by=self.user
        )
        contract1.full_clean()  # Should not raise
        
        # DRAFT with INVALID validation_status
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            validation_status=ValidationStatus.INVALID,
            created_by=self.user
        )
        contract2.full_clean()  # Should not raise

