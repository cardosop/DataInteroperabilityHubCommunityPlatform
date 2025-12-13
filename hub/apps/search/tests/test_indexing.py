"""
Unit tests for Search Indexing

Tests for indexing contracts, assets, datasets, schemas, descriptions, and lineage.
"""
import pytest
from django.test import TestCase
from django.contrib.postgres.search import SearchVector

from hub.apps.search.models import SearchIndex
from hub.apps.search.indexing import SearchIndexer
from hub.apps.contracts.models import Contract
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import DataClassification, ClassificationCategory
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.jobs.models import Job, JobType, JobStatus


pytestmark = pytest.mark.django_db(transaction=True)


class SearchIndexerTest(TestCase):
    """Test SearchIndexer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            name="Test Dataset",
            description="Test dataset description",
            schema_json={
                "fields": [
                    {"name": "email", "type": "string", "sample_values": ["user@example.com"]},
                    {"name": "name", "type": "string", "sample_values": ["John Doe"]}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            name="Test Contract",
            original_spec_type="ODCS",
            hub_contract_json={
                "info": {
                    "title": "Test Contract",
                    "description": "Test contract description",
                    "tags": ["test", "example"]
                },
                "models": [
                    {
                        "name": "UserModel",
                        "fields": [
                            {"name": "email", "type": "string"},
                            {"name": "name", "type": "string"}
                        ]
                    }
                ],
                "lineage": {
                    "contracts": [
                        {"name": "Source Contract", "namespace": "test"}
                    ]
                }
            },
            created_by=self.user
        )
    
    def test_index_contract(self):
        """Test indexing a contract"""
        search_index = SearchIndexer.index_contract(self.contract)
        
        self.assertIsNotNone(search_index)
        self.assertEqual(search_index.resource_type, "CONTRACT")
        self.assertEqual(search_index.resource_id, self.contract.id)
        self.assertEqual(search_index.title, "Test Contract")
        self.assertIn("email", search_index.schema_text.lower())
        self.assertIn("source contract", search_index.lineage_text.lower())
        self.assertIsNotNone(search_index.search_vector)
    
    def test_index_asset(self):
        """Test indexing an asset"""
        search_index = SearchIndexer.index_asset(self.asset)
        
        self.assertIsNotNone(search_index)
        self.assertEqual(search_index.resource_type, "ASSET")
        self.assertEqual(search_index.resource_id, self.asset.id)
        self.assertEqual(search_index.title, "Test Asset")
        self.assertEqual(search_index.description, "Test asset description")
        self.assertIsNotNone(search_index.search_vector)
    
    def test_index_dataset(self):
        """Test indexing a dataset"""
        search_index = SearchIndexer.index_dataset(self.dataset)
        
        self.assertIsNotNone(search_index)
        self.assertEqual(search_index.resource_type, "DATASET")
        self.assertEqual(search_index.resource_id, self.dataset.id)
        self.assertIn("email", search_index.schema_text.lower())
        self.assertIsNotNone(search_index.search_vector)
    
    def test_index_with_classification(self):
        """Test indexing with classification"""
        # Create classification
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="email",
            category=ClassificationCategory.PII.value,
            confidence_score=0.95,
            created_by=self.user
        )
        
        # Index dataset
        search_index = SearchIndexer.index_dataset(self.dataset)
        
        self.assertEqual(search_index.classification, ClassificationCategory.PII.value)
    
    def test_delete_index(self):
        """Test deleting a search index"""
        # Create index
        search_index = SearchIndexer.index_asset(self.asset)
        self.assertIsNotNone(search_index)
        
        # Delete index
        SearchIndexer.delete_index(
            tenant_id=str(self.tenant.id),
            resource_type="ASSET",
            resource_id=str(self.asset.id)
        )
        
        # Verify deleted
        self.assertFalse(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id,
                resource_type="ASSET",
                resource_id=self.asset.id
            ).exists()
        )
    
    def test_rebuild_index(self):
        """Test rebuilding search index"""
        # Rebuild index for tenant
        SearchIndexer.rebuild_index(tenant_id=str(self.tenant.id))
        
        # Verify indices created
        self.assertTrue(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id,
                resource_type="ASSET"
            ).exists()
        )
        self.assertTrue(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id,
                resource_type="DATASET"
            ).exists()
        )
        self.assertTrue(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id,
                resource_type="CONTRACT"
            ).exists()
        )

