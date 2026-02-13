"""
Feature Flags for Workflow Business Rules Validation

Provides feature flag management for enabling/disabling business rules
validation in workflows with support for gradual rollout and per-workflow
configuration.
"""
import logging
from typing import Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class WorkflowBusinessRulesFeatureFlags:
    """
    Feature flags for workflow business rules validation.
    
    Supports:
    - Global enable/disable
    - Gradual rollout (percentage-based)
    - Per-workflow enable/disable
    - Per-tenant enable/disable (optional)
    """

    def __init__(self):
        """Initialize feature flags from settings."""
        # Global feature flag
        self.enabled_globally = getattr(
            settings,
            'ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION',
            True  # Default: enabled
        )

        # Gradual rollout percentage (0-100)
        self.rollout_percentage = getattr(
            settings,
            'WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE',
            100  # Default: 100% (full rollout)
        )

        # Per-workflow configuration
        # Format: {"workflow_name": True/False}
        self.workflow_config = getattr(
            settings,
            'WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS',
            {}  # Default: empty (use global/rollout settings)
        )

        # Disabled workflows (explicitly disabled)
        self.disabled_workflows = getattr(
            settings,
            'WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS',
            []  # Default: empty list
        )

        # Enabled workflows (explicitly enabled, overrides rollout)
        self.enabled_workflows = getattr(
            settings,
            'WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS',
            []  # Default: empty list
        )

        # Per-tenant configuration (optional)
        # Format: {"tenant_id": True/False}
        self.tenant_config = getattr(
            settings,
            'WORKFLOW_BUSINESS_RULES_VALIDATION_TENANTS',
            {}  # Default: empty (use global/rollout settings)
        )

    def is_enabled(
        self,
        workflow_name: str,
        tenant_id: Optional[str] = None,
        workflow_instance_id: Optional[str] = None
    ) -> bool:
        """
        Check if business rules validation is enabled for a workflow.
        
        Priority order:
        1. Per-workflow explicit enable/disable
        2. Per-tenant enable/disable (if tenant_id provided)
        3. Disabled workflows list
        4. Enabled workflows list (overrides rollout)
        5. Gradual rollout percentage
        6. Global enable/disable
        
        Args:
            workflow_name: Name of the workflow
            tenant_id: Optional tenant ID for tenant-specific configuration
            workflow_instance_id: Optional workflow instance ID for consistent rollout
            
        Returns:
            True if validation is enabled, False otherwise
        """
        # Priority order:
        # 1. Per-workflow explicit configuration (highest priority)
        # 2. Disabled workflows list
        # 3. Enabled workflows list (overrides rollout)
        # 4. Per-tenant configuration
        # 5. Gradual rollout percentage
        # 6. Global enable/disable (lowest priority)

        # 1. Check per-workflow explicit configuration (highest priority)
        if workflow_name in self.workflow_config:
            enabled = self.workflow_config[workflow_name]
            status = "enabled" if enabled else "disabled"
            logger.debug(
                f"Workflow business rules validation {status} "
                f"for workflow {workflow_name} (per-workflow config)",
                extra={
                    "workflow_name": workflow_name,
                    "tenant_id": tenant_id
                }
            )
            return enabled

        # 2. Check disabled workflows list
        if workflow_name in self.disabled_workflows:
            logger.debug(
                f"Workflow business rules validation disabled "
                f"for workflow {workflow_name} (disabled workflows list)",
                extra={
                    "workflow_name": workflow_name,
                    "tenant_id": tenant_id
                }
            )
            return False

        # 3. Check enabled workflows list (overrides rollout)
        if workflow_name in self.enabled_workflows:
            logger.debug(
                f"Workflow business rules validation enabled "
                f"for workflow {workflow_name} (enabled workflows list)",
                extra={
                    "workflow_name": workflow_name,
                    "tenant_id": tenant_id
                }
            )
            return True

        # 4. Check per-tenant configuration (if tenant_id provided)
        if tenant_id and tenant_id in self.tenant_config:
            enabled = self.tenant_config[tenant_id]
            status = "enabled" if enabled else "disabled"
            logger.debug(
                f"Workflow business rules validation {status} "
                f"for tenant {tenant_id} (per-tenant config)",
                extra={
                    "workflow_name": workflow_name,
                    "tenant_id": tenant_id
                }
            )
            return enabled

        # 5. Check gradual rollout percentage
        if self.rollout_percentage < 100:
            # Use workflow_instance_id for consistent rollout (if provided)
            # Otherwise use workflow_name hash
            if workflow_instance_id:
                rollout_key = workflow_instance_id
            else:
                rollout_key = workflow_name

            # Simple hash-based rollout (consistent for same key)
            hash_value = hash(rollout_key) % 100
            enabled = hash_value < self.rollout_percentage

            status = "enabled" if enabled else "disabled"
            logger.debug(
                f"Workflow business rules validation {status} "
                f"for workflow {workflow_name} "
                f"(rollout: {self.rollout_percentage}%, hash: {hash_value})",
                extra={
                    "workflow_name": workflow_name,
                    "tenant_id": tenant_id,
                    "rollout_percentage": self.rollout_percentage,
                    "hash_value": hash_value
                }
            )
            return bool(enabled)

        # 6. Check global enable/disable (lowest priority)
        if not self.enabled_globally:
            logger.debug(
                "Workflow business rules validation disabled globally",
                extra={
                    "workflow_name": workflow_name,
                    "tenant_id": tenant_id
                }
            )
            return False

        # 7. Default: enabled (global flag is True and rollout is 100%)
        logger.debug(
            "Workflow business rules validation enabled (default)",
            extra={
                "workflow_name": workflow_name,
                "tenant_id": tenant_id
            }
        )
        return True

    def get_config_summary(self) -> Dict[str, any]:  # noqa: ANN401
        """
        Get summary of current feature flag configuration.
        
        Returns:
            Dictionary with configuration summary
        """
        return {
            "enabled_globally": self.enabled_globally,
            "rollout_percentage": self.rollout_percentage,
            "workflow_config_count": len(self.workflow_config),
            "disabled_workflows_count": len(self.disabled_workflows),
            "enabled_workflows_count": len(self.enabled_workflows),
            "tenant_config_count": len(self.tenant_config),
        }


