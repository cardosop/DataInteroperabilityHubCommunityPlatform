"""
Tests for GET /api/v1/datasets/{id}/sample/ endpoint.

Returns the pre-computed sample_data_json from the Dataset model.
TDD: Tests written FIRST.
"""

import uuid

import pytest
from rest_framework import status

from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase

pytestmark = pytest.mark.django_db(transaction=True)


class DatasetSampleEndpointTest(DatasetsAPITestBase):
    """Tests for the /sample/ action on DatasetViewSet."""

    def setUp(self):
        super().setUp()
        self.sample_data = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
            {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
        ]
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={
                "fields": [
                    {"name": "id", "type": "integer", "nullable": False},
                    {"name": "name", "type": "string", "nullable": False},
                    {"name": "email", "type": "string", "nullable": True},
                ]
            },
            sample_data_json=self.sample_data,
            row_count=3,
            created_by=self.user,
        )

    def test_sample_returns_200_with_data(self):
        """GET /api/v1/datasets/{id}/sample/ returns sample data."""
        url = f"/api/v1/datasets/{self.dataset.id}/sample/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("sample_data", data)
        self.assertEqual(len(data["sample_data"]), 3)
        self.assertEqual(data["sample_data"][0]["name"], "Alice")

    def test_sample_includes_metadata(self):
        """Response includes format, row_count, and sample_size."""
        url = f"/api/v1/datasets/{self.dataset.id}/sample/"
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(data["format"], "CSV")
        self.assertEqual(data["row_count"], 3)
        self.assertIn("sample_size", data)

    def test_sample_with_limit_param(self):
        """?limit=2 returns only 2 rows."""
        url = f"/api/v1/datasets/{self.dataset.id}/sample/?limit=2"
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(len(data["sample_data"]), 2)
        self.assertEqual(data["sample_size"], 2)

    def test_sample_empty_when_no_data(self):
        """Returns empty list when sample_data_json is null."""
        self.dataset.sample_data_json = None
        self.dataset.save()
        url = f"/api/v1/datasets/{self.dataset.id}/sample/"
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(data["sample_data"], [])
        self.assertEqual(data["sample_size"], 0)

    def test_sample_404_for_nonexistent_dataset(self):
        """Returns 404 for non-existent dataset."""
        url = f"/api/v1/datasets/{uuid.uuid4()}/sample/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_sample_requires_authentication(self):
        """Unauthenticated request returns 401."""
        self.client.logout()
        url = f"/api/v1/datasets/{self.dataset.id}/sample/"
        response = self.client.get(url)
        self.assertIn(
            response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )
