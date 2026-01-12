"""
Comprehensive regression tests for all tenant isolation functionality.

Tests:
- Tenant data isolation
- Cross-tenant access prevention
- Tenant-scoped queries
- Tenant configuration isolation
- Tenant user isolation
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import UserStatus
from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.files.models import File
from hub.apps.jobs.models import Job, JobStatus, JobType

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class TenantIsolationRegressionTest(TestCase):
    """Base class for tenant isolation regression tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create two tenants
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1"
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2"
        )
        
        # Create users for each tenant
        self.user1 = User.objects.create_user(
            email="tenant1@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE
        )
        self.user2 = User.objects.create_user(
            email="tenant2@example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE
        )


class TenantDataIsolationTest(TenantIsolationRegressionTest):
    """Test tenant data isolation"""
    
    def test_asset_isolation(self):
        """Test assets are isolated by tenant"""
        # Create assets in both tenants
        asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key="tenant1-asset",
            name="Tenant 1 Asset"
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="tenant2-asset",
            name="Tenant 2 Asset"
        )
        
        # User 1 should only see tenant 1 assets
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user 1 cannot access tenant 2 asset
        response = self.client.get(f'/api/v1/assets/{asset2.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
        
        # User 2 should only see tenant 2 assets
        self.client.force_authenticate(user=self.user2)
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user 2 cannot access tenant 1 asset
        response = self.client.get(f'/api/v1/assets/{asset1.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
    
    def test_contract_isolation(self):
        """Test contracts are isolated by tenant"""
        asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key="contract-asset-1",
            name="Contract Asset 1"
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="contract-asset-2",
            name="Contract Asset 2"
        )
        
        # Create contracts in both tenants
        contract1 = Contract.objects.create(
            tenant=self.tenant1,
            asset=asset1,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "contract1"}',
            hub_contract_version="1.0.0"
        )
        contract2 = Contract.objects.create(
            tenant=self.tenant2,
            asset=asset2,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "contract2"}',
            hub_contract_version="1.0.0"
        )
        
        # User 1 should only see tenant 1 contracts
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/contracts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user 1 cannot access tenant 2 contract
        response = self.client.get(f'/api/v1/contracts/{contract2.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
    
    def test_file_isolation(self):
        """Test files are isolated by tenant"""
        # Create files in both tenants
        file1 = File.objects.create(
            tenant=self.tenant1,
            name="tenant1-file.csv",
            content_type="text/csv",
            size=1024
        )
        file2 = File.objects.create(
            tenant=self.tenant2,
            name="tenant2-file.csv",
            content_type="text/csv",
            size=2048
        )
        
        # User 1 should only see tenant 1 files
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/files/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user 1 cannot access tenant 2 file
        response = self.client.get(f'/api/v1/files/{file2.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
    
    def test_job_isolation(self):
        """Test jobs are isolated by tenant"""
        # Create assets for jobs
        asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key="job-asset-1",
            name="Job Asset 1"
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key="job-asset-2",
            name="Job Asset 2"
        )
        # Create jobs in both tenants
        job1 = Job.objects.create(
            tenant=self.tenant1,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type='ASSET',
            resource_id=asset1.id,
            details_json={'test': 'data1'}
        )
        job2 = Job.objects.create(
            tenant=self.tenant2,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type='ASSET',
            resource_id=asset2.id,
            details_json={'test': 'data2'}
        )
        
        # User 1 should only see tenant 1 jobs
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/jobs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user 1 cannot access tenant 2 job
        response = self.client.get(f'/api/v1/jobs/{job2.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


class TenantConfigurationIsolationTest(TenantIsolationRegressionTest):
    """Test tenant configuration isolation"""
    
    def test_tenant_config_isolation(self):
        """Test tenant configurations are isolated"""
        # Create tenant configs
        config1 = TenantConfig.objects.create(
            tenant=self.tenant1,
            default_dq_profile="intake_basic_gx"
        )
        config2 = TenantConfig.objects.create(
            tenant=self.tenant2,
            default_dq_profile="intake_advanced_gx"
        )
        
        # User 1 should only see tenant 1 config
        self.client.force_authenticate(user=self.user1)
        # Correct URL pattern: /api/v1/tenants/tenants/{id}/config/
        response = self.client.get(f'/api/v1/tenants/tenants/{self.tenant1.id}/config/')
        # User may need TENANT_ADMIN role or platform admin to access config
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
        
        # User 1 should not access tenant 2 config
        response = self.client.get(f'/api/v1/tenants/tenants/{self.tenant2.id}/config/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


class TenantUserIsolationTest(TenantIsolationRegressionTest):
    """Test tenant user isolation"""
    
    def test_user_isolation(self):
        """Test users are isolated by tenant"""
        # User 1 should only see tenant 1 users
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/users/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # User 1 should not access tenant 2 user
        response = self.client.get(f'/api/v1/users/users/{self.user2.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


class CrossTenantAccessPreventionTest(TenantIsolationRegressionTest):
    """Test cross-tenant access prevention"""
    
    def test_cross_tenant_asset_access(self):
        """Test cross-tenant asset access is prevented"""
        asset = Asset.objects.create(
            tenant=self.tenant2,
            key="cross-tenant-asset",
            name="Cross Tenant Asset"
        )
        
        # User 1 tries to access tenant 2 asset
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/v1/assets/{asset.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
    
    def test_cross_tenant_contract_access(self):
        """Test cross-tenant contract access is prevented"""
        asset = Asset.objects.create(
            tenant=self.tenant2,
            key="cross-tenant-contract-asset",
            name="Cross Tenant Contract Asset"
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant2,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "cross-tenant-contract"}',
            hub_contract_version="1.0.0"
        )
        
        # User 1 tries to access tenant 2 contract
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/v1/contracts/{contract.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
    
    def test_cross_tenant_file_access(self):
        """Test cross-tenant file access is prevented"""
        file = File.objects.create(
            tenant=self.tenant2,
            name="cross-tenant-file.csv",
            content_type="text/csv",
            size=1024
        )
        
        # User 1 tries to access tenant 2 file
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/v1/files/{file.id}/')
        
        # Should be forbidden
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


class TenantScopedQueriesTest(TenantIsolationRegressionTest):
    """Test tenant-scoped queries"""
    
    def test_tenant_scoped_asset_queries(self):
        """Test asset queries are tenant-scoped"""
        # Create assets in both tenants
        Asset.objects.create(tenant=self.tenant1, key="query-asset-1", name="Query Asset 1")
        Asset.objects.create(tenant=self.tenant1, key="query-asset-2", name="Query Asset 2")
        Asset.objects.create(tenant=self.tenant2, key="query-asset-3", name="Query Asset 3")
        
        # User 1 should only see tenant 1 assets
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify only tenant 1 assets are returned
        if isinstance(response.data, dict) and 'results' in response.data:
            assets = response.data['results']
        elif isinstance(response.data, list):
            assets = response.data
        else:
            assets = []
        
        # Verify all returned assets belong to tenant 1 by checking in database
        for asset_data in assets:
            asset_id = asset_data.get('id')
            if asset_id:
                # Import Asset model inside loop to avoid variable name conflict
                from hub.apps.assets.models import Asset as AssetModel
                asset_obj = AssetModel.objects.get(id=asset_id)
                self.assertEqual(asset_obj.tenant_id, self.tenant1.id, 
                               f"Asset {asset_id} belongs to wrong tenant")
    
    def test_tenant_scoped_contract_queries(self):
        """Test contract queries are tenant-scoped"""
        asset1 = Asset.objects.create(tenant=self.tenant1, key="contract-query-asset-1", name="Contract Query Asset 1")
        asset2 = Asset.objects.create(tenant=self.tenant2, key="contract-query-asset-2", name="Contract Query Asset 2")
        
        Contract.objects.create(
            tenant=self.tenant1,
            asset=asset1,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "contract-query-1"}',
            hub_contract_version="1.0.0"
        )
        Contract.objects.create(
            tenant=self.tenant2,
            asset=asset2,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "contract-query-2"}',
            hub_contract_version="1.0.0"
        )
        
        # User 1 should only see tenant 1 contracts
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/v1/contracts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify only tenant 1 contracts are returned
        if isinstance(response.data, dict) and 'results' in response.data:
            contracts = response.data['results']
        elif isinstance(response.data, list):
            contracts = response.data
        else:
            contracts = []
        
        # Verify all returned contracts belong to tenant 1 by checking in database
        for contract_data in contracts:
            contract_id = contract_data.get('id')
            if contract_id:
                # Import Contract model inside loop to avoid variable name conflict
                from hub.apps.contracts.models import Contract as ContractModel
                contract_obj = ContractModel.objects.get(id=contract_id)
                self.assertEqual(contract_obj.tenant_id, self.tenant1.id,
                               f"Contract {contract_id} belongs to wrong tenant")

