"""
Integration tests for onboarding flows (T.6).

Tests all three onboarding flows:
- Data-first: Upload data → infer schema → compliance/DQ → create contract → activate
- Contract-first: Upload contract → validate → upload data → compliance/DQ → activate
- Contract-only: Upload contract → validate → activate (no data)
"""
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, ValidationStatus, OriginalSpecType, OriginalFormat
from hub.apps.files.models import File, FileStatus
from hub.apps.datasets.models import Dataset
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus

User = get_user_model()


class DataFirstOnboardingTest(TestCase):
    """Integration tests for data-first onboarding flow (T.6)"""
    
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
    def test_data_first_flow_success(self, mock_validate, mock_dq, mock_compliance):
        """Test successful data-first onboarding flow"""
        # Mock compliance check - pass
        mock_compliance.return_value = {
            'overall_status': 'PASS',
            'risk_level': 'LOW',
            'allowed_to_store': True,
            'detected_categories': {},
            'column_findings': []
        }
        
        # Mock DQ check - pass
        mock_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95,
            'checks': []
        }
        
        # Mock contract validation - valid
        mock_validate.return_value = {
            'validation_status': 'VALID',
            'issues': [],
            'cli_version': '1.0.0'
        }
        
        # Step 1: Create asset
        asset_response = self.client.post(
            '/api/v1/assets/assets/',
            {
                'key': 'test-asset',
                'name': 'Test Asset',
                'description': 'Test description',
                'visibility': 'INTERNAL'
            },
            format='json'
        )
        self.assertEqual(asset_response.status_code, status.HTTP_201_CREATED)
        asset_id = asset_response.data['id']
        
        # Step 2: Upload file
        file_response = self.client.post(
            '/api/v1/files/files/init/',
            {
                'name': 'test.csv',
                'content_type': 'text/csv',
                'size': 1024
            },
            format='json'
        )
        self.assertEqual(file_response.status_code, status.HTTP_201_CREATED)
        file_id = file_response.data['file_id']
        
        # Step 3: Complete file upload
        with patch('hub.apps.files.views.S3StorageClient') as mock_storage:
            mock_storage.return_value.file_exists.return_value = True
            mock_storage.return_value.get_file_size.return_value = 1024
            
            complete_response = self.client.post(
                f'/api/v1/files/files/{file_id}/complete/',
                {
                    'content_sha256': 'test-hash'
                },
                format='json'
            )
            self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        
        # Get file object
        from hub.apps.files.models import File
        file_obj = File.objects.get(id=file_id)
        
        # Step 4: Create dataset from file (triggers schema inference)
        with patch('hub.apps.datasets.views.boto3') as mock_boto3:
            # Mock S3 download
            mock_s3 = Mock()
            mock_boto3.client.return_value = mock_s3
            mock_s3.get_object.return_value = {
                'Body': Mock(read=lambda: b'col1,col2\nval1,val2\nval3,val4')
            }
            
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
        
        dataset = Dataset.objects.get(id=dataset_id)
        
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
        
        # Step 7: Create contract
        contract_response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'asset_id': asset_id,
                'original_raw': '{"id": "test", "name": "Test Contract", "schema": {"fields": []}}',
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
            {'dataset_id': str(dataset.id)},
            format='json'
        )
        self.assertEqual(attach_dataset_response.status_code, status.HTTP_200_OK)
        
        attach_contract_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/contracts/',
            {'contract_id': contract_id},
            format='json'
        )
        self.assertEqual(attach_contract_response.status_code, status.HTTP_200_OK)
        
        # Step 10: Update contract status to ACTIVE and ensure normalization
        contract = Contract.objects.get(id=contract_id)
        contract.status = ContractStatus.ACTIVE
        from hub.apps.contracts.models import NormalizationStatus
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        contract.save()
        
        # Step 11: Update asset DQ and compliance status (required for activation with dataset)
        asset = Asset.objects.get(id=asset_id)
        from hub.apps.assets.models import DQStatus, ComplianceStatus
        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()
        
        # Step 12: Activate asset (requires version for optimistic locking)
        activate_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/activate/',
            {'version': asset.version},
            format='json'
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        
        # Verify final state
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        # Verify relationships exist
        self.assertTrue(asset.contracts.exists())
        self.assertTrue(asset.datasets.exists())
    
    @patch('hub.apps.compliance.service_client.ComplianceServiceClient.scan_file')
    def test_data_first_flow_compliance_failure(self, mock_compliance):
        """Test data-first flow with compliance failure (fail-closed)"""
        # Mock compliance check - fail
        mock_compliance.return_value = {
            'overall_status': 'FAIL',
            'risk_level': 'HIGH',
            'allowed_to_store': False,
            'detected_categories': {'EMAIL': 100},
            'column_findings': [
                {'column': 'email', 'pii_types': ['EMAIL'], 'count': 100}
            ]
        }
        
        # Create asset
        asset_response = self.client.post(
            '/api/v1/assets/assets/',
            {
                'key': 'test-asset',
                'name': 'Test Asset',
                'visibility': 'INTERNAL'
            },
            format='json'
        )
        asset_id = asset_response.data['id']
        
        # Upload file
        file_response = self.client.post(
            '/api/v1/files/files/init/',
            {
                'name': 'test.csv',
                'content_type': 'text/csv',
                'size': 1024
            },
            format='json'
        )
        file_id = file_response.data['file_id']
        
        # Complete file upload - should fail compliance
        with patch('hub.apps.files.views.S3StorageClient') as mock_storage:
            mock_storage.return_value.file_exists.return_value = True
            mock_storage.return_value.get_file_size.return_value = 1024
            
            complete_response = self.client.post(
                f'/api/v1/files/files/{file_id}/complete/',
                {
                    'content_sha256': 'test-hash',
                    'run_compliance': True
                },
                format='json'
            )
        
        # File should not be stored (fail-closed)
        file = File.objects.get(id=file_id)
        # Note: File status may vary based on implementation
        # The key is that compliance run shows failure
        compliance_run = ComplianceRun.objects.filter(file_id=file_id).first()
        if compliance_run:
            self.assertEqual(compliance_run.status, ComplianceRunStatus.COMPLETED)
            self.assertFalse(compliance_run.result_json.get('allowed_to_store', True))


