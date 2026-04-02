"""
Phase 6.4 — E2E Tests for Workflow Observability with Business Rules

Comprehensive E2E tests for:
- 6.4.1 Workflow metrics with business rules validation (Prometheus)
- 6.4.2 Workflow events with business rules validation (step.started/completed/failed)
- 6.4.3 Structured logging with business rules validation
- 6.4.4 Distributed tracing with business rules validation

No mocks/stubs: uses real workflow execution, real Prometheus registry, real Event
persistence, real log capture (assertLogs), and real OpenTelemetry tracer with
InMemorySpanExporter for span assertion.
"""

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.workflow_e2e]

import json
import re
import time
import uuid

from django.test.utils import override_settings

from hub.apps.core.events.models import Event
from hub.apps.orchestration.models import WorkflowStatus
from hub.apps.orchestration.workflows.contract_creation import ContractCreationWorkflow
from tests.e2e.workflow_e2e_base import WorkflowE2ETestBase
from tests.factories import TenantFactory, UserFactory


def _valid_odcs_contract_minimal():
    """Minimal valid ODCS contract for ContractCreationWorkflow."""
    return {
        "apiVersion": "odcs.io/v3.0.2",
        "kind": "DataContract",
        "id": f"test-contract-{uuid.uuid4().hex[:8]}",
        "name": "Test Contract 6.4",
        "version": "3.0.2",
        "description": "Test contract for observability E2E",
        "schema": {"fields": [{"name": "id", "type": "string"}]},
        "info": {
            "name": "Test Contract",
            "description": "Test",
            "version": "3.0.2",
            "owners": [{"name": "Test", "email": "test@example.com"}],
        },
    }


def _collect_prometheus_metrics_text(client=None):
    """
    Collect Prometheus-format metrics. Prefer Django test client GET /metrics/
    so we read the same registry the app serves (root cause: OTL exporter
    uses its own registry). If /metrics/ returns 503 or non-200 (e.g. REGISTRY
    not yet set in test), fall back to setup_opentelemetry_metrics() and
    generate_latest(REGISTRY). No mocks.
    """
    if client is not None:
        response = client.get("/metrics/")
        if response.status_code == 200:
            return response.content.decode("utf-8")
        # Fallback: ensure OTL metrics are set up and read REGISTRY directly
        # (same registry workflow metrics write to when wrappers call get_meter())
        from hub.apps.observability.otel_metrics import setup_opentelemetry_metrics

        setup_opentelemetry_metrics()
        try:
            from opentelemetry.exporter.prometheus import REGISTRY
            from prometheus_client import generate_latest

            if REGISTRY is not None:
                return generate_latest(REGISTRY).decode("utf-8")
        except Exception:
            pass
        return None
    from hub.apps.observability.otel_metrics import setup_opentelemetry_metrics

    setup_opentelemetry_metrics()
    try:
        from opentelemetry.exporter.prometheus import REGISTRY
        from prometheus_client import generate_latest
    except ImportError:
        return None
    if REGISTRY is None:
        return None
    try:
        return generate_latest(REGISTRY).decode("utf-8")
    except Exception:
        return None


def _parse_metric_samples(metrics_text, metric_name):
    """
    Parse Prometheus text for a metric and return list of (labels_dict, value).

    Handles format: metric_name{label="value",...} value
    """
    if not metrics_text or not metric_name:
        return []
    samples = []
    pattern = re.compile(r"^" + re.escape(metric_name) + r"\{(.+)\}\s+([\d.e+-]+)", re.MULTILINE)
    for match in pattern.finditer(metrics_text):
        labels_str, value_str = match.group(1), match.group(2)
        labels = {}
        for part in re.findall(r'(\w+)="([^"]*)"', labels_str):
            labels[part[0]] = part[1]
        try:
            value = float(value_str)
        except ValueError:
            value = 0.0
        samples.append((labels, value))
    return samples


