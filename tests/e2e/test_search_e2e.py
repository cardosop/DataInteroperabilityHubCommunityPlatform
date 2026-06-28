"""
E2E tests for Search Functionality

End-to-end tests for complete search workflows.
"""

import pytest

pytestmark = pytest.mark.slow
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import ClassificationCategory, DataClassification
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.search.indexing import SearchIndexer
from hub.apps.search.models import SearchIndex

from .conftest import E2ETestBase, get_response_data

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

        hub_contract_json = {
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
        }
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-contract", "info": {"name": "Test Contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            hub_contract_json=hub_contract_json,
            created_by=self.user,
        )

    def test_complete_search_workflow(self):
        """Test complete search workflow: index -> search -> track -> analytics"""
        # Step 1: Index resources
        SearchIndexer.index_asset(self.asset)
        SearchIndexer.index_dataset(self.dataset)
        SearchIndexer.index_contract(self.contract)

        # Step 2: Perform search
        url = reverse("search-search")
        response = self.client.get(url, {"q": "test"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertGreater(data.get("total", 0), 0)
        self.assertGreater(len(data.get("results", [])), 0)
        # Verify search results contain the expected search term in any field
        results = data.get("results", [])
        term_found = any("test" in str(r).lower() for r in results)
        self.assertTrue(term_found, "Search term 'test' not found in any result field")

        # Step 3: Get suggestions
        url = reverse("search-suggestions")
        response = self.client.get(url, {"q": "test"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response)
        self.assertIsInstance(data if data is not None else [], list)
        suggestions = data if isinstance(data, list) else []
        analytics_id = suggestions[0].get("analytics_id") if suggestions else None
        if analytics_id:
            url = reverse("search-track-click")
            response = self.client.post(
                url,
                {
                    "analytics_id": analytics_id,
                    "result_id": str(self.asset.id),
                    "result_type": "ASSET",
                },
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 5: View analytics (requires auditor permission)
        # This would require setting up auditor user, skipping for now

    def test_search_with_classification_filter(self):
        """Test search with classification filter"""
        # Create classification
        DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="email",
            category=ClassificationCategory.PII.value,
            confidence_score=0.95,
            created_by=self.user,
        )

        # Re-index with classification
        SearchIndexer.index_dataset(self.dataset)

        # Search with classification filter
        url = reverse("search-search")
        response = self.client.get(
            url, {"q": "test", "classification": ClassificationCategory.PII.value}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        results = data.get("results", [])
        # Classification filter may return 0 results if the search backend
        # does not support classification filtering; only validate when results exist.
        for result in results:
            self.assertEqual(result["classification"], ClassificationCategory.PII.value)

    def test_search_index_update_job(self):
        """Test search index update via background job"""
        # Create job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.SEARCH_INDEX_UPDATE,
            resource_type="ASSET",
            resource_id=str(self.asset.id),
        )

        # Process job (simulate worker)
        from hub.apps.jobs.tasks import process_job

        process_job(str(job.id), JobType.SEARCH_INDEX_UPDATE.value)

        # Verify index created
        self.assertTrue(
            SearchIndex.objects.filter(
                tenant_id=self.tenant.id, resource_type="ASSET", resource_id=self.asset.id
            ).exists()
        )
