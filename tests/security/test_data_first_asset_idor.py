"""
Security tests: IDOR for Data-First Asset Creation API.

Per tasks 29.68.5.3. User from tenant A must not use tenant B's file_id in
POST /api/v1/assets/data-first/. Cross-tenant file_id returns 403 or 404.
No mocks/stubs.
"""

import uuid

import pytest
from rest_framework import status

from hub.apps.files.models import File, FileStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class DataFirstAssetIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not use tenant B's file_id in data-first API."""

    def setUp(self):
        super().setUp()
        ensure_tenant_has_active_subscription(self.tenant_a)
        ensure_tenant_has_active_subscription(self.tenant_b)
        ensure_user_has_data_provider_role(self.user_a)
        ensure_user_has_data_provider_role(self.user_b)

        csv_content = b"id,name,email\n1,John,john@example.com\n2,Jane,jane@example.com\n"
        self.file_b = File.objects.create(
            tenant=self.tenant_b,
            name="tenant_b_data.csv",
            content_type="text/csv",
            size=len(csv_content),
            status=FileStatus.ACTIVE,
            storage_path=f"{str(self.tenant_b.id)}/{uuid.uuid4()}/tenant_b_data.csv",
            created_by=self.user_b,
        )

    def test_data_first_cross_tenant_file_id_returns_403_or_404(self):
        """POST /api/v1/assets/data-first/ with other tenant's file_id returns 403 or 404."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(
            "/api/v1/assets/data-first/",
            {
                "file_id": str(self.file_b.id),
                "key": f"stolen-asset-{uuid.uuid4().hex[:8]}",
                "name": "Attempted Cross-Tenant Asset",
            },
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant file_id in data-first API must return 403 or 404",
        )
