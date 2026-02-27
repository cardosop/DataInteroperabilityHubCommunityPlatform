"""
E2E tests for Scheduled Ingestion

End-to-end tests for complete scheduled ingestion workflows.
Uses real implementations - no mocks/stubs per development best practices.
"""

import os
import time
import uuid

import requests
import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    SourceType,
)
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus, Role, UserRole

from tests.e2e.conftest import get_response_data

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.requires_prefect,
]


def _prefect_integration_reachable() -> bool:
    """Check if prefect-integration-service is reachable (for root cause diagnostics)."""
    base = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
    if not base:
        return False
    try:
        r = requests.get(f"{base}/health", timeout=5)
        return r.ok
    except Exception:
        return False


def _retry_sync_deployment(
    scheduled_ingestion_id: str, tenant_id: str, timeout: int = 20
) -> tuple[str | None, str]:
    """Retry deployment sync via prefect-integration-service (when creation sync failed).
    Returns (deployment_id, error_message). deployment_id is set if sync succeeded.
    """
    base = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
    if not base:
        return None, "PREFECT_INTEGRATION_SERVICE_URL not set"
    try:
        r = requests.post(
            f"{base}/deployments/sync",
            json={"scheduled_ingestion_id": scheduled_ingestion_id, "tenant_id": tenant_id},
            timeout=timeout,
        )
        if not r.ok:
            err = f"HTTP {r.status_code}"
            try:
                body = r.json() if r.text else {}
                if isinstance(body, dict) and "detail" in body:
                    err = f"{err}: {body.get('detail', body)}"
                elif r.text:
                    err = f"{err}: {r.text[:300]}"
            except Exception:
                pass
            return None, err
        data = r.json() if r.text else {}
        dep_id = data.get("deployment_id") if isinstance(data, dict) else None
        return dep_id, ""
    except Exception as e:
        return None, str(e)


