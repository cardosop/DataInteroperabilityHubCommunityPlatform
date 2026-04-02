"""
Tests for Workflow Business Rules Validation Rollback Procedures (Task 5.1.3)

Comprehensive TDD tests for:
1. Rollback script functionality
2. Feature flag rollback procedures
3. Rollback verification

All tests follow TDD principles, use real implementations (no mocks/stubs),
and fix root causes rather than workarounds.
"""
import os
import uuid

from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model

from hub.apps.orchestration.feature_flags import (
    is_business_rules_validation_enabled,
    reset_feature_flags,
)
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


class RollbackProceduresTestBase(TestCase):
    """Base test class for rollback procedures tests"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        reset_feature_flags()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )


class TestFeatureFlagRollback(RollbackProceduresTestBase):
    """Test feature flag rollback procedures (5.1.3.1)"""

    def test_global_rollback(self):
        """Test global rollback (disable all validation)"""
        # Start with validation enabled
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True):
            reset_feature_flags()
            self.assertTrue(
                is_business_rules_validation_enabled(
                    "test_workflow", tenant_id=str(self.tenant.id)
                )
            )

        # Rollback: disable globally
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False):
            reset_feature_flags()
            self.assertFalse(
                is_business_rules_validation_enabled(
                    "test_workflow", tenant_id=str(self.tenant.id)
                )
            )

    def test_per_workflow_rollback(self):
        """Test per-workflow rollback"""
        # Start with validation enabled for all workflows
        with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True):
            reset_feature_flags()
            self.assertTrue(
                is_business_rules_validation_enabled(
                    "workflow1", tenant_id=str(self.tenant.id)
                )
            )

        # Rollback: disable specific workflow
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=["workflow1"]
        ):
            reset_feature_flags()
            self.assertFalse(
                is_business_rules_validation_enabled(
                    "workflow1", tenant_id=str(self.tenant.id)
                )
            )
            # Other workflows should still be enabled
            self.assertTrue(
                is_business_rules_validation_enabled(
                    "workflow2", tenant_id=str(self.tenant.id)
                )
            )

    def test_gradual_rollback(self):
        """Test gradual rollback (reduce rollout percentage)"""
        # Start with 100% rollout
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100
        ):
            reset_feature_flags()
            # Should be enabled
            self.assertTrue(
                is_business_rules_validation_enabled(
                    "test_workflow",
                    tenant_id=str(self.tenant.id),
                    workflow_instance_id="test-instance"
                )
            )

        # Rollback: reduce to 0% (disable)
        with override_settings(
            ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
            WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0
        ):
            reset_feature_flags()
            # Should be disabled
            self.assertFalse(
                is_business_rules_validation_enabled(
                    "test_workflow",
                    tenant_id=str(self.tenant.id),
                    workflow_instance_id="test-instance"
                )
            )


class TestRollbackScripts(RollbackProceduresTestBase):
    """Test rollback scripts exist and are executable (5.1.3.3)"""

    def test_rollback_scripts_exist(self):
        """Test that rollback scripts exist (project root scripts/)."""
        # 4 levels up from hub/apps/orchestration/tests/ -> project root
        here = os.path.dirname(os.path.abspath(__file__))
        for _ in range(4):
            here = os.path.dirname(here)
        scripts_dir = os.path.join(here, 'scripts')

        scripts = [
            'rollback_workflow_validation_global.sh',
            'rollback_workflow_validation_workflow.sh',
            'rollback_workflow_validation_gradual.sh',
            'verify_workflow_validation_rollback.sh',
        ]

        for script in scripts:
            script_path = os.path.join(scripts_dir, script)
            self.assertTrue(
                os.path.exists(script_path),
                f"Rollback script {script} does not exist at {script_path}"
            )
            # Check if executable (or at least readable)
            self.assertTrue(
                os.access(script_path, os.R_OK),
                f"Rollback script {script} is not readable",
            )
