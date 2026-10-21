"""
Integration tests for Observability API Views

Tests for observability API endpoints.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.observability.schema_drift import SchemaDriftDetector
from hub.apps.observability.volume import VolumeMonitor
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class PipelineMonitoringIntegrationTest(TestCase):
    """Integration tests for Pipeline Monitoring API"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

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

        self.client.force_authenticate(user=self.user)

        # Create pipeline executions
        from hub.apps.observability.pipeline_monitoring import PipelineMonitor

        for i in range(5):
            PipelineMonitor.record_execution(
                tenant_id=str(self.tenant.id),
                pipeline_type="SCHEDULED_INGESTION",
                pipeline_id=f"123e4567-e89b-12d3-a456-42661417400{i}",
                pipeline_name=f"Test Pipeline {i}",
                status="COMPLETED" if i < 4 else "FAILED",
                started_at=timezone.now() - timedelta(seconds=60),
                completed_at=timezone.now(),
                execution_time_seconds=60.0,
                items_processed=100,
                items_failed=0 if i < 4 else 10,
            )

    def test_get_pipeline_dashboard(self):
        """Test GET /api/v1/observability/pipelines endpoint"""
        response = self.client.get("/api/v1/observability/pipelines/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("summary", response.data)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["summary"]["total_executions"], 5)
        self.assertEqual(response.data["summary"]["completed_executions"], 4)
        self.assertEqual(response.data["summary"]["failed_executions"], 1)

    def test_get_pipeline_dashboard_with_filters(self):
        """Test pipeline dashboard with filters"""
        response = self.client.get(
            "/api/v1/observability/pipelines/?pipeline_type=SCHEDULED_INGESTION&limit=10"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        # Verify filter actually returned results (setUp creates SCHEDULED_INGESTION pipelines)
        self.assertGreater(
            len(results), 0, "Filter returned no results despite matching pipelines in setUp"
        )
        # All results should be SCHEDULED_INGESTION
        for result in results:
            self.assertEqual(result["pipeline_type"], "SCHEDULED_INGESTION")


class DataSLAsIntegrationTest(TestCase):
    """Integration tests for Data SLAs API"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

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
            description="Test asset",
        )

        self.client.force_authenticate(user=self.user)

        # Create SLAs
        from hub.apps.observability.data_slas import DataSLAMonitor

        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Freshness SLA",
            sla_type="FRESHNESS",
            asset_id=str(self.asset.id),
            freshness_sla_seconds=86400,
        )

        DataSLAMonitor.create_sla(
            tenant_id=str(self.tenant.id),
            name="Quality SLA",
            sla_type="QUALITY",
            asset_id=str(self.asset.id),
            quality_target_score=0.95,
        )

    def test_get_slas_dashboard(self):
        """Test GET /api/v1/observability/slas endpoint"""
        response = self.client.get("/api/v1/observability/slas/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("summary", response.data)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["summary"]["total_slas"], 2)
        self.assertEqual(response.data["summary"]["active_slas"], 2)

    def test_get_slas_dashboard_with_filters(self):
        """Test SLAs dashboard with filters"""
        response = self.client.get("/api/v1/observability/slas/?sla_type=FRESHNESS")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["sla_type"], "FRESHNESS")


class DataIncidentsIntegrationTest(TestCase):
    """Integration tests for Data Incident Management API"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)

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
            description="Test asset",
        )

        self.client.force_authenticate(user=self.user)

        # Create incidents
        from hub.apps.observability.incident_management import IncidentManager

        IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident 1",
            description="Test description 1",
            incident_type="FRESHNESS_VIOLATION",
            severity="HIGH",
            resource_type="ASSET",
            resource_id=str(self.asset.id),
            detected_by_id=str(self.user.id),
        )

        incident2 = IncidentManager.create_incident(
            tenant_id=str(self.tenant.id),
            title="Test Incident 2",
            description="Test description 2",
            incident_type="QUALITY_VIOLATION",
            severity="MEDIUM",
            resource_type="ASSET",
            resource_id=str(self.asset.id),
            detected_by_id=str(self.user.id),
        )

        # Resolve one incident
        IncidentManager.update_incident_status(
            incident_id=str(incident2.id),
            status="RESOLVED",
            resolution_notes="Resolved",
            resolved_by_id=str(self.user.id),
        )

    def test_get_incidents_dashboard(self):
        """Test GET /api/v1/observability/incidents endpoint"""
        response = self.client.get("/api/v1/observability/incidents/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("summary", response.data)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["summary"]["total_incidents"], 2)
        self.assertEqual(response.data["summary"]["detected_incidents"], 1)
        self.assertEqual(response.data["summary"]["resolved_incidents"], 1)

    def test_create_incident(self):
        """Test POST /api/v1/observability/incidents endpoint"""
        response = self.client.post(
            "/api/v1/observability/incidents/",
            {
                "title": "New Incident",
                "description": "New incident description",
                "incident_type": "PIPELINE_FAILURE",
                "severity": "CRITICAL",
                "resource_type": "ASSET",
                "resource_id": str(self.asset.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], "DETECTED")

    def test_update_incident(self):
        """Test PATCH /api/v1/observability/incidents/update endpoint"""
        from hub.apps.observability.models import DataIncident

        incident = DataIncident.objects.filter(tenant=self.tenant).first()

        response = self.client.patch(
            f"/api/v1/observability/incidents/update/?incident_id={incident.id}",
            {"status": "TRIAGED"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "TRIAGED")

    def test_get_incidents_with_filters(self):
        """Test incidents dashboard with filters"""
        response = self.client.get("/api/v1/observability/incidents/?status=RESOLVED")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], "RESOLVED")


class ObservabilityViewSetTest(TestCase):
    """Test ObservabilityViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)

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
            schema_json={"fields": [{"name": "email", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_freshness_dashboard_endpoint(self):
        """Test freshness dashboard endpoint"""
        # Record a metric
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id), dataset=self.dataset, freshness_sla="HOURLY"
        )

        url = reverse("observability-get-freshness-dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("summary", response.data)

    def test_stale_data_endpoint(self):
        """Test stale data endpoint"""
        from datetime import timedelta

        from django.utils import timezone

        # Record stale metric
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            last_update_time=timezone.now() - timedelta(hours=2),
            freshness_sla="HOURLY",
        )

        url = reverse("observability-get-stale-data")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_record_metric_endpoint(self):
        """Test record metric endpoint"""
        url = reverse("observability-record-metric")
        response = self.client.post(
            url,
            {
                "dataset_id": str(self.dataset.id),
                "row_count": 1000,
                "size_bytes": 50000,
                "freshness_sla": "HOURLY",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

    def test_volume_dashboard_endpoint(self):
        """Test volume dashboard endpoint"""
        # Record metrics and aggregate
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id), dataset=self.dataset, row_count=1000, size_bytes=50000
        )

        VolumeMonitor.aggregate_daily_trends(
            tenant_id=str(self.tenant.id), dataset_id=str(self.dataset.id), days=30
        )

        url = reverse("observability-get-volume-dashboard")
        response = self.client.get(url, {"period_type": "DAILY"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("summary", response.data)

    def test_schema_drift_dashboard_endpoint(self):
        """Test schema drift dashboard endpoint"""
        # Record initial metric
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            schema_json=self.dataset.schema_json,
        )

        # Detect drift
        new_schema = {
            "fields": [
                {"name": "email", "type": "string"},
                {"name": "age", "type": "integer"},  # New field
            ]
        }

        SchemaDriftDetector.detect_drift(
            tenant_id=str(self.tenant.id), dataset=self.dataset, current_schema_json=new_schema
        )

        url = reverse("observability-get-schema-drift-dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("summary", response.data)
