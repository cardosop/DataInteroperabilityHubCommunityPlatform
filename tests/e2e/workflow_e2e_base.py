"""
Workflow E2E Test Base and Helpers (Phase 6.1.1)

Extends E2ETestBase with workflow-specific infrastructure:
- Workflow instance creation helpers
- Workflow execution helpers with business rules validation
- Workflow state verification helpers
- Business rules validation result verification helpers

No mocks/stubs; uses real WorkflowEngine, WorkflowRegistry, and business rules.
"""

from typing import Any

from tests.e2e.conftest import E2ETestBase

# Lazy imports inside methods to avoid circular/optional Django deps
# and to allow this module to load when orchestration is available


def get_workflow_classes_for_e2e():
    """Return workflow classes that support register_workflow + register_tasks (for E2E)."""
    from hub.apps.orchestration.workflows import (
        AccessRequestWorkflow,
        APIKeyManagementWorkflow,
        AssetCreationWorkflow,
        ComplianceReportingWorkflow,
        ContractCreationWorkflow,
        DataMeshWorkflow,
        DataQualityCheckWorkflow,
        DatasetCreationWorkflow,
        MarketplacePublicationWorkflow,
        MarketplaceSyncWorkflow,
        ModelInferenceWorkflow,
        ModelTrainingWorkflow,
        ProductCreationWorkflow,
        ScheduledIngestionWorkflow,
        VersionCreationWorkflow,
        VirtualizationWorkflow,
    )

    return [
        ProductCreationWorkflow,
        ContractCreationWorkflow,
        AssetCreationWorkflow,
        DatasetCreationWorkflow,
        VersionCreationWorkflow,
        MarketplacePublicationWorkflow,
        MarketplaceSyncWorkflow,
        AccessRequestWorkflow,
        DataMeshWorkflow,
        DataQualityCheckWorkflow,
        ComplianceReportingWorkflow,
        ScheduledIngestionWorkflow,
        VirtualizationWorkflow,
        APIKeyManagementWorkflow,
        ModelTrainingWorkflow,
        ModelInferenceWorkflow,
    ]


def create_engine_with_all_workflows_and_tasks():
    """
    Create WorkflowEngine and WorkflowRegistry with all workflow definitions
    and tasks registered. Uses real implementations (no mocks).
    """
    from hub.apps.orchestration.registry import WorkflowRegistry
    from hub.apps.orchestration.workflow_engine import WorkflowEngine

    engine = WorkflowEngine()
    registry = WorkflowRegistry()
    for wf_class in get_workflow_classes_for_e2e():
        if hasattr(wf_class, "register_workflow"):
            wf_class.register_workflow(registry)
        if hasattr(wf_class, "register_tasks"):
            wf_class.register_tasks(engine)
    return engine, registry


