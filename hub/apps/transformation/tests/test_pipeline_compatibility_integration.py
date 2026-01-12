"""
Integration tests for PipelineCompatibilityValidator with TransformationService.

Tests integration between PipelineCompatibilityValidator and TransformationService
using real services and models (no mocks/stubs).
"""
import uuid
from django.test import TestCase
from django.core.cache import cache

from hub.apps.transformation.services import TransformationService
from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineStatus
)
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


class PipelineCompatibilityIntegrationTest(TestCase):
    """Integration tests for pipeline compatibility validation with TransformationService."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create test asset with dataset and schema
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE[0]
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path="test/test.csv",
            size=1000,
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            semantic_version="1.0.0",
            format="CSV",
            schema_json={
                "fields": [
                    {
                        "name": "customer_id",
                        "data_type": "string",
                        "nullable": False
                    },
                    {
                        "name": "age",
                        "data_type": "integer",
                        "nullable": True
                    },
                    {
                        "name": "name",
                        "data_type": "string",
                        "nullable": True
                    },
                    {
                        "name": "amount",
                        "data_type": "float",
                        "nullable": True
                    }
                ]
            }
        )

        # Create valid pipeline definition
        self.valid_pipeline_definition = {
            "version": "1.0.0",
            "input_schema": {
                "fields": [
                    {
                        "name": "customer_id",
                        "data_type": "string",
                        "nullable": False
                    },
                    {
                        "name": "age",
                        "data_type": "integer",
                        "nullable": True
                    },
                    {
                        "name": "name",
                        "data_type": "string",
                        "nullable": True
                    }
                ]
            },
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "filter",
                        "filter_expression": "age > 18"
                    }
                },
                {
                    "name": "transform_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "transform",
                        "transform_expression": "name.upper()"
                    }
                },
                {
                    "name": "output_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "output"
                    }
                }
            ]
        }

    def test_service_validate_pipeline_compatibility_with_asset(self):
        """Test TransformationService.validate_pipeline_compatibility with asset."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.service.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("validation_checks", result.details)
        self.assertIn("pipeline_definition", result.details["validation_checks"])
        self.assertIn("node_compatibility", result.details["validation_checks"])
        self.assertIn("schema_compatibility", result.details["validation_checks"])
        self.assertIn("data_type_compatibility", result.details["validation_checks"])

    def test_service_validate_pipeline_compatibility_with_schema(self):
        """Test TransformationService.validate_pipeline_compatibility with explicit schema."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        input_schema = {
            "fields": [
                {
                    "name": "customer_id",
                    "data_type": "string",
                    "nullable": False
                },
                {
                    "name": "age",
                    "data_type": "integer",
                    "nullable": True
                },
                {
                    "name": "name",
                    "data_type": "string",
                    "nullable": True
                }
            ]
        }

        result = self.service.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_schema=input_schema
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details.get("input_schema_source"), "provided")

    def test_service_validate_pipeline_compatibility_invalid_schema(self):
        """Test TransformationService.validate_pipeline_compatibility with invalid schema."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Missing required fields
        input_schema = {
            "fields": [
                {
                    "name": "customer_id",
                    "data_type": "string",
                    "nullable": False
                }
                # Missing 'age' and 'name'
            ]
        }

        result = self.service.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_schema=input_schema
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_service_validate_pipeline_compatibility_invalid_pipeline(self):
        """Test TransformationService.validate_pipeline_compatibility with invalid pipeline."""
        # Pipeline with invalid node type
        invalid_pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "invalid_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "invalid_type"
                    }
                }
            ]
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=invalid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.service.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_service_validate_pipeline_compatibility_caching(self):
        """Test that TransformationService uses caching."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Clear cache
        cache.clear()

        # First call - should compute
        result1 = self.service.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset,
            use_cache=True
        )

        # Second call - should use cache
        result2 = self.service.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset,
            use_cache=True
        )

        self.assertTrue(result1.is_valid)
        self.assertTrue(result2.is_valid)
        # Results should be identical
        self.assertEqual(result1.details, result2.details)

    def test_service_validate_pipeline_compatibility_no_cache(self):
        """Test TransformationService validation without caching."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.service.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset,
            use_cache=False
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_service_validate_pipeline_compatibility_comprehensive(self):
        """Test comprehensive validation through TransformationService."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.service.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset
        )

        # Verify all validation checks were performed
        self.assertIsInstance(result, ValidationResult)
        validation_checks = result.details.get("validation_checks", {})

        # Pipeline definition check
        self.assertIn("pipeline_definition", validation_checks)
        self.assertTrue(validation_checks["pipeline_definition"].get("checks", {}).get("pipeline_definition_type", False))

        # Node compatibility check
        self.assertIn("node_compatibility", validation_checks)
        self.assertTrue(validation_checks["node_compatibility"].get("node_compatibility_checks", {}).get("has_steps", False))

        # Schema compatibility check
        self.assertIn("schema_compatibility", validation_checks)

        # Data type compatibility check
        self.assertIn("data_type_compatibility", validation_checks)

