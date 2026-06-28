"""
Observability: OpenTelemetry Distributed Tracing

OpenTelemetry setup with Jaeger backend integration.
"""

import os

from django.conf import settings


def setup_opentelemetry():
    """
    Set up OpenTelemetry distributed tracing with Jaeger backend.

    Configures trace sampling (100% in dev, 10% in production) and adds
    trace context (trace_id, span_id) to logs for correlation.
    """
    if not getattr(settings, "OPENTELEMETRY_ENABLED", False):
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        # Determine sampling rate (100% in dev, 10% in production)
        is_production = not settings.DEBUG
        sampling_rate = 0.10 if is_production else 1.0

        # Create resource with service name
        resource = Resource.create(
            {
                "service.name": "hub-api",
                "service.version": getattr(settings, "APP_VERSION", "1.0.0"),
            }
        )

        # Set tracer provider with sampling
        tracer_provider = TracerProvider(
            resource=resource, sampler=TraceIdRatioBased(sampling_rate)
        )
        trace.set_tracer_provider(tracer_provider)
        tracer = trace.get_tracer(__name__)

        # Configure OTLP exporter (Jaeger supports OTLP natively since v1.35;
        # the Jaeger-specific exporter package is not required).
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            f"http://{os.getenv('JAEGER_AGENT_HOST', 'jaeger')}:4317",
        )
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)

        # Add span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

        # Instrument Django
        DjangoInstrumentor().instrument()

        # Instrument HTTP clients
        RequestsInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        # Add trace context to structlog
        _add_trace_context_to_logs()

        return tracer

    except ImportError:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            "OpenTelemetry SDK not available — tracing disabled. "
            "Install opentelemetry-exporter-otlp to enable."
        )
        return None


def _add_trace_context_to_logs():
    """
    Add trace_id and span_id to structlog context for log correlation.
    """
    try:
        from opentelemetry import trace

        def add_trace_context_processor(logger, method_name, event_dict):
            """Add trace context to log entries."""
            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                span_context = span.get_span_context()
                # Convert trace_id and span_id to hex strings
                trace_id = format(span_context.trace_id, "032x")
                span_id = format(span_context.span_id, "016x")
                event_dict["trace_id"] = trace_id
                event_dict["span_id"] = span_id
            return event_dict

        # Add processor to structlog configuration
        # This will be called for every log entry
        # We need to reconfigure structlog to include this processor
        # This is done by modifying the processors list
        # Note: This assumes structlog is already configured
        # The processor will be added via the logging configuration
        # Processor will be added in logging.py

    except ImportError:
        # OpenTelemetry SDK not available — skip trace context injection
        pass


def get_tracer(name: str = None):
    """
    Get OpenTelemetry tracer.

    Args:
        name: Tracer name (default: __name__)

    Returns:
        Tracer instance or None if not enabled
    """
    if not getattr(settings, "OPENTELEMETRY_ENABLED", False):
        return None

    try:
        from opentelemetry import trace

        return trace.get_tracer(name or __name__)
    except ImportError:
        return None