class WorkflowE2ETestBase(E2ETestBase):
    """
    Base class for workflow E2E tests extending E2ETestBase.

    Provides:
    - Workflow engine and registry with workflow(s) registered
    - Helpers to create workflow instances, execute, and verify state
    - Helpers to verify business rules validation results and metrics

    Subclasses can set workflow_classes to a list of workflow classes to register
    only those (faster setUp, avoids registering unused workflows). If not set,
    all workflows from get_workflow_classes_for_e2e() are registered.
    """

    workflow_classes = None  # If set, register only these; else register all

    def setUp(self):
        """Set up E2E fixtures and workflow engine/registry."""
        super().setUp()
        if not hasattr(self, "tenant") or not hasattr(self, "user"):
            return
        from hub.apps.orchestration.registry import WorkflowRegistry
        from hub.apps.orchestration.workflow_engine import WorkflowEngine

        self._engine = WorkflowEngine()
        self._registry = WorkflowRegistry()
        classes = (
            self.workflow_classes
            if self.workflow_classes is not None
            else get_workflow_classes_for_e2e()
        )
        for wf_class in classes:
            if hasattr(wf_class, "register_workflow"):
                wf_class.register_workflow(self._registry)
            if hasattr(wf_class, "register_tasks"):
                wf_class.register_tasks(self._engine)
        self.workflow_engine = self._engine
        self.workflow_registry = self._registry

    # --- Workflow instance creation helpers ---

    def create_workflow_instance(
        self,
        workflow_name: str,
        input_data: dict[str, Any],
        tenant_id: str | None = None,
        created_by_id: str | None = None,
        workflow_version: str | None = None,
    ):
        """
        Create a workflow instance using the test engine.

        Returns:
            WorkflowInstance (DRAFT).
        """
        tenant_id = tenant_id or str(self.tenant.id)
        created_by_id = created_by_id or str(self.user.id)
        return self.workflow_engine.create_instance(
            workflow_name=workflow_name,
            input_data=input_data,
            tenant_id=tenant_id,
            created_by_id=created_by_id,
            workflow_version=workflow_version,
        )

    def start_workflow_instance(self, instance_id: str):
        """Start a DRAFT workflow instance. Returns updated WorkflowInstance."""
        return self.workflow_engine.start_instance(instance_id)

    def execute_workflow_instance(self, instance_id: str):
        """
        Execute a RUNNING workflow instance to completion (or first failure).
        Returns updated WorkflowInstance.
        """
        return self.workflow_engine.execute_instance(instance_id)

    def create_start_and_execute(
        self,
        workflow_name: str,
        input_data: dict[str, Any],
        tenant_id: str | None = None,
        created_by_id: str | None = None,
    ):
        """
        Create, start, and execute a workflow in one call.
        Returns (instance_after_execute, error_if_raised).
        """
        instance = self.create_workflow_instance(
            workflow_name=workflow_name,
            input_data=input_data,
            tenant_id=tenant_id,
            created_by_id=created_by_id,
        )
        instance = self.start_workflow_instance(str(instance.id))
        try:
            instance = self.execute_workflow_instance(str(instance.id))
            return instance, None
        except Exception as e:
            instance.refresh_from_db()
            return instance, e

    # --- Workflow state verification helpers ---

    def assert_workflow_completed(self, instance, msg: str | None = None):
        """Assert workflow instance status is COMPLETED."""
        from hub.apps.orchestration.models import WorkflowStatus

        instance.refresh_from_db()
        self.assertEqual(
            instance.status,
            WorkflowStatus.COMPLETED,
            msg or f"Expected COMPLETED, got {instance.status}",
        )

    def assert_workflow_failed(self, instance, msg: str | None = None):
        """Assert workflow instance status is FAILED or ROLLED_BACK (both indicate failure)."""
        from hub.apps.orchestration.models import WorkflowStatus

        instance.refresh_from_db()
        # Normalize to string for robust comparison (DB may return str, enum, or value)
        status_str = str(instance.status) if instance.status else ""
        valid_failures = (WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK)
        valid_strs = [str(s) for s in valid_failures]
        self.assertIn(
            status_str,
            valid_strs,
            msg or f"Expected FAILED or ROLLED_BACK, got {instance.status}",
        )

    def assert_workflow_error_details_contain_validation(self, instance):
        """Assert workflow error_details or error_message reference validation/spec/required failure."""
        instance.refresh_from_db()
        err_msg = (instance.error_message or "").lower()
        details = instance.error_details or {}
        details_str = str(details).lower()
        combined = err_msg + " " + details_str
        # Accept: validation, business rules, spec format, required field, or step validation wording
        validation_like = (
            "validation" in combined
            or "business rules" in combined
            or "invalid_spec_format" in combined
            or "must have" in combined
            or "required" in combined
            or "key is required" in combined
        )
        self.assertTrue(
            validation_like,
            f"Expected validation/spec/required in error_message or error_details; "
            f"error_message={instance.error_message!r}, error_details={details}",
        )

    def assert_validation_results_in_state_data(self, instance):
        """
        Assert that instance.state_data contains _validation_results
        (stored by engine when business rules validation runs).
        """
        instance.refresh_from_db()
        state = instance.state_data or {}
        self.assertIn(
            "_validation_results",
            state,
            "state_data should contain _validation_results from business rules validation",
        )
        vr = state["_validation_results"]
        # At least one validation type should be present (from last executed step)
        expected_keys = (
            "workflow_state",
            "step_input",
            "step_execution",
            "step_output",
            "post_workflow_state",
        )
        found = [k for k in expected_keys if k in vr]
        self.assertTrue(
            len(found) >= 1,
            f"_validation_results should contain at least one of {expected_keys}, got keys: {list(vr.keys())}",
        )

    def assert_validation_metrics_recorded(self, instance):
        """
        Assert that validation results in state_data include duration/cached
        (indicating metrics path was exercised). Does not call Prometheus.
        """
        self.assert_validation_results_in_state_data(instance)
        vr = (instance.state_data or {}).get("_validation_results", {})
        for key, val in vr.items():
            if isinstance(val, dict):
                self.assertIn("valid", val, f"{key} should have 'valid'")
                self.assertIn("duration", val, f"{key} should have 'duration'")

    def assert_workflow_step_count_at_least(self, instance, min_steps: int):
        """Assert workflow has at least min_steps steps (any status)."""
        instance.refresh_from_db()
        count = instance.steps.count()
        self.assertGreaterEqual(
            count,
            min_steps,
            f"Expected at least {min_steps} steps, got {count}",
        )
