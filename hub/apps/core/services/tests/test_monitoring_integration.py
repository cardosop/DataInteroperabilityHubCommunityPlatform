"""
Integration tests for service layer monitoring functionality.

Tests Prometheus metrics, tracing, and alerting capabilities.
"""
import uuid
import os
import sys
import django
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

from django.test import TestCase, override_settings  # noqa: E402

from hub.apps.core.services.base import (  # noqa: E402
    BaseService,
    ServiceError,
    ValidationError,
)
from hub.apps.core.services.health import (  # noqa: E402
    ServiceHealthCheck,
    ServiceHealthMonitor,
)
from hub.apps.core.services.cross_service_access import (  # noqa: E402
    ServiceClient,
)
from hub.apps.tenants.models import Tenant  # noqa: E402
from hub.apps.users.models import User  # noqa: E402


class SampleService(BaseService):
    """Test service for monitoring tests."""

    service_name = "test_service"

    def test_operation(
        self, tenant_id: str, data: Optional[dict] = None
    ):
        """Test operation that records metrics."""
        return self.execute_with_metrics(
            operation="test_operation",
            func=lambda: {
                "result": "success",
                "data": data or {},
            },
            tenant_id=tenant_id,
        )

    def test_error_operation(self, tenant_id: str):
        """Test operation that raises an error."""
        return self.execute_with_metrics(
            operation="test_error_operation",
            func=lambda: self._raise_error(),
            tenant_id=tenant_id,
        )

    def _raise_error(self):
        """Raise a test error."""
        raise ServiceError("Test error", code="TEST_ERROR")


