"""
Unit tests for Schema Drift Detection

Tests for schema comparison, drift detection, and tolerance configuration.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.observability.schema_drift import SchemaDriftDetector
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class SchemaDriftDetectorTest(TestCase):
    """Test SchemaDriftDetector"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
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
                    {"name": "email", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True},
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Record initial metric
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            schema_json=self.dataset.schema_json,
        )

    def test_calculate_schema_hash(self):
        """Test schema hash calculation"""
        schema = {"fields": [{"name": "email", "type": "string"}]}
        hash1 = SchemaDriftDetector.calculate_schema_hash(schema)
        hash2 = SchemaDriftDetector.calculate_schema_hash(schema)

        self.assertIsNotNone(hash1)
        self.assertEqual(hash1, hash2)  # Same schema = same hash

        # Different schema = different hash
        schema2 = {"fields": [{"name": "email", "type": "integer"}]}
        hash3 = SchemaDriftDetector.calculate_schema_hash(schema2)
        self.assertNotEqual(hash1, hash3)

    def test_compare_schemas(self):
        """Test schema comparison"""
        previous = {
            "fields": [
                {"name": "email", "type": "string", "nullable": False},
                {"name": "name", "type": "string", "nullable": True},
            ]
        }

        current = {
            "fields": [
                {"name": "email", "type": "string", "nullable": False},
                {"name": "name", "type": "string", "nullable": True},
                {"name": "age", "type": "integer", "nullable": True},  # New field
            ]
        }

        comparison = SchemaDriftDetector.compare_schemas(previous, current)

        self.assertTrue(comparison["has_changes"])
        self.assertIn("age", comparison["new_fields"])
        self.assertEqual(len(comparison["removed_fields"]), 0)

    def test_compare_schemas_type_change(self):
        """Test schema comparison with type change"""
        previous = {"fields": [{"name": "email", "type": "string", "nullable": False}]}

        current = {
            "fields": [{"name": "email", "type": "integer", "nullable": False}]  # Type change
        }

        comparison = SchemaDriftDetector.compare_schemas(previous, current)

        self.assertTrue(comparison["has_changes"])
        self.assertEqual(len(comparison["type_changes"]), 1)
        self.assertEqual(comparison["type_changes"][0]["field_name"], "email")

    def test_detect_drift(self):
        """Test drift detection"""
        # Update schema
        new_schema = {
            "fields": [
                {"name": "email", "type": "string", "nullable": False},
                {"name": "name", "type": "string", "nullable": True},
                {"name": "age", "type": "integer", "nullable": True},  # New field
            ]
        }

        drift = SchemaDriftDetector.detect_drift(
            tenant_id=str(self.tenant.id), dataset=self.dataset, current_schema_json=new_schema
        )

        self.assertIsNotNone(drift)
        self.assertIn("age", drift.new_fields)
        self.assertEqual(drift.drift_severity, "MINOR")  # New field is minor

    def test_drift_severity_breaking(self):
        """Test breaking change detection"""
        previous = {"fields": [{"name": "email", "type": "string", "nullable": False}]}

        current = {"fields": []}  # Field removed

        comparison = SchemaDriftDetector.compare_schemas(previous, current)
        severity, is_within_tolerance = SchemaDriftDetector.calculate_drift_severity(
            comparison["new_fields"],
            comparison["removed_fields"],
            comparison["type_changes"],
            comparison["nullable_changes"],
            SchemaDriftDetector.DEFAULT_TOLERANCE,
        )

        self.assertEqual(severity, "BREAKING")
        self.assertFalse(is_within_tolerance)

    def test_get_drift_dashboard(self):
        """Test drift dashboard"""
        # Create a drift
        new_schema = {
            "fields": [
                {"name": "email", "type": "string", "nullable": False},
                {"name": "name", "type": "string", "nullable": True},
                {"name": "age", "type": "integer", "nullable": True},
            ]
        }

        SchemaDriftDetector.detect_drift(
            tenant_id=str(self.tenant.id), dataset=self.dataset, current_schema_json=new_schema
        )

        dashboard = SchemaDriftDetector.get_drift_dashboard(
            tenant_id=str(self.tenant.id), dataset_id=str(self.dataset.id)
        )

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertGreater(len(dashboard["results"]), 0)
