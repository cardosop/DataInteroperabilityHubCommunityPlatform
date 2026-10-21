"""
E2E tests for Dataset Version History

End-to-end tests for complete version lifecycle.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileStatus

from .conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class DatasetVersionHistoryE2ETest(E2ETestBase):
    """E2E tests for dataset version history"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create file
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

    def test_complete_version_lifecycle(self):
        """Test complete version lifecycle: create, query, archive, restore"""
        # Step 1: Create first version
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v1, semantic_version="1.0.0", version_tags=["production"], is_current=True
        )

        # Verify v1
        v1.refresh_from_db()
        self.assertEqual(v1.semantic_version, "1.0.0")
        self.assertTrue(v1.is_current)
        self.assertIn("production", v1.version_tags)

        # Step 2: Create second version (non-breaking change)
        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user,
        )

        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={
                "fields": [
                    {"name": "col1", "type": "string"},
                    {"name": "col2", "type": "integer"},  # New field
                ]
            },
            format="CSV",
            version=2,
            created_by=self.user,
        )
        VersionHistoryManager.create_version(
            v2, parent_version=v1, version_tags=["staging"], is_current=True
        )

        # Verify v2
        v2.refresh_from_db()
        self.assertEqual(v2.semantic_version, "1.1.0")  # Minor increment
        self.assertEqual(v2.parent_version, v1)
        self.assertTrue(v2.is_current)

        # Verify v1 is no longer current
        v1.refresh_from_db()
        self.assertFalse(v1.is_current)

        # Step 3: Query versions
        current = VersionHistoryManager.get_current_version(self.asset.id, self.tenant.id)
        self.assertEqual(current.id, v2.id)

        by_semver = VersionHistoryManager.get_version_by_semantic_version(
            self.asset.id, self.tenant.id, "1.0.0"
        )
        self.assertEqual(by_semver.id, v1.id)

        production_versions = VersionHistoryManager.get_versions_by_tag(
            self.asset.id, self.tenant.id, "production"
        )
        self.assertEqual(len(production_versions), 1)
        self.assertEqual(production_versions[0].id, v1.id)

        # Step 4: Test version tree traversal
        ancestors = VersionHistoryManager.get_ancestors(v2)
        self.assertEqual(len(ancestors), 1)
        self.assertEqual(ancestors[0].id, v1.id)

        descendants = VersionHistoryManager.get_descendants(v1)
        self.assertEqual(len(descendants), 1)
        self.assertEqual(descendants[0].id, v2.id)

        # Step 5: Archive v1
        VersionHistoryManager.archive_version(v1)
        v1.refresh_from_db()
        self.assertIsNotNone(v1.archived_at)
        self.assertFalse(v1.is_current)

        # Step 6: Restore v1
        VersionHistoryManager.restore_version(v1)
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertIsNone(v1.archived_at)
        self.assertTrue(v1.is_current)
        self.assertFalse(v2.is_current)

    def test_time_travel_queries(self):
        """Test time-travel queries for version history"""
        # Create versions at different times
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )
        v1.created_at = timezone.now() - timedelta(days=3)
        v1.save()
        VersionHistoryManager.create_version(v1, is_current=False)

        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user,
        )
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user,
        )
        v2.created_at = timezone.now() - timedelta(days=1)
        v2.save()
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)

        # Query version at different timestamps
        timestamp_before_v1 = timezone.now() - timedelta(days=5)
        found = VersionHistoryManager.get_versions_by_timestamp(
            self.asset.id, self.tenant.id, timestamp_before_v1
        )
        self.assertIsNone(found)  # No version exists yet

        timestamp_between = timezone.now() - timedelta(days=2)
        found = VersionHistoryManager.get_versions_by_timestamp(
            self.asset.id, self.tenant.id, timestamp_between
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.id, v1.id)

        timestamp_after_v2 = timezone.now()
        found = VersionHistoryManager.get_versions_by_timestamp(
            self.asset.id, self.tenant.id, timestamp_after_v2
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.id, v2.id)
