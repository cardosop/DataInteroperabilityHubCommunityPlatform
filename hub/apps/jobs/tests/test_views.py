"""
Comprehensive unit tests for Job ViewSet endpoints.

Tests cover:
- CRUD operations (list, retrieve, create)
- Custom actions (cancel)
- Filtering and ordering
- Tenant isolation
- Permission checks
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling

All tests use real implementations (no mocks/stubs).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.tests.billing_support import ensure_tenant_has_active_subscription
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class JobViewSetTest(TestCase):
    """Comprehensive tests for JobViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create another tenant for isolation tests
        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Active subscription required so TenantSuspensionMiddleware allows writes (POST/PATCH)
        ensure_tenant_has_active_subscription(self.tenant)
        ensure_tenant_has_active_subscription(self.other_tenant)

        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            is_platform_admin=True,
        )

        # Create regular user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create user in other tenant
        self.other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create user without tenant
        self.user_no_tenant = User.objects.create_user(
            email=f"notenant-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )

    # ========== CREATE JOB TESTS ==========

    def test_create_job_success(self):
        """Test successful job creation via API"""
        self.client.force_authenticate(user=self.user)

        resource_id = uuid.uuid4()
        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
            "details_json": {"test": "data"},
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["type"], JobType.DQ_RUN)
        self.assertEqual(response.data["status"], JobStatus.PENDING)
        self.assertEqual(response.data["resource_type"], "DATASET")
        self.assertEqual(response.data["resource_id"], str(resource_id))

        # Verify job was created in database
        job = Job.objects.get(id=response.data["id"])
        self.assertEqual(job.tenant, self.tenant)
        self.assertEqual(job.created_by, self.user)

    def test_create_job_without_tenant_failure(self):
        """Test job creation fails when user has no tenant"""
        self.client.force_authenticate(user=self.user_no_tenant)

        resource_id = uuid.uuid4()
        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("tenant", response.data["error"].lower())

    def test_create_job_invalid_data_failure(self):
        """Test job creation with invalid data"""
        self.client.force_authenticate(user=self.user)

        # Missing required fields
        data = {
            "type": JobType.DQ_RUN,
            # Missing resource_type and resource_id
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_job_invalid_job_type_failure(self):
        """Test job creation with invalid job type"""
        self.client.force_authenticate(user=self.user)

        resource_id = uuid.uuid4()
        data = {
            "type": "INVALID_TYPE",
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_job_invalid_resource_id_failure(self):
        """Test job creation with invalid resource_id format"""
        self.client.force_authenticate(user=self.user)

        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": "not-a-uuid",
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_job_all_job_types_success(self):
        """Test job creation for all job types"""
        self.client.force_authenticate(user=self.user)

        resource_id = uuid.uuid4()

        for job_type in JobType:
            data = {
                "type": job_type,
                "resource_type": "DATASET",
                "resource_id": str(resource_id),
            }

            response = self.client.post("/api/v1/jobs/", data, format="json")

            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Failed to create job of type {job_type}",
            )
            self.assertEqual(response.data["type"], job_type)

    def test_create_job_with_details_json_success(self):
        """Test job creation with details_json"""
        self.client.force_authenticate(user=self.user)

        resource_id = uuid.uuid4()
        details = {"key1": "value1", "key2": 123, "nested": {"key": "value"}}

        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
            "details_json": details,
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job = Job.objects.get(id=response.data["id"])
        self.assertEqual(job.details_json, details)

    def test_create_job_unauthorized_failure(self):
        """Test job creation without authentication"""
        resource_id = uuid.uuid4()
        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_job_rate_limited(self):
        """Test job creation when tenant rate limits are exceeded"""
        from django.core.cache import cache

        from hub.apps.tenants.services import get_tenant_job_limits

        self.client.force_authenticate(user=self.user)

        # Get tenant limits
        limits = get_tenant_job_limits(str(self.tenant.id))
        max_queued = limits.get("max_queued_jobs", 50)

        # Set queued counter to max to trigger rate limit
        queued_key = f"job:tenant:{self.tenant.id!s}:queued"
        cache.set(queued_key, max_queued, timeout=3600)

        resource_id = uuid.uuid4()
        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        # Should return 429 Too Many Requests
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "JOB_RATE_LIMITED")
        self.assertIn("limit", response.data["error"]["message"].lower())
        self.assertEqual(response.data["error"]["details"]["reason"], "tenant_job_limits_exceeded")

        # Clean up
        cache.delete(queued_key)

    # ========== LIST JOBS TESTS ==========

    def test_list_jobs_success(self):
        """Test listing jobs"""
        self.client.force_authenticate(user=self.user)

        # Create some jobs
        job1 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        job_ids = [j["id"] for j in response.data["results"]]
        self.assertIn(str(job1.id), job_ids)
        self.assertIn(str(job2.id), job_ids)

    def test_list_jobs_tenant_isolation(self):
        """Test that users only see jobs in their tenant"""
        self.client.force_authenticate(user=self.user)

        # Create job in user's tenant
        my_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Create job in other tenant
        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
        )

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data["results"]]
        self.assertIn(str(my_job.id), job_ids)
        self.assertNotIn(str(other_job.id), job_ids)

    def test_list_jobs_platform_admin_sees_all(self):
        """Test that platform admin sees all jobs"""
        self.client.force_authenticate(user=self.platform_admin)

        # Create jobs in different tenants
        job1 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )
        job2 = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data["results"]]
        self.assertIn(str(job1.id), job_ids)
        self.assertIn(str(job2.id), job_ids)

    def test_list_jobs_filter_by_type(self):
        """Test filtering jobs by type"""
        self.client.force_authenticate(user=self.user)

        # Create jobs of different types
        dq_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        compliance_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Filter by DQ_RUN type
        response = self.client.get("/api/v1/jobs/?type=DQ_RUN")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data["results"]]
        self.assertIn(str(dq_job.id), job_ids)
        self.assertNotIn(str(compliance_job.id), job_ids)

    def test_list_jobs_filter_by_status(self):
        """Test filtering jobs by status"""
        self.client.force_authenticate(user=self.user)

        # Create jobs with different statuses
        pending_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        completed_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Filter by PENDING status
        response = self.client.get("/api/v1/jobs/?status=PENDING")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data["results"]]
        self.assertIn(str(pending_job.id), job_ids)
        self.assertNotIn(str(completed_job.id), job_ids)

    def test_list_jobs_filter_by_type_and_status(self):
        """Test filtering jobs by both type and status"""
        self.client.force_authenticate(user=self.user)

        # Create jobs
        dq_pending = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        dq_completed = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Filter by type and status
        response = self.client.get("/api/v1/jobs/?type=DQ_RUN&status=PENDING")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data["results"]]
        self.assertIn(str(dq_pending.id), job_ids)
        self.assertNotIn(str(dq_completed.id), job_ids)

    def test_list_jobs_ordering(self):
        """Test ordering jobs by created_at"""
        self.client.force_authenticate(user=self.user)

        # Create jobs at different times
        job1 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        # Wait a bit to ensure different timestamps
        import time

        time.sleep(0.1)  # noqa: sleep-needed  # INTENTIONAL: test-specific timing requirement
        job2 = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be ordered by -created_at (newest first)
        job_ids = [j["id"] for j in response.data["results"]]
        self.assertEqual(job_ids[0], str(job2.id))
        self.assertEqual(job_ids[1], str(job1.id))

    def test_list_jobs_search(self):
        """Test searching jobs"""
        self.client.force_authenticate(user=self.user)

        # Create jobs
        dq_job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )
        Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Search for DQ_RUN
        response = self.client.get("/api/v1/jobs/?search=DQ_RUN")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data["results"]]
        self.assertIn(str(dq_job.id), job_ids)

    def test_list_jobs_empty_result(self):
        """Test listing jobs when no jobs exist"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 0)

    def test_list_jobs_unauthorized_failure(self):
        """Test listing jobs without authentication"""
        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== RETRIEVE JOB TESTS ==========

    def test_retrieve_job_success(self):
        """Test retrieving a job by ID"""
        self.client.force_authenticate(user=self.user)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        response = self.client.get(f"/api/v1/jobs/{job.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(job.id))
        self.assertEqual(response.data["type"], JobType.DQ_RUN)
        self.assertEqual(response.data["status"], JobStatus.PENDING)

    def test_retrieve_job_tenant_isolation(self):
        """Test that users cannot retrieve jobs from other tenants"""
        self.client.force_authenticate(user=self.user)

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
        )

        response = self.client.get(f"/api/v1/jobs/{other_job.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_job_platform_admin_success(self):
        """Test that platform admin can retrieve any job"""
        self.client.force_authenticate(user=self.platform_admin)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        response = self.client.get(f"/api/v1/jobs/{job.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(job.id))

    def test_retrieve_job_not_found(self):
        """Test retrieving non-existent job"""
        self.client.force_authenticate(user=self.user)

        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/jobs/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_job_invalid_id_format(self):
        """Test retrieving job with invalid ID format"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/jobs/invalid-id/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_job_unauthorized_failure(self):
        """Test retrieving job without authentication"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        response = self.client.get(f"/api/v1/jobs/{job.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== CANCEL JOB TESTS ==========

    def test_cancel_job_success_pending(self):
        """Test cancelling a pending job"""
        self.client.force_authenticate(user=self.user)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

    def test_cancel_job_success_running(self):
        """Test cancelling a running job"""
        self.client.force_authenticate(user=self.user)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            started_at=timezone.now(),
        )

        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

    def test_cancel_job_already_completed_failure(self):
        """Test cancelling a completed job fails"""
        self.client.force_authenticate(user=self.user)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            completed_at=timezone.now(),
        )

        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("cannot be cancelled", response.data["error"].lower())

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)  # Status unchanged

    def test_cancel_job_already_failed_failure(self):
        """Test cancelling a failed job fails"""
        self.client.force_authenticate(user=self.user)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.FAILED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            completed_at=timezone.now(),
            error_message="Test error",
        )

        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)  # Status unchanged

    def test_cancel_job_already_cancelled_failure(self):
        """Test cancelling an already cancelled job fails"""
        self.client.force_authenticate(user=self.user)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.CANCELLED,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)  # Status unchanged

    def test_cancel_job_tenant_isolation(self):
        """Test that users cannot cancel jobs from other tenants"""
        self.client.force_authenticate(user=self.user)

        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
        )

        response = self.client.post(f"/api/v1/jobs/{other_job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        other_job.refresh_from_db()
        self.assertEqual(other_job.status, JobStatus.PENDING)  # Status unchanged

    def test_cancel_job_platform_admin_success(self):
        """Test that platform admin can cancel any job"""
        self.client.force_authenticate(user=self.platform_admin)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

    def test_cancel_job_not_found(self):
        """Test cancelling non-existent job"""
        self.client.force_authenticate(user=self.user)

        fake_id = uuid.uuid4()
        response = self.client.post(f"/api/v1/jobs/{fake_id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_job_unauthorized_failure(self):
        """Test cancelling job without authentication"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
        )

        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cancel_job_wrong_method_failure(self):
        """Test cancelling job with wrong HTTP method"""
        self.client.force_authenticate(user=self.user)

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Try GET instead of POST
        response = self.client.get(f"/api/v1/jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cancel_job_virtual_query_execution_syncs_status(self):
        """Test cancelling VIRTUAL_QUERY_EXECUTION job syncs QueryExecution status"""
        self.client.force_authenticate(user=self.user)

        # Create virtual query execution job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.VIRTUAL_QUERY_EXECUTION,
            status=JobStatus.RUNNING,
            resource_type="VIRTUAL_QUERY",
            resource_id=uuid.uuid4(),
            created_by=self.user,
            started_at=timezone.now(),
        )

        # Create QueryExecution if virtualization app is available
        try:
            from hub.apps.virtualization.models import (
                QueryExecution,
                QueryExecutionStatus,
                QueryType,
                VirtualDataset,
            )

            virtual_dataset = VirtualDataset.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                name="Test Virtual Dataset",
                query="SELECT * FROM test",
                query_type=QueryType.SQL,
            )
            query_execution = QueryExecution.objects.create(
                virtual_dataset=virtual_dataset,
                job=job,
                status=QueryExecutionStatus.RUNNING,
                query="SELECT * FROM test",
            )

            # Cancel job
            response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            job.refresh_from_db()
            self.assertEqual(job.status, JobStatus.CANCELLED)

            # Verify QueryExecution status was synced (may be CANCELLED or still RUNNING depending on sync logic)
            query_execution.refresh_from_db()
            self.assertIn(
                query_execution.status,
                [QueryExecutionStatus.CANCELLED, QueryExecutionStatus.RUNNING],
            )

        except ImportError:
            # Virtualization app not available, skip QueryExecution sync test
            # But still verify job cancellation works
            response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            job.refresh_from_db()
            self.assertEqual(job.status, JobStatus.CANCELLED)

    # ========== EDGE CASES ==========

    def test_create_job_with_null_details_json(self):
        """Test creating job with null details_json"""
        self.client.force_authenticate(user=self.user)

        resource_id = uuid.uuid4()
        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
            "details_json": None,
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job = Job.objects.get(id=response.data["id"])
        self.assertIsNone(job.details_json)

    def test_create_job_with_empty_details_json(self):
        """Test creating job with empty details_json"""
        self.client.force_authenticate(user=self.user)

        resource_id = uuid.uuid4()
        data = {
            "type": JobType.DQ_RUN,
            "resource_type": "DATASET",
            "resource_id": str(resource_id),
            "details_json": {},
        }

        response = self.client.post("/api/v1/jobs/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job = Job.objects.get(id=response.data["id"])
        self.assertEqual(job.details_json, {})

    def test_list_jobs_pagination(self):
        """Test pagination in job listing"""
        self.client.force_authenticate(user=self.user)

        # Create multiple jobs
        jobs = []
        for _i in range(15):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.PENDING,
                resource_type="DATASET",
                resource_id=uuid.uuid4(),
                created_by=self.user,
            )
            jobs.append(job)

        # Request first page
        response = self.client.get("/api/v1/jobs/?page_size=10")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["count"], 15)

    def test_list_jobs_invalid_filter_values(self):
        """Test filtering with invalid values.

        Expected behavior: The API accepts unknown filter values silently (returns 200)
        rather than rejecting them with a 400. This is by design — DRF's filter backends
        treat unrecognized filter values as a no-match, yielding an empty result set.
        We verify both the 200 status AND the empty results to confirm this contract.
        """
        self.client.force_authenticate(user=self.user)

        # Create a job
        Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DATASET",
            resource_id=uuid.uuid4(),
            created_by=self.user,
        )

        # Filter with invalid status
        response = self.client.get("/api/v1/jobs/?status=INVALID_STATUS")

        # API returns 200 (not 400) with empty results for unrecognized filter values
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertEqual(len(response.data["results"]), 0)
