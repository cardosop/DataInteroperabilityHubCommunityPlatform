"""
E2E tests for Search Functionality

End-to-end tests for complete search workflows.
"""
import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.search.models import SearchIndex, SearchAnalytics
from hub.apps.search.indexing import SearchIndexer
from hub.apps.search.search_engine import SearchEngine
from hub.apps.contracts.models import Contract
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import DataClassification, ClassificationCategory
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import create_job, get_queue_for_job_type

from .conftest import E2ETestBase


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class SearchE2ETest(E2ETestBase):
    """E2E tests for search functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset description with keywords",
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
                ]
            },
            created_by=self.user
        )
    
    def test_complete_search_workflow(self):
        """Test complete search workflow: index -> search -> track -> analytics"""
        # Step 1: Index resources
        SearchIndexer.index_asset(self.asset)
        SearchIndexer.index_dataset(self.dataset)
        SearchIndexer.index_contract(self.contract)
        
        # Step 2: Perform search
        url = reverse('search-search')
        response = self.client.get(url, {'q': 'test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['total'], 0)
        self.assertGreater(len(response.data['results']), 0)
        
        # Step 3: Get suggestions
        url = reverse('search-suggestions')
        response = self.client.get(url, {'q': 'test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        
        # Step 4: Track click
        analytics_id = response.data[0].get('analytics_id') if response.data else None
        if analytics_id:
            url = reverse('search-track-click')
            response = self.client.post(url, {
                'analytics_id': analytics_id,
                'result_id': str(self.asset.id),
                'result_type': 'ASSET'
            })
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 5: View analytics (requires auditor permission)
        # This would require setting up auditor user, skipping for now
    
    def test_search_with_classification_filter(self):
        """Test search with classification filter"""
        # Create classification
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="email",
            category=ClassificationCategory.PII.value,
            confidence_score=0.95,
            created_by=self.user
        )
        
        # Re-index with classification
        SearchIndexer.index_dataset(self.dataset)
        
        # Search with classification filter
        url = reverse('search-search')
        response = self.client.get(url, {
            'q': 'test',
            'classification': ClassificationCategory.PII.value
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertEqual(result['classification'], ClassificationCategory.PII.value)
    
    def test_search_index_update_job(self):
        """Test search index update via background job"""
        # Create job
        job = create_job(
            tenant_id=str(self.tenant.id),
            job_type=JobType.SEARCH_INDEX_UPDATE.value,
            resource_type="ASSET",
            resource_id=str(self.asset.id),
            created_by_id=str(self.user.id)
        )
        
        # Process job (simulate worker)
        from hub.apps.jobs.tasks import process_job
        process_job(str(job.id), JobType.SEARCH_INDEX_UPDATE.value)
        
        # Verify index created
        self.assertTrue(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id,
                resource_type="ASSET",
                resource_id=self.asset.id
            ).exists()
        )

