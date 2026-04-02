"""
Unit tests for TransformationPipeline model.
"""
import uuid
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model

from hub.apps.transformation.models import TransformationPipeline, PipelineStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class TransformationPipelineModelTest(TestCase):
    """Test cases for TransformationPipeline model."""

    @classmethod
    def setUpTestData(cls):
        """Create Tenant and User once for the whole test class (read-only)."""
        uid = uuid.uuid4().hex[:8]
        cls.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}"
        )
        cls.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=cls.tenant
        )

    def setUp(self):
        """Set up per-test fixtures."""
        self.valid_pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "extract_data",
                    "input": {}
                },
                {
                    "name": "step2",
                    "type": "task",
                    "task": "transform_data",
                    "input": {}
                }
            ]
        }

    def test_create_pipeline(self):
        """Test creating a transformation pipeline."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            description="Test pipeline description",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0",
            status=PipelineStatus.DRAFT
        )

        self.assertIsNotNone(pipeline.id)
        self.assertEqual(pipeline.name, "Test Pipeline")
        self.assertEqual(pipeline.description, "Test pipeline description")
        self.assertEqual(pipeline.get_pipeline_definition(), self.valid_pipeline_definition)
        self.assertEqual(pipeline.version, "1.0.0")
        self.assertEqual(pipeline.status, PipelineStatus.DRAFT)
        self.assertEqual(pipeline.tenant, self.tenant)
        self.assertEqual(pipeline.created_by, self.user)

    def test_pipeline_str_representation(self):
        """Test pipeline string representation."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0",
            status=PipelineStatus.ACTIVE
        )

        expected_str = f"Test Pipeline v1.0.0 ({PipelineStatus.ACTIVE})"
        self.assertEqual(str(pipeline), expected_str)

    def test_pipeline_default_status(self):
        """Test pipeline defaults to DRAFT status."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        self.assertEqual(pipeline.status, PipelineStatus.DRAFT)

    def test_pipeline_default_metadata(self):
        """Test pipeline has default empty metadata."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        self.assertEqual(pipeline.metadata, {})

    def test_pipeline_validation_empty_name(self):
        """Test pipeline validation fails with empty name."""
        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="",
            pipeline_definition=self.valid_pipeline_definition
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_validation_whitespace_name(self):
        """Test pipeline validation fails with whitespace-only name."""
        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="   ",
            pipeline_definition=self.valid_pipeline_definition
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_validation_invalid_definition_not_dict(self):
        """Test pipeline validation fails when definition is not a dict."""
        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition="not a dict"
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_validation_missing_version(self):
        """Test pipeline validation fails when definition missing version."""
        invalid_definition = {
            "steps": [
                {
                    "name": "step1",
                    "type": "task",
                    "task": "extract_data"
                }
            ]
        }

        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=invalid_definition
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_validation_missing_steps(self):
        """Test pipeline validation fails when definition missing steps."""
        invalid_definition = {
            "version": "1.0.0"
        }

        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=invalid_definition
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_validation_empty_steps(self):
        """Test pipeline validation fails when steps list is empty."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": []
        }

        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=invalid_definition
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_validation_invalid_step_not_dict(self):
        """Test pipeline validation fails when step is not a dict."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": ["not a dict"]
        }

        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=invalid_definition
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_validation_step_missing_name(self):
        """Test pipeline validation fails when step missing name."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "type": "task",
                    "task": "extract_data"
                }
            ]
        }

        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=invalid_definition
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_validation_step_missing_type(self):
        """Test pipeline validation fails when step missing type."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "step1",
                    "task": "extract_data"
                }
            ]
        }

        pipeline = TransformationPipeline(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=invalid_definition
        )

        with self.assertRaises(ValidationError):
            pipeline.full_clean()

    def test_pipeline_is_active(self):
        """Test is_active method."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        self.assertTrue(pipeline.is_active())

        pipeline.status = PipelineStatus.DRAFT
        self.assertFalse(pipeline.is_active())

    def test_pipeline_is_draft(self):
        """Test is_draft method."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        self.assertTrue(pipeline.is_draft())

        pipeline.status = PipelineStatus.ACTIVE
        self.assertFalse(pipeline.is_draft())

    def test_pipeline_can_execute(self):
        """Test can_execute method."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        self.assertTrue(pipeline.can_execute())

        pipeline.status = PipelineStatus.DRAFT
        self.assertFalse(pipeline.can_execute())

        pipeline.status = PipelineStatus.INACTIVE
        self.assertFalse(pipeline.can_execute())

    def test_pipeline_activate(self):
        """Test activate method."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        pipeline.activate()

        self.assertEqual(pipeline.status, PipelineStatus.ACTIVE)
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.status, PipelineStatus.ACTIVE)

    def test_pipeline_deactivate(self):
        """Test deactivate method."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        pipeline.deactivate()

        self.assertEqual(pipeline.status, PipelineStatus.INACTIVE)
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.status, PipelineStatus.INACTIVE)

    def test_pipeline_archive(self):
        """Test archive method."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        pipeline.archive()

        self.assertEqual(pipeline.status, PipelineStatus.ARCHIVED)
        pipeline.refresh_from_db()
        self.assertEqual(pipeline.status, PipelineStatus.ARCHIVED)

    def test_pipeline_get_step_count(self):
        """Test get_step_count method."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        self.assertEqual(pipeline.get_step_count(), 2)

        # Test with different step count
        new_def = pipeline.get_pipeline_definition()
        new_def = {
            "version": "1.0.0",
            "steps": [
                {"name": "step1", "type": "task", "task": "extract"}
            ]
        }
        pipeline.pipeline_definition = new_def
        self.assertEqual(pipeline.get_step_count(), 1)

    def test_pipeline_get_pipeline_version(self):
        """Test get_pipeline_version method."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        self.assertEqual(pipeline.get_pipeline_version(), "1.0.0")

        # Test with different version
        pipeline.pipeline_definition = {
            "version": "2.1.0",
            "steps": [{"name": "step1", "type": "task", "task": "extract"}]
        }
        self.assertEqual(pipeline.get_pipeline_version(), "2.1.0")

    def test_pipeline_unique_constraint(self):
        """Test unique constraint on tenant, name, and version."""
        TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0"
        )

        # Try to create duplicate
        with self.assertRaises((IntegrityError, ValidationError)):
            TransformationPipeline.objects.create(
                tenant=self.tenant,
                name="Test Pipeline",
                pipeline_definition=self.valid_pipeline_definition,
                version="1.0.0"
            )

    def test_pipeline_different_versions_allowed(self):
        """Test that same name with different version is allowed."""
        TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0"
        )

        # Different version should be allowed
        pipeline2 = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            version="2.0.0"
        )

        self.assertIsNotNone(pipeline2.id)
        self.assertEqual(pipeline2.version, "2.0.0")

    def test_pipeline_different_tenants_allowed(self):
        """Test that same name in different tenant is allowed."""
        TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0"
        )

        # Different tenant should be allowed
        import uuid as _uuid
        _uid = _uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Test Tenant 2 {_uid}",
            slug=f"test-tenant-2-{_uid}",
        )
        pipeline2 = TransformationPipeline.objects.create(
            tenant=tenant2,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            version="1.0.0"
        )

        self.assertIsNotNone(pipeline2.id)
        self.assertEqual(pipeline2.tenant, tenant2)

    def test_pipeline_created_at_auto_set(self):
        """Test created_at is automatically set."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        self.assertIsNotNone(pipeline.created_at)

    def test_pipeline_updated_at_auto_set(self):
        """Test updated_at is automatically set and updated."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition
        )

        original_updated_at = pipeline.updated_at

        # Update pipeline
        pipeline.name = "Updated Pipeline"
        pipeline.save()

        pipeline.refresh_from_db()
        self.assertGreater(pipeline.updated_at, original_updated_at)

    def test_pipeline_metadata_can_store_arbitrary_data(self):
        """Test metadata field can store arbitrary JSON data."""
        metadata = {
            "tags": ["etl", "customer-data"],
            "source_asset_id": str(uuid.uuid4()),
            "target_asset_id": str(uuid.uuid4()),
            "category": "data-enrichment"
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            metadata=metadata
        )

        self.assertEqual(pipeline.metadata, metadata)
        self.assertEqual(pipeline.metadata["tags"], ["etl", "customer-data"])

