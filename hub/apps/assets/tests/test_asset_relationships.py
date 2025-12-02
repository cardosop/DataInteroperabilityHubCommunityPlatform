"""
Unit tests for asset-dataset-contract relationships.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, NormalizationStatus, OriginalSpecType, OriginalFormat
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetRelationshipsTest(TestCase):
    """Test asset relationships with datasets and contracts"""
    
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
    
    def test_attach_dataset_to_asset(self):
        """Test attaching a dataset to an asset"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        # Create dataset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=file_obj,
            format="CSV",
            created_by=self.user
        )
        
        # Attach dataset to asset
        data = {"dataset_id": str(dataset.id)}
        response = self.client.post(f"/api/v1/assets/assets/{asset.id}/datasets/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["dataset_version"], 1)
        
        # Verify dataset was attached
        dataset.refresh_from_db()
        self.assertEqual(dataset.asset, asset)
        self.assertEqual(dataset.version, 1)
    
    def test_attach_multiple_datasets_to_asset(self):
        """Test attaching multiple datasets to an asset (versions)"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create files
        file1 = File.objects.create(
            tenant=self.tenant,
            name="test1.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path/file1.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2048,
            storage_path="test/path/file2.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user
        )
        
        # Create datasets
        dataset1 = Dataset.objects.create(
            tenant=self.tenant,
            file=file1,
            format="CSV",
            created_by=self.user
        )
        
        dataset2 = Dataset.objects.create(
            tenant=self.tenant,
            file=file2,
            format="CSV",
            created_by=self.user
        )
        
        # Attach first dataset
        response1 = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/datasets/",
            {"dataset_id": str(dataset1.id)},
            format="json"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data["dataset_version"], 1)
        
        # Attach second dataset
        response2 = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/datasets/",
            {"dataset_id": str(dataset2.id)},
            format="json"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data["dataset_version"], 2)
        
        # Verify both datasets are attached
        dataset1.refresh_from_db()
        dataset2.refresh_from_db()
        self.assertEqual(dataset1.asset, asset)
        self.assertEqual(dataset2.asset, asset)
        self.assertEqual(dataset1.version, 1)
        self.assertEqual(dataset2.version, 2)
    
    def test_attach_contract_to_asset(self):
        """Test attaching a contract to an asset"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            created_by=self.user
        )
        
        # Attach contract to asset
        data = {"contract_id": str(contract.id)}
        response = self.client.post(f"/api/v1/assets/assets/{asset.id}/contracts/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["contract_version"], 1)
        
        # Verify contract was attached
        contract.refresh_from_db()
        self.assertEqual(contract.asset, asset)
        self.assertEqual(contract.version, 1)
    
    def test_attach_multiple_contracts_to_asset(self):
        """Test attaching multiple contracts to an asset (versions)"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create contracts
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test1", "name": "Test1"}',
            created_by=self.user
        )
        
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test2", "name": "Test2"}',
            created_by=self.user
        )
        
        # Attach first contract
        response1 = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/contracts/",
            {"contract_id": str(contract1.id)},
            format="json"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data["contract_version"], 1)
        
        # Attach second contract
        response2 = self.client.post(
            f"/api/v1/assets/assets/{asset.id}/contracts/",
            {"contract_id": str(contract2.id)},
            format="json"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data["contract_version"], 2)
        
        # Verify both contracts are attached
        contract1.refresh_from_db()
        contract2.refresh_from_db()
        self.assertEqual(contract1.asset, asset)
        self.assertEqual(contract2.asset, asset)
        self.assertEqual(contract1.version, 1)
        self.assertEqual(contract2.version, 2)
    
    def test_activate_asset_with_valid_contract(self):
        """Test activating asset with valid contract"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
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
        data = {
            "status": AssetStatus.ACTIVE,
            "version": asset.version
        }
        response = self.client.patch(f"/api/v1/assets/assets/{asset.id}/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], AssetStatus.ACTIVE)
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
    
    def test_activate_asset_without_valid_contract_fails(self):
        """Test activating asset without valid contract fails"""
        self.client.force_authenticate(user=self.user)
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create invalid contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            validation_status=ValidationStatus.INVALID,
            created_by=self.user
        )
        
        # Try to activate asset
        data = {
            "status": AssetStatus.ACTIVE,
            "version": asset.version
        }
        response = self.client.patch(f"/api/v1/assets/assets/{asset.id}/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot activate asset", response.data["error"])
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.DRAFT)  # Status unchanged
    
    @patch('hub.apps.semantic.utils.SemanticServiceClient')
    def test_attach_contract_triggers_field_remapping(self, mock_client_class):
        """Test that attaching contract to asset triggers field remapping"""
        from hub.apps.semantic.models import SemanticResource, ResourceType
        from hub.apps.semantic.utils import remap_contract_if_needed
        
        self.client.force_authenticate(user=self.user)
        
        # Setup mock semantic service
        mock_client = MagicMock()
        mock_client.map_contract.return_value = {
            'contract_uri': 'https://hub.example.com/id/contract/test-uuid',
            'triples_count': 20,
            'semantic_status': 'OK'
        }
        mock_client_class.return_value = mock_client
        
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            created_by=self.user
        )
        
        # Create contract with hub_contract_json and schema fields, but no asset
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            hub_contract_json={
                'id': 'test',
                'name': 'Test Contract',
                'schema': {
                    'fields': [
                        {'name': 'id', 'type': 'string'},
                        {'name': 'name', 'type': 'string'}
                    ]
                }
            },
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Attach contract to asset (should trigger remapping)
        data = {"contract_id": str(contract.id)}
        response = self.client.post(f"/api/v1/assets/assets/{asset.id}/contracts/", data, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify contract was attached
        contract.refresh_from_db()
        self.assertEqual(contract.asset, asset)
        
        # Verify remapping was called with asset_uuid
        mock_client.map_contract.assert_called()
        call_args = mock_client.map_contract.call_args
        self.assertEqual(call_args[1]['asset_uuid'], str(asset.id))
        
        # Verify semantic resource was created/updated
        semantic_resource = SemanticResource.objects.filter(
            resource_type=ResourceType.CONTRACT,
            resource_id=contract.id
        ).first()
        self.assertIsNotNone(semantic_resource)

