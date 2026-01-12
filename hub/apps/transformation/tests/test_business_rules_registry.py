"""
Unit tests for TransformationBusinessRules registry integration.

Tests rule registration and execution through the business rules registry.
"""
import uuid
from django.test import TestCase

from hub.apps.transformation.business_rules import (
    TransformationBusinessRules,
    TransformationRuleExecutionContext,
)
from hub.apps.core.business_rules.base import ValidationResult, RuleExecutionContext
from hub.apps.core.business_rules.registry import get_registry
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


class TransformationBusinessRulesRegistryTest(TestCase):
    """Test cases for TransformationBusinessRules registry integration."""

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

        # Create valid pipeline definition
        self.valid_pipeline_definition = {
            "version": "1.0.0",
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
                    "name": "output_step",
                    "type": "task",
                    "node_config": {
                        "node_type": "output"
                    }
                }
            ]
        }

        # Create test asset with dataset
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
            format="CSV",
            row_count=100,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "age", "data_type": "integer"}
                ]
            }
        )

    def test_rule_registration(self):
        """Test that TransformationBusinessRules is registered in the registry."""
        registry = get_registry()
        rule_metadata = registry.get_rule("transformation_pipeline_validation")

        self.assertIsNotNone(rule_metadata)
        self.assertEqual(rule_metadata.rule_name, "transformation_pipeline_validation")
        self.assertEqual(rule_metadata.rule_class, TransformationBusinessRules)
        self.assertIn("transformation", rule_metadata.tags)
        self.assertIn("pipeline", rule_metadata.tags)
        self.assertIn("validation", rule_metadata.tags)

    def test_rule_initialization(self):
        """Test TransformationBusinessRules initialization."""
        rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))
        self.assertEqual(rules.get_rule_name(), "TransformationBusinessRules")

    def test_execute_with_transformation_context(self):
        """Test execute method with TransformationRuleExecutionContext."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        context = TransformationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            pipeline=pipeline,
            source_asset=self.asset
        )

        result = rules.execute(context, validation_type='structure')

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_execute_with_standard_context(self):
        """Test execute method with standard RuleExecutionContext."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource=pipeline,
            metadata={
                'source_asset': self.asset
            }
        )

        result = rules.execute(context, validation_type='structure')

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_execute_with_kwargs(self):
        """Test execute method with pipeline and assets in kwargs."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = rules.execute(
            context,
            pipeline=pipeline,
            source_asset=self.asset,
            validation_type='structure'
        )

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_execute_missing_pipeline(self):
        """Test execute method with missing pipeline."""
        rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        result = rules.execute(context)

        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertIn("Pipeline is required", result.errors[0])

    def test_execute_all_validations(self):
        """Test execute method with all validations."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        rules = TransformationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        context = TransformationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            pipeline=pipeline,
            source_asset=self.asset
        )

        result = rules.execute(context, validation_type='all')

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("validation_results", result.details)
        self.assertIn("structure", result.details["validation_results"])
        self.assertIn("node_compatibility", result.details["validation_results"])

    def test_execute_through_registry(self):
        """Test executing rule through the registry."""
        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE
        )

        registry = get_registry()
        context = TransformationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            pipeline=pipeline,
            source_asset=self.asset
        )

        # Execute through registry - kwargs are passed to rule.execute()
        results = registry.execute_rules(
            rule_names=["transformation_pipeline_validation"],
            context=context,
            pipeline=pipeline,
            source_asset=self.asset,
            validation_type='structure'
        )

        self.assertIn("transformation_pipeline_validation", results)
        result = results["transformation_pipeline_validation"]
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

