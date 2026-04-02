"""
Phase 121G-C.1 — ScheduledIngestion serializer to_representation decrypt tests.

Verifies that ScheduledIngestionSerializer.to_representation() decrypts
source_config via the model accessor so API consumers never see the
{"_encrypted": "..."} wrapper.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.serializers import ScheduledIngestionSerializer
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ScheduledIngestionSerializerDecryptionTest(TestCase):
    """Test that to_representation decrypts source_config."""

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
            "bucket": "my-bucket",
            "region": "us-east-1",
            "access_key": "AKIA...",
            "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCY...",
        }

    def _create_ingestion(self, source_config):
        """Helper to create a ScheduledIngestion with given source_config."""
        return ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"ingest-{uuid.uuid4().hex[:6]}",
            source_type=SourceType.S3,
            source_config=source_config,
            schedule_type=ScheduleType.DAILY,
            schedule_config={"cron_expression": "0 0 * * *"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )

    def test_to_representation_decrypts_encrypted_config(self):
        """Encrypted source_config should be decrypted in API response."""
        ingestion = self._create_ingestion(self.plaintext_config)
        # After save(), source_config is {"_encrypted": "..."}
        ingestion.refresh_from_db()
        self.assertIn("_encrypted", ingestion.source_config)

        serializer = ScheduledIngestionSerializer(ingestion)
        data = serializer.data

        # API response should have decrypted config with sensitive fields masked
        sc = data["source_config"]
        self.assertNotIn("_encrypted", sc)
        self.assertEqual(sc["bucket"], "my-bucket")
        self.assertEqual(sc["region"], "us-east-1")
        # Sensitive fields should be masked
        self.assertEqual(sc["secret_key"], "***masked***")

    def test_to_representation_handles_legacy_plaintext(self):
        """Legacy plaintext source_config (pre-encryption) should pass through."""
        ingestion = self._create_ingestion(self.plaintext_config)
        # Simulate legacy row by overwriting the DB field directly
        ScheduledIngestion.objects.filter(pk=ingestion.pk).update(
            source_config={"bucket": "legacy-bucket", "region": "eu-west-1"},
        )
        ingestion.refresh_from_db()

        serializer = ScheduledIngestionSerializer(ingestion)
        data = serializer.data

        sc = data["source_config"]
        self.assertEqual(sc["bucket"], "legacy-bucket")
        self.assertEqual(sc["region"], "eu-west-1")

    def test_to_representation_handles_empty_config(self):
        """Empty source_config should return empty dict."""
        ingestion = self._create_ingestion(self.plaintext_config)
        ScheduledIngestion.objects.filter(pk=ingestion.pk).update(
            source_config={},
        )
        ingestion.refresh_from_db()

        serializer = ScheduledIngestionSerializer(ingestion)
        data = serializer.data
        self.assertEqual(data["source_config"], {})

    def test_to_representation_masks_sensitive_fields(self):
        """Sensitive fields (password, api_key, token, etc.) should be masked."""
        config_with_secrets = {
            "host": "db.example.com",
            "password": "supersecret",
            "api_key": "key-12345",
            "token": "tok-abcdef",
            "connection_string": "postgres://user:pass@host/db",
        }
        ingestion = self._create_ingestion(config_with_secrets)
        ingestion.refresh_from_db()

        serializer = ScheduledIngestionSerializer(ingestion)
        sc = serializer.data["source_config"]

        # Non-sensitive fields visible
        self.assertEqual(sc["host"], "db.example.com")
        # Sensitive fields masked
        self.assertEqual(sc["password"], "***masked***")
        self.assertEqual(sc["api_key"], "***masked***")
        self.assertEqual(sc["token"], "***masked***")
        self.assertEqual(sc["connection_string"], "***masked***")
