"""
Phase 26-OB: Mock S3 fallback removal tests.

Verifies that _generate_mock_file_content raises ValueError
for all file formats instead of returning fake data.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.datasets.services import _generate_mock_file_content
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class MockFallbackRemovedTest(TestCase):
    """_generate_mock_file_content must raise ValueError for every format."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Mock Tenant {uid}",
            slug=f"mock-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"mock-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=256,
            storage_path=f"tenants/{self.tenant.id}/files/data.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

    def test_mock_content_raises_value_error_csv(self):
        """CSV format raises ValueError with 'not found in S3' message."""
        with self.assertRaises(ValueError) as ctx:
            _generate_mock_file_content(self.file, "CSV")
        self.assertIn("not found in S3", str(ctx.exception))

    def test_mock_content_raises_value_error_json(self):
        """JSON format raises ValueError with 'not found in S3' message."""
        with self.assertRaises(ValueError) as ctx:
            _generate_mock_file_content(self.file, "JSON")
        self.assertIn("not found in S3", str(ctx.exception))

    def test_mock_content_raises_value_error_parquet(self):
        """PARQUET format raises ValueError with 'not found in S3' message."""
        with self.assertRaises(ValueError) as ctx:
            _generate_mock_file_content(self.file, "PARQUET")
        self.assertIn("not found in S3", str(ctx.exception))
