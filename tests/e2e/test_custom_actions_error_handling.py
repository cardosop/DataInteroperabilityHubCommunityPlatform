"""
E2E tests for error handling in custom actions.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.jobs.models import Job, JobStatus
from hub.apps.users.models import User
from tests.e2e.conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e_batch5]


class CustomActionsErrorHandlingE2ETest(E2ETestBase):
    """E2E tests for error handling in custom actions."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_activate_nonexistent_asset(self):
        """Test activating a non-existent asset."""
        response = self.client.post("/api/v1/assets/00000000-0000-0000-0000-000000000000/activate/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_activate_already_active_asset(self):
        """Test activating an already active asset."""
        # Create and activate an asset
        asset = Asset.objects.create(
            tenant=self.tenant, name="Test Asset", status=AssetStatus.ACTIVE
        )

        response = self.client.post(
            f"/api/v1/assets/{asset.id}/activate/", {"version": asset.version}, format="json"
        )

        # Activating an already-active asset is a client error (bad request or conflict)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_400_BAD_REQUEST,  # Already active
                status.HTTP_409_CONFLICT,  # Conflict - asset already in desired state
            ],
        )

    def test_attach_dataset_to_nonexistent_asset(self):
        """Test attaching dataset to non-existent asset."""
        dataset_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            f"/api/v1/assets/{dataset_id}/datasets/", {"dataset_id": dataset_id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_attach_contract_to_nonexistent_asset(self):
        """Test attaching contract to non-existent asset."""
        contract_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            f"/api/v1/assets/{contract_id}/contracts/", {"contract_id": contract_id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_nonexistent_job(self):
        """Test canceling a non-existent job."""
        response = self.client.post("/api/v1/jobs/00000000-0000-0000-0000-000000000000/cancel/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_already_completed_job(self):
        """Test canceling an already completed job."""
        import uuid

        from hub.apps.jobs.models import JobType

        # Job requires resource_id (not null)
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=str(uuid.uuid4()),
        )

        response = self.client.post(f"/api/v1/jobs/{job.id}/cancel/")

        # Canceling an already-completed job is a client error (bad request or conflict)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_400_BAD_REQUEST,  # Already completed
                status.HTTP_409_CONFLICT,  # Conflict - job already in terminal state
            ],
        )

    def test_validate_nonexistent_contract(self):
        """Test validating a non-existent contract."""
        response = self.client.post(
            "/api/v1/contracts/00000000-0000-0000-0000-000000000000/validate/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_lint_nonexistent_contract(self):
        """Test linting a non-existent contract."""
        response = self.client.post("/api/v1/contracts/00000000-0000-0000-0000-000000000000/lint/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_convert_nonexistent_contract(self):
        """Test converting a non-existent contract."""
        response = self.client.post(
            "/api/v1/contracts/00000000-0000-0000-0000-000000000000/convert/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_migrate_nonexistent_contract(self):
        """Test migrating a non-existent contract."""
        response = self.client.post(
            "/api/v1/contracts/00000000-0000-0000-0000-000000000000/migrate/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_nonexistent_file(self):
        """Test downloading a non-existent file."""
        response = self.client.get("/api/v1/files/00000000-0000-0000-0000-000000000000/download/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_complete_nonexistent_file_upload(self):
        """Test completing upload for non-existent file."""
        response = self.client.post("/api/v1/files/00000000-0000-0000-0000-000000000000/complete/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_audit_events_unauthorized(self):
        """Test exporting audit events without authentication."""
        client = APIClient()  # Not authenticated
        response = client.get("/api/v1/audit/audit-events/export/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invite_user_invalid_email(self):
        """Test inviting user with invalid email."""
        # The invite endpoint is at /api/v1/users/invite/
        response = self.client.post(
            "/api/v1/users/invite/",
            {"email": "invalid-email", "role": "DATA_PROVIDER"},
            format="json",
        )

        # Invalid email must return 400 (validation error)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_role_to_nonexistent_user(self):
        """Test assigning role to non-existent user."""
        response = self.client.post(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/roles/",
            {"role": "DATA_PROVIDER"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_suspend_nonexistent_tenant(self):
        """Test suspending a non-existent tenant."""
        # Suspend requires IsPlatformAdmin; use platform admin to reach get_object (404)
        platform_admin = User.objects.filter(
            email=f"e2e_platform_admin_tenant-{uuid.uuid4().hex[:8]}@example.com"
        ).first()
        if platform_admin is None:
            platform_admin = User.objects.create_user(
                email=f"e2e_platform_admin_tenant-{uuid.uuid4().hex[:8]}@example.com",
                password="testpass123",
                tenant=None,
                is_platform_admin=True,
            )
        if not platform_admin.is_platform_admin:
            platform_admin.is_platform_admin = True
            platform_admin.save()
        self.client.force_authenticate(user=platform_admin)
        response = self.client.post("/api/v1/tenants/00000000-0000-0000-0000-000000000000/suspend/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reactivate_nonexistent_tenant(self):
        """Test reactivating a non-existent tenant."""
        # Reactivate requires IsPlatformAdmin; use platform admin to reach get_object (404)
        platform_admin = User.objects.filter(
            email=f"e2e_platform_admin_tenant-{uuid.uuid4().hex[:8]}@example.com"
        ).first()
        if platform_admin is None:
            platform_admin = User.objects.create_user(
                email=f"e2e_platform_admin_tenant-{uuid.uuid4().hex[:8]}@example.com",
                password="testpass123",
                tenant=None,
                is_platform_admin=True,
            )
        if not platform_admin.is_platform_admin:
            platform_admin.is_platform_admin = True
            platform_admin.save()
        self.client.force_authenticate(user=platform_admin)
        response = self.client.post(
            "/api/v1/tenants/00000000-0000-0000-0000-000000000000/reactivate/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
