"""
Phase 121G-C.2 — ScheduledExport serializer to_representation decrypt tests.

Verifies that ScheduledExportSerializer.to_representation() decrypts
destination_config via the model accessor so API consumers never see the
{"_encrypted": "..."} wrapper.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
)
from hub.apps.scheduled_export.serializers import ScheduledExportSerializer
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ScheduledExportSerializerDecryptionTest(TestCase):
    """Test that to_representation decrypts destination_config."""

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
        self.plaintext_config = {
            "bucket": "export-bucket",
            "region": "us-west-2",
            "access_key": "AKIA...",
            "secret_key": "wJalrXUtnFEMI...",
        }

    def _create_export(self, destination_config):
        """Helper to create a ScheduledExport with given destination_config."""
        return ScheduledExport.objects.create(
            tenant=self.tenant,
            name=f"export-{uuid.uuid4().hex[:6]}",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config=destination_config,
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )

    def test_to_representation_decrypts_encrypted_config(self):
        """Encrypted destination_config should be decrypted in API response."""
        export = self._create_export(self.plaintext_config)
        export.refresh_from_db()
        self.assertIn("_encrypted", export.destination_config)

        serializer = ScheduledExportSerializer(export)
        data = serializer.data

        dc = data["destination_config"]
        self.assertNotIn("_encrypted", dc)
        self.assertEqual(dc["bucket"], "export-bucket")
        self.assertEqual(dc["region"], "us-west-2")
        # Sensitive fields should be masked
        self.assertEqual(dc["secret_key"], "***masked***")

    def test_to_representation_handles_legacy_plaintext(self):
        """Legacy plaintext destination_config should pass through."""
        export = self._create_export(self.plaintext_config)
        ScheduledExport.objects.filter(pk=export.pk).update(
            destination_config={"bucket": "legacy-bucket", "region": "eu-west-1"},
        )
        export.refresh_from_db()

        serializer = ScheduledExportSerializer(export)
        dc = serializer.data["destination_config"]
        self.assertEqual(dc["bucket"], "legacy-bucket")

    def test_to_representation_handles_empty_config(self):
        """Empty destination_config should return empty dict."""
        export = self._create_export(self.plaintext_config)
        ScheduledExport.objects.filter(pk=export.pk).update(
            destination_config={},
        )
        export.refresh_from_db()

        serializer = ScheduledExportSerializer(export)
        self.assertEqual(serializer.data["destination_config"], {})

    def test_to_representation_masks_sensitive_fields(self):
        """Sensitive fields should be masked."""
        config = {
            "bucket": "out-bucket",
            "password": "supersecret",
            "api_key": "key-12345",
            "token": "tok-abcdef",
            "connection_string": "s3://key:secret@bucket/path",
        }
        export = self._create_export(config)
        export.refresh_from_db()

        serializer = ScheduledExportSerializer(export)
        dc = serializer.data["destination_config"]

        self.assertEqual(dc["bucket"], "out-bucket")
        self.assertEqual(dc["password"], "***masked***")
        self.assertEqual(dc["api_key"], "***masked***")
        self.assertEqual(dc["token"], "***masked***")
        self.assertEqual(dc["connection_string"], "***masked***")
