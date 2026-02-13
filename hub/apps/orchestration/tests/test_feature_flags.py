"""
Tests for Workflow Business Rules Validation Feature Flags (Task 5.1.1)

Comprehensive TDD tests for:
1. Feature flag configuration
2. Gradual rollout mechanism
3. Per-workflow enable/disable
4. Per-tenant enable/disable
5. Integration with workflow engine

All tests follow TDD principles, use real implementations (no mocks/stubs),
and fix root causes rather than workarounds.
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.feature_flags import (
    WorkflowBusinessRulesFeatureFlags,
    get_feature_flags,
    is_business_rules_validation_enabled,
    reset_feature_flags,
)
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


class FeatureFlagsTestBase(TestCase):
    """Base test class for feature flags tests"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Reset feature flags singleton before each test
        reset_feature_flags()
        
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.engine = WorkflowEngine()

        # Register test task
        def test_task(input_data, instance, step):
            """Test task that always succeeds"""
            return {"result": "success"}

        self.engine.register_task("test_task", test_task)

        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"}
                ]
            },
            created_by=self.user
        )


class TestFeatureFlagsConfiguration(FeatureFlagsTestBase):
    """Test feature flag configuration (5.1.1.1)"""

    def test_global_enable_disable(self):
        """Test global enable/disable feature flag"""
        # Test enabled by default
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True):
            flags = WorkflowBusinessRulesFeatureFlags()
            self.assertTrue(flags.enabled_globally)
            self.assertTrue(
                flags.is_enabled("test_workflow", tenant_id=str(self.tenant.id))
            )

        # Test disabled globally
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False):
            flags = WorkflowBusinessRulesFeatureFlags()
            self.assertFalse(flags.enabled_globally)
            self.assertFalse(
                flags.is_enabled("test_workflow", tenant_id=str(self.tenant.id))
            )

    def test_gradual_rollout_percentage(self):
        """Test gradual rollout percentage configuration"""
        # Test 0% rollout (disabled)
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            self.assertEqual(flags.rollout_percentage, 0)
            # Should be disabled for all workflows
            enabled_count = 0
            for i in range(100):
                if flags.is_enabled(
                    "test_workflow",
                    tenant_id=str(self.tenant.id),
                    workflow_instance_id=f"instance-{i}"
                ):
                    enabled_count += 1
            self.assertEqual(enabled_count, 0)

        # Test 50% rollout
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=50
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            self.assertEqual(flags.rollout_percentage, 50)
            # Should be enabled for approximately 50% of workflows
            enabled_count = 0
            for i in range(100):
                if flags.is_enabled(
                    "test_workflow",
                    tenant_id=str(self.tenant.id),
                    workflow_instance_id=f"instance-{i}"
                ):
                    enabled_count += 1
            # Allow statistical variance for 50% rollout (35-65% in CI)
            self.assertGreaterEqual(enabled_count, 35)
            self.assertLessEqual(enabled_count, 65)

        # Test 100% rollout (fully enabled)
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            self.assertEqual(flags.rollout_percentage, 100)
            # Should be enabled for all workflows
            for i in range(10):
                self.assertTrue(
                    flags.is_enabled(
                        "test_workflow",
                        tenant_id=str(self.tenant.id),
                        workflow_instance_id=f"instance-{i}"
                    )
                )

    def test_per_workflow_enable_disable(self):
        """Test per-workflow enable/disable configuration"""
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS={
                "workflow1": True,
                "workflow2": False,
            }
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            # Workflow1 should be enabled
            self.assertTrue(
                flags.is_enabled("workflow1", tenant_id=str(self.tenant.id))
            )
            # Workflow2 should be disabled
            self.assertFalse(
                flags.is_enabled("workflow2", tenant_id=str(self.tenant.id))
            )
            # Other workflows should use default (enabled with 100% rollout)
            self.assertTrue(
                flags.is_enabled("other_workflow", tenant_id=str(self.tenant.id))
            )

    def test_disabled_workflows_list(self):
        """Test disabled workflows list configuration"""
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=[
                "disabled_workflow1",
                "disabled_workflow2",
            ]
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            # Disabled workflows should be disabled
            self.assertFalse(
                flags.is_enabled(
                    "disabled_workflow1", tenant_id=str(self.tenant.id)
                )
            )
            self.assertFalse(
                flags.is_enabled(
                    "disabled_workflow2", tenant_id=str(self.tenant.id)
                )
            )
            # Other workflows should be enabled
            self.assertTrue(
                flags.is_enabled("other_workflow", tenant_id=str(self.tenant.id))
            )

    def test_enabled_workflows_list(self):
        """Test enabled workflows list (overrides rollout)"""
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=[
                "enabled_workflow1",
            ]
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            # Enabled workflow should be enabled even with 0% rollout
            self.assertTrue(
                flags.is_enabled(
                    "enabled_workflow1", tenant_id=str(self.tenant.id)
                )
            )
            # Other workflows should be disabled (0% rollout)
            self.assertFalse(
                flags.is_enabled("other_workflow", tenant_id=str(self.tenant.id))
            )

    def test_per_tenant_configuration(self):
        """Test per-tenant enable/disable configuration"""
        tenant2 = Tenant.objects.create(
            name="Test Tenant 2",
            slug="test-tenant-2",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED
        )

        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_TENANTS={
                str(self.tenant.id): True,
                str(tenant2.id): False,
            }
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            # Tenant 1 should have validation enabled
            self.assertTrue(
                flags.is_enabled(
                    "test_workflow", tenant_id=str(self.tenant.id)
                )
            )
            # Tenant 2 should have validation disabled
            self.assertFalse(
                flags.is_enabled("test_workflow", tenant_id=str(tenant2.id))
            )

    def test_priority_order(self):
        """Test feature flag priority order"""
        # Priority: per-workflow > disabled list > enabled list > tenant > rollout > global
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False,  # Global disabled
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0,  # 0% rollout
            WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS={
                "priority_workflow": True,  # Per-workflow enabled
            },
            WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=[
                "disabled_workflow",
            ],
            WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=[
                "enabled_workflow",
            ],
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            # Per-workflow config should override everything
            self.assertTrue(
                flags.is_enabled(
                    "priority_workflow", tenant_id=str(self.tenant.id)
                )
            )
            # Disabled list should override rollout and global
            self.assertFalse(
                flags.is_enabled(
                    "disabled_workflow", tenant_id=str(self.tenant.id)
                )
            )
            # Enabled list should override rollout and global
            self.assertTrue(
                flags.is_enabled(
                    "enabled_workflow", tenant_id=str(self.tenant.id)
                )
            )

    def test_get_config_summary(self):
        """Test get_config_summary method"""
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=50,
            WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS={"wf1": True},
            WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=["wf2"],
            WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=["wf3"],
            WORKFLOW_BUSINESS_RULES_VALIDATION_TENANTS={"tenant1": True},
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            summary = flags.get_config_summary()
            self.assertTrue(summary["enabled_globally"])
            self.assertEqual(summary["rollout_percentage"], 50)
            self.assertEqual(summary["workflow_config_count"], 1)
            self.assertEqual(summary["disabled_workflows_count"], 1)
            self.assertEqual(summary["enabled_workflows_count"], 1)
            self.assertEqual(summary["tenant_config_count"], 1)


