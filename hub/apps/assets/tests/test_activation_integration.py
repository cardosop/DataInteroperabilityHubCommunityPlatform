"""
Integration tests for asset activation flow.
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
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetActivationIntegrationTest(TestCase):
    """Integration tests for complete asset activation flow"""
    
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
        
        self.client.force_authenticate(user=self.user)
    
    def test_complete_activation_flow_with_dataset(self):
        """Test complete activation flow: create asset → attach contract → attach dataset → run DQ/compliance → activate"""
        # Step 1: Create asset
        create_response = self.client.post(
            "/api/v1/assets/assets/",
            {
                "key": "test-asset",
                "name": "Test Asset",
                "description": "Test description"
            },
            format="json"
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.DRAFT)
        
        # Step 2: Create and attach contract
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
        
        # Step 3: Create file and dataset
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
        
        # Step 4: Simulate DQ and compliance runs (set statuses directly)
        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()
        
        # Step 5: Activate asset
        activate_response = self.client.post(
            f"/api/v1/assets/assets/{asset_id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activate_response.data["status"], AssetStatus.ACTIVE)
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
    
    def test_activation_flow_contract_only(self):
        """Test activation flow for contract-only asset (no dataset)"""
        # Step 1: Create asset
        create_response = self.client.post(
            "/api/v1/assets/assets/",
            {
                "key": "contract-only-asset",
                "name": "Contract Only Asset",
                "description": "Asset with contract but no dataset"
            },
            format="json"
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)
        
        # Step 2: Create and attach contract
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
        
        # Step 3: Activate asset (no dataset required)
        activate_response = self.client.post(
            f"/api/v1/assets/assets/{asset_id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activate_response.data["status"], AssetStatus.ACTIVE)
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        self.assertFalse(asset.datasets.exists())  # No dataset
    
    def test_activation_blocked_until_all_requirements_met(self):
        """Test that activation is blocked until all requirements are met"""
        # Step 1: Create asset
        create_response = self.client.post(
            "/api/v1/assets/assets/",
            {
                "key": "test-asset",
                "name": "Test Asset"
            },
            format="json"
        )
        asset_id = create_response.data["id"]
        asset = Asset.objects.get(id=asset_id)
        
        # Step 2: Try to activate without contract (should fail)
        activate_response = self.client.post(
            f"/api/v1/assets/assets/{asset_id}/activate/",
            {"version": asset.version},
            format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(activate_response.data["code"], "ASSET_ACTIVATION_BLOCKED")
        
        # Step 3: Add contract with invalid validation (should still fail)
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
        
        activate_response = self.client.post(
            f"/api/v1/assets/assets/{asset_id}/activate/",
            {"version": asset.version},
            format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Step 4: Fix contract validation (should succeed for contract-only)
        contract.validation_status = ValidationStatus.VALID
        contract.save()
        
        activate_response = self.client.post(
            f"/api/v1/assets/assets/{asset_id}/activate/",
            {"version": asset.version},
            format="json"
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activate_response.data["status"], AssetStatus.ACTIVE)
    
    def test_activation_with_warning_statuses_allowed(self):
        """Test that WARN statuses for DQ and compliance are allowed"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            dq_status=DQStatus.WARN,
            compliance_status=ComplianceStatus.WARN,
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
            validation_status=ValidationStatus.WARNING_ONLY,
            normalization_status=NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            created_by=self.user
        )
        
        # Create dataset
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
        
        # Activate should succeed with WARN statuses
        activate_response = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json"
        )
        
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(activate_response.data["status"], AssetStatus.ACTIVE)

