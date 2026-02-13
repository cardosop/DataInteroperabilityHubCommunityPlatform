"""
Tests for Workflow Business Rules Validation Gradual Rollout (Task 5.2).

Verifies:
- 5.2.1 Enable for test workflows only
- 5.2.2 Enable for production workflows incrementally
- 5.2.3 Full rollout (all workflows)

Uses real feature flags and override_settings; no mocks/stubs.
"""
from django.test import TestCase
from django.test.utils import override_settings

from hub.apps.orchestration.feature_flags import (
    get_feature_flags,
    is_business_rules_validation_enabled,
    reset_feature_flags,
)


class GradualRolloutTestBase(TestCase):
    """Base for gradual rollout tests."""

    def setUp(self):
        super().setUp()
        reset_feature_flags()


class TestPhase1TestWorkflowsOnly(GradualRolloutTestBase):
    """5.2.1: Enable validation only for test/non-critical workflows."""

    @override_settings(
        ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=[
            "model_training",
            "model_inference",
            "api_key_management",
            "data_quality_check",
            "virtualization_query_execution",
        ],
        WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=[],
        WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS={},
    )
    def test_only_test_workflows_have_validation_enabled(self):
        """Test workflows have validation enabled; critical do not."""
        reset_feature_flags()
        test_workflows = [
            "model_training",
            "model_inference",
            "api_key_management",
            "data_quality_check",
            "virtualization_query_execution",
        ]
        critical_workflows = [
            "product_creation",
            "contract_creation",
            "asset_creation",
        ]
        for name in test_workflows:
            self.assertTrue(
                is_business_rules_validation_enabled(name),
                f"Test workflow {name} should have validation enabled",
            )
        for name in critical_workflows:
            self.assertFalse(
                is_business_rules_validation_enabled(name),
                f"Critical {name} should not have validation in phase 1",
            )

    @override_settings(
        ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=[
            "model_training",
            "data_quality_check",
        ],
    )
    def test_phase1_verify_behavior_via_feature_flags(self):
        """Verify behavior: only enabled list gets validation."""
        reset_feature_flags()
        self.assertTrue(
            is_business_rules_validation_enabled("model_training")
        )
        self.assertTrue(
            is_business_rules_validation_enabled("data_quality_check")
        )
        self.assertFalse(
            is_business_rules_validation_enabled("product_creation")
        )
        self.assertFalse(
            is_business_rules_validation_enabled("contract_creation")
        )


class TestPhase2IncrementalProduction(GradualRolloutTestBase):
    """5.2.2: Enable for production workflows incrementally."""

    @override_settings(
        ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=[
            "model_training",
            "data_quality_check",
            "product_creation",
            "contract_creation",
        ],
    )
    def test_incremental_critical_added_to_enabled_list(self):
        """Adding critical workflows to enabled list enables validation."""
        reset_feature_flags()
        self.assertTrue(
            is_business_rules_validation_enabled("product_creation"),
            "product_creation should have validation after incremental add",
        )
        self.assertTrue(
            is_business_rules_validation_enabled("contract_creation"),
            "contract_creation should have validation after incremental add",
        )
        self.assertFalse(
            is_business_rules_validation_enabled("asset_creation"),
            "asset_creation not in list yet should be disabled",
        )

    @override_settings(
        ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0,
        WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS={
            "product_creation": True,
            "contract_creation": True,
        },
        WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=[
            "model_training",
        ],
    )
    def test_incremental_via_per_workflow_config(self):
        """Per-workflow config can enable critical workflows incrementally."""
        reset_feature_flags()
        self.assertTrue(
            is_business_rules_validation_enabled("product_creation")
        )
        self.assertTrue(
            is_business_rules_validation_enabled("contract_creation")
        )
        self.assertTrue(
            is_business_rules_validation_enabled("model_training")
        )
        self.assertFalse(
            is_business_rules_validation_enabled("asset_creation")
        )


class TestPhase3FullRollout(GradualRolloutTestBase):
    """5.2.3: Full rollout — enable for all workflows."""

    @override_settings(
        ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=[],
        WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=[],
        WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS={},
    )
    def test_full_rollout_all_workflows_enabled(self):
        """With 100% rollout and global True, all workflows have validation."""
        reset_feature_flags()
        workflows = [
            "product_creation",
            "contract_creation",
            "asset_creation",
            "model_training",
            "data_quality_check",
        ]
        for name in workflows:
            self.assertTrue(
                is_business_rules_validation_enabled(name),
                f"Full rollout: {name} should have validation enabled",
            )

    @override_settings(
        ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100,
        WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=["model_inference"],
    )
    def test_full_rollout_with_one_disabled(self):
        """Full rollout with one workflow explicitly disabled."""
        reset_feature_flags()
        self.assertTrue(
            is_business_rules_validation_enabled("product_creation")
        )
        self.assertFalse(
            is_business_rules_validation_enabled("model_inference"),
            "Explicitly disabled workflow must remain disabled",
        )


class TestRolloutConfigSummary(GradualRolloutTestBase):
    """Verify config summary reflects rollout state."""

    @override_settings(
        ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=50,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=["product_creation"],
    )
    def test_config_summary_has_rollout_fields(self):
        """get_config_summary includes rollout-related fields."""
        reset_feature_flags()
        flags = get_feature_flags()
        summary = flags.get_config_summary()
        self.assertTrue(summary["enabled_globally"])
        self.assertEqual(summary["rollout_percentage"], 50)
        self.assertEqual(summary["enabled_workflows_count"], 1)
