"""
Unit tests for PipelineCompatibilityValidator.

Tests all validation methods using real services and models (no mocks/stubs).
"""
import uuid
from django.test import TestCase
from django.core.cache import cache

from hub.apps.transformation.pipeline_compatibility_validator import (
    PipelineCompatibilityValidator,
    SchemaField
)
from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.transformation.models import (
    TransformationPipeline,
    NodeType,
    PipelineStatus
)
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


class PipelineCompatibilityValidatorTest(TestCase):
    """Test cases for PipelineCompatibilityValidator."""

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

        self.validator = PipelineCompatibilityValidator(
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

    def test_validate_pipeline_definition_valid(self):
        """Test pipeline definition validation with valid pipeline."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.validator.validate_pipeline_definition(pipeline)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("pipeline_id", result.details)
        self.assertEqual(result.details["pipeline_id"], str(pipeline.id))

    def test_validate_pipeline_definition_missing_version(self):
        """Test pipeline definition validation with missing version."""
        # Create valid pipeline first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Update to invalid definition using update() to bypass validation
        invalid_definition = {
            "steps": [
                {
                    "name": "step1",
                    "type": "task"
                }
            ]
        }
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=invalid_definition
        )
        pipeline.refresh_from_db()

        result = self.validator.validate_pipeline_definition(pipeline)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("version" in error.lower() for error in result.errors))

    def test_validate_pipeline_definition_missing_steps(self):
        """Test pipeline definition validation with missing steps."""
        # Create valid pipeline first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Update to invalid definition using update() to bypass validation
        invalid_definition = {
            "version": "1.0.0"
        }
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=invalid_definition
        )
        pipeline.refresh_from_db()

        result = self.validator.validate_pipeline_definition(pipeline)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("steps" in error.lower() for error in result.errors))

    def test_validate_pipeline_definition_empty_steps(self):
        """Test pipeline definition validation with empty steps."""
        # Create valid pipeline first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Update to invalid definition using update() to bypass validation
        invalid_definition = {
            "version": "1.0.0",
            "steps": []
        }
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=invalid_definition
        )
        pipeline.refresh_from_db()

        result = self.validator.validate_pipeline_definition(pipeline)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("at least one step" in error.lower() for error in result.errors))

    def test_validate_node_compatibility_valid(self):
        """Test node compatibility validation with valid nodes."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.validator.validate_node_compatibility(pipeline)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("node_count", result.details)

    def test_validate_node_compatibility_invalid_node_type(self):
        """Test node compatibility validation with invalid node type."""
        invalid_definition = {
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
            pipeline_definition=invalid_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.validator.validate_node_compatibility(pipeline)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("invalid node_type" in error.lower() for error in result.errors))

    def test_validate_node_compatibility_missing_required_fields(self):
        """Test node compatibility validation with missing required fields."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "filter"
                        # Missing filter_expression
                    }
                }
            ]
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=invalid_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.validator.validate_node_compatibility(pipeline)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("filter_expression" in error.lower() for error in result.errors))

    def test_validate_schema_compatibility_valid(self):
        """Test schema compatibility validation with compatible schemas."""
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

        result = self.validator.validate_schema_compatibility(pipeline, input_schema)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_schema_compatibility_missing_fields(self):
        """Test schema compatibility validation with missing fields."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Missing 'age' field
        input_schema = {
            "fields": [
                {
                    "name": "customer_id",
                    "data_type": "string",
                    "nullable": False
                },
                {
                    "name": "name",
                    "data_type": "string",
                    "nullable": True
                }
            ]
        }

        result = self.validator.validate_schema_compatibility(pipeline, input_schema)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("not present" in error.lower() for error in result.errors))

    def test_validate_schema_compatibility_extra_fields(self):
        """Test schema compatibility validation with extra fields (should warn)."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Extra 'amount' field
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
                },
                {
                    "name": "amount",
                    "data_type": "float",
                    "nullable": True
                }
            ]
        }

        result = self.validator.validate_schema_compatibility(pipeline, input_schema)

        self.assertTrue(result.is_valid)  # Extra fields are warnings, not errors
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any("not referenced" in warning.lower() for warning in result.warnings))

    def test_validate_data_type_compatibility_valid(self):
        """Test data type compatibility validation with compatible types."""
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

        result = self.validator.validate_data_type_compatibility(pipeline, input_schema)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_data_type_compatibility_incompatible_types(self):
        """Test data type compatibility validation with incompatible types."""
        # Create valid pipeline first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Update to test definition using update() to bypass validation
        pipeline_definition = {
            "version": "1.0.0",
            "input_schema": {
                "fields": [
                    {
                        "name": "age",
                        "data_type": "string",  # Pipeline expects string
                        "nullable": True
                    }
                ]
            },
            "steps": [
                {
                    "name": "test_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "output"
                    }
                }
            ]
        }
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=pipeline_definition
        )
        pipeline.refresh_from_db()

        # Input schema has integer, but pipeline expects string
        input_schema = {
            "fields": [
                {
                    "name": "age",
                    "data_type": "integer",  # Incompatible with string
                    "nullable": True
                }
            ]
        }

        result = self.validator.validate_data_type_compatibility(pipeline, input_schema)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("incompatible types" in error.lower() for error in result.errors))

    def test_validate_data_type_compatibility_compatible_types(self):
        """Test data type compatibility validation with compatible but different types."""
        # Create valid pipeline first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        # Update to test definition using update() to bypass validation
        pipeline_definition = {
            "version": "1.0.0",
            "input_schema": {
                "fields": [
                    {
                        "name": "age",
                        "data_type": "number",  # Pipeline expects number
                        "nullable": True
                    }
                ]
            },
            "steps": [
                {
                    "name": "test_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "output"
                    }
                }
            ]
        }
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=pipeline_definition
        )
        pipeline.refresh_from_db()

        # Input schema has integer, which is compatible with number
        input_schema = {
            "fields": [
                {
                    "name": "age",
                    "data_type": "integer",  # Compatible with number
                    "nullable": True
                }
            ]
        }

        result = self.validator.validate_data_type_compatibility(pipeline, input_schema)

        self.assertTrue(result.is_valid)
        # May have warnings about type differences
        self.assertEqual(len(result.errors), 0)

    def test_validate_pipeline_compatibility_comprehensive(self):
        """Test comprehensive pipeline compatibility validation."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.validator.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset
        )

        self.assertTrue(result.is_valid)
        self.assertIn("validation_checks", result.details)
        self.assertIn("pipeline_definition", result.details["validation_checks"])
        self.assertIn("node_compatibility", result.details["validation_checks"])
        self.assertIn("schema_compatibility", result.details["validation_checks"])
        self.assertIn("data_type_compatibility", result.details["validation_checks"])

    def test_validate_pipeline_compatibility_with_input_schema(self):
        """Test comprehensive validation with explicit input schema."""
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

        result = self.validator.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_schema=input_schema
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details.get("input_schema_source"), "provided")

    def test_validate_pipeline_compatibility_caching(self):
        """Test that validation results are cached."""
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
        result1 = self.validator.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset,
            use_cache=True
        )

        # Second call - should use cache
        result2 = self.validator.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset,
            use_cache=True
        )

        self.assertTrue(result1.is_valid)
        self.assertTrue(result2.is_valid)
        # Results should be identical
        self.assertEqual(result1.details, result2.details)

    def test_validate_pipeline_compatibility_no_cache(self):
        """Test validation without caching."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        result = self.validator.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_asset=self.asset,
            use_cache=False
        )

        self.assertTrue(result.is_valid)

    def test_schema_field_from_dict(self):
        """Test SchemaField.from_dict method."""
        field_dict = {
            "name": "test_field",
            "data_type": "string",
            "nullable": False,
            "description": "Test field",
            "min_length": 1,
            "max_length": 100
        }

        field = SchemaField.from_dict(field_dict)

        self.assertEqual(field.name, "test_field")
        self.assertEqual(field.data_type, "string")
        self.assertFalse(field.nullable)
        self.assertEqual(field.description, "Test field")
        self.assertEqual(field.min_length, 1)
        self.assertEqual(field.max_length, 100)

    def test_extract_referenced_fields(self):
        """Test extraction of referenced fields from pipeline."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.DRAFT
        )

        referenced_fields = self.validator._extract_referenced_fields(pipeline)

        self.assertIn("age", referenced_fields)
        self.assertIn("name", referenced_fields)

    def test_extract_schema_from_asset(self):
        """Test extraction of schema from asset."""
        schema = self.validator._extract_schema_from_asset(self.asset)

        self.assertIsNotNone(schema)
        self.assertIn("fields", schema)
        self.assertEqual(len(schema["fields"]), 4)

    def test_extract_schema_from_asset_no_dataset(self):
        """Test extraction of schema from asset without dataset."""
        asset_no_dataset = Asset.objects.create(
            tenant=self.tenant,
            key="no-dataset-asset",
            name="No Dataset Asset",
            status=AssetStatus.ACTIVE[0]
        )

        schema = self.validator._extract_schema_from_asset(asset_no_dataset)

        self.assertIsNone(schema)

