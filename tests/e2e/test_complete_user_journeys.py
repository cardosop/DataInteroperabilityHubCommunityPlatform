"""
End-to-End tests for complete user journeys (T.11).

Tests multiple complete user journeys end-to-end.
"""
from unittest.mock import patch, Mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ValidationStatus
from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel, Order, OrderStatus

User = get_user_model()


class CompleteUserJourneysE2ETest(TestCase):
    """E2E tests for complete user journeys (T.11)"""
    
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
    def test_data_provider_journey(self, mock_boto3, mock_storage, mock_dq, mock_compliance, mock_validate):
        """Test complete data provider journey: onboard → publish → manage"""
        # Mock services
        mock_validate.return_value = {'validation_status': 'VALID', 'issues': []}
        mock_compliance.return_value = {'overall_status': 'PASS', 'allowed_to_store': True}
        mock_dq.return_value = {'overall_status': 'PASS', 'quality_score': 0.95}
        mock_storage.return_value.file_exists.return_value = True
        mock_storage.return_value.get_file_size.return_value = 1024
        mock_s3 = Mock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.get_object.return_value = {'Body': Mock(read=lambda: b'col1,col2\nval1,val2')}
        
        # 1. Onboard data (data-first)
        asset_response = self.client.post(
            '/api/v1/assets/assets/',
            {'key': 'sales-data', 'name': 'Sales Data', 'visibility': 'INTERNAL'},
            format='json'
        )
        asset_id = asset_response.data['id']
        
        file_response = self.client.post(
            '/api/v1/files/files/init/',
            {'name': 'sales.csv', 'content_type': 'text/csv', 'size': 1024},
            format='json'
        )
        file_id = file_response.data['file_id']
        
        self.client.post(
            f'/api/v1/files/files/{file_id}/complete/',
            {'content_sha256': 'abc123'},
            format='json'
        )
        
        dataset_response = self.client.post(
            '/api/v1/datasets/datasets/',
            {'file_id': file_id, 'asset_id': asset_id},
            format='json'
        )
        dataset_id = dataset_response.data['id']
        
        # 2. Run compliance and DQ
        self.client.post(
            '/api/v1/compliance/compliance-runs/',
            {'file_id': file_id, 'dataset_id': dataset_id, 'asset_id': asset_id, 'scan_mode': 'internal'},
            format='json'
        )
        
        self.client.post(
            '/api/v1/dq/dq-runs/',
            {'file_id': file_id, 'dataset_id': dataset_id, 'asset_id': asset_id},
            format='json'
        )
        
        # 3. Create and validate contract
        contract_response = self.client.post(
            '/api/v1/contracts/contracts/',
            {
                'asset_id': asset_id,
                'original_raw': '{"id": "sales-data", "name": "Sales Data", "schema": {"fields": []}}',
                'original_format': 'JSON',
                'original_spec_type': 'ODCS'
            },
            format='json'
        )
        contract_id = contract_response.data['id']
        
        self.client.post(
            f'/api/v1/contracts/contracts/{contract_id}/validate/',
            {'async': False},
            format='json'
        )
        
        # 4. Attach and activate
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
        
        # Update contract to ACTIVE
        contract = Contract.objects.get(id=contract_id)
        contract.status = ContractStatus.ACTIVE
        from hub.apps.contracts.models import NormalizationStatus
        contract.normalization_status = NormalizationStatus.NORMALIZED_OK
        contract.save()
        
        # Update asset DQ and compliance status
        asset = Asset.objects.get(id=asset_id)
        from hub.apps.assets.models import DQStatus, ComplianceStatus
        asset.dq_status = DQStatus.PASS
        asset.compliance_status = ComplianceStatus.PASS
        asset.save()
        
        # Activate asset
        self.client.post(
            f'/api/v1/assets/assets/{asset_id}/activate/',
            {'version': asset.version},
            format='json'
        )
        
        # 5. Publish to marketplace
        listing_response = self.client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': asset_id,
                'title': 'Sales Data',
                'short_description': 'Monthly sales data',
                'pricing_model': PricingModel.FREE_AUTO_APPROVE,
                'price_amount': 0.0
            },
            format='json'
        )
        listing_id = listing_response.data['id']
        
        self.client.patch(
            f'/api/v1/marketplace/listings/{listing_id}/',
            {'status': ListingStatus.PUBLISHED},
            format='json'
        )
        
        # Verify final state
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        
        listing = Listing.objects.get(id=listing_id)
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
    
    @patch('hub.apps.contracts.cli_client.DataContractCLIClient.validate')
    def test_data_consumer_journey(self, mock_validate):
        """Test complete data consumer journey: browse → purchase → access"""
        # Create provider and listing
        provider_tenant = Tenant.objects.create(
            name="Provider",
            slug="provider",
            kyc_status=KYCStatus.VERIFIED
        )
        provider_user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=provider_tenant
        )
        
        asset = Asset.objects.create(
            tenant=provider_tenant,
            key="public-data",
            name="Public Data",
            status=AssetStatus.ACTIVE,
            created_by=provider_user
        )
        
        provider_client = APIClient()
        provider_client.force_authenticate(user=provider_user)
        
        listing_response = provider_client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': str(asset.id),
                'title': 'Public Data',
                'short_description': 'Public dataset',
                'pricing_model': PricingModel.FREE_AUTO_APPROVE,
                'price_amount': 0.0
            },
            format='json'
        )
        listing_id = listing_response.data['id']
        
        provider_client.patch(
            f'/api/v1/marketplace/listings/{listing_id}/',
            {'status': ListingStatus.PUBLISHED},
            format='json'
        )
        
        # Consumer browses and purchases
        search_response = self.client.get(
            '/api/v1/marketplace/listings/search/',
            {'q': 'public'}
        )
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        
        order_response = self.client.post(
            '/api/v1/marketplace/orders/',
            {'listing_id': listing_id},
            format='json'
        )
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)
        
        # Verify order created
        order = Order.objects.get(id=order_response.data['id'])
        self.assertIsNotNone(order)

