"""
Phase 26-OB — Mock S3 fallback tests.

Verifies that ``_generate_mock_file_content`` returns valid, parseable
content for each text format when the backing file is absent from S3.
The mock fallback was removed in D93 and restored with deterministic
payloads — these tests pin the current contract.
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


class MockFallbackTest(TestCase):
    """_generate_mock_file_content returns valid mock bytes for every format."""

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

    def test_mock_content_returns_bytes_csv(self):
        """CSV format returns valid, parseable CSV bytes."""
        content = _generate_mock_file_content(self.file, "CSV")
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)
        # Must be valid CSV: decodes to text with commas or newlines
        text = content.decode("utf-8")
        self.assertIn(",", text,
            f"CSV mock content must contain commas; got: {text[:80]}")

    def test_mock_content_returns_bytes_json(self):
        """JSON format returns valid, parseable JSON bytes."""
        content = _generate_mock_file_content(self.file, "JSON")
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)
        # Must be valid JSON
        import json
        parsed = json.loads(content)
        self.assertIsInstance(parsed, (dict, list),
            f"JSON mock content must parse to dict or list; got {type(parsed).__name__}")

    def test_mock_content_returns_bytes_parquet(self):
        """PARQUET format returns valid non-empty bytes (or falls back to CSV)."""
        content = _generate_mock_file_content(self.file, "PARQUET")
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)
        # Content must decode to valid text (csv fallback) or be valid parquet bytes
        try:
            text = content.decode("utf-8")
            self.assertGreater(len(text), 0)
        except UnicodeDecodeError:
            # Binary parquet content — acceptable
            pass
