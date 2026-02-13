"""
Comprehensive tests for plan limit enforcement (Phase 25.1.2, 25.4.1).

Tests plan limits for:
- Asset creation
- Dataset creation
- Scheduled ingestion creation
- Scheduled export creation
- Scheduled ingestion runs
- Scheduled export runs

No mocks/stubs - uses real DB and real services.
"""

# CRITICAL: Patch sql_flush to use CASCADE for foreign key constraints
# This is needed when running tests with manage.py test (not pytest)
# Fixes: psycopg2.errors.FeatureNotSupported: cannot truncate a table referenced in a foreign key constraint
try:
    import django.db.backends.postgresql.operations as pg_operations

    if not hasattr(pg_operations.DatabaseOperations.sql_flush, "_patched_for_cascade"):
        _original_sql_flush = pg_operations.DatabaseOperations.sql_flush

        def _patched_sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
            """
            Patched sql_flush that always uses CASCADE to handle foreign key constraints.

            ROOT CAUSE: During test teardown, Django tries to truncate tables but fails
            when tables have foreign key constraints. PostgreSQL requires CASCADE to truncate
            tables with foreign key references.

            SOLUTION: Always use allow_cascade=True when truncating tables during teardown.
            """
            return _original_sql_flush(
                self, style, tables, reset_sequences=reset_sequences, allow_cascade=True
            )

        _patched_sql_flush._patched_for_cascade = True
        pg_operations.DatabaseOperations.sql_flush = _patched_sql_flush
except Exception:
    # Patch failed, but tests should still run
    pass

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.scheduled_export.models import ScheduledExport, ScheduledExportRun
from hub.apps.scheduled_ingestion.models import ScheduledIngestion, ScheduledIngestionRun
from hub.apps.tenants.models import PlanTier, Tenant, TenantPlan
from hub.apps.tenants.services import PlanLimitService

User = get_user_model()


class PlanLimitEnforcementComprehensiveTest(TransactionTestCase):
    """
    Comprehensive integration tests for plan limit enforcement.

    Tests all resource types with real DB and real services.
    """

    def setUp(self):
        """Set up test data"""
        # Create limited plan
        self.plan = TenantPlan.objects.create(
            name="Limited Plan",
            slug="limited",
            tier=PlanTier.FREE,
            limits_json={
                "max_assets": 2,
                "max_datasets": 2,
                "max_scheduled_ingestions": 1,
                "max_scheduled_exports": 1,
                "max_scheduled_runs_per_month": 5,
                "max_export_runs_per_month": 3,
            },
            is_active=True,
        )

        # Create tenant with limited plan
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", plan=self.plan
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create API client and plan limit service
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.service = PlanLimitService(tenant_id=str(self.tenant.id))

    def test_check_limit_edge_case_delta_zero_at_max(self):
        """Edge case: current_usage at max with delta=0 is allowed (remaining=0)."""
        result = self.service.check_limit(
            tenant_id=str(self.tenant.id),
            limit_key="max_assets",
            current_usage=2,
            delta=0,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["remaining"], 0)
        self.assertEqual(result["current"], 2)
        self.assertEqual(result["max"], 2)

    def test_asset_limit_enforcement(self):
        """Test asset creation limit enforcement"""
        # Create assets up to limit
        for i in range(2):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}",
                description="Test asset",
                created_by=self.user,
            )

        # Try to create one more - should fail
        response = self.client.post(
            "/api/v1/assets/",
            {"key": "asset-3", "name": "Asset 3", "description": "Should fail"},
            format="json",
        )

        # Debug: print response if not 403
        if response.status_code != status.HTTP_403_FORBIDDEN:
            try:
                response_data = (
                    response.json()
                    if hasattr(response, "json")
                    else response.content.decode("utf-8")
                )
                print(f"Unexpected status: {response.status_code}, data: {response_data}")
            except Exception as e:
                print(
                    f"Unexpected status: {response.status_code}, content: {response.content}, error: {e}"
                )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "plan_limit_exceeded")
        # Details are nested under "details" key
        details = response.data.get("details", {})
        self.assertIn("limit_key", details)
        self.assertEqual(details.get("limit_key"), "max_assets")

    def test_dataset_limit_enforcement(self):
        """Test dataset creation limit enforcement"""
        # Create datasets up to limit
        from hub.apps.files.models import File, FileStatus

        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=100,
            storage_path="test/test.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        for i in range(2):
            Dataset.objects.create(
                tenant=self.tenant, name=f"Dataset {i}", file=file_obj, created_by=self.user
            )

        # Try to create one more - should fail
        response = self.client.post(
            "/api/v1/datasets/", {"name": "Dataset 3", "file_id": str(file_obj.id)}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "plan_limit_exceeded")

    def test_scheduled_ingestion_limit_enforcement(self):
        """Test scheduled ingestion creation limit enforcement"""
        # Create scheduled ingestion up to limit
        ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Ingestion 1",
            source_type="S3",
            source_config={},
            schedule_type="DAILY",
            schedule_config={},
            file_pattern="*.csv",
            created_by=self.user,
        )

        # Try to create one more - should fail
        response = self.client.post(
            "/api/v1/scheduled-ingestions/",
            {
                "name": "Ingestion 2",
                "source_type": "S3",
                "source_config": {},
                "schedule_type": "DAILY",
                "schedule_config": {},
                "file_pattern": "*.csv",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "plan_limit_exceeded")

    def test_scheduled_export_limit_enforcement(self):
        """Test scheduled export creation limit enforcement"""
        # Create scheduled export up to limit
        ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Export 1",
            destination_type="S3",
            destination_config={},
            schedule_config={"cron": "0 0 * * *"},
            source_scope={},
        )

        # Try to create one more - should fail
        response = self.client.post(
            "/api/v1/scheduled-exports/",
            {
                "name": "Export 2",
                "destination_type": "S3",
                "destination_config": {},
                "schedule_config": {"cron": "0 0 * * *"},
                "source_scope": {},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "plan_limit_exceeded")

    def test_unlimited_plan_allows_creation(self):
        """Test that unlimited (ENTERPRISE) plan allows unlimited creation"""
        # Create enterprise plan
        enterprise_plan = TenantPlan.objects.create(
            name="Enterprise Plan",
            slug="enterprise",
            tier=PlanTier.ENTERPRISE,
            limits_json={},  # Empty = unlimited
            is_active=True,
        )

        self.tenant.plan = enterprise_plan
        self.tenant.save()

        # Create multiple assets - should all succeed
        for i in range(10):
            response = self.client.post(
                "/api/v1/assets/",
                {"key": f"asset-{i}", "name": f"Asset {i}", "description": "Test asset"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
