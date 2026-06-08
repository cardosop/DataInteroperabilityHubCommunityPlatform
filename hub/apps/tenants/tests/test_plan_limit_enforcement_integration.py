"""
Integration tests for plan limit enforcement in asset/dataset/scheduled ingestion creation.

Tests use real DB, no mocks/stubs per Phase 25 requirements.
"""

import pytest
from django.contrib.auth import get_user_model
from django.db.transaction import TransactionManagementError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.core.services.base import ValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.tenants.models import PlanTier, Tenant, TenantPlan
import uuid

User = get_user_model()


pytestmark = pytest.mark.django_db(transaction=True)


class PlanLimitEnforcementIntegrationTest(TestCase):
    """Integration tests for plan limit enforcement"""

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        except TransactionManagementError:
            # TransactionTestCase truncates tables outside an atomic
            # block; the subsequent set_rollback(False) raises a
            # cosmetic error.  The database is already clean.
            pass

    def setUp(self):
        """Set up test data"""
        # TransactionTestCase._fixture_teardown may leave the default
        # connection with a closed psycopg2 object.  Only touch the
        # 'default' alias — other aliases (admin, baas) are restricted
        # and would raise DatabaseOperationForbidden.
        from django.db import connections
        conn = connections["default"]
        try:
            conn.close_if_unusable_or_obsolete()
        except Exception:
            pass
        if conn.connection is None or getattr(conn.connection, "closed", 1):
            try:
                conn.close()
            except Exception:
                pass
            conn.connection = None
            conn.closed_in_transaction = False
            conn.needs_rollback = False
            conn.in_atomic_block = False
            conn.savepoint_ids = []
            conn.atomic_blocks = []
            conn.ensure_connection()

        # Create plan with low limits
        self.limited_plan = TenantPlan.objects.create(
            name=f"Limited Plan {uuid.uuid4().hex[:8]}",
            slug=f"limited-{uuid.uuid4().hex[:8]}",
            tier=PlanTier.FREE,
            limits_json={
                "max_assets": 2,
                "max_datasets": 3,
                "max_scheduled_ingestions": 1,
            },
        )

        # Create tenant with limited plan
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", plan=self.limited_plan
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_asset_creation_within_limit_success(self):
        """Success: creating assets up to limit succeeds (no ValidationError)."""
        from hub.apps.assets.services import AssetService

        service = AssetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        asset1 = service.create_asset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            key="asset-1",
            name="Asset 1",
        )
        self.assertIsNotNone(asset1.id)
        self.assertEqual(Asset.objects.filter(tenant=self.tenant).count(), 1)

    def test_asset_creation_enforces_limit(self):
        """Failure: creating asset over plan limit raises ValidationError with plan_limit_exceeded."""
        # Create assets up to limit
        asset1 = Asset.objects.create(tenant=self.tenant, key="asset-1", name="Asset 1")
        asset2 = Asset.objects.create(tenant=self.tenant, key="asset-2", name="Asset 2")

        # Try to create third asset - should fail
        from hub.apps.assets.services import AssetService

        service = AssetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        with self.assertRaises(ValidationError) as cm:
            service.create_asset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                key="asset-3",
                name="Asset 3",
            )

        error = cm.exception
        self.assertEqual(error.code, "plan_limit_exceeded")
        self.assertEqual(error.http_status, 403)
        self.assertEqual(error.details["limit_key"], "max_assets")
        self.assertEqual(error.details["current"], 2)
        self.assertEqual(error.details["max"], 2)

    def test_dataset_creation_enforces_limit(self):
        """Test dataset creation enforces plan limit"""
        # Create datasets up to limit
        from hub.apps.files.models import File, FileStatus

        # Create files first (must be ACTIVE for dataset creation)
        file_defaults = dict(
            tenant=self.tenant,
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            created_by=self.user,
            content_sha256="abc123",
        )
        file1 = File.objects.create(name="file1.csv", storage_path="file1.csv", **file_defaults)
        file2 = File.objects.create(name="file2.csv", storage_path="file2.csv", **file_defaults)
        file3 = File.objects.create(name="file3.csv", storage_path="file3.csv", **file_defaults)
        file4 = File.objects.create(name="file4.csv", storage_path="file4.csv", **file_defaults)

        # Create datasets up to limit
        from hub.apps.datasets.services import DatasetService

        service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        service.create_dataset(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), file_id=str(file1.id)
        )
        service.create_dataset(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), file_id=str(file2.id)
        )
        service.create_dataset(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), file_id=str(file3.id)
        )

        # Try to create fourth dataset - should fail
        with self.assertRaises(ValidationError) as cm:
            service.create_dataset(
                tenant_id=str(self.tenant.id), user_id=str(self.user.id), file_id=str(file4.id)
            )

        error = cm.exception
        self.assertEqual(error.code, "plan_limit_exceeded")
        self.assertEqual(error.http_status, 403)
        self.assertEqual(error.details["limit_key"], "max_datasets")
        self.assertEqual(error.details["current"], 3)
        self.assertEqual(error.details["max"], 3)

    def test_scheduled_ingestion_creation_enforces_limit(self):
        """Test scheduled ingestion creation enforces plan limit"""
        # Create scheduled ingestion up to limit
        from hub.apps.scheduled_ingestion.services import IngestionService

        service = IngestionService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        ingestion1 = service.create_scheduled_ingestion(
            tenant=self.tenant,
            created_by=self.user,
            name="Ingestion 1",
            source_type="S3",
            source_config={"bucket": "test-bucket", "prefix": "data/"},
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
        )

        # Try to create second scheduled ingestion - should fail
        with self.assertRaises(ValidationError) as cm:
            service.create_scheduled_ingestion(
                tenant=self.tenant,
                created_by=self.user,
                name="Ingestion 2",
                source_type="S3",
                source_config={"bucket": "test-bucket", "prefix": "data2/"},
                schedule_type="DAILY",
                schedule_config={"time": "00:00"},
                file_pattern=".*\\.csv",
            )

        error = cm.exception
        self.assertEqual(error.code, "plan_limit_exceeded")
        self.assertEqual(error.http_status, 403)
        self.assertEqual(error.details["limit_key"], "max_scheduled_ingestions")
        self.assertEqual(error.details["current"], 1)
        self.assertEqual(error.details["max"], 1)

    def test_unlimited_plan_allows_unlimited_resources(self):
        """Test unlimited plan (ENTERPRISE) allows unlimited resources"""
        # Create enterprise plan with unlimited limits
        import uuid as _uuid
        _uid = _uuid.uuid4().hex[:8]
        enterprise_plan = TenantPlan.objects.create(
            name=f"Enterprise Plan {_uid}",
            slug=f"enterprise-{_uid}",
            tier=PlanTier.ENTERPRISE,
            limits_json={
                "max_assets": None,
                "max_datasets": None,
                "max_scheduled_ingestions": None,
            },
        )

        # Update tenant to enterprise plan
        self.tenant.plan = enterprise_plan
        self.tenant.save()

        # Should be able to create many resources
        from hub.apps.assets.services import AssetService

        asset_service = AssetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create 10 assets - should all succeed
        for i in range(10):
            asset = asset_service.create_asset(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                key=f"asset-{i}",
                name=f"Asset {i}",
            )
            self.assertIsNotNone(asset)

        # Verify all were created
        self.assertEqual(Asset.objects.filter(tenant=self.tenant).count(), 10)