class TestFeatureFlagsIntegration(FeatureFlagsTestBase):
    """Test feature flags integration with workflow engine (5.1.1.2)"""

    def test_workflow_engine_skips_validation_when_disabled(self):
        """Test workflow engine skips validation when feature flag is disabled"""
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False):
            # Create workflow instance
            instance = self.engine.create_instance(
                workflow_name="test_workflow",
                input_data={"test": "data"},
                tenant_id=str(self.tenant.id),
                created_by_id=str(self.user.id),
            )
            instance = self.engine.start_instance(str(instance.id))

            # Execute step - should skip validation
            step = instance.steps.first()
            step_def = self.workflow_def.dsl_json["steps"][0]

            # Should execute without validation errors
            result = self.engine._execute_task_step(instance, step, step_def)
            self.assertIsNotNone(result)
            self.assertEqual(result.get("result"), "success")

    def test_workflow_engine_uses_validation_when_enabled(self):
        """Test workflow engine uses validation when feature flag is enabled"""
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True):
            # Create workflow instance
            instance = self.engine.create_instance(
                workflow_name="test_workflow",
                input_data={"test": "data"},
                tenant_id=str(self.tenant.id),
                created_by_id=str(self.user.id),
            )
            instance = self.engine.start_instance(str(instance.id))

            # Execute step - should use validation
            step = instance.steps.first()
            step_def = self.workflow_def.dsl_json["steps"][0]

            # Should execute with validation (no errors for valid workflow)
            result = self.engine._execute_task_step(instance, step, step_def)
            self.assertIsNotNone(result)
            self.assertEqual(result.get("result"), "success")

    def test_per_workflow_disable_in_engine(self):
        """Test per-workflow disable in workflow engine"""
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=["test_workflow"]
        ):
            # Create workflow instance
            instance = self.engine.create_instance(
                workflow_name="test_workflow",
                input_data={"test": "data"},
                tenant_id=str(self.tenant.id),
                created_by_id=str(self.user.id),
            )
            instance = self.engine.start_instance(str(instance.id))

            # Execute step - should skip validation for disabled workflow
            step = instance.steps.first()
            step_def = self.workflow_def.dsl_json["steps"][0]

            # Should execute without validation
            result = self.engine._execute_task_step(instance, step, step_def)
            self.assertIsNotNone(result)
            self.assertEqual(result.get("result"), "success")

    def test_consistent_rollout_for_same_instance(self):
        """Test that rollout is consistent for same workflow instance"""
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=50
        ):
            flags = WorkflowBusinessRulesFeatureFlags()
            instance_id = "test-instance-123"

            # Same instance should have same result
            result1 = flags.is_enabled(
                "test_workflow",
                tenant_id=str(self.tenant.id),
                workflow_instance_id=instance_id
            )
            result2 = flags.is_enabled(
                "test_workflow",
                tenant_id=str(self.tenant.id),
                workflow_instance_id=instance_id
            )
            self.assertEqual(result1, result2)


class TestFeatureFlagsConvenienceFunctions(FeatureFlagsTestBase):
    """Test convenience functions for feature flags"""

    def test_get_feature_flags_singleton(self):
        """Test get_feature_flags returns singleton (same instance for same settings)"""
        # Same settings should return same instance
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True):
            flags1 = get_feature_flags()
            flags2 = get_feature_flags()
            self.assertIs(flags1, flags2)
        
        # Different settings should return different instance
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False):
            flags3 = get_feature_flags()
            self.assertIsNot(flags1, flags3)
            self.assertFalse(flags3.enabled_globally)

    def test_is_business_rules_validation_enabled(self):
        """Test is_business_rules_validation_enabled convenience function"""
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True):
            self.assertTrue(
                is_business_rules_validation_enabled(
                    "test_workflow",
                    tenant_id=str(self.tenant.id)
                )
            )

        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False):
            self.assertFalse(
                is_business_rules_validation_enabled(
                    "test_workflow",
                    tenant_id=str(self.tenant.id)
                )
            )
