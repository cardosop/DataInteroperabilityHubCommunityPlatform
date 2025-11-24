"""
End-to-End tests for contract-first onboarding flow (T.13).

Tests complete user journey from contract upload to asset activation.
"""
from unittest.mock import patch, Mock
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


class ContractFirstE2ETest(TestCase):
    """E2E tests for contract-first onboarding flow (T.13)"""
    
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
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.validate')
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient.scan_file')
    @patch('hub.apps.dq.service_client.DQServiceClient.run_dq')
    @patch('hub.apps.files.views.S3StorageClient')
    @patch('hub.apps.datasets.views.boto3')
    def test_complete_contract_first_journey(self, mock_boto3, mock_storage, mock_dq, mock_compliance, mock_validate):
        """Test complete contract-first onboarding journey"""
        # Mock external services
        mock_validate.return_value = {
            'validation_status': 'VALID',
            'issues': []
        }
        
        mock_compliance.return_value = {
            'overall_status': 'PASS',
            'allowed_to_store': True
        }
        
        mock_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95
        }
        
        # Mock S3 storage
        mock_storage.return_value.file_exists.return_value = True
        mock_storage.return_value.get_file_size.return_value = 1024
        
        # Mock S3 download
        mock_s3 = Mock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: b'col1,col2\nval1,val2')
        }
        
        # Step 1: Create asset
        asset_response = self.client.post(
            '/api/v1/assets/assets/',
            {
                'key': 'product-catalog',
                'name': 'Product Catalog',
                'visibility': 'INTERNAL'
            },
            format='json'
        )
        asset_id = asset_response.data['id']
        
        # Step 2: Create contract first
        contract_response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'asset_id': asset_id,
                'original_raw': '{"id": "product-catalog", "name": "Product Catalog", "schema": {"fields": [{"name": "col1", "type": "string"}, {"name": "col2", "type": "string"}]}}',
                'original_format': 'JSON',
                'original_spec_type': 'ODCS'
            },
            format='json'
        )
        self.assertEqual(contract_response.status_code, status.HTTP_201_CREATED)
        contract_id = contract_response.data['id']
        
        # Step 3: Validate contract
        validate_response = self.client.post(
            f'/api/v1/contracts/contracts/{contract_id}/validate/',
            {'async': False},
            format='json'
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        
        # Step 4: Upload data file
        file_init_response = self.client.post(
            '/api/v1/files/files/init/',
            {
                'name': 'products.csv',
                'content_type': 'text/csv',
                'size': 1024
            },
            format='json'
        )
        file_id = file_init_response.data['file_id']
        
        # Step 5: Complete file upload
        self.client.post(
            f'/api/v1/files/files/{file_id}/complete/',
            {'content_sha256': 'abc123'},
            format='json'
        )
        
        # Step 6: Create dataset
        dataset_response = self.client.post(
            '/api/v1/datasets/datasets/',
            {
                'file_id': file_id,
                'asset_id': asset_id
            },
            format='json'
        )
        dataset_id = dataset_response.data['id']
        
        # Step 7: Run compliance and DQ checks
        self.client.post(
            '/api/v1/compliance/compliance-runs/',
            {
                'file_id': file_id,
                'dataset_id': dataset_id,
                'asset_id': asset_id,
                'scan_mode': 'internal'
            },
            format='json'
        )
        
        self.client.post(
            '/api/v1/dq/dq-runs/',
            {
                'file_id': file_id,
                'dataset_id': dataset_id,
                'asset_id': asset_id
            },
            format='json'
        )
        
        # Step 8: Attach dataset and contract to asset
        self.client.post(
            f'/api/v1/assets/assets/{asset_id}/datasets/',
            {'dataset_id': dataset_id},
            format='json'
        )
        
        self.client.post(
            f'/api/v1/assets/assets/{asset_id}/contracts/',
            {'contract_id': contract_id},
            format='json'
        )
        
        # Step 9: Update contract status to ACTIVE
        contract = Contract.objects.get(id=contract_id)
        contract.status = ContractStatus.ACTIVE
        from hub.apps.contracts.models import NormalizationStatus
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        contract.save()
        
        # Step 10: Update asset DQ and compliance status
        asset = Asset.objects.get(id=asset_id)
        from hub.apps.assets.models import DQStatus, ComplianceStatus
        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()
        
        # Step 11: Activate asset (requires version)
        activate_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/activate/',
            {'version': asset.version},
            format='json'
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        
        # Verify final state
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        contract.refresh_from_db()
        self.assertEqual(contract.validation_status, ValidationStatus.VALID)

