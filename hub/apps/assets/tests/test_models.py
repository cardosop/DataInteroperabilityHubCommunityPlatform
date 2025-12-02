"""
Unit tests for Asset model.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import (
    Asset,
    AssetStatus,
    AssetVisibility,
    DQStatus,
    ComplianceStatus,
)
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetModelTest(TestCase):
    """Test Asset model"""
    
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
    
    def test_create_asset(self):
        """Test asset creation"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.DRAFT,
            created_by=self.user
        )
        
        self.assertEqual(asset.tenant, self.tenant)
        self.assertEqual(asset.key, "test-asset")
        self.assertEqual(asset.name, "Test Asset")
        self.assertEqual(asset.status, AssetStatus.DRAFT)
        self.assertEqual(asset.dq_status, DQStatus.UNKNOWN)
        self.assertEqual(asset.compliance_status, ComplianceStatus.UNKNOWN)
    
    def test_asset_status_choices(self):
        """Test asset status enum"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
        )
        
        asset.status = AssetStatus.ACTIVE
        asset.save()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
    
    def test_asset_clean_validation(self):
        """Test asset clean() validation for ACTIVE status"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )
        
        # DRAFT status should not require validation
        asset.clean()
        
        # ACTIVE status requires active contract
        asset.status = AssetStatus.ACTIVE
        with self.assertRaises(ValidationError) as cm:
            asset.clean()
        self.assertIn("ACTIVE contract", str(cm.exception))
    
    def test_can_activate(self):
        """Test can_activate method"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.DRAFT,
        )
        
        # No contract - cannot activate
        can_activate, blockers = asset.can_activate()
        self.assertFalse(can_activate)
        self.assertGreater(len(blockers), 0)
        
        # Add valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": 1},
        )
        
        # Contract-only asset can activate
        can_activate, blockers = asset.can_activate()
        self.assertTrue(can_activate)
        self.assertEqual(len(blockers), 0)
    
    def test_increment_version(self):
        """Test increment_version method"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            version=1,
        )
        
        initial_version = asset.version
        asset.increment_version()
        asset.refresh_from_db()
        
        self.assertEqual(asset.version, initial_version + 1)