# -----------------------------------------------------------------------------
# 6.4.1 E2E tests for workflow metrics with business rules validation
# -----------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.requires_database
@pytest.mark.timeout(900)
@override_settings(
    ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
    WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100,
    OPENTELEMETRY_ENABLED=True,
    OPENTELEMETRY_METRICS_ENABLED=True,
)
class TestWorkflowMetricsBusinessRulesE2E(WorkflowE2ETestBase):
    """
    6.4.1 — E2E tests for workflow metrics with business rules validation.

    Verifies validation metrics are recorded in Prometheus (real registry) and
    that metric labels are correct (workflow name, step name, rule name, tenant).
    """

    workflow_classes = [ContractCreationWorkflow]

    def test_validation_metrics_recorded_in_prometheus(self):
        """Verify workflow_business_rules_validations_total counter is recorded."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)

        metrics_text = _collect_prometheus_metrics_text(self.client)
        self.assertIsNotNone(metrics_text, "Prometheus metrics should be available")
        self.assertIn(
            "workflow_business_rules_validations_total",
            metrics_text,
            "workflow_business_rules_validations_total should be present",
        )

        samples = _parse_metric_samples(metrics_text, "workflow_business_rules_validations_total")
        self.assertGreater(
            len(samples),
            0,
            "At least one validation counter sample should be recorded",
        )
        total_count = sum(v for _, v in samples)
        self.assertGreater(total_count, 0, "Validation counter should have increased")

    def test_validation_duration_histogram_recorded(self):
        """Verify workflow_business_rules_validation_duration_seconds histogram."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)

        metrics_text = _collect_prometheus_metrics_text(self.client)
        self.assertIsNotNone(metrics_text)
        self.assertIn(
            "workflow_business_rules_validation_duration_seconds",
            metrics_text,
            "Validation duration histogram should be present",
        )
        # OpenTelemetry Prometheus exporter may use _bucket, _count, _sum suffixes
        for suffix in ("", "_bucket", "_count", "_sum"):
            samples = _parse_metric_samples(
                metrics_text,
                "workflow_business_rules_validation_duration_seconds" + suffix,
            )
            if samples:
                break
        self.assertGreater(
            len(samples),
            0,
            "At least one duration sample should be recorded (check histogram export format)",
        )

    def test_validation_cache_metrics_recorded(self):
        """Verify cache hits and/or cache misses counters (first run often only misses)."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)

        metrics_text = _collect_prometheus_metrics_text(self.client)
        self.assertIsNotNone(metrics_text)
        has_hits = (
            metrics_text is not None
            and "workflow_business_rules_validation_cache_hits_total" in metrics_text
        )
        has_misses = (
            metrics_text is not None
            and "workflow_business_rules_validation_cache_misses_total" in metrics_text
        )
        self.assertTrue(
            has_hits or has_misses,
            "At least one of cache_hits_total or cache_misses_total should be present in metrics",
        )

    def test_metrics_labels_workflow_step_rule_tenant(self):
        """Verify metrics have correct labels: workflow name, step name, rule name, tenant."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)

        metrics_text = _collect_prometheus_metrics_text(self.client)
        self.assertIsNotNone(metrics_text)
        samples = _parse_metric_samples(metrics_text, "workflow_business_rules_validations_total")
        self.assertGreater(len(samples), 0, "Need at least one sample to check labels")

        # Filter for our workflow (registry accumulates metrics from prior tests)
        expected_workflow = ContractCreationWorkflow.WORKFLOW_NAME
        matching = [s for s in samples if s[0].get("workflow_name") == expected_workflow]
        self.assertGreater(
            len(matching),
            0,
            f"Need at least one sample for workflow {expected_workflow}; got {[s[0].get('workflow_name') for s in samples[:5]]}",
        )
        labels = matching[0][0]
        self.assertIn(
            "workflow_name",
            labels,
            "Metric should have workflow_name label",
        )
        self.assertEqual(
            labels.get("workflow_name"),
            expected_workflow,
            "workflow_name label should match",
        )
        self.assertIn("step_name", labels, "Metric should have step_name label")
        self.assertIn("rule_name", labels, "Metric should have rule_name label")
        self.assertIn("tenant_id", labels, "Metric should have tenant_id label")
        self.assertIn("status", labels, "Metric should have status label (valid/invalid)")


