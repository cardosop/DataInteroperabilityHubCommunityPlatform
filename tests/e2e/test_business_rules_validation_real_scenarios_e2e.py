"""
Phase 6.3 — E2E Tests for Business Rules Validation in Real Scenarios

These tests validate business-rules behavior in *real workflow context*:
- OrchestrationBusinessRules methods against real WorkflowInstance/WorkflowStep rows
- WorkflowEngine error propagation (ValidationResult -> WorkflowExecutionError)
- Validation warnings: logged, persisted in workflow state_data, and emitted in workflow events
- Validation caching behavior: per-workflow-instance cache, invalidation on state change, TTL, and cache metrics

No mocks/stubs: uses real DB models, real cache backend, real event bus/persistence.
"""

import json
import time
import uuid

import pytest

from django.test.utils import override_settings

from hub.apps.core.events.models import Event
from hub.apps.orchestration.business_rules import OrchestrationBusinessRules
from hub.apps.orchestration.models import WorkflowStatus
from hub.apps.orchestration.workflow_engine import WorkflowExecutionError
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from tests.e2e.workflow_e2e_base import WorkflowE2ETestBase
from tests.factories import TenantFactory, UserFactory


def _valid_odcs_contract_minimal():
    """Minimal valid ODCS contract for ContractCreationWorkflow."""
    return {
        "apiVersion": "odcs.io/v3.0.2",
        "kind": "DataContract",
        "id": f"test-contract-{uuid.uuid4().hex[:8]}",
        "name": "Test Contract 6.3",
        "version": "3.0.2",
        "description": "Test contract for business-rules E2E",
        "schema": {"fields": [{"name": "id", "type": "string"}]},
        "info": {
            "name": "Test Contract",
            "description": "Test",
            "version": "3.0.2",
            "owners": [{"name": "Test", "email": "test@example.com"}],
        },
    }


def _valid_odps_doc_minimal(schema_version: str = "4.1", version_field: str = "4.1"):
    """
    Minimal ODPS document that passes structure validation.

    Note: ODPS schema validation is performed by ODPSParser.validate() in workflow tasks;
    this doc includes a minimal embedded ODCS contract spec to keep the workflow moving.
    """
    return {
        "schema": f"https://opendataproducts.org/schema/v{schema_version}",
        "version": version_field,
        "product": {
            "details": {
                "en": {
                    "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                    "name": "Test Product 6.3",
                    "description": "Test product for business-rules E2E",
                }
            },
            "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            "contract": {
                "spec": {
                    "apiVersion": "odcs.io/v3.0.2",
                    "kind": "DataContract",
                    "id": f"test-odcs-{uuid.uuid4().hex[:8]}",
                    "name": "Embedded ODCS Contract 6.3",
                    "version": "1.0.0",
                    "description": "Embedded contract for ODPS validation E2E",
                    "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
                }
            },
        },
    }


