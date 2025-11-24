"""
End-to-End tests for data-first onboarding flow (T.12).

Tests complete user journey from file upload to asset activation.
"""
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset

User = get_user_model()


class DataFirstE2ETest(TestCase):
    """E2E tests for data-first onboarding flow (T.12)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        self.client.force_authenticate(user=self.user)
    
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient.scan_file')
    @patch('hub.apps.dq.service_client.DQServiceClient.run_dq')
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.validate')
    @patch('hub.apps.files.views.S3StorageClient')
    @patch('hub.apps.datasets.views.boto3')
    def test_complete_data_first_journey(self, mock_boto3, mock_storage, mock_validate, mock_dq, mock_compliance):
        """Test complete data-first onboarding journey"""
        # Mock external services
        mock_compliance.return_value = {
            'overall_status': 'PASS',
            'risk_level': 'LOW',
            'allowed_to_store': True
        }
        
        mock_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95
        }
        
        mock_validate.return_value = {
            'validation_status': 'VALID',
            'issues': []
        }
        
        # Mock S3 storage
        mock_storage.return_value.file_exists.return_value = True
        mock_storage.return_value.get_file_size.return_value = 1024
        
        # Mock S3 download for dataset creation
        mock_s3 = Mock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: b'col1,col2\nval1,val2\nval3,val4')
        }
        
        # Step 1: Create asset
        asset_response = self.client.post(
            '/api/v1/assets/assets/',
            {
                'key': 'customer-orders',
                'name': 'Customer Orders',
                'description': 'Customer order data',
                'domain': 'sales',
                'visibility': 'INTERNAL'
            },
            format='json'
        )
        self.assertEqual(asset_response.status_code, status.HTTP_201_CREATED)
        asset_id = asset_response.data['id']
        
        # Step 2: Initialize file upload
        file_init_response = self.client.post(
            '/api/v1/files/files/init/',
            {
                'name': 'orders.csv',
                'content_type': 'text/csv',
                'size': 1024
            },
            format='json'
        )
        self.assertEqual(file_init_response.status_code, status.HTTP_201_CREATED)
        file_id = file_init_response.data['file_id']
        
        # Step 3: Complete file upload (simulating S3 upload)
        file_complete_response = self.client.post(
            f'/api/v1/files/files/{file_id}/complete/',
            {
                'content_sha256': 'abc123def456'
            },
            format='json'
        )
        self.assertEqual(file_complete_response.status_code, status.HTTP_200_OK)
        
        # Step 4: Create dataset (triggers schema inference)
        dataset_response = self.client.post(
            '/api/v1/datasets/datasets/',
            {
                'file_id': file_id,
                'asset_id': asset_id
            },
            format='json'
        )
        self.assertEqual(dataset_response.status_code, status.HTTP_201_CREATED)
        dataset_id = dataset_response.data['id']
        
        # Verify schema was inferred
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertIsNotNone(dataset.schema_json)
        
        # Step 5: Run compliance check (fail-closed gate)
        compliance_response = self.client.post(
            '/api/v1/compliance/compliance-runs/',
            {
                'file_id': file_id,
                'dataset_id': dataset_id,
                'asset_id': asset_id,
                'scan_mode': 'internal'
            },
            format='json'
        )
        self.assertEqual(compliance_response.status_code, status.HTTP_201_CREATED)
        
        # Step 6: Run DQ check
        dq_response = self.client.post(
            '/api/v1/dq/dq-runs/',
            {
                'file_id': file_id,
                'dataset_id': dataset_id,
                'asset_id': asset_id,
                'profile_key': 'intake_basic_gx'
            },
            format='json'
        )
        self.assertEqual(dq_response.status_code, status.HTTP_201_CREATED)
        
        # Step 7: Create contract from inferred schema
        contract_response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'asset_id': asset_id,
                'original_raw': '{"id": "customer-orders", "name": "Customer Orders", "schema": {"fields": [{"name": "col1", "type": "string"}, {"name": "col2", "type": "string"}]}}',
                'original_format': 'JSON',
                'original_spec_type': 'ODCS'
            },
            format='json'
        )
        self.assertEqual(contract_response.status_code, status.HTTP_201_CREATED)
        contract_id = contract_response.data['id']
        
        # Step 8: Validate contract
        validate_response = self.client.post(
            f'/api/v1/contracts/contracts/{contract_id}/validate/',
            {'async': False},
            format='json'
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(validate_response.data['validation_status'], 'VALID')
        
        # Step 9: Attach dataset and contract to asset
        attach_dataset_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/datasets/',
            {'dataset_id': dataset_id},
            format='json'
        )
        self.assertEqual(attach_dataset_response.status_code, status.HTTP_200_OK)
        
        attach_contract_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/contracts/',
            {'contract_id': contract_id},
            format='json'
        )
        self.assertEqual(attach_contract_response.status_code, status.HTTP_200_OK)
        
        # Step 10: Update contract status to ACTIVE
        contract = Contract.objects.get(id=contract_id)
        contract.status = ContractStatus.ACTIVE
        from hub.apps.contracts.models import NormalizationStatus
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        contract.save()
        
        # Step 11: Update asset DQ and compliance status
        asset = Asset.objects.get(id=asset_id)
        from hub.apps.assets.models import DQStatus, ComplianceStatus
        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()
        
        # Step 12: Activate asset (requires version)
        activate_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/activate/',
            {'version': asset.version},
            format='json'
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        
        # Verify final state
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        self.assertTrue(asset.contracts.exists())
        self.assertTrue(asset.datasets.exists())
        
        # Verify contract is valid
        contract.refresh_from_db()
        self.assertEqual(contract.validation_status, ValidationStatus.VALID)
        self.assertEqual(contract.status, ContractStatus.ACTIVE)