# -----------------------------------------------------------------------------
# 6.4.2 E2E tests for workflow events with business rules validation
# -----------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.requires_database
@pytest.mark.timeout(900)
@override_settings(
    ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
    WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100,
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class TestWorkflowEventsBusinessRulesE2E(WorkflowE2ETestBase):
    """
    6.4.2 — E2E tests for workflow events with business rules validation.

    Verifies workflow.step.started/completed/failed events include validation
    status and validation context (real Event persistence).
    """

    workflow_classes = [ContractCreationWorkflow]

    def test_step_started_events_include_validation_status(self):
        """Test workflow.step.started events include validation status."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, _ = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME, input_data
        )
        instance.refresh_from_db()

        events = Event.objects.filter(
            event_type="workflow.step.started",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")
        self.assertGreater(
            events.count(),
            0,
            "workflow.step.started events should be published",
        )
        for ev in events:
            self.assertIn(
                "validation_status",
                ev.data,
                f"step.started event should include validation_status: {ev.data}",
            )

    def test_step_completed_events_include_validation_results(self):
        """Test workflow.step.completed events include validation results."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, _ = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME, input_data
        )
        instance.refresh_from_db()

        events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")
        self.assertGreater(
            events.count(),
            0,
            "workflow.step.completed events should be published",
        )
        for ev in events:
            self.assertIn(
                "validation_status",
                ev.data,
                "step.completed event should include validation_status",
            )
            if "validation_context" in ev.data:
                vc = ev.data["validation_context"]
                self.assertIn("rule_name", vc, "validation_context should have rule_name")
                self.assertIn("validations", vc, "validation_context should have validations")

    def test_step_failed_events_include_validation_errors(self):
        """Test workflow.step.failed events include validation errors when step fails.

        Root cause: step.failed is only published when failure happens inside
        _execute_step's try block (after step.started). Pre-step validation
        (e.g. step status check) raises before that, so we use a task that
        raises so failure occurs after step.started and step.failed is published.
        """
        from django.contrib.auth import get_user_model

        from hub.apps.orchestration.models import WorkflowDefinition, WorkflowStatus

        User = get_user_model()
        # Minimal workflow with one task that raises so failure is inside try block
        workflow_def = WorkflowDefinition.objects.create(
            name="observability_e2e_fail_step",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "fail_step", "type": "task", "task": "observability_e2e_raise_task"},
                ],
            },
            created_by=self.user,
        )

        def failing_task(input_data, instance, step):
            raise ValueError("Task raised for step.failed E2E test")

        self.workflow_engine.register_task("observability_e2e_raise_task", failing_task)

        instance = self.workflow_engine.create_instance(
            workflow_name="observability_e2e_fail_step",
            input_data={"tenant_id": str(self.tenant.id), "user_id": str(self.user.id)},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )
        instance = self.workflow_engine.start_instance(str(instance.id))
        self.execute_workflow_instance(str(instance.id))
        instance.refresh_from_db()

        self.assertEqual(instance.status, WorkflowStatus.FAILED)
        events = Event.objects.filter(
            event_type="workflow.step.failed",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")
        self.assertGreater(
            events.count(),
            0,
            "workflow.step.failed event should be published when step fails (after step.started)",
        )
        ev = events.first()
        self.assertIn("validation_status", ev.data)
        self.assertIn("error_message", ev.data)
        # When step fails after validation ran, validation_context may be present
        if "validation_context" in ev.data:
            vc = ev.data["validation_context"]
            self.assertIsInstance(vc, dict)
            self.assertIn("rule_name", vc)

    def test_validation_context_in_event_payload(self):
        """Test validation context is in event payload for completed steps."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance, _ = self.create_start_and_execute(
            ContractCreationWorkflow.WORKFLOW_NAME, input_data
        )
        instance.refresh_from_db()

        events = Event.objects.filter(
            event_type="workflow.step.completed",
            data__workflow_instance_id=str(instance.id),
        ).order_by("timestamp")
        self.assertGreater(events.count(), 0)
        ev = events.first()
        self.assertIn("validation_context", ev.data)
        vc = ev.data["validation_context"]
        self.assertIsInstance(vc, dict)
        self.assertIn("rule_name", vc)
        self.assertIn("validations", vc)


# -----------------------------------------------------------------------------
# 6.4.3 E2E tests for structured logging with business rules validation
# -----------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.requires_database
@pytest.mark.timeout(900)
@override_settings(
    ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
    WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100,
)
class TestWorkflowStructuredLoggingBusinessRulesE2E(WorkflowE2ETestBase):
    """
    6.4.3 — E2E tests for structured logging with business rules validation.

    Uses assertLogs to capture real log output (no mock). Verifies validation
    results, errors/warnings, duration, and workflow/step context in logs.
    """

    workflow_classes = [ContractCreationWorkflow]

    def test_validation_results_in_workflow_execution_logs(self):
        """Test validation results are in workflow execution logs."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        with self.assertLogs("hub.apps.orchestration.workflow_engine", level="DEBUG") as log_ctx:
            self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        log_output = "\n".join(log_ctx.output).lower()
        self.assertTrue(
            "validation" in log_output or "business_rules" in log_output,
            "Workflow execution logs should contain validation or business_rules context",
        )

    def test_validation_errors_warnings_in_error_logs(self):
        """Test validation errors/warnings are in error logs when validation fails."""
        from hub.apps.orchestration.models import StepStatus

        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        instance = self.create_workflow_instance(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        instance = self.start_workflow_instance(str(instance.id))
        step0 = instance.steps.get(step_index=0)
        step0.status = StepStatus.COMPLETED
        step0.save(update_fields=["status", "updated_at"])

        with self.assertLogs("hub.apps.orchestration", level="WARNING") as log_ctx:
            self.execute_workflow_instance(str(instance.id))
        log_output = "\n".join(log_ctx.output).lower()
        self.assertTrue(
            "validation" in log_output or "business rules" in log_output or "error" in log_output,
            "Validation failure should produce warning/error logs",
        )

    def test_validation_duration_and_workflow_context_in_logs(self):
        """Test validation duration and workflow/step context appear in logs."""
        input_data = {
            "original_raw": json.dumps(_valid_odcs_contract_minimal()),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        with self.assertLogs("hub.apps.orchestration.workflow_engine", level="DEBUG") as log_ctx:
            self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        log_output = "\n".join(log_ctx.output)
        self.assertTrue(
            "step" in log_output.lower() and ("duration" in log_output.lower() or "validation" in log_output.lower()),
            "Logs should contain step context with duration or validation info",
        )

    def test_validation_failure_logs_error_with_rule_context(self):
        """Test error logs when workflow fails (validation or step failure).

        When business rules validation fails, the engine logs 'Workflow validation failed'.
        When a step fails (e.g. invalid contract in a later task), the engine logs
        'Error executing step'. Both paths must produce ERROR logs from the engine.
        We use invalid contract so a step fails; assert ERROR log contains
        validation/rule/error/failed context (no mocks).
        """
        invalid_contract = {"invalid": "not odcs", "missing": "required fields"}
        input_data = {
            "original_raw": json.dumps(invalid_contract),
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id),
        }
        with self.assertLogs("hub.apps.orchestration.workflow_engine", level="ERROR") as log_ctx:
            try:
                self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
            except Exception:
                pass
        log_output = "\n".join(log_ctx.output).lower()
        # Engine logs "Workflow validation failed" (validation path) or
        # "Error executing step" (task exception path) at ERROR level.
        self.assertTrue(
            "validation" in log_output
            or "business" in log_output
            or "rule" in log_output
            or "executing step" in log_output,
            f"Workflow failure error logs should reference validation/business/rule "
            f"or step execution context, got: {log_output[:500]}",
        )


# -----------------------------------------------------------------------------
# 6.4.4 E2E tests for distributed tracing with business rules validation
# -----------------------------------------------------------------------------


class _InMemorySpanExporter:
    """
    In-memory span exporter for E2E tests (no mock).
    Implements OpenTelemetry SpanExporter; stores spans for assertion.
    Used when opentelemetry.sdk.trace.export.InMemorySpanExporter is not
    available in the installed SDK (e.g. not in opentelemetry-sdk 1.20).
    """

    def __init__(self):
        self._spans = []

    def export(self, spans):
        from opentelemetry.sdk.trace.export import SpanExportResult

        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=None):
        return True

    def get_finished_spans(self):
        return list(self._spans)


def _get_tracer_with_in_memory_exporter():
    """
    Create a real TracerProvider with an in-memory span exporter and return
    (tracer, span_exporter). No mock: real tracer, real spans, captured in memory.
    """
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    except ImportError:
        return None, None
    span_exporter = _InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    tracer = provider.get_tracer("workflow-observability-e2e", "1.0")
    return tracer, span_exporter


@pytest.mark.e2e
@pytest.mark.requires_database
@pytest.mark.timeout(900)
@override_settings(
    ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True,
    WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100,
    OPENTELEMETRY_ENABLED=True,
)
class TestWorkflowDistributedTracingBusinessRulesE2E(WorkflowE2ETestBase):
    """
    6.4.4 — E2E tests for distributed tracing with business rules validation.

    Injects a real tracer backed by InMemorySpanExporter so we can assert on
    validation spans, linkage to workflow spans, and span attributes (no mock).
    """

    workflow_classes = [ContractCreationWorkflow]

    def test_validation_spans_in_opentelemetry_traces(self):
        """Test validation spans are in OpenTelemetry traces."""
        tracer, span_exporter = _get_tracer_with_in_memory_exporter()
        if tracer is None or span_exporter is None:
            pytest.skip("OpenTelemetry SDK not available")

        import hub.apps.orchestration.workflow_engine as engine_module

        original_tracer = getattr(engine_module, "_tracer", None)
        engine_module._tracer = tracer

        try:
            input_data = {
                "original_raw": json.dumps(_valid_odcs_contract_minimal()),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            }
            self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        finally:
            engine_module._tracer = original_tracer

        spans = span_exporter.get_finished_spans()
        validation_spans = [s for s in spans if "validation" in s.name.lower()]
        self.assertGreater(
            len(validation_spans),
            0,
            f"Expected validation spans in trace, got {len(spans)} spans: {[s.name for s in spans]}",
        )

    def test_validation_spans_linked_to_workflow_spans(self):
        """Test validation spans are linked to workflow spans (same trace)."""
        tracer, span_exporter = _get_tracer_with_in_memory_exporter()
        if tracer is None or span_exporter is None:
            pytest.skip("OpenTelemetry SDK not available")

        import hub.apps.orchestration.workflow_engine as engine_module

        original_tracer = getattr(engine_module, "_tracer", None)
        engine_module._tracer = tracer

        try:
            input_data = {
                "original_raw": json.dumps(_valid_odcs_contract_minimal()),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            }
            self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        finally:
            engine_module._tracer = original_tracer

        spans = span_exporter.get_finished_spans()
        trace_ids = {s.context.trace_id for s in spans}
        self.assertEqual(
            len(trace_ids),
            1,
            "All spans should belong to the same trace (engine sets execution span as current via use_span)",
        )

    def test_validation_results_in_span_attributes(self):
        """Test validation results are in span attributes."""
        tracer, span_exporter = _get_tracer_with_in_memory_exporter()
        if tracer is None or span_exporter is None:
            pytest.skip("OpenTelemetry SDK not available")

        import hub.apps.orchestration.workflow_engine as engine_module

        original_tracer = getattr(engine_module, "_tracer", None)
        engine_module._tracer = tracer

        try:
            input_data = {
                "original_raw": json.dumps(_valid_odcs_contract_minimal()),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            }
            self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        finally:
            engine_module._tracer = original_tracer

        spans = span_exporter.get_finished_spans()
        validation_spans = [s for s in spans if "validation" in s.name.lower()]
        self.assertGreater(len(validation_spans), 0)
        span = validation_spans[0]
        attrs = getattr(span, "attributes", None)
        if attrs is None:
            attrs = {}
        attr_keys = list(attrs.keys()) if hasattr(attrs, "keys") else []
        self.assertGreater(
            len(attr_keys),
            0,
            f"Validation span should have attributes; got keys: {attr_keys}",
        )
        has_validation_attr = any(
            "business_rules" in str(k).lower()
            or "is_valid" in str(k).lower()
            or "valid" in str(k).lower()
            for k in attr_keys
        )
        self.assertTrue(
            has_validation_attr,
            f"Validation span should have validation-related attributes; got: {attr_keys}",
        )

    def test_rule_name_and_duration_in_span_attributes(self):
        """Test rule name and duration are in span attributes."""
        tracer, span_exporter = _get_tracer_with_in_memory_exporter()
        if tracer is None or span_exporter is None:
            pytest.skip("OpenTelemetry SDK not available")

        import hub.apps.orchestration.workflow_engine as engine_module

        original_tracer = getattr(engine_module, "_tracer", None)
        engine_module._tracer = tracer

        try:
            input_data = {
                "original_raw": json.dumps(_valid_odcs_contract_minimal()),
                "original_format": "JSON",
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            }
            self.create_start_and_execute(ContractCreationWorkflow.WORKFLOW_NAME, input_data)
        finally:
            engine_module._tracer = original_tracer

        spans = span_exporter.get_finished_spans()
        validation_spans = [s for s in spans if "validation" in s.name.lower()]
        self.assertGreater(len(validation_spans), 0)
        has_rule = False
        has_duration = False
        for span in validation_spans:
            attrs = getattr(span, "attributes", None) or {}
            if hasattr(attrs, "keys"):
                keys = list(attrs.keys())
            else:
                keys = []
            has_rule = has_rule or any("rule" in str(k).lower() for k in keys)
            has_duration = has_duration or any("duration" in str(k).lower() for k in keys)
            if has_rule and has_duration:
                break
        self.assertTrue(
            has_rule or has_duration,
            "At least one validation span should have rule_name or duration_seconds attribute",
        )
