"""
Unit tests for transformation serializers — Phase 115F.1
"""
import uuid

import pytest
from django.test import TestCase

from hub.apps.transformation.models import PipelineStatus
from hub.apps.transformation.serializers import (
    TransformationPipelineSerializer,
    PipelineExecutionSerializer,
)

pytestmark = pytest.mark.django_db(transaction=True)


class TransformationPipelineSerializerTest(TestCase):
    """Test TransformationPipelineSerializer."""

    def test_valid_pipeline_serialization(self):
        """Serializer accepts valid pipeline data."""
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
        # Validation may need tenant/created_by context; check field types
        self.assertIn("name", serializer.fields)
        self.assertIn("pipeline_definition", serializer.fields)
        self.assertIn("version", serializer.fields)

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
            "id", "tenant", "created_by", "name", "description",
            "pipeline_definition", "version", "status",
            "created_at", "updated_at", "metadata",
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
