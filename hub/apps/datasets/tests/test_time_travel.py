"""
Unit tests for Time-Travel Queries

Tests for timestamp-based queries, version number queries, and snapshot operations.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.datasets.models import Dataset, DatasetSnapshot
from hub.apps.datasets.time_travel import TimeTravelQuery
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class TimeTravelQueryTest(TestCase):
    """Test TimeTravelQuery"""
    
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
    
    def test_get_version_at_timestamp(self):
        """Test getting version at specific timestamp"""
        # Create versions at different times
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
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
            created_by=self.user
        )
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user
        )
        v2.created_at = timezone.now() - timedelta(days=1)
        v2.save()
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)
        
        # Query at different timestamps
        timestamp_before = timezone.now() - timedelta(days=5)
        result = TimeTravelQuery.get_version_at_timestamp(
            self.asset.id,
            self.tenant.id,
            timestamp_before
        )
        self.assertIsNone(result)
        
        timestamp_between = timezone.now() - timedelta(days=2)
        result = TimeTravelQuery.get_version_at_timestamp(
            self.asset.id,
            self.tenant.id,
            timestamp_between
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.id, v1.id)
        
        timestamp_after = timezone.now()
        result = TimeTravelQuery.get_version_at_timestamp(
            self.asset.id,
            self.tenant.id,
            timestamp_after
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.id, v2.id)
    
    def test_get_version_by_number(self):
        """Test getting version by version number"""
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v1, is_current=False)
        
        file2 = File.objects.create(
            tenant=self.tenant,
            name="test2.csv",
            content_type="text/csv",
            size=2000,
            status=FileStatus.ACTIVE,
            storage_path="test/test2.csv",
            content_sha256="def456",
            created_by=self.user
        )
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=True)
        
        # Query by version number
        result = TimeTravelQuery.get_version_by_number(
            self.asset.id,
            self.tenant.id,
            1
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.id, v1.id)
        self.assertEqual(result.version, 1)
        
        result = TimeTravelQuery.get_version_by_number(
            self.asset.id,
            self.tenant.id,
            2
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.id, v2.id)
        self.assertEqual(result.version, 2)
    
    def test_get_versions_in_range(self):
        """Test getting versions in time range"""
        # Create versions at different times
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        v1.created_at = timezone.now() - timedelta(days=5)
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
            created_by=self.user
        )
        v2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_by=self.user
        )
        v2.created_at = timezone.now() - timedelta(days=2)
        v2.save()
        VersionHistoryManager.create_version(v2, parent_version=v1, is_current=False)
        
        file3 = File.objects.create(
            tenant=self.tenant,
            name="test3.csv",
            content_type="text/csv",
            size=3000,
            status=FileStatus.ACTIVE,
            storage_path="test/test3.csv",
            content_sha256="ghi789",
            created_by=self.user
        )
        v3 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file3,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=3,
            created_by=self.user
        )
        v3.created_at = timezone.now() - timedelta(days=1)
        v3.save()
        VersionHistoryManager.create_version(v3, parent_version=v2, is_current=True)
        
        # Query versions in range
        start = timezone.now() - timedelta(days=3)
        end = timezone.now()
        
        results = TimeTravelQuery.get_versions_in_range(
            self.asset.id,
            self.tenant.id,
            start_timestamp=start,
            end_timestamp=end
        )
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, v2.id)
        self.assertEqual(results[1].id, v3.id)
    
    def test_create_snapshot_full(self):
        """Test creating full snapshot"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            sample_data_json=[{"col1": "value1"}],
            row_count=100,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            version_tags=["production"],
            created_by=self.user
        )
        VersionHistoryManager.create_version(dataset, is_current=True)
        
        snapshot = TimeTravelQuery.create_snapshot(dataset, snapshot_type="FULL")
        
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.dataset, dataset)
        self.assertEqual(snapshot.snapshot_type, "FULL")
        self.assertIn('schema_json', snapshot.snapshot_data)
        self.assertIn('sample_data_json', snapshot.snapshot_data)
        self.assertIn('row_count', snapshot.snapshot_data)
        self.assertIn('semantic_version', snapshot.snapshot_data)
    
    def test_create_snapshot_schema_only(self):
        """Test creating schema-only snapshot"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(dataset, is_current=True)
        
        snapshot = TimeTravelQuery.create_snapshot(dataset, snapshot_type="SCHEMA_ONLY")
        
        self.assertEqual(snapshot.snapshot_type, "SCHEMA_ONLY")
        self.assertIn('schema_json', snapshot.snapshot_data)
        self.assertNotIn('sample_data_json', snapshot.snapshot_data)
    
    def test_restore_from_snapshot(self):
        """Test restoring dataset from snapshot"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            sample_data_json=[{"col1": "value1"}],
            row_count=100,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            version_tags=["production"],
            created_by=self.user
        )
        VersionHistoryManager.create_version(dataset, is_current=True)
        
        snapshot = TimeTravelQuery.create_snapshot(dataset, snapshot_type="FULL")
        
        # Restore from snapshot
        restored = TimeTravelQuery.restore_from_snapshot(snapshot)
        
        self.assertIsNotNone(restored)
        self.assertEqual(restored.asset, self.asset)
        self.assertEqual(restored.version, 2)  # Next version
        self.assertEqual(restored.schema_json, dataset.schema_json)
        self.assertEqual(restored.semantic_version, "1.0.0")
        self.assertTrue(restored.is_current)
    
    def test_get_snapshots_for_dataset(self):
        """Test getting all snapshots for a dataset"""
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(dataset, is_current=True)
        
        # Create multiple snapshots
        snapshot1 = TimeTravelQuery.create_snapshot(dataset, snapshot_type="FULL")
        snapshot2 = TimeTravelQuery.create_snapshot(dataset, snapshot_type="SCHEMA_ONLY")
        
        snapshots = TimeTravelQuery.get_snapshots_for_dataset(dataset)
        
        self.assertEqual(len(snapshots), 2)
        self.assertIn(snapshot1.id, {s.id for s in snapshots})
        self.assertIn(snapshot2.id, {s.id for s in snapshots})