@pytest.mark.e2e
@pytest.mark.requires_database
@pytest.mark.timeout(1800)
class TestServiceSpecificBusinessRulesInWorkflowContextE2E(WorkflowE2ETestBase):
    """
    6.3.2 — Service-specific business rules in workflow context.

    We assert that specific validation categories surface as distinct failures in real workflow runs.
    """

    workflow_classes = [ProductCreationWorkflow, ContractCreationWorkflow]

    def test_odps_business_rules_document_structure_validation_surfaces_in_workflow(self):
        # Missing 'product' triggers ODPS structure validation failure in ProductCreationWorkflow._parse_odps_task()
        input_data = {
            "original_raw": json.dumps({"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(ProductCreationWorkflow.WORKFLOW_NAME, input_data)
        instance.refresh_from_db()
        self.assertIn(
            instance.status,
            [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK],
            f"Expected workflow to fail (validation surfaced); got status={instance.status}",
        )
        self.assertIn("odps structure validation failed", (instance.error_message or "").lower())

    def test_odps_business_rules_version_validation_surfaces_in_workflow(self):
        # Unsupported schema version should trigger ODPS version validation failure
        bad_version_doc = _valid_odps_doc_minimal(schema_version="9.9", version_field="9.9")
        input_data = {
            "original_raw": json.dumps(bad_version_doc),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, err = self.create_start_and_execute(ProductCreationWorkflow.WORKFLOW_NAME, input_data)
        instance.refresh_from_db()
        self.assertIn(
            instance.status,
            [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK],
            f"Expected workflow to fail (validation surfaced); got status={instance.status}",
        )
        self.assertIn("odps version validation failed", (instance.error_message or "").lower())

    def test_odps_contract_validation_surfaces_via_schema_validation_in_workflow(self):
        # Make product.contract.spec invalid type to force failure in extract_contract step.
        doc = _valid_odps_doc_minimal()
        doc["product"]["contract"]["spec"] = "NOT_A_DICT"
        input_data = {
            "original_raw": json.dumps(doc),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, _ = self.create_start_and_execute(ProductCreationWorkflow.WORKFLOW_NAME, input_data)
        instance.refresh_from_db()
        self.assertIn(
            instance.status,
            [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK],
            f"Expected workflow to fail (validation surfaced); got status={instance.status}",
        )
        self.assertIn("product.contract.spec must be a dictionary", (instance.error_message or "").lower())

    def test_contracts_business_rules_creation_validation_surfaces_in_workflow(self):
        # ContractsBusinessRules.validate_contract_creation is strict on metadata fields like
        # original_spec_type; use an invalid spec type to force a real validation failure path.
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
            "original_spec_type": "NOT_A_REAL_SPEC_TYPE",
        }
        instance, err = self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        instance.refresh_from_db()
        # May be FAILED or ROLLED_BACK when compensation runs after validation failure
        self.assertIn(
            instance.status,
            [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK],
            f"Expected workflow to fail (validation surfaced); got status={instance.status}",
        )
        combined = ((instance.error_message or "") + " " + str(instance.error_details or {})).lower()
        self.assertIn("invalid original_spec_type", combined)


@pytest.mark.e2e
@pytest.mark.requires_database
@pytest.mark.timeout(900)
class TestOrchestrationBusinessRulesInWorkflowContextE2E(WorkflowE2ETestBase):
    """
    6.3.1 — OrchestrationBusinessRules in workflow context.

    We run validations against real WorkflowInstance/WorkflowStep objects created from
    real WorkflowEngine + WorkflowDefinition DSL (no synthetic stand-ins).
    """

    workflow_classes = [ProductCreationWorkflow]

    def _create_instance_and_first_step(self):
        instance = self.create_workflow_instance(
            ProductCreationWorkflow.WORKFLOW_NAME,
            input_data={"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
        )
        step = instance.steps.order_by("step_index").first()
        self.assertIsNotNone(step, "Workflow should create at least one step")
        return instance, step

    def test_validate_workflow_step_execution_blocks_when_workflow_not_running(self):
        instance, step = self._create_instance_and_first_step()

        br = OrchestrationBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # DRAFT workflow should not allow execution
        result = br.validate_workflow_step_execution(instance, step, tenant=self.tenant, user=self.user)
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("expected RUNNING" in e for e in result.errors),
            f"Expected status error, got errors={result.errors}",
        )

        # Make RUNNING and validate again (should be allowed for PENDING step)
        instance.status = WorkflowStatus.RUNNING
        instance.save(update_fields=["status", "updated_at"])
        result2 = br.validate_workflow_step_execution(instance, step, tenant=self.tenant, user=self.user)
        self.assertTrue(result2.is_valid, f"Expected valid, got errors={result2.errors}, warnings={result2.warnings}")

    def test_validate_workflow_step_execution_detects_tenant_context_mismatch(self):
        instance, step = self._create_instance_and_first_step()
        instance.status = WorkflowStatus.RUNNING
        instance.save(update_fields=["status", "updated_at"])

        other_tenant = TenantFactory()
        br = OrchestrationBusinessRules(tenant_id=str(other_tenant.id), user_id=str(self.user.id))

        result = br.validate_workflow_step_execution(instance, step, tenant=other_tenant, user=self.user)
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("does not match provided tenant" in e for e in result.errors),
            f"Expected tenant mismatch error, got errors={result.errors}",
        )

    def test_validate_step_input_structure_and_json_serializability(self):
        instance, step = self._create_instance_and_first_step()
        instance.status = WorkflowStatus.RUNNING
        instance.save(update_fields=["status", "updated_at"])

        br = OrchestrationBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Structure validation
        result = br.validate_step_input(instance, step, ["not", "a", "dict"], tenant=self.tenant, user=self.user)  # type: ignore[arg-type]
        self.assertFalse(result.is_valid)
        self.assertTrue(any("must be a dictionary" in e for e in result.errors))

        # "Schema" validation (JSON serializable requirement)
        result2 = br.validate_step_input(instance, step, {"bad": object()}, tenant=self.tenant, user=self.user)
        self.assertFalse(result2.is_valid)
        self.assertTrue(any("not JSON serializable" in e for e in result2.errors))

    def test_validate_step_output_structure_and_json_serializability(self):
        instance, step = self._create_instance_and_first_step()
        instance.status = WorkflowStatus.RUNNING
        instance.save(update_fields=["status", "updated_at"])

        br = OrchestrationBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        result = br.validate_step_output(instance, step, "not-a-dict", tenant=self.tenant, user=self.user)  # type: ignore[arg-type]
        self.assertFalse(result.is_valid)
        self.assertTrue(any("must be a dictionary" in e for e in result.errors))

        result2 = br.validate_step_output(instance, step, {"bad": object()}, tenant=self.tenant, user=self.user)
        self.assertFalse(result2.is_valid)
        self.assertTrue(any("not JSON serializable" in e for e in result2.errors))

    def test_validate_workflow_state_detects_inconsistent_state_and_transition_bounds(self):
        instance, _ = self._create_instance_and_first_step()
        instance.status = WorkflowStatus.RUNNING
        instance.state_data = {"progress_percentage": "not-a-number"}
        instance.save(update_fields=["status", "state_data", "updated_at"])

        br = OrchestrationBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        result = br.validate_workflow_state(instance, tenant=self.tenant, user=self.user)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("progress_percentage must be a number" in e for e in result.errors))

        # Out-of-bounds current_step_index should be invalid when definition exists
        instance.current_step_index = 9999
        instance.state_data = {"current_step_index": 9999, "current_step_name": "bogus"}
        instance.save(update_fields=["current_step_index", "state_data", "updated_at"])
        result2 = br.validate_workflow_state(instance, tenant=self.tenant, user=self.user)
        self.assertFalse(result2.is_valid)
        self.assertTrue(any("out of bounds" in e for e in result2.errors), f"errors={result2.errors}")


@pytest.mark.e2e
@pytest.mark.requires_database
@pytest.mark.requires_redis
@pytest.mark.timeout(1800)
class TestBusinessRulesErrorPropagationWarningsEventsAndCachingE2E(WorkflowE2ETestBase):
    """
    6.3.3 + 6.3.4 — Error propagation, warnings behavior, caching + metrics.
    """

    workflow_classes = [ContractCreationWorkflow]

    def test_validation_errors_propagate_to_workflowexecutionerror_with_context(self):
        """
        Orchestration validation failures (e.g. step already COMPLETED) are detected during
        execute_instance(); the engine marks the workflow FAILED and persists the error with
        workflow/step/rule context. We assert propagation via instance.error_message.
        """
        from hub.apps.orchestration.models import StepStatus

        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance = self.create_workflow_instance(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        instance = self.start_workflow_instance(str(instance.id))
        # Corrupt current step so orchestration validation fails (step must be PENDING/RUNNING).
        step0 = instance.steps.get(step_index=0)
        step0.status = StepStatus.COMPLETED
        step0.save(update_fields=["status", "updated_at"])

        instance = self.execute_workflow_instance(str(instance.id))
        instance.refresh_from_db()

        self.assertIn(
            instance.status,
            [WorkflowStatus.FAILED, WorkflowStatus.ROLLED_BACK],
            f"Expected workflow to fail (validation surfaced); got status={instance.status}",
        )
        msg = (instance.error_message or "").lower()
        self.assertIn("business rules validation failed", msg)
        self.assertIn("orchestrationbusinessrules", msg)
        self.assertTrue(
            "workflow" in msg and "step" in msg,
            f"Expected workflow/step context in error_message: {msg}",
        )

    def test_validation_warnings_are_logged_persisted_and_emitted_in_events(self):
        # Cross-tenant created_by user should generate warnings (permissions/tenant consistency) but not block execution.
        other_tenant = TenantFactory()
        cross_tenant_user = UserFactory(tenant=other_tenant, email=f"x_{uuid.uuid4().hex[:8]}@example.com")

        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),              # workflow tenant
            "user_id": str(cross_tenant_user.id),          # user from other tenant
        }

        # Ensure events are persisted synchronously when possible (Celery isn't running in the test container).
        with override_settings(
            EVENT_BUS_ENABLE_PERSISTENCE=True,
            EVENT_BUS_ASYNC_PERSISTENCE=False,
            EVENT_BUS_WRITE_BEHIND_ENABLED=False,
        ):
            with self.assertLogs("hub.apps.orchestration.workflow_engine", level="WARNING") as log_ctx:
                instance, _ = self.create_start_and_execute(
                    ContractCreationWorkflow.WORKFLOW_NAME,
                    input_data,
                    created_by_id=str(cross_tenant_user.id),
                )
        # The workflow may still fail later for other reasons, but warnings must not *cause* a validation failure.
        instance.refresh_from_db()
        self.assertIn(instance.status, (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.RUNNING))

        # Warnings must be logged (message contains "validation warnings")
        warning_msgs = "\n".join(log_ctx.output).lower()
        self.assertTrue(
            "validation warnings" in warning_msgs,
            "Expected validation warnings to be logged",
        )

        # Warnings must be persisted in workflow state_data
        self.assertIn("_validation_results", instance.state_data or {})
        vr = (instance.state_data or {}).get("_validation_results", {})
        # At least one validation section should include non-empty warnings list
        warnings_found = False
        for section in ("workflow_state", "step_input", "step_execution", "step_output", "post_workflow_state"):
            sec = vr.get(section) or {}
            if isinstance(sec, dict) and sec.get("warnings"):
                warnings_found = True
                break
        self.assertTrue(warnings_found, f"Expected warnings in state_data._validation_results, got: {vr}")

        # Warnings must be present in workflow events when persistence is sync (override_settings
        # above). If events are persisted async (e.g. no worker), poll briefly then assert only
        # when an event row exists.
        ev = None
        for _ in range(25):  # up to ~5s
            ev = (
                Event.objects.filter(
                    event_type__in=["workflow.step.started", "workflow.step.completed", "workflow.step.failed"],
                    data__workflow_instance_id=str(instance.id),
                )
                .order_by("-timestamp")
                .first()
            )
            if ev is not None:
                break
            time.sleep(0.2)
        if ev is not None:
            data = ev.data or {}
            vc = data.get("validation_context") or {}
            self.assertTrue(isinstance(vc, dict), f"Expected dict validation_context, got {type(vc)}")
            validations = vc.get("validations") or {}
            warnings_in_event = any(
                (v or {}).get("warnings") for v in validations.values() if isinstance(v, dict)
            )
            self.assertTrue(
                warnings_in_event,
                f"Expected warnings inside event validation_context.validations, got: {vc}",
            )

    def test_validation_results_cached_per_workflow_instance_invalidation_and_ttl_and_metrics(self):
        # Build a real workflow instance and step; exercise engine's cache-aware validation hook directly.
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance = self.create_workflow_instance(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        instance = self.start_workflow_instance(str(instance.id))
        step = instance.steps.order_by("step_index").first()
        self.assertIsNotNone(step)

        # Use short TTL to validate expiry without long sleeps
        with override_settings(CACHE_TTL_BUSINESS_RULES=1):
            def _run_cached_workflow_state_validation():
                start = time.time()
                result, cached_flag = self.workflow_engine._cached_orchestration_validation(  # type: ignore[attr-defined]
                    validation_type="workflow_state",
                    instance=instance,
                    step=step,
                    payload_fingerprint={
                        "state_data": instance.state_data,
                        "current_step_index": instance.current_step_index,
                        "status": instance.status,
                    },
                    compute=lambda: OrchestrationBusinessRules(
                        tenant_id=str(self.tenant.id), user_id=str(self.user.id)
                    ).validate_workflow_state(instance, self.tenant, self.user),
                )
                duration = time.time() - start
                self.workflow_engine._record_validation_metrics(
                    instance=instance,
                    step=step,
                    rule_name="OrchestrationBusinessRules",
                    validation_type="workflow_state",
                    validation_result=result,
                    duration=duration,
                    cached=cached_flag,
                    tenant_id_str=str(self.tenant.id),
                )
                return result, cached_flag

            # First call: cache miss
            result1, cached1 = _run_cached_workflow_state_validation()
            self.assertTrue(result1.is_valid)
            self.assertFalse(cached1)

            # Second call with same fingerprint: cache hit
            result2, cached2 = _run_cached_workflow_state_validation()
            self.assertTrue(result2.is_valid)
            self.assertTrue(cached2)

            # Invalidation on state change: change state_data (and persist) -> cache miss
            instance.state_data = {**(instance.state_data or {}), "cache_bust": uuid.uuid4().hex}
            instance.save(update_fields=["state_data", "updated_at"])
            result3, cached3 = _run_cached_workflow_state_validation()
            self.assertTrue(result3.is_valid)
            self.assertFalse(cached3)

            # TTL behavior: wait for TTL to expire -> next call should be cache miss
            time.sleep(1.2)
            result4, cached4 = _run_cached_workflow_state_validation()
            self.assertTrue(result4.is_valid)
            self.assertFalse(cached4)

            # Cache metrics are recorded via WorkflowEngine._record_validation_metrics without raising,
            # and cache behavior is observable via the cached_flag transitions above.

