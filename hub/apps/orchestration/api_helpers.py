"""
Helpers for Workflows API: shared registry and engine with all workflows registered.

Used by views to list workflows, get by name, and trigger. Lazy init on first use.
Registration matches process_workflows command.
"""

import logging
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from hub.apps.orchestration.registry import WorkflowRegistry
    from hub.apps.orchestration.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)

_engine: Optional["WorkflowEngine"] = None
_registry: Optional["WorkflowRegistry"] = None


def _get_workflow_classes() -> list:
    """Return workflow classes that support register_workflow and register_tasks."""
    from hub.apps.orchestration.workflows import (
        AccessRequestWorkflow,
        AssetCreationWorkflow,
        ComplianceReportingWorkflow,
        ContractCreationWorkflow,
        DataQualityCheckWorkflow,
        DatasetCreationWorkflow,
        MarketplacePublicationWorkflow,
        MarketplaceSyncWorkflow,
        ProductCreationWorkflow,
        ScheduledIngestionWorkflow,
        VersionCreationWorkflow,
        VirtualizationWorkflow,
    )

    return [
        ContractCreationWorkflow,
        ScheduledIngestionWorkflow,
        AccessRequestWorkflow,
        DataQualityCheckWorkflow,
        ComplianceReportingWorkflow,
        AssetCreationWorkflow,
        DatasetCreationWorkflow,
        VersionCreationWorkflow,
        MarketplacePublicationWorkflow,
        ProductCreationWorkflow,
        MarketplaceSyncWorkflow,
        VirtualizationWorkflow,
    ]


def get_workflow_registry():  # -> WorkflowRegistry
    """Return shared registry with all workflow definitions registered (DB)."""
    global _registry
    if _registry is None:
        from hub.apps.orchestration.registry import WorkflowRegistry

        _registry = WorkflowRegistry()
        for wf_class in _get_workflow_classes():
            if hasattr(wf_class, "register_workflow"):
                wf_class.register_workflow(_registry)
        logger.debug("Initialized WorkflowRegistry for API with all workflow definitions")
    return _registry


def get_workflow_engine():  # -> WorkflowEngine
    """Return shared engine with all workflow tasks registered."""
    global _engine
    if _engine is None:
        from hub.apps.orchestration.workflow_engine import WorkflowEngine

        _engine = WorkflowEngine()
        for wf_class in _get_workflow_classes():
            if hasattr(wf_class, "register_tasks"):
                wf_class.register_tasks(_engine)
        logger.debug("Initialized WorkflowEngine for API with all workflow tasks")
    return _engine


def get_registry_and_engine() -> Tuple["WorkflowRegistry", "WorkflowEngine"]:
    """Return (registry, engine) both initialized."""
    return get_workflow_registry(), get_workflow_engine()
