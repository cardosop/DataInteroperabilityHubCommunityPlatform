"""
Unit tests for asset activation requirements.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus, DQStatus, ComplianceStatus
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus, OriginalSpecType, OriginalFormat
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetActivationTest(TestCase):
    """Test asset activation requirements"""
    
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
    
    def test_activate_asset_with_all_requirements_met(self):
        """Test activating asset with all requirements met"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user
        )
        
        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Activate asset
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], AssetStatus.ACTIVE)
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
    
    def test_activate_asset_without_valid_contract_fails(self):
        """Test that activation fails without valid contract"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Try to activate without contract
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        self.assertIn("details", response.data)
        self.assertIn("ACTIVE contract", response.data["details"][0])
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged
    
    def test_activate_asset_with_invalid_contract_validation_fails(self):
        """Test that activation fails with invalid contract validation status"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create contract with invalid validation status
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.INVALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Try to activate
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        self.assertIn("validation_status", response.data["details"][0])
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged
    
    def test_activate_asset_with_failed_dq_fails(self):
        """Test that activation fails with FAIL DQ status"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset with FAIL DQ status
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.FAIL,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user
        )
        
        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Create dataset (DQ check only applies if dataset exists)
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            created_by=self.user
        )
        
        # Try to activate
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        self.assertIn("dq_status", response.data["details"][0])
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged
    
    def test_activate_asset_with_failed_compliance_fails(self):
        """Test that activation fails with FAIL compliance status"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset with FAIL compliance status
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.FAIL,
            created_by=self.user
        )
        
        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Create dataset (compliance check only applies if dataset exists)
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            created_by=self.user
        )
        
        # Try to activate
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        self.assertIn("compliance_status", response.data["details"][0])
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged
    
    def test_activate_contract_only_asset(self):
        """Test that contract-only assets (no dataset) can be activated"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset without dataset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            # DQ and compliance status are UNKNOWN (not checked for contract-only assets)
            created_by=self.user
        )
        
        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Verify no dataset exists
        self.assertFalse(asset.datasets.exists())
        
        # Activate asset (should succeed for contract-only)
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], AssetStatus.ACTIVE)
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
    
    def test_activate_asset_optimistic_locking(self):
        """Test that activation requires correct version for optimistic locking"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user
        )
        
        # Create valid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Simulate concurrent update: increment version
        asset.increment_version()
        
        # Try to activate with old version
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": 1},  # Old version
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "ASSET_CONCURRENT_MODIFICATION")
    
    def test_activate_already_active_asset_fails(self):
        """Test that activating an already active asset fails"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset that's already active
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        # Try to activate again
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_ALREADY_ACTIVE")
    
    def test_activate_retired_asset_fails(self):
        """Test that retired assets cannot be reactivated"""
        self.client.force_authenticate(user=self.user)
        
        # Create retired asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.RETIRED,
            created_by=self.user
        )
        
        # Try to activate
        response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ASSET_RETIRED")

