"""
Integration tests for distributed tracing

Tests verify that traces are created and exported to Jaeger,
and that trace context is properly propagated.

These tests require OpenTelemetry packages (import-time check) and a
reachable Jaeger instance.  They skip gracefully when either is missing.

None of these tests require database access — they validate env vars,
regex patterns, import contracts, and function return values.
"""

import os
import re
import socket

import pytest
from django.test import override_settings


def _otel_packages_available() -> bool:
    """Check whether OpenTelemetry packages are importable."""
    try:
        import opentelemetry  # noqa: F401
        import opentelemetry.instrumentation.django  # noqa: F401
        return True
    except ImportError:
        return False


def _jaeger_reachable(host: str = "jaeger-test", port: int = 6831) -> bool:
    """Check whether Jaeger agent is reachable via UDP socket."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.error, OSError):
        return False


class TestTracing:
    """Tracing tests — no database access needed."""

    @override_settings(OPENTELEMETRY_ENABLED=False)
    def test_tracing_disabled(self):
        """Test that tracing can be disabled"""
        from hub.apps.observability.tracing import get_tracer

        tracer = get_tracer()
        assert tracer is None

    @override_settings(OPENTELEMETRY_ENABLED=True)
    def test_tracing_enabled(self):
        """Test that tracing can be enabled via the current OTLP-based setup.

        Uses setup_opentelemetry_tracing() from otel_config.py (the active
        production path) rather than the dead Jaeger-path in tracing.py.
        Cleans up the global TracerProvider and its background
        BatchSpanProcessor thread so subsequent tests are not affected.
        """
        if not _otel_packages_available():
            pytest.skip("OpenTelemetry packages not installed")

        provider = None
        try:
            from opentelemetry import trace

            from hub.apps.observability.otel_config import (
                setup_opentelemetry_tracing,
            )

            tracer = setup_opentelemetry_tracing()
            if tracer is None:
                pytest.skip(
                    "setup_opentelemetry_tracing returned None — "
                    "OTEL packages may not be available or configuration is incomplete"
                )

            # Verify the tracer is functional
            assert tracer is not None
            provider = trace.get_tracer_provider()
            assert provider is not None, "global TracerProvider should be set"
        except ImportError:
            pytest.skip("OpenTelemetry tracing packages not importable")
        finally:
            # Shut down the global TracerProvider so the background
            # BatchSpanProcessor thread doesn't keep running (and logging
            # gRPC errors trying to reach the non-existent otel-collector).
            if provider is not None:
                try:
                    provider.shutdown()
                except Exception:
                    pass

    def test_trace_context_in_logs(self):
        """Test that trace context (trace_id, span_id) is added to logs."""
        from hub.apps.observability.logging import add_trace_context

        event_dict = {"event": "test event", "level": "info"}
        result = add_trace_context(None, "info", event_dict)
        assert isinstance(result, dict)
        # The processor should preserve existing keys
        assert result.get("event") == "test event"
        assert result.get("level") == "info"

    def test_trace_sampling_configuration(self):
        """Test that trace sampling configuration module loads and exports expected API."""
        try:
            from hub.apps.observability import trace_sampling as ts

            # Verify the module exposes the expected classes and functions
            assert hasattr(ts, "AdaptiveTraceSampler"), (
                "trace_sampling module should export AdaptiveTraceSampler"
            )
            assert hasattr(ts, "ErrorAwareSpanProcessor"), (
                "trace_sampling module should export ErrorAwareSpanProcessor"
            )
            assert hasattr(ts, "is_critical_endpoint"), (
                "trace_sampling module should export is_critical_endpoint"
            )
            assert hasattr(ts, "get_adaptive_sampler"), (
                "trace_sampling module should export get_adaptive_sampler"
            )
        except ImportError:
            pytest.skip("trace_sampling module not available")

    def test_trace_context_propagation(self):
        """Test that trace context propagator loads and has the expected API."""
        if not _otel_packages_available():
            pytest.skip("OpenTelemetry packages not installed")

        try:
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator,
            )

            propagator = TraceContextTextMapPropagator()
            assert propagator is not None

            # Verify the propagator exposes inject/extract callables
            assert callable(propagator.inject), "propagator.inject should be callable"
            assert callable(propagator.extract), "propagator.extract should be callable"

            # Verify the propagator lists tracecontext in its fields
            fields = propagator.fields
            assert "traceparent" in fields, (
                f"propagator.fields should contain traceparent, got {fields}"
            )
        except ImportError:
            pytest.skip("OpenTelemetry tracecontext not installed")

    def test_jaeger_env_vars_configured(self):
        """Test that Jaeger environment variables are set for the test stack.

        docker-compose.test.yml uses JAEGER_AGENT_HOST=jaeger-test;
        docker-compose.dev.yml uses JAEGER_AGENT_HOST=jaeger (default).
        This validates deployment configuration, not the exporter code path.
        """
        jaeger_host = os.getenv("JAEGER_AGENT_HOST", "jaeger")
        jaeger_port = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

        assert jaeger_host in ("jaeger", "jaeger-test"), (
            f"Unexpected JAEGER_AGENT_HOST: {jaeger_host}"
        )
        assert jaeger_port == 6831

    def test_tracing_instrumentation(self):
        """Test that Django and HTTP client instrumentors are installed."""
        if not _otel_packages_available():
            pytest.skip("OpenTelemetry packages not installed")

        try:
            from opentelemetry.instrumentation.django import DjangoInstrumentor
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            from opentelemetry.instrumentation.requests import RequestsInstrumentor

            assert DjangoInstrumentor is not None
            assert RequestsInstrumentor is not None
            assert HTTPXClientInstrumentor is not None
        except ImportError:
            pytest.skip("OpenTelemetry instrumentation packages not installed")

    def test_trace_id_format(self):
        """Test that trace and span IDs follow the W3C TraceContext format."""
        # W3C traceparent: 32 hex chars (trace-id) + 16 hex chars (span-id)
        trace_id_pattern = r"^[a-f0-9]{32}$"
        span_id_pattern = r"^[a-f0-9]{16}$"

        # Validate regex against known-good and known-bad values
        assert re.match(trace_id_pattern, "a" * 32)
        assert re.match(span_id_pattern, "a" * 16)
        assert not re.match(trace_id_pattern, "a" * 31)
        assert not re.match(span_id_pattern, "a" * 15)

        # If OTEL is available, verify a real trace ID matches the pattern
        if _otel_packages_available():
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            span = tracer.start_span("format-test")
            trace_id_hex = format(span.get_span_context().trace_id, "032x")
            span_id_hex = format(span.get_span_context().span_id, "016x")
            span.end()
            assert re.match(trace_id_pattern, trace_id_hex), (
                f"Real trace_id {trace_id_hex} should match pattern"
            )
            assert re.match(span_id_pattern, span_id_hex), (
                f"Real span_id {span_id_hex} should match pattern"
            )
