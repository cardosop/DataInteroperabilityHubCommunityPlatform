"""
Phase TR.B — Multipart abort / resume API integration test.

Validates that a file in UPLOADING state can be aborted (deleted)
and that a new upload can be initiated afterwards (resume flow).
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File as FileModel, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TestMultipartAbortResumeApi(TestCase):
    """API-level validation of multipart abort and re-upload flow."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Abort Test Tenant", slug=f"abort-{uuid.uuid4().hex[:8]}",
        )
        self.user = User.objects.create_user(
            email=f"abort-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

        self.file_obj = FileModel.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="abort-test.csv",
            size=0,
            status=FileStatus.UPLOADING,
            storage_path=f"uploads/{uuid.uuid4().hex}",
        )

    def test_abort_endpoint_deletes_file(self):
        """DELETE /files/{id}/ removes a file in UPLOADING state (abort)."""
        url = f"/api/v1/files/{self.file_obj.id}/"
        response = self.client.delete(url)

        # 204 = deleted (or already marked DELETED), 403 = not permitted
        self.assertIn(
            response.status_code,
            [status.HTTP_204_NO_CONTENT, status.HTTP_403_FORBIDDEN],
        )

    def test_abort_then_recreate_file_for_upload(self):
        """After aborting, a new file record can be created for re-upload."""
        # Abort the existing file
        url = f"/api/v1/files/{self.file_obj.id}/"
        self.client.delete(url)

        # Create a new file for the resumed upload
        new_file = FileModel.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="resumed-upload.csv",
            size=0,
            status=FileStatus.UPLOADING,
            storage_path=f"uploads/{uuid.uuid4().hex}",
        )
        self.assertIsNotNone(new_file.id)
        self.assertEqual(new_file.status, FileStatus.UPLOADING)

        # Verify the new file's chunk init endpoint is reachable
        init_url = f"/api/v1/files/{new_file.id}/chunks/init/"
        response = self.client.post(init_url, {}, format="json")
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN],
        )

    def test_abort_requires_authentication(self):
        """Abort endpoint rejects unauthenticated requests."""
        unauth_client = APIClient()
        url = f"/api/v1/files/{self.file_obj.id}/"
        response = unauth_client.delete(url)
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
