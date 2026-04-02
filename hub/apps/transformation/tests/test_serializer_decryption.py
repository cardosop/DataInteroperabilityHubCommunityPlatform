"""
Phase 121G-C.4 — TransformationPipeline serializer to_representation decrypt tests.

Verifies that TransformationPipelineSerializer.to_representation() decrypts
pipeline_definition via the model accessor so API consumers never see the
{"_encrypted": "..."} wrapper.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.transformation.models import TransformationPipeline
from hub.apps.transformation.serializers import TransformationPipelineSerializer
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TransformationPipelineSerializerDecryptionTest(TestCase):
    """Test that to_representation decrypts pipeline_definition."""

    @classmethod
    def setUpTestData(cls):
        """Create shared fixtures once per class.

        Tenant and User are never mutated by individual tests, so creating
        them once avoids repeated INSERT+SAVEPOINT churn that causes
        statement_timeout under Docker resource constraints.
        """
        uid = uuid.uuid4().hex[:8]
        cls.tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(cls.tenant)
        cls.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=cls.tenant,
            status=UserStatus.ACTIVE,
        )

    def setUp(self):
        self.pipeline_def = {
            "version": "1.0",
            "steps": [
                {
                    "name": "extract",
                    "type": "sql_query",
                    "config": {
                        "query": "SELECT * FROM users",
                        "connection_string": "postgres://user:pass@host/db",
                    },
                },
                {
                    "name": "transform",
                    "type": "map",
                    "config": {"expression": "row.name.upper()"},
                },
            ],
        }

    def _create_pipeline(self, pipeline_definition):
        return TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"pipe-{uuid.uuid4().hex[:6]}",
            pipeline_definition=pipeline_definition,
        )

    def test_to_representation_decrypts_encrypted_definition(self):
        """Encrypted pipeline_definition should be decrypted in API response."""
        pipeline = self._create_pipeline(self.pipeline_def)
        pipeline.refresh_from_db()
        self.assertIn("_encrypted", pipeline.pipeline_definition)

        serializer = TransformationPipelineSerializer(pipeline)
        data = serializer.data

        pd = data["pipeline_definition"]
        self.assertNotIn("_encrypted", pd)
        self.assertEqual(pd["version"], "1.0")
        self.assertEqual(len(pd["steps"]), 2)
        self.assertEqual(pd["steps"][0]["name"], "extract")

    def test_to_representation_handles_legacy_plaintext(self):
        """Legacy plaintext pipeline_definition should pass through."""
        pipeline = self._create_pipeline(self.pipeline_def)
        legacy_def = {
            "version": "0.9",
            "steps": [{"name": "old_step", "type": "filter"}],
        }
        TransformationPipeline.objects.filter(pk=pipeline.pk).update(
            pipeline_definition=legacy_def,
        )
        pipeline.refresh_from_db()

        serializer = TransformationPipelineSerializer(pipeline)
        pd = serializer.data["pipeline_definition"]
        self.assertEqual(pd["version"], "0.9")
        self.assertEqual(pd["steps"][0]["name"], "old_step")

    def test_to_representation_handles_empty_definition(self):
        """Empty pipeline_definition should return empty dict."""
        pipeline = self._create_pipeline(self.pipeline_def)
        TransformationPipeline.objects.filter(pk=pipeline.pk).update(
            pipeline_definition={},
        )
        pipeline.refresh_from_db()

        serializer = TransformationPipelineSerializer(pipeline)
        self.assertEqual(serializer.data["pipeline_definition"], {})

    def test_full_roundtrip_preserves_data(self):
        """Create → save (encrypts) → serialize (decrypts) preserves all data."""
        complex_def = {
            "version": "2.0",
            "steps": [
                {
                    "name": "ingest",
                    "type": "source",
                    "config": {"format": "parquet", "path": "/data/in"},
                },
                {
                    "name": "clean",
                    "type": "filter",
                    "config": {"condition": "age > 0"},
                },
                {
                    "name": "output",
                    "type": "sink",
                    "config": {"format": "csv", "path": "/data/out"},
                },
            ],
            "metadata": {"author": "test", "tags": ["etl", "prod"]},
        }
        pipeline = self._create_pipeline(complex_def)
        pipeline.refresh_from_db()

        serializer = TransformationPipelineSerializer(pipeline)
        pd = serializer.data["pipeline_definition"]

        self.assertEqual(pd["version"], "2.0")
        self.assertEqual(len(pd["steps"]), 3)
        self.assertEqual(pd["metadata"]["tags"], ["etl", "prod"])
