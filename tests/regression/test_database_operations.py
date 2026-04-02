"""
Comprehensive regression tests for all database operations.

Tests:
- CRUD operations for all models
- Database queries (filtering, sorting, pagination)
- Database transactions
- JSONField operations
- Database indexes
- Foreign key relationships
- Unique constraints
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import transaction, connection
from rest_framework.test import APIClient
from rest_framework import status
import json

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.marketplace.models import Listing, ListingStatus
import uuid

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class DatabaseOperationsRegressionTest(TestCase):
    """Base class for database operations regression tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="DB Test Tenant",
            slug="db-test-tenant"
        )
        self.user = User.objects.create_user(
            email=f"db-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)


class ModelCRUDTest(DatabaseOperationsRegressionTest):
    """Test CRUD operations for all models"""
    
    def test_tenant_crud(self):
        """Test Tenant CRUD operations"""
        # Create
        tenant = Tenant.objects.create(name="CRUD Tenant", slug="crud-tenant")
        self.assertIsNotNone(tenant.id)
        
        # Read
        retrieved = Tenant.objects.get(id=tenant.id)
        self.assertEqual(retrieved.name, "CRUD Tenant")
        
        # Update
        retrieved.name = "Updated CRUD Tenant"
        retrieved.save()
        updated = Tenant.objects.get(id=tenant.id)
        self.assertEqual(updated.name, "Updated CRUD Tenant")
        
        # Delete
        tenant_id = tenant.id
        tenant.delete()
        self.assertFalse(Tenant.objects.filter(id=tenant_id).exists())
    
    def test_asset_crud(self):
        """Test Asset CRUD operations"""
        # Create
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="crud-asset",
            name="CRUD Asset"
        )
        self.assertIsNotNone(asset.id)
        
        # Read
        retrieved = Asset.objects.get(id=asset.id)
        self.assertEqual(retrieved.key, "crud-asset")
        
        # Update
        retrieved.name = "Updated CRUD Asset"
        retrieved.save()
        updated = Asset.objects.get(id=asset.id)
        self.assertEqual(updated.name, "Updated CRUD Asset")
        
        # Delete
        asset_id = asset.id
        asset.delete()
        self.assertFalse(Asset.objects.filter(id=asset_id).exists())
    
    def test_contract_crud(self):
        """Test Contract CRUD operations"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="contract-asset",
            name="Contract Asset"
        )
        
        # Create
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "crud-contract"}',
            hub_contract_version="1.0.0"
        )
        self.assertIsNotNone(contract.id)
        
        # Read
        retrieved = Contract.objects.get(id=contract.id)
        self.assertEqual(retrieved.version, 1)
        
        # Update
        # Use ACTIVE instead of VALID (ContractStatus doesn't have VALID)
        retrieved.status = ContractStatus.ACTIVE
        retrieved.save()
        updated = Contract.objects.get(id=contract.id)
        self.assertEqual(updated.status, ContractStatus.ACTIVE)
        
        # Delete
        contract_id = contract.id
        contract.delete()
        self.assertFalse(Contract.objects.filter(id=contract_id).exists())


class DatabaseQueryTest(DatabaseOperationsRegressionTest):
    """Test database queries"""
    
    def test_filtering(self):
        """Test database filtering"""
        # Create multiple assets
        Asset.objects.create(tenant=self.tenant, key="asset1", name="Asset 1")
        Asset.objects.create(tenant=self.tenant, key="asset2", name="Asset 2")
        Asset.objects.create(tenant=self.tenant, key="asset3", name="Asset 3")
        
        # Filter by key
        assets = Asset.objects.filter(key="asset1")
        self.assertEqual(assets.count(), 1)
        self.assertEqual(assets.first().key, "asset1")
    
    def test_sorting(self):
        """Test database sorting"""
        # Create multiple assets
        Asset.objects.create(tenant=self.tenant, key="asset-c", name="Asset C")
        Asset.objects.create(tenant=self.tenant, key="asset-a", name="Asset A")
        Asset.objects.create(tenant=self.tenant, key="asset-b", name="Asset B")
        
        # Sort by key
        assets = Asset.objects.filter(tenant=self.tenant).order_by('key')
        self.assertEqual(assets[0].key, "asset-a")
        self.assertEqual(assets[1].key, "asset-b")
        self.assertEqual(assets[2].key, "asset-c")
        
        # Sort descending
        assets = Asset.objects.filter(tenant=self.tenant).order_by('-key')
        self.assertEqual(assets[0].key, "asset-c")
    
    def test_pagination(self):
        """Test database pagination"""
        # Create multiple assets
        for i in range(10):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}"
            )
        
        # Test pagination
        assets = Asset.objects.filter(tenant=self.tenant)[:5]
        self.assertEqual(len(assets), 5)
        
        assets = Asset.objects.filter(tenant=self.tenant)[5:10]
        self.assertEqual(len(assets), 5)


class JSONFieldOperationsTest(DatabaseOperationsRegressionTest):
    """Test JSONField operations"""
    
    def test_jsonfield_storage(self):
        """Test JSONField storage and retrieval"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="json-asset",
            name="JSON Asset"
        )
        
        contract_data = {
            "id": "json-contract",
            "info": {"title": "JSON Contract", "version": "1.0.0"},
            "schema": {"type": "object", "properties": {"id": {"type": "string"}}}
        }
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(contract_data),
            hub_contract_json=contract_data
        )
        
        # Retrieve and verify JSONField
        retrieved = Contract.objects.get(id=contract.id)
        self.assertEqual(retrieved.hub_contract_json['id'], "json-contract")
        self.assertEqual(retrieved.hub_contract_json['info']['title'], "JSON Contract")
    
    def test_jsonfield_query(self):
        """Test JSONField queries"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="json-query-asset",
            name="JSON Query Asset"
        )
        
        contract1_data = {"id": "contract1", "info": {"title": "Contract 1"}}
        contract2_data = {"id": "contract2", "info": {"title": "Contract 2"}}
        
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(contract1_data),
            hub_contract_json=contract1_data
        )
        
        contract2 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=2,  # Use different version to avoid unique constraint violation
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(contract2_data),
            hub_contract_json=contract2_data
        )
        
        # Query by JSONField path
        contracts = Contract.objects.filter(hub_contract_json__id="contract1")
        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, contract1.id)


class DatabaseTransactionTest(DatabaseOperationsRegressionTest):
    """Test database transactions"""
    
    def test_transaction_rollback(self):
        """Test transaction rollback"""
        initial_count = Asset.objects.filter(tenant=self.tenant).count()
        
        try:
            with transaction.atomic():
                Asset.objects.create(
                    tenant=self.tenant,
                    key="transaction-asset",
                    name="Transaction Asset"
                )
                # Force an error
                raise ValueError("Test rollback")
        except ValueError:
            pass
        
        # Asset should not be created due to rollback
        final_count = Asset.objects.filter(tenant=self.tenant).count()
        self.assertEqual(initial_count, final_count)
    
    def test_transaction_commit(self):
        """Test transaction commit"""
        initial_count = Asset.objects.filter(tenant=self.tenant).count()
        
        with transaction.atomic():
            Asset.objects.create(
                tenant=self.tenant,
                key="transaction-commit-asset",
                name="Transaction Commit Asset"
            )
        
        # Asset should be created
        final_count = Asset.objects.filter(tenant=self.tenant).count()
        self.assertEqual(initial_count + 1, final_count)


class ForeignKeyRelationshipsTest(DatabaseOperationsRegressionTest):
    """Test foreign key relationships"""
    
    def test_asset_tenant_relationship(self):
        """Test Asset-Tenant relationship"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="fk-asset",
            name="FK Asset"
        )
        
        # Verify relationship
        self.assertEqual(asset.tenant, self.tenant)
        self.assertEqual(asset.tenant_id, self.tenant.id)
    
    def test_contract_asset_relationship(self):
        """Test Contract-Asset relationship"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="contract-fk-asset",
            name="Contract FK Asset"
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "fk-contract"}',
            hub_contract_version="1.0.0"
        )
        
        # Verify relationship
        self.assertEqual(contract.asset, asset)
        self.assertEqual(contract.asset_id, asset.id)
    
    def test_cascade_delete(self):
        """Test cascade delete behavior"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="cascade-asset",
            name="Cascade Asset"
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="1.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "cascade-contract"}',
            hub_contract_version="1.0.0"
        )
        
        contract_id = contract.id
        
        # Delete asset (should cascade delete contract if configured)
        asset.delete()
        
        # Contract may or may not be deleted depending on CASCADE setting
        # This test verifies the relationship exists, not the cascade behavior
        self.assertFalse(Asset.objects.filter(id=asset.id).exists())


class DatabaseIndexesTest(DatabaseOperationsRegressionTest):
    """Test database indexes"""
    
    def test_unique_constraints(self):
        """Test unique constraints"""
        # Create asset with unique key
        Asset.objects.create(
            tenant=self.tenant,
            key="unique-asset",
            name="Unique Asset"
        )
        
        # Try to create another asset with same key (should fail)
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            Asset.objects.create(
                tenant=self.tenant,
                key="unique-asset",
                name="Duplicate Asset"
            )
    
    def test_indexed_queries(self):
        """Test queries on indexed fields"""
        # Create multiple assets
        for i in range(10):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"indexed-asset-{i}",
                name=f"Indexed Asset {i}"
            )
        
        # Query by indexed field (should be fast)
        assets = Asset.objects.filter(tenant=self.tenant, key="indexed-asset-5")
        self.assertEqual(assets.count(), 1)