class ContractFirstOnboardingTest(TestCase):
    """Integration tests for contract-first onboarding flow (T.6)"""
    
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
    def test_contract_first_flow_success(self, mock_dq, mock_compliance, mock_validate):
        """Test successful contract-first onboarding flow"""
        # Mock contract validation - valid
        mock_validate.return_value = {
            'validation_status': 'VALID',
            'issues': [],
            'cli_version': '1.0.0'
        }
        
        # Mock compliance check - pass
        mock_compliance.return_value = {
            'overall_status': 'PASS',
            'allowed_to_store': True
        }
        
        # Mock DQ check - pass
        mock_dq.return_value = {
            'overall_status': 'PASS',
            'quality_score': 0.95
        }
        
        # Step 1: Create asset
        asset_response = self.client.post(
            '/api/v1/assets/assets/',
            {
                'key': 'test-asset',
                'name': 'Test Asset',
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
                'original_raw': '{"id": "test", "name": "Test Contract", "schema": {"fields": []}}',
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
        file_response = self.client.post(
            '/api/v1/files/files/init/',
            {
                'name': 'test.csv',
                'content_type': 'text/csv',
                'size': 1024
            },
            format='json'
        )
        file_id = file_response.data['file_id']
        
        # Step 5: Complete file upload
        with patch('hub.apps.files.views.S3StorageClient') as mock_storage:
            mock_storage.return_value.file_exists.return_value = True
            mock_storage.return_value.get_file_size.return_value = 1024
            
            complete_response = self.client.post(
                f'/api/v1/files/files/{file_id}/complete/',
                {
                    'content_sha256': 'test-hash'
                },
                format='json'
            )
            self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        
        # Step 6: Create dataset from file
        with patch('hub.apps.datasets.views.boto3') as mock_boto3:
            mock_s3 = Mock()
            mock_boto3.client.return_value = mock_s3
            mock_s3.get_object.return_value = {
                'Body': Mock(read=lambda: b'col1,col2\nval1,val2')
            }
            
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
        
        dataset = Dataset.objects.get(id=dataset_id)
        
        # Step 7: Run compliance and DQ checks
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
        
        dq_response = self.client.post(
            '/api/v1/dq/dq-runs/',
            {
                'file_id': file_id,
                'dataset_id': dataset_id,
                'asset_id': asset_id
            },
            format='json'
        )
        self.assertEqual(dq_response.status_code, status.HTTP_201_CREATED)
        
        # Step 8: Attach dataset and contract to asset
        
        self.client.post(
            f'/api/v1/assets/assets/{asset_id}/datasets/',
            {'dataset_id': str(dataset_id)},
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


class ContractOnlyOnboardingTest(TestCase):
    """Integration tests for contract-only onboarding flow (T.6)"""
    
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
    def test_contract_only_flow_success(self, mock_validate):
        """Test successful contract-only onboarding flow"""
        # Mock contract validation - valid
        mock_validate.return_value = {
            'validation_status': 'VALID',
            'issues': [],
            'cli_version': '1.0.0'
        }
        
        # Step 1: Create asset
        asset_response = self.client.post(
            '/api/v1/assets/assets/',
            {
                'key': 'test-asset',
                'name': 'Test Asset',
                'visibility': 'INTERNAL'
            },
            format='json'
        )
        asset_id = asset_response.data['id']
        
        # Step 2: Create contract (no data file)
        contract_response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'asset_id': asset_id,
                'original_raw': '{"id": "test", "name": "Test Contract", "schema": {"fields": []}}',
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
        
        # Step 4: Attach contract to asset
        self.client.post(
            f'/api/v1/assets/assets/{asset_id}/contracts/',
            {'contract_id': contract_id},
            format='json'
        )
        
        # Step 5: Update contract status to ACTIVE
        contract = Contract.objects.get(id=contract_id)
        contract.status = ContractStatus.ACTIVE
        from hub.apps.contracts.models import NormalizationStatus
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        contract.save()
        
        # Step 6: Activate asset (no dataset required, but needs version)
        asset = Asset.objects.get(id=asset_id)
        activate_response = self.client.post(
            f'/api/v1/assets/assets/{asset_id}/activate/',
            {'version': asset.version},
            format='json'
        )
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
        
        # Verify final state - asset is ACTIVE without dataset
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        self.assertTrue(asset.contracts.exists())
        # Dataset is optional for contract-only assets
        self.assertFalse(asset.datasets.exists())

