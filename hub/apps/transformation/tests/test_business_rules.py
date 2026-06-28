"""
Unit tests for TransformationBusinessRules.

Tests all validation methods using real services and models (no mocks/stubs).
"""

import uuid

from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.transformation.business_rules import (
    TransformationBusinessRules,
)
from hub.apps.transformation.exceptions import (
    AssetCompatibilityError,
    ResourceQuotaExceededError,
    TransformationValidationError,
)
from hub.apps.transformation.models import (
    PipelineStatus,
    TransformationPipeline,
)
from hub.apps.users.models import User, UserStatus


class TransformationBusinessRulesTest(TestCase):
    """Test cases for TransformationBusinessRules."""

    def setUp(self):
        """Set up per-test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create valid pipeline definition
        self.valid_pipeline_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {"node_type": "filter", "filter_expression": "age > 18"},
                },
                {
                    "name": "transform_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "transform",
                        "transform_expression": "name.upper()",
                    },
                },
                {"name": "output_step", "type": "task", "node_config": {"node_type": "output"}},
            ],
        }

        # Create test asset with dataset (per-test: some tests mutate these)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            storage_path=f"test/test-{uuid.uuid4().hex[:8]}.csv",
            size=1000,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=100,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "age", "data_type": "integer"},
                ]
            },
        )

    def test_validate_pipeline_structure_valid(self):
        """Test validate_pipeline_structure with valid pipeline."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_pipeline_structure(pipeline, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("pipeline_id", result.details)
        self.assertIn("validation_checks", result.details)

    def test_validate_pipeline_structure_missing_version(self):
        """Test validate_pipeline_structure with missing version."""
        # Create pipeline with valid definition first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Update to invalid definition using update() to bypass validation
        invalid_definition = {"steps": [{"name": "step1", "type": "task"}]}
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=invalid_definition
        )
        pipeline.refresh_from_db()

        result = self.business_rules.validate_pipeline_structure(pipeline, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("version" in error.lower() for error in result.errors))

    def test_validate_pipeline_structure_empty_steps(self):
        """Test validate_pipeline_structure with empty steps."""
        # Create pipeline with valid definition first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Update to invalid definition using update() to bypass validation
        invalid_definition = {"version": "1.0.0", "steps": []}
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=invalid_definition
        )
        pipeline.refresh_from_db()

        result = self.business_rules.validate_pipeline_structure(pipeline, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("at least one step" in error.lower() for error in result.errors))

    def test_validate_pipeline_structure_duplicate_step_names(self):
        """Test validate_pipeline_structure with duplicate step names."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task"}, {"name": "step1", "type": "task"}],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=invalid_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_pipeline_structure(pipeline, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("duplicate" in error.lower() for error in result.errors))

    def test_validate_pipeline_structure_raises_exception(self):
        """Test validate_pipeline_structure raises exception when raise_on_error=True."""
        # Create pipeline with valid definition first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Update to invalid definition using update() to bypass validation
        invalid_definition = {"steps": []}
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=invalid_definition
        )
        pipeline.refresh_from_db()

        with self.assertRaises(TransformationValidationError) as cm:
            self.business_rules.validate_pipeline_structure(pipeline, raise_on_error=True)

        self.assertEqual(
            cm.exception.error_code,
            TransformationValidationError.ERROR_CODE_INVALID_PIPELINE_DEFINITION,
        )

    def test_validate_node_compatibility_valid(self):
        """Test validate_node_compatibility with valid nodes."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_node_compatibility(pipeline, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertIn("node_compatibility_checks", result.details)

    def test_validate_node_compatibility_invalid_node_type(self):
        """Test validate_node_compatibility with invalid node type."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "invalid_step",
                    "type": "task",
                    "node_config": {"node_type": "invalid_type"},
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=invalid_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_node_compatibility(pipeline, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("invalid node_type" in error.lower() for error in result.errors))

    def test_validate_node_compatibility_missing_required_fields(self):
        """Test validate_node_compatibility with missing required fields."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "filter"
                        # Missing filter_expression
                    },
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=invalid_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_node_compatibility(pipeline, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("missing required fields" in error.lower() for error in result.errors))

    def test_validate_node_compatibility_no_output_node(self):
        """Test validate_node_compatibility with no output node."""
        definition_no_output = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {"node_type": "filter", "filter_expression": "age > 18"},
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=definition_no_output,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_node_compatibility(pipeline, raise_on_error=False)

        # Should have warning but may still be valid
        self.assertTrue(any("output" in warning.lower() for warning in result.warnings))

    def test_validate_node_compatibility_raises_exception(self):
        """Test validate_node_compatibility raises exception when raise_on_error=True."""
        invalid_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "filter"
                        # Missing filter_expression
                    },
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=invalid_definition,
            status=PipelineStatus.ACTIVE,
        )

        with self.assertRaises(TransformationValidationError) as cm:
            self.business_rules.validate_node_compatibility(pipeline, raise_on_error=True)

        self.assertEqual(
            cm.exception.error_code, TransformationValidationError.ERROR_CODE_INVALID_NODE_CONFIG
        )

    def test_validate_schema_alignment_valid(self):
        """Test validate_schema_alignment with valid schema."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            pipeline, self.asset, raise_on_error=False
        )

        # Check if validation passed or if there are only warnings
        # Field extraction might find 'age' and 'name' which exist in schema
        if result.is_valid:
            self.assertIn("schema_alignment_checks", result.details)
            if "all_fields_present" in result.details["schema_alignment_checks"]:
                self.assertTrue(result.details["schema_alignment_checks"]["all_fields_present"])
        else:
            # If not valid, check that errors are about missing fields (not about no dataset)
            self.assertIn("schema_alignment_checks", result.details)
            # The test should at least check that schema alignment was attempted
            self.assertTrue(result.details["schema_alignment_checks"]["source_dataset_exists"])

    def test_validate_schema_alignment_missing_field(self):
        """Test validate_schema_alignment with missing field in schema."""
        # Pipeline references 'email' field which doesn't exist in schema
        definition_with_missing_field = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "filter",
                        "filter_expression": "email IS NOT NULL",
                    },
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=definition_with_missing_field,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            pipeline, self.asset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("don't exist" in error.lower() for error in result.errors))

    def test_validate_schema_alignment_no_dataset(self):
        """Test validate_schema_alignment with asset that has no dataset."""
        asset_no_dataset = Asset.objects.create(
            tenant=self.tenant,
            key="no-dataset-asset",
            name="No Dataset Asset",
            status=AssetStatus.ACTIVE,
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            pipeline, asset_no_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("no dataset" in error.lower() for error in result.errors))

    def test_validate_schema_alignment_raises_exception(self):
        """Test validate_schema_alignment raises exception when raise_on_error=True."""
        asset_no_dataset = Asset.objects.create(
            tenant=self.tenant,
            key="no-dataset-asset",
            name="No Dataset Asset",
            status=AssetStatus.ACTIVE,
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        with self.assertRaises(AssetCompatibilityError) as cm:
            self.business_rules.validate_schema_alignment(
                pipeline, asset_no_dataset, raise_on_error=True
            )

        self.assertEqual(
            cm.exception.error_code, AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE
        )

    def test_validate_asset_compatibility_valid(self):
        """Test validate_asset_compatibility with valid asset."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("asset_compatibility_checks", result.details)
        self.assertTrue(result.details["asset_compatibility_checks"]["source_asset_status"])
        self.assertTrue(result.details["asset_compatibility_checks"]["source_dataset_exists"])

    def test_validate_asset_compatibility_invalid_status(self):
        """Test validate_asset_compatibility with asset in invalid status."""
        asset_draft = Asset.objects.create(
            tenant=self.tenant, key="draft-asset", name="Draft Asset", status=AssetStatus.DRAFT
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, asset_draft, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("must be ACTIVE or PUBLIC" in error for error in result.errors))

    def test_validate_asset_compatibility_no_dataset(self):
        """Test validate_asset_compatibility with asset that has no dataset."""
        asset_no_dataset = Asset.objects.create(
            tenant=self.tenant,
            key="no-dataset-asset",
            name="No Dataset Asset",
            status=AssetStatus.ACTIVE,
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, asset_no_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("no dataset" in error.lower() for error in result.errors))

    def test_validate_asset_compatibility_with_target_asset(self):
        """Test validate_asset_compatibility with target asset."""
        target_asset = Asset.objects.create(
            tenant=self.tenant, key="target-asset", name="Target Asset", status=AssetStatus.DRAFT
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, target_asset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("target_asset_id", result.details)

    def test_validate_asset_compatibility_raises_exception(self):
        """Test validate_asset_compatibility raises exception when raise_on_error=True."""
        asset_no_dataset = Asset.objects.create(
            tenant=self.tenant,
            key="no-dataset-asset",
            name="No Dataset Asset",
            status=AssetStatus.ACTIVE,
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        with self.assertRaises(AssetCompatibilityError) as cm:
            self.business_rules.validate_asset_compatibility(
                pipeline, asset_no_dataset, raise_on_error=True
            )

        self.assertEqual(
            cm.exception.error_code, AssetCompatibilityError.ERROR_CODE_ASSET_INCOMPATIBLE
        )

    def test_validate_asset_compatibility_schema_validation(self):
        """Test asset schema validation matches pipeline input schema."""
        # Create pipeline with explicit input schema
        pipeline_def = {
            "version": "1.0.0",
            "input_schema": {
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "age", "data_type": "integer"},
                ]
            },
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {"node_type": "filter", "filter_expression": "age > 18"},
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=pipeline_def,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        schema_validation = result.details["asset_compatibility_checks"]["schema_validation"]
        self.assertTrue(schema_validation["asset_schema_valid"])
        self.assertTrue(schema_validation["schema_fields_match"])

    def test_validate_asset_compatibility_schema_missing_fields(self):
        """Test asset schema validation detects missing fields."""
        # Create pipeline requiring fields not in asset schema
        pipeline_def = {
            "version": "1.0.0",
            "input_schema": {
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "age", "data_type": "integer"},
                    {"name": "email", "data_type": "string"},  # Not in asset schema
                ]
            },
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {"node_type": "filter", "filter_expression": "age > 18"},
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=pipeline_def,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        schema_validation = result.details["asset_compatibility_checks"]["schema_validation"]
        self.assertFalse(schema_validation["asset_schema_valid"])
        self.assertIn("email", schema_validation["missing_fields"])

    def test_validate_asset_compatibility_schema_extracted_from_steps(self):
        """Test asset schema validation extracts schema from pipeline steps."""
        # Pipeline without explicit input_schema, but references fields in steps
        pipeline_def = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "filter",
                        "filter_expression": "age > 18 and name != ''",
                    },
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=pipeline_def,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        schema_validation = result.details["asset_compatibility_checks"]["schema_validation"]
        self.assertEqual(schema_validation["pipeline_input_schema_source"], "extracted_from_steps")

    def test_validate_asset_compatibility_format_validation_csv(self):
        """Test asset format validation for CSV format."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        format_validation = result.details["asset_compatibility_checks"]["format_validation"]
        self.assertTrue(format_validation["format_valid"])
        self.assertTrue(format_validation["supported_format"])
        self.assertEqual(format_validation["format"], "CSV")

    def test_validate_asset_compatibility_format_validation_json(self):
        """Test asset format validation for JSON format."""
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=2,
            format="JSON",
            row_count=100,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                ]
            },
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        format_validation = result.details["asset_compatibility_checks"]["format_validation"]
        self.assertTrue(format_validation["format_valid"])
        self.assertEqual(format_validation["format"], "JSON")

    def test_validate_asset_compatibility_format_validation_parquet(self):
        """Test asset format validation for Parquet format."""
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=3,
            format="PARQUET",
            row_count=100,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                ]
            },
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        format_validation = result.details["asset_compatibility_checks"]["format_validation"]
        self.assertTrue(format_validation["format_valid"])
        self.assertEqual(format_validation["format"], "PARQUET")

    def test_validate_asset_compatibility_format_validation_unsupported(self):
        """Test asset format validation rejects unsupported formats."""
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=4,
            format="XML",  # Unsupported format
            row_count=100,
            schema_json={"fields": [{"name": "id", "data_type": "integer"}]},
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        format_validation = result.details["asset_compatibility_checks"]["format_validation"]
        self.assertFalse(format_validation["supported_format"])

    def test_validate_asset_compatibility_size_validation_sync_mode(self):
        """Test asset size validation selects SYNC mode for small datasets."""
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=5,
            format="CSV",
            row_count=5000,  # Below SYNC threshold (10000)
            schema_json={"fields": [{"name": "id", "data_type": "integer"}]},
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        size_validation = result.details["asset_compatibility_checks"]["size_validation"]
        self.assertTrue(size_validation["size_valid"])
        self.assertEqual(size_validation["execution_mode"], "SYNC")
        self.assertFalse(size_validation["size_threshold_exceeded"])

    def test_validate_asset_compatibility_size_validation_async_mode(self):
        """Test asset size validation selects ASYNC mode for large datasets."""
        large_file = File.objects.create(
            tenant=self.tenant,
            name="large.csv",
            storage_path="test/large.csv",
            size=20 * 1024 * 1024,  # 20MB, above SYNC threshold (10MB)
            content_type="text/csv",
            status=FileStatus.ACTIVE,
        )

        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=large_file,
            version=6,
            format="CSV",
            row_count=50000,  # Above SYNC threshold
            schema_json={"fields": [{"name": "id", "data_type": "integer"}]},
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        size_validation = result.details["asset_compatibility_checks"]["size_validation"]
        self.assertTrue(size_validation["size_valid"])
        self.assertEqual(size_validation["execution_mode"], "ASYNC")
        self.assertTrue(size_validation["size_threshold_exceeded"])

    def test_validate_asset_compatibility_size_validation_no_size_info(self):
        """Test asset size validation handles missing size information."""
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            version=7,
            format="CSV",
            row_count=None,  # No row count
            schema_json={"fields": [{"name": "id", "data_type": "integer"}]},
        )
        # Set file size to 0
        self.file.size = 0
        self.file.save()

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        size_validation = result.details["asset_compatibility_checks"]["size_validation"]
        self.assertTrue(size_validation["size_valid"])  # Not an error, just warning
        self.assertEqual(size_validation["execution_mode"], "ASYNC")
        self.assertTrue(any("size information" in w.lower() for w in result.warnings))

    def test_validate_asset_compatibility_access_validation_same_tenant(self):
        """Test asset access validation for same-tenant access."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, self.asset, raise_on_error=False
        )

        access_validation = result.details["asset_compatibility_checks"]["access_validation"]
        self.assertTrue(access_validation["access_valid"])
        self.assertTrue(access_validation["access_allowed"])
        self.assertFalse(access_validation["cross_tenant"])

    def test_validate_asset_compatibility_access_validation_cross_tenant(self):
        """Test asset access validation for cross-tenant access."""
        # Create another tenant and asset
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")

        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset", status=AssetStatus.ACTIVE
        )

        other_file = File.objects.create(
            tenant=other_tenant,
            name="other.csv",
            storage_path="other/other.csv",
            size=1000,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
        )

        Dataset.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            file=other_file,
            version=1,
            format="CSV",
            row_count=100,
            schema_json={"fields": [{"name": "id", "data_type": "integer"}]},
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_asset_compatibility(
            pipeline, other_asset, raise_on_error=False
        )

        access_validation = result.details["asset_compatibility_checks"]["access_validation"]
        self.assertTrue(access_validation["cross_tenant"])
        # Access validation may fail for cross-tenant without entitlement
        # This is expected behavior

    def test_validate_asset_compatibility_integration_with_asset_service(self):
        """Integration test with AssetService."""
        from hub.apps.assets.services import AssetService

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Use AssetService to get asset
        asset_service = AssetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        retrieved_asset = asset_service.get_asset(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id)
        )

        # Validate compatibility using business rules
        result = self.business_rules.validate_asset_compatibility(
            pipeline, retrieved_asset, raise_on_error=False
        )

        # Debug output if test fails
        if not result.is_valid:
            print(f"\nValidation failed. Errors: {result.errors}")
            print(f"Warnings: {result.warnings}")
            print(f"Details: {result.details}")

        self.assertTrue(
            result.is_valid,
            f"Validation failed with errors: {result.errors}, warnings: {result.warnings}",
        )
        self.assertIn("asset_compatibility_checks", result.details)
        self.assertIn("schema_validation", result.details["asset_compatibility_checks"])
        self.assertIn("format_validation", result.details["asset_compatibility_checks"])
        self.assertIn("size_validation", result.details["asset_compatibility_checks"])
        self.assertIn("access_validation", result.details["asset_compatibility_checks"])

    def test_validate_all_valid(self):
        """Test validate_all with valid pipeline and asset."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_all(pipeline, self.asset, raise_on_error=False)

        # Validate_all combines all validations, so check structure is present
        self.assertIn("validation_results", result.details)
        self.assertIn("structure", result.details["validation_results"])
        self.assertIn("node_compatibility", result.details["validation_results"])
        self.assertIn("asset_compatibility", result.details["validation_results"])
        self.assertIn("schema_alignment", result.details["validation_results"])

        # validate_all should pass
        self.assertTrue(result.is_valid)

        # Structure and node_compatibility should be valid
        structure_valid = result.details["validation_results"]["structure"].get(
            "validation_checks", {}
        )
        self.assertTrue(structure_valid)
        # Check that basic validations passed
        self.assertTrue(structure_valid.get("pipeline_definition_type", False))

    def test_validate_all_invalid_pipeline(self):
        """Test validate_all with invalid pipeline."""
        # Create pipeline with valid definition first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Update to invalid definition using update() to bypass validation
        invalid_definition = {"steps": []}
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=invalid_definition
        )
        pipeline.refresh_from_db()

        result = self.business_rules.validate_all(pipeline, self.asset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_all_raises_exception(self):
        """Test validate_all raises exception when raise_on_error=True."""
        # Create pipeline with valid definition first
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Update to invalid definition using update() to bypass validation
        invalid_definition = {"steps": []}
        TransformationPipeline.objects.filter(id=pipeline.id).update(
            pipeline_definition=invalid_definition
        )
        pipeline.refresh_from_db()

        # validate_all may raise either TransformationValidationError or AssetCompatibilityError
        # depending on the type of validation failure
        with self.assertRaises((TransformationValidationError, AssetCompatibilityError)):
            self.business_rules.validate_all(pipeline, self.asset, raise_on_error=True)

    def test_validate_join_node_config(self):
        """Test validation of JOIN node configuration."""
        join_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "join_step",
                    "type": "task",
                    "node_config": {"node_type": "join", "join_keys": ["id"], "join_type": "inner"},
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=join_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_node_compatibility(pipeline, raise_on_error=False)

        self.assertTrue(result.is_valid)

    def test_validate_aggregate_node_config(self):
        """Test validation of AGGREGATE node configuration."""
        aggregate_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "aggregate_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "aggregate",
                        "group_by": ["category"],
                        "aggregation_functions": {"total": "sum(amount)"},
                    },
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=aggregate_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_node_compatibility(pipeline, raise_on_error=False)

        self.assertTrue(result.is_valid)

    def test_validate_join_node_missing_config(self):
        """Test validation of JOIN node with missing configuration."""
        invalid_join_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "join_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "join"
                        # Missing join_keys and join_type
                    },
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=invalid_join_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_node_compatibility(pipeline, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(
                "join_keys" in error.lower() or "join_type" in error.lower()
                for error in result.errors
            )
        )

    def test_validate_aggregate_node_missing_config(self):
        """Test validation of AGGREGATE node with missing configuration."""
        invalid_aggregate_definition = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "aggregate_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "aggregate"
                        # Missing group_by and aggregation_functions
                    },
                }
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=invalid_aggregate_definition,
            status=PipelineStatus.ACTIVE,
        )

        result = self.business_rules.validate_node_compatibility(pipeline, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(
                "group_by" in error.lower() or "aggregation_functions" in error.lower()
                for error in result.errors
            )
        )

    # Cross-service business rules tests

    def test_validate_cross_tenant_operations_same_tenant(self):
        """Test cross-tenant validation with same-tenant assets"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        result = business_rules.validate_cross_tenant_operations(
            pipeline, self.asset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["cross_tenant_checks"]["source_is_same_tenant"])

    def test_validate_cross_tenant_operations_missing_tenant_id(self):
        """Test cross-tenant validation fails without tenant_id"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules()

        result = business_rules.validate_cross_tenant_operations(
            pipeline, self.asset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertIn("tenant_id is required", result.errors[0])

    def test_validate_cross_tenant_operations_with_abac_allow(self):
        """Test cross-tenant validation with ABAC allow + entitlement.

        Cross-tenant access requires both:
        1. ABAC policy allowing access
        2. Marketplace entitlement granting access
        """
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.marketplace.models import (
            Entitlement,
            Listing,
            ListingStatus,
            PricingModel,
        )

        # Create another tenant (KYC-verified, required to publish listings) and asset
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status="VERIFIED",
        )

        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key=f"other-asset-{uuid.uuid4().hex[:8]}",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
        )

        # Gate 1: ABAC ALLOW policy for cross-tenant access
        AccessPolicy.objects.create(
            tenant=other_tenant,
            name="Allow Cross-Tenant Access",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            priority=100,
            asset=other_asset,
        )

        # Gate 2: Marketplace entitlement
        listing = Listing.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
        )
        Entitlement.objects.create(
            tenant=self.tenant,
            asset=other_asset,
            listing=listing,
        )

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name=f"Test Pipeline {uuid.uuid4().hex[:8]}",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        result = business_rules.validate_cross_tenant_operations(
            pipeline, other_asset, raise_on_error=False
        )

        self.assertTrue(
            result.is_valid, f"Expected valid with ABAC+entitlement, got errors: {result.errors}"
        )

    def test_validate_resource_quota_success(self):
        """Test resource quota validation with available quota"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(tenant_id=str(self.tenant.id))

        result = business_rules.validate_resource_quota(pipeline, raise_on_error=False)

        self.assertTrue(result.is_valid)

    def test_validate_resource_quota_missing_tenant_id(self):
        """Test resource quota validation fails without tenant_id"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules()

        result = business_rules.validate_resource_quota(pipeline, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertIn("tenant_id is required", result.errors[0])

    def test_validate_resource_quota_exceeded(self):
        """Test resource quota validation when quota is exceeded"""
        from django.core.cache import cache

        from hub.apps.tenants.services import get_tenant_job_limits

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Set running jobs to exceed limit
        limits = get_tenant_job_limits(str(self.tenant.id))
        max_concurrency = limits["max_job_concurrency"]

        running_key = f"job:tenant:{self.tenant.id}:running"
        cache.set(running_key, max_concurrency, timeout=300)  # Set to limit

        business_rules = TransformationBusinessRules(tenant_id=str(self.tenant.id))

        with self.assertRaises(ResourceQuotaExceededError):
            business_rules.validate_resource_quota(pipeline, raise_on_error=True)

        # Cleanup
        cache.delete(running_key)

    def test_validate_pipeline_execution_permission_success(self):
        """Test pipeline execution permission validation with allowed access"""
        from hub.apps.governance.models import AccessPolicy

        # Create ALLOW policy for pipeline execution
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Pipeline Execution",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            priority=100,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        result = business_rules.validate_pipeline_execution_permission(
            pipeline, raise_on_error=False
        )

        self.assertTrue(result.is_valid)

    def test_validate_pipeline_execution_permission_missing_user_id(self):
        """Test pipeline execution permission validation fails without user_id"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(tenant_id=str(self.tenant.id))

        result = business_rules.validate_pipeline_execution_permission(
            pipeline, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertIn("user_id is required", result.errors[0])

    def test_validate_pipeline_execution_permission_with_assets(self):
        """Test pipeline execution permission validation with source and target assets"""
        from hub.apps.governance.models import AccessPolicy

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Create policies for assets
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Source Asset Read",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            priority=100,
            asset=self.asset,
        )

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow Target Asset Write",
            conditions={"user": {"tenant_id": str(self.tenant.id)}},
            effect="ALLOW",
            priority=100,
            asset=self.asset,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        result = business_rules.validate_pipeline_execution_permission(
            pipeline, source_asset=self.asset, target_asset=self.asset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)

    def test_validate_resource_quota_with_governance_service_integration(self):
        """Test resource quota validation integrates with GovernanceService"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        result = business_rules.validate_resource_quota(
            pipeline, source_asset=None, is_preview=False, raise_on_error=False
        )

        # Should have quota checks details
        self.assertIn("quota_checks", result.details)
        quota_checks = result.details["quota_checks"]

        # Should have estimated quotas
        self.assertIn("estimated_compute", quota_checks)
        self.assertIn("estimated_storage", quota_checks)
        self.assertIn("estimated_query", quota_checks)

        # Should have requested quota
        self.assertIn("requested_quota", quota_checks)

        # Compute quota should have CPU, memory, and compute_hours
        compute_quota = quota_checks["estimated_compute"]
        self.assertIn("cpu_cores", compute_quota)
        self.assertIn("memory_gb", compute_quota)
        self.assertIn("compute_hours", compute_quota)

        # Storage quota should have storage_gb
        storage_quota = quota_checks["estimated_storage"]
        self.assertIn("storage_gb", storage_quota)

        # Query quota should be 0 for non-preview operations
        query_quota = quota_checks["estimated_query"]
        self.assertEqual(query_quota["query_quota"], 0.0)

    def test_validate_resource_quota_compute_quota_estimation(self):
        """Test compute quota estimation from pipeline"""
        # Create pipeline with multiple complex nodes
        complex_pipeline_def = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": "filter1",
                    "type": "task",
                    "node_config": {"node_type": "FILTER", "filter_expression": "age > 18"},
                },
                {
                    "name": "join1",
                    "type": "task",
                    "node_config": {"node_type": "JOIN", "join_keys": ["id"], "join_type": "INNER"},
                },
                {
                    "name": "aggregate1",
                    "type": "task",
                    "node_config": {
                        "node_type": "AGGREGATE",
                        "group_by": ["category"],
                        "aggregation_functions": {"sum": "amount"},
                    },
                },
                {
                    "name": "transform1",
                    "type": "task",
                    "node_config": {
                        "node_type": "TRANSFORM",
                        "transform_expression": "amount * 1.1",
                    },
                },
                {"name": "output1", "type": "task", "node_config": {"node_type": "OUTPUT"}},
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Complex Pipeline",
            pipeline_definition=complex_pipeline_def,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Test compute quota estimation
        compute_quota = business_rules._estimate_compute_quota(pipeline)

        self.assertIn("cpu_cores", compute_quota)
        self.assertIn("memory_gb", compute_quota)
        self.assertIn("compute_hours", compute_quota)

        # Should have higher CPU/memory for complex nodes
        self.assertGreater(compute_quota["cpu_cores"], 0)
        self.assertGreater(compute_quota["memory_gb"], 0)
        self.assertGreater(compute_quota["compute_hours"], 0)

    def test_validate_resource_quota_storage_quota_estimation(self):
        """Test storage quota estimation from pipeline"""
        # Create source asset with dataset
        source_asset = Asset.objects.create(
            tenant=self.tenant, key="source-asset", name="Source Asset", status=AssetStatus.ACTIVE
        )

        source_file = File.objects.create(
            tenant=self.tenant,
            name="source.csv",
            storage_path="test/source.csv",
            size=5 * 1024 * 1024,  # 5MB
            content_type="text/csv",
            status=FileStatus.ACTIVE,
        )

        source_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=source_asset,
            file=source_file,
            version=1,
            format="CSV",
            row_count=1000,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                ]
            },
        )

        # Set dataset size_bytes
        source_dataset.size_bytes = 5 * 1024 * 1024
        source_dataset.save()

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Test storage quota estimation
        storage_quota = business_rules._estimate_storage_quota(pipeline, source_asset)

        self.assertIn("storage_gb", storage_quota)
        self.assertGreater(storage_quota["storage_gb"], 0)

    def test_validate_resource_quota_query_quota_estimation_preview(self):
        """Test query quota estimation for preview operations"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Test query quota estimation for preview
        query_quota_preview = business_rules._estimate_query_quota(pipeline, is_preview=True)
        self.assertIn("query_quota", query_quota_preview)
        self.assertGreater(query_quota_preview["query_quota"], 0)

        # Test query quota estimation for non-preview
        query_quota_non_preview = business_rules._estimate_query_quota(pipeline, is_preview=False)
        self.assertIn("query_quota", query_quota_non_preview)
        self.assertEqual(query_quota_non_preview["query_quota"], 0.0)

    def test_validate_resource_quota_with_preview_operation(self):
        """Test resource quota validation for preview operations includes query quota"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        result = business_rules.validate_resource_quota(
            pipeline, source_asset=None, is_preview=True, raise_on_error=False
        )

        quota_checks = result.details["quota_checks"]
        query_quota = quota_checks["estimated_query"]
        self.assertGreater(query_quota["query_quota"], 0)

        # Requested quota should include query_quota for preview operations
        requested_quota = quota_checks.get("requested_quota", {})
        if quota_checks.get("governance_validation_passed"):
            self.assertIn("query_quota", requested_quota)

    def test_validate_resource_quota_storage_quota_metadata_present(self):
        """Test resource quota validation includes storage quota metadata"""

        # Create a pipeline
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        # Create source asset with large dataset
        source_asset = Asset.objects.create(
            tenant=self.tenant, key="large-asset", name="Large Asset", status=AssetStatus.ACTIVE
        )

        source_file = File.objects.create(
            tenant=self.tenant,
            name="large.csv",
            storage_path="test/large.csv",
            size=100 * 1024 * 1024 * 1024,  # 100GB
            content_type="text/csv",
            status=FileStatus.ACTIVE,
        )

        source_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=source_asset,
            file=source_file,
            version=1,
            format="CSV",
            row_count=10000000,
            schema_json={"fields": [{"name": "id", "data_type": "integer"}]},
        )

        source_dataset.size_bytes = 100 * 1024 * 1024 * 1024
        source_dataset.save()

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Mock GovernanceService to raise ValidationError for storage
        # Since we can't mock, we'll test the error handling path
        # by ensuring the method handles GovernanceService errors gracefully
        result = business_rules.validate_resource_quota(
            pipeline, source_asset=source_asset, is_preview=False, raise_on_error=False
        )

        # Should have attempted governance validation
        quota_checks = result.details["quota_checks"]
        self.assertIn("estimated_storage", quota_checks)
        # If governance validation fails, should have error or warning
        if not result.is_valid:
            self.assertGreater(len(result.errors), 0)

    def test_validate_resource_quota_compute_quota_metadata_present(self):
        """Test resource quota validation includes compute quota metadata"""
        # Create a complex pipeline that requires significant compute
        complex_pipeline_def = {
            "version": "1.0.0",
            "steps": [
                {
                    "name": f"join{i}",
                    "type": "task",
                    "node_config": {"node_type": "JOIN", "join_keys": ["id"], "join_type": "INNER"},
                }
                for i in range(20)  # 20 join operations
            ],
        }

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Complex Pipeline",
            pipeline_definition=complex_pipeline_def,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Test that compute quota is estimated correctly
        compute_quota = business_rules._estimate_compute_quota(pipeline)
        self.assertGreater(compute_quota["cpu_cores"], 0)
        self.assertGreater(compute_quota["memory_gb"], 0)
        self.assertGreater(compute_quota["compute_hours"], 0)

        # Validate quota (should pass if GovernanceService allows it)
        result = business_rules.validate_resource_quota(
            pipeline, source_asset=None, is_preview=False, raise_on_error=False
        )

        quota_checks = result.details["quota_checks"]
        self.assertIn("estimated_compute", quota_checks)
        self.assertGreater(quota_checks["estimated_compute"]["cpu_cores"], 0)

    def test_validate_resource_quota_tenant_level_validation(self):
        """Test tenant-level quota validation via GovernanceService"""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        result = business_rules.validate_resource_quota(
            pipeline, source_asset=None, is_preview=False, raise_on_error=False
        )

        quota_checks = result.details["quota_checks"]

        # Should have attempted tenant-level validation
        # If governance service is available, should have validation result
        if "governance_validation_passed" in quota_checks:
            # Should have either passed or failed with clear error
            validation_passed = quota_checks.get("governance_validation_passed")
            if validation_passed is False:
                self.assertIn("governance_validation_error", quota_checks)
            elif validation_passed is True:
                self.assertIn("validated_quota", quota_checks)
                self.assertIn("tenant_limits_check_passed", quota_checks)

    def test_validate_resource_quota_integration_with_governance_service(self):
        """Test full integration with GovernanceService for quota validation"""

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )

        business_rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Validate quota - should integrate with GovernanceService
        result = business_rules.validate_resource_quota(
            pipeline, source_asset=None, is_preview=False, raise_on_error=False
        )

        quota_checks = result.details["quota_checks"]

        # Should have requested quota
        self.assertIn("requested_quota", quota_checks)
        requested_quota = quota_checks["requested_quota"]
        self.assertIn("storage_gb", requested_quota)
        self.assertIn("compute_hours", requested_quota)

        # Should have attempted governance validation
        # If GovernanceService is available and working, should have validation result
        if "governance_validation_passed" in quota_checks:
            validation_passed = quota_checks["governance_validation_passed"]
            if validation_passed is True:
                # Should have validated quota
                self.assertIn("validated_quota", quota_checks)
                self.assertIn("tenant_limits_check_passed", quota_checks)
                self.assertTrue(quota_checks["tenant_limits_check_passed"])
            elif validation_passed is False:
                # Should have error details
                self.assertIn("governance_validation_error", quota_checks)
                self.assertIn("quota_exceeded", quota_checks)
                self.assertTrue(quota_checks["quota_exceeded"])