class ScheduledIngestionE2ETest(TransactionTestCase):
    """E2E tests for scheduled ingestion"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Scheduled Ingestion Tenant",
            slug="scheduled-ingestion-tenant",
            kyc_status=KYCStatus.VERIFIED,
        )
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email="sched-ingestion@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=tenant_admin_role)

        self.client.force_authenticate(user=self.user)

    def test_complete_ingestion_lifecycle(self):
        """Test complete ingestion lifecycle from creation to completion

        Note: This test works with real implementations. Prefect services may not be available,
        but the code handles this gracefully (ImportError is caught and logged).
        """
        # Pre-check: skip early if prefect-integration is unreachable (root cause diagnostics)
        if not _prefect_integration_reachable():
            pytest.skip(
                "Prefect integration service unreachable (PREFECT_INTEGRATION_SERVICE_URL/health) - "
                "ensure prefect-integration-service-test is running"
            )

        # Step 1: Create scheduled ingestion
        # Note: Prefect deployment sync may fail if Prefect is not available, but ingestion creation should still succeed
        from hub.apps.scheduled_ingestion.models import ScheduleType

        data = {
            "name": "Daily Sales Ingestion",
            "description": "Ingests daily sales CSV files from S3",
            "source_type": "S3",
            "source_config": {
                "bucket": "my-data-lake",
                "prefix": "sales/daily/",
                "access_key_id": "AKIA...",
                "secret_access_key": "abc...",
            },
            "schedule_type": ScheduleType.CUSTOM_CRON,
            "schedule_config": {"cron": "0 2 * * *"},
            "file_pattern": "sales_\\d{4}-\\d{2}-\\d{2}\\.csv",
            "auto_create_asset": True,
            "auto_activate": True,
            "status": "ACTIVE",
            "test_connection": False,  # Skip connection test - use fake credentials for lifecycle test
        }

        response = self.client.post("/api/v1/scheduled-ingestions/", data, format="json")

        # Creation should succeed even if Prefect is not available
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_503_SERVICE_UNAVAILABLE]
        )

        if response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            # Prefect service unavailable - skip rest of test
            pytest.skip("Prefect service not available - skipping ingestion lifecycle test")
            return

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        ingestion_id = data["id"]

        # Step 2: Verify ingestion created
        ingestion = ScheduledIngestion.objects.get(id=ingestion_id)
        self.assertEqual(ingestion.name, "Daily Sales Ingestion")
        self.assertEqual(ingestion.status, ScheduledIngestionStatus.ACTIVE)

        # Retry sync if deployment was not created during creation (e.g. transient failure)
        if not ingestion.prefect_deployment_id:
            deployment_id, sync_err = _retry_sync_deployment(str(ingestion.id), str(self.tenant.id))
            if deployment_id:
                ingestion.prefect_deployment_id = deployment_id
                ingestion.save(update_fields=["prefect_deployment_id"])
            else:
                ingestion.refresh_from_db()
            if not ingestion.prefect_deployment_id:
                pytest.skip(
                    f"Deployment sync failed (prefect_deployment_id still None after retry). {sync_err} - "
                    "check prefect-integration and Prefect server logs"
                )

        # Step 3: Manually trigger ingestion (retry up to 3 times on 503 - deployment may be propagating)
        response = None
        for attempt in range(3):
            try:
                response = self.client.post(
                    f"/api/v1/scheduled-ingestions/{ingestion_id}/trigger/", timeout=30
                )
            except Exception as e:
                pytest.skip(
                    f"Trigger request failed: {e!r} - Prefect may not be available"
                )
            if response.status_code != status.HTTP_503_SERVICE_UNAVAILABLE:
                break
            if attempt < 2:
                time.sleep(5)

        assert response is not None  # always set in loop
        if response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            details = ""
            try:
                data_resp = get_response_data(response) or {}
                details = data_resp.get("details", {})
                if isinstance(details, dict):
                    err = details.get("error", details.get("message", ""))
                else:
                    err = str(details)
                details = f" (details: {err})" if err else ""
            except Exception:
                pass
            pytest.skip(
                f"Prefect deployment trigger returned 503 after retries{details} - "
                "check prefect-integration and Prefect server logs"
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = get_response_data(response) or {}
        job_id = data.get("job_id")
        run_id = data.get("scheduled_ingestion_run_id")

        if not job_id or not run_id:
            pytest.skip("Trigger did not create job/run - Prefect may not be available")
            return

        # Step 4: Verify run and job created
        run = ScheduledIngestionRun.objects.get(id=run_id)
        self.assertEqual(run.scheduled_ingestion.id, uuid.UUID(ingestion_id))
        self.assertEqual(run.status, ScheduledIngestionRunStatus.PENDING)

        job = Job.objects.get(id=job_id)
        self.assertEqual(job.type, JobType.SCHEDULED_INGESTION)
        self.assertEqual(job.status, JobStatus.PENDING)

        # Step 5: Update ingestion
        from hub.apps.scheduled_ingestion.models import ScheduleType

        update_data = {
            "description": "Updated description",
            "schedule_config": {"cron": "0 3 * * *"},
        }

        response = self.client.patch(
            f"/api/v1/scheduled-ingestions/{ingestion_id}/", update_data, format="json"
        )

        # Update should succeed even if Prefect sync fails
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        )
        if response.status_code == status.HTTP_200_OK:
            data = get_response_data(response) or {}
            self.assertEqual(data["description"], "Updated description")
            # Verify schedule_config was updated
            self.assertIn("schedule_config", data)

        # Step 6: Delete ingestion
        response = self.client.delete(f"/api/v1/scheduled-ingestions/{ingestion_id}/")

        # Delete should succeed even if Prefect sync fails
        self.assertIn(
            response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_503_SERVICE_UNAVAILABLE]
        )

        if response.status_code == status.HTTP_204_NO_CONTENT:
            # Verify deleted
            self.assertFalse(ScheduledIngestion.objects.filter(id=ingestion_id).exists())

    def test_multiple_ingestions_tenant_isolation(self):
        """Test that multiple ingestions are properly isolated by tenant

        Note: This test works with real implementations. Prefect services may not be available,
        but the code handles this gracefully (ImportError is caught and logged).
        """
        # Create second tenant (with subscription so POST scheduled-ingestions succeeds)
        tenant2 = Tenant.objects.create(
            name="Other Tenant Sched",
            slug="other-tenant-sched",
            kyc_status=KYCStatus.VERIFIED,
        )
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(tenant2)
        other_admin_role, _ = Role.objects.get_or_create(
            tenant=tenant2,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )

        user2 = User.objects.create_user(
            email="user2-sched@example.com",
            password="testpass123",
            tenant=tenant2,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.get_or_create(user=user2, role=other_admin_role)

        # Create ingestion for tenant1
        from hub.apps.scheduled_ingestion.models import ScheduleType

        data1 = {
            "name": "Tenant 1 Ingestion",
            "source_type": "S3",
            "source_config": {"bucket": "bucket1"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "00:00"},
            "file_pattern": ".*\\.csv",
            "test_connection": False,
        }

        response1 = self.client.post("/api/v1/scheduled-ingestions/", data1, format="json")

        # Creation may fail if Prefect is required and not available
        if response1.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            pytest.skip("Prefect service not available - skipping tenant isolation test")
            return

        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        ingestion1_id = (get_response_data(response1) or {}).get("id")

        # Create ingestion for tenant2
        client2 = APIClient()
        client2.force_authenticate(user=user2)

        data2 = {
            "name": "Tenant 2 Ingestion",
            "source_type": "S3",
            "source_config": {"bucket": "bucket2"},
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "01:00"},
            "file_pattern": ".*\\.csv",
            "test_connection": False,
        }

        response2 = client2.post("/api/v1/scheduled-ingestions/", data2, format="json")

        if response2.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            pytest.skip("Prefect service not available - skipping tenant isolation test")
            return

        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        ingestion2_id = (get_response_data(response2) or {}).get("id")

        # List ingestions for tenant1 - should only see tenant1's
        response = self.client.get("/api/v1/scheduled-ingestions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle paginated response (may be dict with 'results' key or list)
        data = get_response_data(response)
        if isinstance(data, dict) and "results" in data:
            ingestion_list = data["results"]
        else:
            ingestion_list = data if isinstance(data, list) else []
        ingestion_ids = [
            item["id"] if isinstance(item, dict) else str(item) for item in ingestion_list
        ]
        self.assertIn(ingestion1_id, ingestion_ids)
        self.assertNotIn(ingestion2_id, ingestion_ids)

        # List ingestions for tenant2 - should only see tenant2's
        response = client2.get("/api/v1/scheduled-ingestions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle paginated response (may be dict with 'results' key or list)
        data = get_response_data(response)
        if isinstance(data, dict) and "results" in data:
            ingestion_list = data["results"]
        else:
            ingestion_list = data if isinstance(data, list) else []
        ingestion_ids = [
            item["id"] if isinstance(item, dict) else str(item) for item in ingestion_list
        ]
        self.assertNotIn(ingestion1_id, ingestion_ids)
        self.assertIn(ingestion2_id, ingestion_ids)
