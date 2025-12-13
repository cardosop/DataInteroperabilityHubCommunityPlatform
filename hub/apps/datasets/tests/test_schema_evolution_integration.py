"""
Integration tests for Schema Evolution Tracking

Tests for schema evolution in the context of dataset creation and version management.
"""
import pytest
from django.test import TestCase

from hub.apps.datasets.models import Dataset, SchemaVersion
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.datasets.schema_evolution import SchemaEvolutionTracker, CompatibilityLevel
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class SchemaEvolutionIntegrationTest(TestCase):
    """Integration tests for schema evolution"""
    
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
    
    def test_schema_evolution_automatic_tracking(self):
        """Test that schema evolution is automatically tracked on version creation"""
        # Create parent version
        parent = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(parent, semantic_version="1.0.0", is_current=False)
        
        # Verify schema version was created
        self.assertTrue(hasattr(parent, 'schema_version'))
        schema_v1 = parent.schema_version
        self.assertIsNotNone(schema_v1)
        self.assertEqual(schema_v1.compatibility_level, CompatibilityLevel.FULLY_COMPATIBLE.value)
        
        # Create child version
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
        
        child = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=file2,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True}
                ]
            },
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(child, parent_version=parent, semantic_version="1.1.0", is_current=True)
        
        # Verify schema version was created with correct compatibility
        self.assertTrue(hasattr(child, 'schema_version'))
        schema_v2 = child.schema_version
        self.assertIsNotNone(schema_v2)
        self.assertEqual(schema_v2.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE.value)
        self.assertEqual(schema_v2.parent_schema_version, schema_v1)
        self.assertIn('FIELD_ADDED', schema_v2.change_summary)
    
    def test_schema_evolution_chain(self):
        """Test schema evolution through multiple versions"""
        # Create version chain: v1 -> v2 -> v3
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)
        
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
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True}
                ]
            },
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.1.0", is_current=False)
        
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
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True},
                    {"name": "col3", "data_type": "boolean", "nullable": True}
                ]
            },
            format="CSV",
            version=3,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v3, parent_version=v2, semantic_version="1.2.0", is_current=True)
        
        # Verify schema evolution chain
        schema_v1 = v1.schema_version
        schema_v2 = v2.schema_version
        schema_v3 = v3.schema_version
        
        self.assertIsNone(schema_v1.parent_schema_version)
        self.assertEqual(schema_v2.parent_schema_version, schema_v1)
        self.assertEqual(schema_v3.parent_schema_version, schema_v2)
        
        # Verify compatibility levels
        self.assertEqual(schema_v1.compatibility_level, CompatibilityLevel.FULLY_COMPATIBLE.value)
        self.assertEqual(schema_v2.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE.value)
        self.assertEqual(schema_v3.compatibility_level, CompatibilityLevel.BACKWARD_COMPATIBLE.value)
    
    def test_change_log_generation_integration(self):
        """Test change log generation in integration context"""
        # Create versions
        v1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v1, semantic_version="1.0.0", is_current=False)
        
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
            schema_json={
                "fields": [
                    {"name": "col1", "data_type": "string", "nullable": True},
                    {"name": "col2", "data_type": "integer", "nullable": True}
                ]
            },
            format="CSV",
            version=2,
            created_by=self.user
        )
        VersionHistoryManager.create_version(v2, parent_version=v1, semantic_version="1.1.0", is_current=True)
        
        # Generate change log
        change_log = SchemaEvolutionTracker.generate_change_log(v1, v2)
        
        # Verify change log structure
        self.assertIn('from_version', change_log)
        self.assertIn('to_version', change_log)
        self.assertIn('compatibility_level', change_log)
        self.assertIn('summary', change_log)
        self.assertIn('changes', change_log)
        
        # Verify change log content
        self.assertEqual(change_log['from_version']['semantic_version'], "1.0.0")
        self.assertEqual(change_log['to_version']['semantic_version'], "1.1.0")
        self.assertEqual(change_log['compatibility_level'], CompatibilityLevel.BACKWARD_COMPATIBLE.value)
        self.assertGreater(change_log['summary'].get('FIELD_ADDED', 0), 0)

