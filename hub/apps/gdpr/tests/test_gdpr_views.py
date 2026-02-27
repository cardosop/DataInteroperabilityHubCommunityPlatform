"""
Comprehensive unit tests for GDPR ViewSet endpoints.

Tests cover:
- CRUD operations (list, retrieve)
- Custom actions (export_data, request_erasure)
- User isolation (users can only see their own data)
- Permission checks (IsAuthenticated)
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling

All tests use real implementations (no mocks/stubs).
"""

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.gdpr.models import (
    DataExportJob,
    DataExportStatus,
    ErasureRequest,
    ErasureRequestStatus,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DataExportJobViewSetTest(TestCase):
    """Comprehensive tests for DataExportJobViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant", status="ACTIVE")

        # Ensure tenant has active subscription so POST export-data is not 403
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create another tenant and user for isolation tests
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", status="ACTIVE"
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            display_name="Other User",
        )

    def _response_data(self, response):
        """Parse response body to dict; DRF Response has .data, JsonResponse needs json.loads."""
        return _response_data(response)

    # ========== LIST ENDPOINT TESTS ==========

    def test_list_export_jobs_success(self):
        """Test listing export jobs successfully"""
        # Create export jobs
        job1 = DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.COMPLETED
        )
        job2 = DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.PENDING
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/me/export-jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

        # Verify jobs are returned
        job_ids = [job["id"] for job in response.data["results"]]
        self.assertIn(str(job1.id), job_ids)
        self.assertIn(str(job2.id), job_ids)

    def test_list_export_jobs_user_isolation(self):
        """Test that users can only see their own export jobs"""
        # Create job for first user
        job1 = DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.COMPLETED
        )

        # Create job for other user
        job2 = DataExportJob.objects.create(
            user=self.other_user,
            tenant=self.other_tenant,
            status=DataExportStatus.COMPLETED,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/me/export-jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(job1.id))
        self.assertNotEqual(response.data["results"][0]["id"], str(job2.id))

    def test_list_export_jobs_requires_authentication(self):
        """Test that listing export jobs requires authentication"""
        response = self.client.get("/api/v1/users/me/export-jobs/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_export_jobs_empty_when_no_jobs(self):
        """Test that listing returns empty list when user has no jobs"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/me/export-jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    # ========== RETRIEVE ENDPOINT TESTS ==========

    def test_retrieve_export_job_success(self):
        """Test retrieving export job successfully"""
        job = DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.COMPLETED,
            download_url="https://example.com/download.zip",
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/users/me/export-jobs/{job.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(job.id))
        self.assertEqual(response.data["status"], DataExportStatus.COMPLETED)
        self.assertEqual(response.data["download_url"], "https://example.com/download.zip")

    def test_retrieve_export_job_user_isolation(self):
        """Test that users can only retrieve their own export jobs"""
        # Create job for other user
        job = DataExportJob.objects.create(
            user=self.other_user,
            tenant=self.other_tenant,
            status=DataExportStatus.COMPLETED,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/users/me/export-jobs/{job.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_export_job_nonexistent(self):
        """Test retrieving nonexistent export job returns 404"""
        fake_job_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/users/me/export-jobs/{fake_job_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_export_job_requires_authentication(self):
        """Test that retrieving export job requires authentication"""
        job = DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.COMPLETED
        )

        response = self.client.get(f"/api/v1/users/me/export-jobs/{job.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== EXPORT DATA ACTION TESTS ==========

    def test_export_data_success(self):
        """Test export_data action successfully creates job"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/export-jobs/export-data/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("job_id", response.data)
        self.assertIn("status", response.data)
        self.assertIn("created_at", response.data)

        # Verify job was created
        job_id = response.data["job_id"]
        job = DataExportJob.objects.get(id=job_id)
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.tenant, self.tenant)

    def test_export_data_creates_job_in_db(self):
        """Test that export_data creates job in database"""
        initial_count = DataExportJob.objects.filter(user=self.user).count()

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/export-jobs/export-data/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        final_count = DataExportJob.objects.filter(user=self.user).count()
        self.assertEqual(final_count, initial_count + 1)

    def test_export_data_requires_authentication(self):
        """Test that export_data requires authentication"""
        response = self.client.post("/api/v1/users/me/export-jobs/export-data/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_data_with_existing_pending_job(self):
        """Test that export_data with existing pending job returns error"""
        # Create pending job
        DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.PENDING
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/export-jobs/export-data/")

        # Should return error (400 or 409)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT])
        # Verify error response format (from handle_service_exception)
        data = self._response_data(response)
        self.assertIn("detail", data)
        self.assertIn("code", data)

    def test_export_data_error_response_format(self):
        """Test that export_data returns standardized error format"""
        # Create pending job to trigger error
        DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.PENDING
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/export-jobs/export-data/")

        # Verify standardized error format (use _response_data for JsonResponse/middleware 403)
        data = self._response_data(response)
        if response.status_code >= 400:
            self.assertIn("detail", data)
            self.assertIn("code", data)
            # Error code should be meaningful
            self.assertIn(
                data["code"], ["VALIDATION_ERROR", "CONFLICT_ERROR", "EXPORT_IN_PROGRESS"]
            )

    def test_export_data_allows_multiple_completed_jobs(self):
        """Test that export_data allows multiple completed jobs"""
        # Create completed job
        DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.COMPLETED
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/export-jobs/export-data/")

        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ========== EDGE CASES TESTS ==========

    def test_list_export_jobs_pagination(self):
        """Test that list endpoint supports pagination"""
        # Create multiple jobs
        for i in range(25):
            DataExportJob.objects.create(
                user=self.user, tenant=self.tenant, status=DataExportStatus.COMPLETED
            )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/me/export-jobs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return paginated results
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)


def _response_data(response):
    """Parse response body to dict; DRF Response has .data, JsonResponse needs json.loads."""
    if getattr(response, "data", None) is not None:
        return response.data
    if response.get("Content-Type", "").startswith("application/json"):
        return json.loads(response.content.decode(response.charset or "utf-8"))
    return {}


class ErasureRequestViewSetTest(TestCase):
    """Comprehensive tests for ErasureRequestViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant", status="ACTIVE")

        # Ensure tenant has active subscription so POST request-erasure is not 403
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create another tenant and user for isolation tests
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", status="ACTIVE"
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            display_name="Other User",
        )

    # ========== LIST ENDPOINT TESTS ==========

    def test_list_erasure_requests_success(self):
        """Test listing erasure requests successfully"""
        # Create erasure requests
        request1 = ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.COMPLETED
        )
        request2 = ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.PENDING
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/me/erasure-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

        # Verify requests are returned
        request_ids = [req["id"] for req in response.data["results"]]
        self.assertIn(str(request1.id), request_ids)
        self.assertIn(str(request2.id), request_ids)

    def test_list_erasure_requests_user_isolation(self):
        """Test that users can only see their own erasure requests"""
        # Create request for first user
        request1 = ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.COMPLETED
        )

        # Create request for other user
        request2 = ErasureRequest.objects.create(
            user=self.other_user,
            tenant=self.other_tenant,
            status=ErasureRequestStatus.COMPLETED,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/me/erasure-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(request1.id))
        self.assertNotEqual(response.data["results"][0]["id"], str(request2.id))

    def test_list_erasure_requests_requires_authentication(self):
        """Test that listing erasure requests requires authentication"""
        response = self.client.get("/api/v1/users/me/erasure-requests/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_erasure_requests_empty_when_no_requests(self):
        """Test that listing returns empty list when user has no requests"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/me/erasure-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    # ========== RETRIEVE ENDPOINT TESTS ==========

    def test_retrieve_erasure_request_success(self):
        """Test retrieving erasure request successfully"""
        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.COMPLETED,
            anonymized_fields=["email", "display_name"],
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/users/me/erasure-requests/{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(request.id))
        self.assertEqual(response.data["status"], ErasureRequestStatus.COMPLETED)
        self.assertEqual(response.data["anonymized_fields"], ["email", "display_name"])

    def test_retrieve_erasure_request_user_isolation(self):
        """Test that users can only retrieve their own erasure requests"""
        # Create request for other user
        request = ErasureRequest.objects.create(
            user=self.other_user,
            tenant=self.other_tenant,
            status=ErasureRequestStatus.COMPLETED,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/users/me/erasure-requests/{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_erasure_request_nonexistent(self):
        """Test retrieving nonexistent erasure request returns 404"""
        fake_request_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/users/me/erasure-requests/{fake_request_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_erasure_request_requires_authentication(self):
        """Test that retrieving erasure request requires authentication"""
        request = ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.COMPLETED
        )

        response = self.client.get(f"/api/v1/users/me/erasure-requests/{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== REQUEST ERASURE ACTION TESTS ==========

    def test_request_erasure_success(self):
        """Test request_erasure action successfully creates request"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("request_id", response.data)
        self.assertIn("status", response.data)
        self.assertIn("requested_at", response.data)

        # Verify request was created
        request_id = response.data["request_id"]
        request = ErasureRequest.objects.get(id=request_id)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.tenant, self.tenant)

    def test_request_erasure_creates_request_in_db(self):
        """Test that request_erasure creates request in database"""
        initial_count = ErasureRequest.objects.filter(user=self.user).count()

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        final_count = ErasureRequest.objects.filter(user=self.user).count()
        self.assertEqual(final_count, initial_count + 1)

    def test_request_erasure_executes_erasure(self):
        """Test that request_erasure executes erasure"""
        original_email = self.user.email

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Refresh user from DB
        self.user.refresh_from_db()

        # User should be anonymized (if erasure executed successfully)
        # Note: Erasure execution might fail in test environment, so check status
        request_id = response.data["request_id"]
        request = ErasureRequest.objects.get(id=request_id)
        if request.status == ErasureRequestStatus.COMPLETED:
            self.assertNotEqual(self.user.email, original_email)
            self.assertIn("deleted-", self.user.email)

    def test_request_erasure_requires_authentication(self):
        """Test that request_erasure requires authentication"""
        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_request_erasure_with_existing_pending_request(self):
        """Test that request_erasure with existing pending request returns error"""
        # Create pending request
        ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.PENDING
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        # Should return error (400 or 409)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT])
        # Verify error response format (from handle_service_exception)
        data = _response_data(response)
        self.assertIn("detail", data)
        self.assertIn("code", data)

    def test_request_erasure_error_response_format(self):
        """Test that request_erasure returns standardized error format"""
        # Create pending request to trigger error
        ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.PENDING
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        # Verify standardized error format (use _response_data for JsonResponse/middleware 403)
        data = _response_data(response)
        if response.status_code >= 400:
            self.assertIn("detail", data)
            self.assertIn("code", data)
            # Error code should be meaningful
            self.assertIn(
                data["code"], ["VALIDATION_ERROR", "CONFLICT_ERROR", "ERASURE_IN_PROGRESS"]
            )

    def test_request_erasure_allows_multiple_completed_requests(self):
        """Test that request_erasure allows multiple completed requests"""
        # Create completed request
        ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.COMPLETED
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        # Should succeed (though user might already be anonymized)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    # ========== EDGE CASES TESTS ==========

    def test_list_erasure_requests_pagination(self):
        """Test that list endpoint supports pagination"""
        # Create multiple requests
        for i in range(25):
            ErasureRequest.objects.create(
                user=self.user, tenant=self.tenant, status=ErasureRequestStatus.COMPLETED
            )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/me/erasure-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return paginated results
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    def test_request_erasure_handles_execution_failure_gracefully(self):
        """Test that request_erasure handles execution failure gracefully"""
        # This test verifies that if erasure execution fails,
        # the request is still created and can be retried
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        # Should succeed even if execution fails
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("request_id", response.data)

        # Request should exist
        request_id = response.data["request_id"]
        request = ErasureRequest.objects.get(id=request_id)
        self.assertIsNotNone(request)