# Global instance (will be recreated when settings change)
_feature_flags = None
_feature_flags_settings_hash = None


def reset_feature_flags():
    """
    Reset feature flags singleton (useful for testing).
    
    This function should be called in test teardown or between test cases
    that change settings to ensure fresh instances.
    """
    global _feature_flags, _feature_flags_settings_hash
    _feature_flags = None
    _feature_flags_settings_hash = None


def _get_settings_hash() -> int:
    """Get hash of current settings for feature flags."""
    import json
    # Get settings values directly
    enabled_globally = getattr(
        settings, 'ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION', True
    )
    rollout_percentage = getattr(
        settings, 'WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE', 100
    )
    workflow_config = getattr(
        settings, 'WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS', {}
    )
    disabled_workflows = getattr(
        settings, 'WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS', []
    )
    enabled_workflows = getattr(
        settings, 'WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS', []
    )
    tenant_config = getattr(
        settings, 'WORKFLOW_BUSINESS_RULES_VALIDATION_TENANTS', {}
    )
    
    # Create hash from all settings values
    # Convert dicts/lists to sorted JSON strings for consistent hashing
    settings_tuple = (
        enabled_globally,
        rollout_percentage,
        json.dumps(workflow_config, sort_keys=True) if workflow_config else '{}',
        json.dumps(sorted(disabled_workflows), sort_keys=True) if disabled_workflows else '[]',
        json.dumps(sorted(enabled_workflows), sort_keys=True) if enabled_workflows else '[]',
        json.dumps(tenant_config, sort_keys=True) if tenant_config else '{}',
    )
    return hash(settings_tuple)


def get_feature_flags() -> WorkflowBusinessRulesFeatureFlags:
    """
    Get global feature flags instance (singleton with settings change detection).
    
    The singleton is recreated when settings change to ensure tests work correctly
    with override_settings.
    
    Returns:
        WorkflowBusinessRulesFeatureFlags instance
    """
    global _feature_flags, _feature_flags_settings_hash
    current_hash = _get_settings_hash()
    if _feature_flags is None or _feature_flags_settings_hash != current_hash:
        _feature_flags = WorkflowBusinessRulesFeatureFlags()
        _feature_flags_settings_hash = current_hash
    return _feature_flags


def is_business_rules_validation_enabled(
    workflow_name: str,
    tenant_id: Optional[str] = None,
    workflow_instance_id: Optional[str] = None
) -> bool:
    """
    Convenience function to check if business rules validation is enabled.
    
    Args:
        workflow_name: Name of the workflow
        tenant_id: Optional tenant ID
        workflow_instance_id: Optional workflow instance ID
        
    Returns:
        True if validation is enabled, False otherwise
    """
    return get_feature_flags().is_enabled(
        workflow_name=workflow_name,
        tenant_id=tenant_id,
        workflow_instance_id=workflow_instance_id
    )
