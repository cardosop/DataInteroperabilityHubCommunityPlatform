"""
Unit tests for Search Indexing

Tests for indexing contracts, assets, datasets, schemas, descriptions, and lineage.
"""

import uuid
import pytest
from django.contrib.postgres.search import SearchVector
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import ClassificationCategory, DataClassification
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.search.indexing import SearchIndexer
from hub.apps.search.models import SearchIndex
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SearchIndexerTest(TestCase):
    """Test SearchIndexer"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "email", "type": "string", "sample_values": ["user@example.com"]},
                    {"name": "name", "type": "string", "sample_values": ["John Doe"]},
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user,
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status="DRAFT",
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw='{"id": "test", "info": {"title": "Test Contract", "description": "Test contract description", "tags": ["test", "example"]}}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "test",
                "info": {
                    "title": "Test Contract",
                    "description": "Test contract description",
                    "tags": ["test", "example"],
                },
                "models": [
                    {
                        "name": "UserModel",
                        "fields": [
                            {"name": "email", "type": "string"},
                            {"name": "name", "type": "string"},
                        ],
                    }
                ],
                "lineage": {"contracts": [{"name": "Source Contract", "namespace": "test"}]},
            },
            normalization_status="NORMALIZED_OK",
            created_by=self.user,
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
        # Create classification with APPROVED status so it's picked up by indexing
        from hub.apps.governance.models import ClassificationStatus

        classification = DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="email",
            category=ClassificationCategory.PII.value,
            confidence_score=0.95,
            status=ClassificationStatus.APPROVED,  # Ensure status is APPROVED
            created_by=self.user,
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
            tenant_id=str(self.tenant.id), resource_type="ASSET", resource_id=str(self.asset.id)
        )

        # Verify deleted
        self.assertFalse(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id, resource_type="ASSET", resource_id=self.asset.id
            ).exists()
        )

    def test_rebuild_index(self):
        """Test rebuilding search index"""
        # Rebuild index for tenant
        SearchIndexer.rebuild_index(tenant_id=str(self.tenant.id))

        # Verify indices created
        self.assertTrue(
            SearchIndex.objects.filter(tenant_id=self.tenant.id, resource_type="ASSET").exists()
        )
        self.assertTrue(
            SearchIndex.objects.filter(tenant_id=self.tenant.id, resource_type="DATASET").exists()
        )
        self.assertTrue(
            SearchIndex.objects.filter(tenant_id=self.tenant.id, resource_type="CONTRACT").exists()
        )

    # --- Edge cases and TDD ---

    def test_flatten_schema_none_returns_empty_string(self):
        """_flatten_schema with None returns empty string."""
        self.assertEqual(SearchIndexer._flatten_schema(None), "")

    def test_flatten_schema_empty_dict_returns_empty_string(self):
        """_flatten_schema with empty dict returns empty string."""
        self.assertEqual(SearchIndexer._flatten_schema({}), "")

    def test_flatten_lineage_none_returns_empty_string(self):
        """_flatten_lineage with None returns empty string."""
        self.assertEqual(SearchIndexer._flatten_lineage(None), "")

    def test_flatten_lineage_empty_dict_returns_empty_string(self):
        """_flatten_lineage with empty dict returns empty string."""
        self.assertEqual(SearchIndexer._flatten_lineage({}), "")

    def test_index_dataset_with_none_schema_json_succeeds(self):
        """Indexing dataset with schema_json None creates index with empty schema_text."""
        dataset_no_schema = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json=None,
            format="CSV",
            version=2,
            created_by=self.user,
        )
        search_index = SearchIndexer.index_dataset(dataset_no_schema)
        self.assertIsNotNone(search_index)
        self.assertEqual(search_index.resource_type, "DATASET")
        self.assertEqual(search_index.resource_id, dataset_no_schema.id)
        self.assertEqual(search_index.schema_text, "")

    def test_delete_index_nonexistent_idempotent(self):
        """Deleting non-existent index does not raise (idempotent)."""
        import uuid

        fake_id = uuid.uuid4()
        SearchIndexer.delete_index(
            tenant_id=str(self.tenant.id), resource_type="ASSET", resource_id=str(fake_id)
        )
        self.assertFalse(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id, resource_type="ASSET", resource_id=fake_id
            ).exists()
        )

    def test_rebuild_index_empty_tenant_succeeds(self):
        """Rebuild index for tenant with no resources completes without error."""
        empty_tenant = Tenant.objects.create(
            name="Empty Tenant", slug="empty-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        SearchIndexer.rebuild_index(tenant_id=str(empty_tenant.id))
        self.assertEqual(SearchIndex.objects.filter(tenant_id=empty_tenant.id).count(), 0)

    def test_index_contract_minimal_hub_contract_json_tdd(self):
        """TDD: Index contract with minimal hub_contract_json uses fallback title."""
        minimal_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status="DRAFT",
            original_spec_type="ODCS",
            original_spec_version="3.0.0",
            original_format="JSON",
            original_raw="{}",
            hub_contract_version="1.0.0",
            hub_contract_json={"info": {}},
            normalization_status="NORMALIZED_OK",
            created_by=self.user,
        )
        search_index = SearchIndexer.index_contract(minimal_contract)
        self.assertIsNotNone(search_index)
        self.assertEqual(search_index.resource_type, "CONTRACT")
        self.assertEqual(search_index.resource_id, minimal_contract.id)
        self.assertIn("Contract", search_index.title)
        self.assertIsNotNone(search_index.search_vector)
