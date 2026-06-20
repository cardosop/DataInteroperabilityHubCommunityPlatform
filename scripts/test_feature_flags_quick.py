#!/usr/bin/env python
"""
Quick test script for feature flags (without Django test framework overhead)
"""

import os
import sys

import django

# Setup Django
sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

from django.test.utils import override_settings

from hub.apps.orchestration.feature_flags import (
    WorkflowBusinessRulesFeatureFlags,
    get_feature_flags,
    is_business_rules_validation_enabled,
    reset_feature_flags,
)


def test_priority_order():
    """Test priority order"""
    print("Testing priority order...")
    with override_settings(
        ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False,
        WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0,
        WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS={
            "priority_workflow": True,
        },
        WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=[
            "disabled_workflow",
        ],
        WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=[
            "enabled_workflow",
        ],
    ):
        reset_feature_flags()
        flags = WorkflowBusinessRulesFeatureFlags()

        # Per-workflow should override global
        result1 = flags.is_enabled("priority_workflow", tenant_id="test-tenant")
        print(f"  priority_workflow: {result1} (expected: True)")
        assert result1 == True, f"Expected True, got {result1}"

        # Disabled list should override rollout and global
        result2 = flags.is_enabled("disabled_workflow", tenant_id="test-tenant")
        print(f"  disabled_workflow: {result2} (expected: False)")
        assert result2 == False, f"Expected False, got {result2}"

        # Enabled list should override rollout and global
        result3 = flags.is_enabled("enabled_workflow", tenant_id="test-tenant")
        print(f"  enabled_workflow: {result3} (expected: True)")
        assert result3 == True, f"Expected True, got {result3}"

    print("✅ Priority order test passed!")


def test_singleton():
    """Test singleton behavior"""
    print("Testing singleton...")
    reset_feature_flags()

    with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True):
        flags1 = get_feature_flags()
        flags2 = get_feature_flags()
        assert flags1 is flags2, "Same settings should return same instance"
        print("  Same settings -> same instance: ✅")

    with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False):
        flags3 = get_feature_flags()
        assert flags3 is not flags1, "Different settings should return different instance"
        assert flags3.enabled_globally == False, "Should be disabled"
        print("  Different settings -> different instance: ✅")

    print("✅ Singleton test passed!")


def test_convenience_function():
    """Test convenience function"""
    print("Testing convenience function...")
    reset_feature_flags()

    with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True):
        result1 = is_business_rules_validation_enabled("test_workflow", tenant_id="test-tenant")
        assert result1 == True, f"Expected True, got {result1}"
        print("  Enabled: ✅")

    with override_settings(ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=False):
        result2 = is_business_rules_validation_enabled("test_workflow", tenant_id="test-tenant")
        assert result2 == False, f"Expected False, got {result2}"
        print("  Disabled: ✅")

    print("✅ Convenience function test passed!")


if __name__ == "__main__":
    try:
        test_priority_order()
        test_singleton()
        test_convenience_function()
        print("\n✅ All quick tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
