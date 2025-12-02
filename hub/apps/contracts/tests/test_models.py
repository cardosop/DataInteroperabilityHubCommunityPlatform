"""
Unit tests for Contract model.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import (


    Contract,
    ContractStatus,
    ValidationStatus,
    NormalizationStatus,
    OriginalSpecType,
    OriginalFormat,
)


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ContractModelTest(TestCase):
    """Test Contract model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
    def test_create_contract(self):
        """Test contract creation"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1, "id": "test"},
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.version, 1)
        self.assertEqual(contract.status, ContractStatus.DRAFT)
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODCS)
    
    def test_contract_status_choices(self):
        """Test contract status enum"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )
        
        contract.status = ContractStatus.ACTIVE
        contract.save()
        self.assertEqual(contract.status, ContractStatus.ACTIVE)
    
    def test_contract_clean_validation(self):
        """Test contract clean() validation"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
        )
        
        # DRAFT status should not require validation
        contract.clean()
        
        # ACTIVE status requires valid validation and normalization
        contract.status = ContractStatus.ACTIVE
        contract.validation_status = ValidationStatus.INVALID
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        
        with self.assertRaises(ValidationError):
            contract.clean()
    
    def test_can_activate(self):
        """Test can_activate method"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )
        
        can_activate, reason = contract.can_activate()
        self.assertTrue(can_activate)
        self.assertEqual(reason, "")
        
        # Invalid validation status
        contract.validation_status = ValidationStatus.INVALID
        contract.save()
        can_activate, reason = contract.can_activate()
        self.assertFalse(can_activate)
        self.assertIn("validation_status", reason)

