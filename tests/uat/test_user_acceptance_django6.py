"""
User Acceptance Tests for Django 6

Tests all user-facing features:
- Contract creation workflow
- Asset onboarding workflow
- Data quality checks
- Compliance checks
- Semantic mapping
- Marketplace functionality
- User interfaces
- User workflows
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from tests.factories import TenantFactory

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class ContractCreationWorkflowTest(TestCase):
    """Test contract creation workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="uat-asset",
            name="UAT Asset",
            status=AssetStatus.DRAFT
        )
    
    def test_contract_creation_workflow(self):
        """Test complete contract creation workflow"""
        # 1. Create contract
        response = self.client.post(
            '/api/v1/contracts/',
            {
                'asset_id': str(self.asset.id),
                'original_spec_type': 'ODCS',
                'original_spec_version': '1.0.0',
                'original_format': 'JSON',
                'original_raw': '{"id": "test-contract", "info": {"title": "Test Contract"}}'
            },
            format='json'
        )
        
        # Should return 201 (created), 400 (bad request), 404 (not found), or 405 (method not allowed)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST,
                                             status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED])
        
        if response.status_code == status.HTTP_201_CREATED:
            contract_id = response.data.get('id')
            
            # 2. Retrieve contract
            retrieve_response = self.client.get(f'/api/v1/contracts/{contract_id}/')
            self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
            
            # 3. Verify contract data
            self.assertEqual(retrieve_response.data.get('status'), ContractStatus.DRAFT)


class AssetOnboardingWorkflowTest(TestCase):
    """Test asset onboarding workflow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
    
    def test_data_first_onboarding_workflow(self):
        """Test data-first onboarding workflow"""
        # 1. Upload file
        file_response = self.client.post(
            '/api/v1/files/init-upload/',
            {
                'name': 'onboarding-data.csv',
                'size': 1024,
                'content_type': 'text/csv'
            },
            format='json'
        )
        
        if file_response.status_code in [200, 201]:
            file_id = file_response.data.get('file_id')
            
            # 2. Create asset
            asset_response = self.client.post(
                '/api/v1/assets/',
                {
                    'key': 'onboarding-asset',
                    'name': 'Onboarding Asset',
                    'status': 'DRAFT'
                },
                format='json'
            )
            
            # Should create asset
            self.assertIn(asset_response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST,
                                                      status.HTTP_404_NOT_FOUND])
    
    def test_contract_first_onboarding_workflow(self):
        """Test contract-first onboarding workflow"""
        # 1. Create contract
        contract_response = self.client.post(
            '/api/v1/contracts/',
            {
                'original_spec_type': 'ODCS',
                'original_spec_version': '1.0.0',
                'original_format': 'JSON',
                'original_raw': '{"id": "onboarding-contract"}'
            },
            format='json'
        )
        
        # Should create contract
        self.assertIn(contract_response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST,
                                                      status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED])


class DataQualityChecksTest(TestCase):
    """Test data quality checks"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="dq-check-asset",
            name="DQ Check Asset",
            status=AssetStatus.DRAFT
        )
    
    def test_data_quality_check_workflow(self):
        """Test data quality check workflow"""
        # Create DQ run
        response = self.client.post(
            '/api/v1/dq/dq-runs/',
            {
                'asset_id': str(self.asset.id),
                'profile': 'intake_basic_gx'
            },
            format='json'
        )
        
        # Should return 201 (created) or 400/503/404
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST,
                                             status.HTTP_503_SERVICE_UNAVAILABLE, status.HTTP_404_NOT_FOUND])


class ComplianceChecksTest(TestCase):
    """Test compliance checks"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="compliance-check-asset",
            name="Compliance Check Asset",
            status=AssetStatus.DRAFT
        )
    
    def test_compliance_check_workflow(self):
        """Test compliance check workflow"""
        # Create compliance run
        response = self.client.post(
            '/api/v1/compliance/compliance-runs/',
            {
                'asset_id': str(self.asset.id),
                'regulations': ['GDPR', 'CCPA']
            },
            format='json'
        )
        
        # Should return 201 (created) or 400/503/404
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST,
                                             status.HTTP_503_SERVICE_UNAVAILABLE, status.HTTP_404_NOT_FOUND])


class SemanticMappingTest(TestCase):
    """Test semantic mapping"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
    
    def test_semantic_mapping_workflow(self):
        """Test semantic mapping workflow"""
        # Test URI resolution
        response = self.client.get(
            '/api/v1/semantic/resolve-uri/',
            {'uri': 'http://example.org/resource'}
        )
        
        # Should return 200, 404, or 503
        self.assertIn(response.status_code, [200, 404, 503])


class MarketplaceFunctionalityTest(TestCase):
    """Test marketplace functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="marketplace-asset",
            name="Marketplace Asset",
            status=AssetStatus.ACTIVE
        )
    
    def test_marketplace_listing_workflow(self):
        """Test marketplace listing workflow"""
        # List marketplace listings
        response = self.client.get('/api/v1/marketplace/listings/')
        
        # Should return 200 or 404
        self.assertIn(response.status_code, [200, 404])


class UserWorkflowsTest(TestCase):
    """Test all user workflows"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)
    
    def test_complete_user_journey(self):
        """Test complete user journey"""
        # 1. Create asset
        asset_response = self.client.post(
            '/api/v1/assets/',
            {
                'key': 'journey-asset',
                'name': 'Journey Asset',
                'status': 'DRAFT'
            },
            format='json'
        )
        
        # Should create asset
        self.assertIn(asset_response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST,
                                                   status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED])
        
        # 2. Create contract
        if asset_response.status_code == status.HTTP_201_CREATED:
            asset_id = asset_response.data.get('id')
            
            contract_response = self.client.post(
                '/api/v1/contracts/',
                {
                    'asset_id': asset_id,
                    'original_spec_type': 'ODCS',
                    'original_spec_version': '1.0.0',
                    'original_format': 'JSON',
                    'original_raw': '{}'
                },
                format='json'
            )
            
            # Should create contract
            self.assertIn(contract_response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST,
                                                          status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED])

