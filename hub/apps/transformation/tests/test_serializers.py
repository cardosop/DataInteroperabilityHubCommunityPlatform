"""
Unit tests for transformation serializers — Phase 115F.1
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.transformation.serializers import (
    PipelineExecutionSerializer,
    TransformationPipelineSerializer,
)

pytestmark = pytest.mark.django_db(transaction=True)

User = None


class TransformationPipelineSerializerTest(TestCase):
    """Test TransformationPipelineSerializer."""

    def setUp(self):
        """Create shared fixtures for each test."""
        from django.contrib.auth import get_user_model

        global User
        User = get_user_model()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"test-tenant-{uid}",
            slug=f"ts-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"ser-{uid}@test.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_valid_pipeline_serialization(self):
        """Serializer validates and saves valid pipeline data."""
        data = {
            "name": "Test Pipeline",
            "description": "A test pipeline",
            "version": "1.0.0",
            "pipeline_definition": {
                "version": "1.0.0",
                "steps": [
                    {"name": "s1", "type": "filter", "config": {}},
                ],
            },
        }
        serializer = TransformationPipelineSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        pipeline = serializer.save(tenant=self.tenant, created_by=self.user)
        self.assertIsNotNone(pipeline.id)
        self.assertEqual(pipeline.name, "Test Pipeline")

    def test_status_is_read_only(self):
        """Status field should be read-only."""
        serializer = TransformationPipelineSerializer()
        self.assertTrue(serializer.fields["status"].read_only)

    def test_id_is_read_only(self):
        """ID field should be read-only."""
        serializer = TransformationPipelineSerializer()
        self.assertTrue(serializer.fields["id"].read_only)

    def test_tenant_is_read_only(self):
        """Tenant field should be read-only."""
        serializer = TransformationPipelineSerializer()
        self.assertTrue(serializer.fields["tenant"].read_only)

    def test_created_at_is_read_only(self):
        serializer = TransformationPipelineSerializer()
        self.assertTrue(serializer.fields["created_at"].read_only)

    def test_fields_present(self):
        """All expected fields are in the serializer."""
        serializer = TransformationPipelineSerializer()
        expected = {
            "id",
            "tenant",
            "created_by",
            "name",
            "description",
            "pipeline_definition",
            "version",
            "status",
            "created_at",
            "updated_at",
            "metadata",
        }
        self.assertTrue(expected.issubset(set(serializer.fields.keys())))


class PipelineExecutionSerializerTest(TestCase):
    """Test PipelineExecutionSerializer."""

    def test_fields_present(self):
        serializer = PipelineExecutionSerializer()
        self.assertIn("id", serializer.fields)
        self.assertIn("pipeline_id", serializer.fields)
        self.assertIn("status", serializer.fields)

    def test_status_field_exists(self):
        serializer = PipelineExecutionSerializer()
        self.assertIn("status", serializer.fields)
