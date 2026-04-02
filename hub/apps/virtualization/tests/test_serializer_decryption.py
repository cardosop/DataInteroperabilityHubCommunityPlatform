"""
Phase 121G-C.3 — VirtualDataset serializer to_representation decrypt tests.

Verifies the existing VirtualDatasetSerializer.to_representation() correctly
decrypts sources via get_sources() and masks sensitive fields. These tests
exercise the real encryption round-trip (no mocks).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from hub.apps.virtualization.models import (
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)
from hub.apps.virtualization.serializers import VirtualDatasetSerializer

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualDatasetSerializerDecryptionTest(TestCase):
    """Test that to_representation decrypts and masks sources."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def _create_dataset(self, sources):
        return VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"vds-{uuid.uuid4().hex[:6]}",
            query="SELECT 1",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.DRAFT,
        )

    def test_to_representation_decrypts_encrypted_sources(self):
        """Encrypted sources should be decrypted and masked in API response."""
        sources = [
            {"type": "postgresql", "host": "db.example.com", "database": "testdb", "password": "secret123"},
        ]
        ds = self._create_dataset(sources)
        ds.refresh_from_db()
        # Model save() encrypts sources
        self.assertIn("_encrypted", ds.sources)

        serializer = VirtualDatasetSerializer(ds)
        data = serializer.data

        src_list = data["sources"]
        self.assertEqual(len(src_list), 1)
        self.assertEqual(src_list[0]["type"], "postgresql")
        self.assertEqual(src_list[0]["host"], "db.example.com")
        self.assertEqual(src_list[0]["password"], "***masked***")

    def test_to_representation_handles_legacy_plaintext(self):
        """Legacy plaintext sources (list) should pass through and be masked."""
        ds = self._create_dataset([{"type": "mysql", "host": "legacy.host"}])
        VirtualDataset.objects.filter(pk=ds.pk).update(
            sources=[{"type": "mysql", "host": "legacy.host"}],
        )
        ds.refresh_from_db()

        serializer = VirtualDatasetSerializer(ds)
        src_list = serializer.data["sources"]
        self.assertEqual(src_list[0]["host"], "legacy.host")

    def test_to_representation_handles_empty_sources(self):
        """None/empty sources should return empty list."""
        ds = self._create_dataset([])
        VirtualDataset.objects.filter(pk=ds.pk).update(sources=None)
        ds.refresh_from_db()

        serializer = VirtualDatasetSerializer(ds)
        self.assertEqual(serializer.data["sources"], [])

    def test_masks_all_sensitive_fields(self):
        """All known sensitive field names should be masked."""
        sources = [
            {
                "type": "rest",
                "url": "https://api.example.com",
                "api_key": "key-abc",
                "token": "tok-xyz",
                "secret": "s3cr3t",
                "credentials": '{"type": "service_account"}',
                "private_key": "-----BEGIN RSA-----",
            },
        ]
        ds = self._create_dataset(sources)
        ds.refresh_from_db()

        serializer = VirtualDatasetSerializer(ds)
        src = serializer.data["sources"][0]

        self.assertEqual(src["url"], "https://api.example.com")
        self.assertEqual(src["api_key"], "***masked***")
        self.assertEqual(src["token"], "***masked***")
        self.assertEqual(src["secret"], "***masked***")
        self.assertEqual(src["credentials"], "***masked***")
        self.assertEqual(src["private_key"], "***masked***")