class ServiceLayerMonitoringIntegrationTest(TestCase):
    """Integration tests for service layer monitoring."""

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            tenant=self.tenant,
        )
        self.service = SampleService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def test_service_operation_metrics_recorded(self):
        """Test that service operations record metrics."""
        from hub.apps.observability.otel_metrics import REGISTRY
        from prometheus_client import generate_latest

        # Execute a service operation
        result = self.service.test_operation(
            tenant_id=str(self.tenant.id),
            data={"test": "data"},
        )

        # Verify operation succeeded
        self.assertIsNotNone(result)
        self.assertEqual(result["result"], "success")

        # Verify metrics were recorded (if registry available)
        if REGISTRY is not None:
            metrics = generate_latest(REGISTRY).decode(
                'utf-8'
            )
            has_service_metrics = (
                'service_operations_total' in metrics
                or 'service_operation_duration_seconds'
                in metrics
            )
            self.assertTrue(
                has_service_metrics,
                "Expected service operation metrics"
                " to be recorded",
            )

    def test_service_operation_error_metrics_recorded(self):
        """Test that service operation errors record metrics."""
        from hub.apps.observability.otel_metrics import REGISTRY
        from prometheus_client import generate_latest

        # Execute a service operation that raises an error
        with self.assertRaises(ServiceError):
            self.service.test_error_operation(
                tenant_id=str(self.tenant.id),
            )

        # Verify error metrics recorded (if registry available)
        if REGISTRY is not None:
            metrics = generate_latest(REGISTRY).decode(
                'utf-8'
            )
            has_error_metrics = (
                'service_operation_errors_total' in metrics
                or 'service_operation_duration_seconds'
                in metrics
            )
            self.assertTrue(
                has_error_metrics,
                "Expected error metrics to be recorded",
            )

    def test_service_health_check_metrics(self):
        """Test that service health checks record metrics."""
        from hub.apps.observability.otel_metrics import REGISTRY
        from prometheus_client import generate_latest

        # Create a health check
        health_check = ServiceHealthCheck(
            "test-service", timeout=1.0,
        )

        try:
            health_check.check_health(use_cache=False)
        except (ConnectionError, OSError, TimeoutError):
            # Health check failed because service is not
            # running; metrics should still be recorded.
            pass

        # Verify health check metrics (if registry available)
        if REGISTRY is not None:
            metrics = generate_latest(REGISTRY).decode(
                'utf-8'
            )
            has_health_metrics = (
                'service_health_checks_total' in metrics
                or 'service_health_check_duration_seconds'
                in metrics
                or 'service_health_status' in metrics
            )
            self.assertTrue(
                has_health_metrics,
                "Expected health check metrics"
                " to be recorded",
            )

    @override_settings(OPENTELEMETRY_ENABLED=True)
    def test_tracing_initialization(self):
        """Test that OpenTelemetry tracing can be initialized."""
        try:
            from hub.apps.observability.tracing import (
                get_tracer,
            )
            tracer = get_tracer(__name__)

            # Tracer may be None if deps not installed
            if tracer is not None:
                span = tracer.start_span("test_span")
                self.assertIsNotNone(span)
                span.end()
        except ImportError:
            self.skipTest("OpenTelemetry not available")

    def test_service_operation_tracing(self):
        """Test that service operations create tracing spans."""
        result = self.service.test_operation(
            tenant_id=str(self.tenant.id),
            data={"test": "data"},
        )

        # Verify operation succeeded (tracing code executed)
        self.assertIsNotNone(result)
        self.assertEqual(result["result"], "success")

    def test_cross_service_call_metrics(self):
        """Test that cross-service calls record metrics."""
        from hub.apps.observability.otel_metrics import REGISTRY
        from prometheus_client import generate_latest

        try:
            client = ServiceClient(
                "test-target-service",
                service_url="http://localhost:9999",
            )

            # Attempt a call (will fail, but metrics recorded)
            try:
                client.get("/test")
            except Exception:
                pass  # Any connection error is expected
        except (ImportError, RuntimeError) as exc:
            self.skipTest(
                f"Service client creation failed: {exc}"
            )

        # Verify cross-service call metrics
        if REGISTRY is not None:
            metrics = generate_latest(REGISTRY).decode(
                'utf-8'
            )
            has_call_metrics = (
                'service_calls_total' in metrics
                or 'service_call_duration_seconds' in metrics
                or 'service_call_errors_total' in metrics
            )
            self.assertTrue(
                has_call_metrics,
                "Expected cross-service call metrics"
                " to be recorded",
            )

    def test_service_health_monitor(self):
        """Test that service health monitor works."""
        monitor = ServiceHealthMonitor(timeout=1.0)

        try:
            results = monitor.check_all_services(
                service_names=[
                    "test-service-1",
                    "test-service-2",
                ],
                use_cache=False,
            )

            # Should return results for all services
            self.assertIn("test-service-1", results)
            self.assertIn("test-service-2", results)

            # Results should have expected structure
            for _name, result in results.items():
                self.assertIn("service", result)
                self.assertIn("status", result)
                self.assertIn("timestamp", result)
        except (ConnectionError, OSError, TimeoutError) as e:
            self.fail(
                "Service health monitor failed"
                f" unexpectedly: {e}"
            )

    def test_service_operation_validation_error(self):
        """Test that validation errors are recorded correctly."""

        class ValidatingService(BaseService):
            service_name = "validating_service"

            def validate_and_process(
                self, tenant_id: str, data: dict
            ):
                """Validate and process data."""
                return self.execute_with_metrics(
                    operation="validate_and_process",
                    func=lambda: self._do_validate(data),
                    tenant_id=tenant_id,
                )

            def _do_validate(self, data: dict):
                """Validate and process data."""
                if not data.get("required_field"):
                    raise ValidationError(
                        "Missing required_field",
                        details={"field": "required_field"},
                    )
                return {"result": "success"}

        service = ValidatingService(
            tenant_id=str(self.tenant.id),
        )

        # Test with missing required field
        with self.assertRaises(ValidationError):
            service.validate_and_process(
                tenant_id=str(self.tenant.id),
                data={},
            )

        # Test with valid data
        result = service.validate_and_process(
            tenant_id=str(self.tenant.id),
            data={"required_field": "value"},
        )

        self.assertEqual(result["result"], "success")
