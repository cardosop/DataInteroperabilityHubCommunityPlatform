"""
Observability: OpenTelemetry Distributed Tracing

OpenTelemetry setup with Jaeger backend integration.
"""
import os
from django.conf import settings


def setup_opentelemetry():
    """
    Set up OpenTelemetry distributed tracing with Jaeger backend.
    """
    if not getattr(settings, 'OPENTELEMETRY_ENABLED', False):
        return
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        
        # Create resource with service name
        resource = Resource.create({
            "service.name": "hub-api",
            "service.version": getattr(settings, 'APP_VERSION', '1.0.0'),
        })
        
        # Set tracer provider
        trace.set_tracer_provider(TracerProvider(resource=resource))
        tracer = trace.get_tracer(__name__)
        
        # Configure Jaeger exporter
        jaeger_agent_host = os.getenv('JAEGER_AGENT_HOST', 'jaeger')
        jaeger_agent_port = int(os.getenv('JAEGER_AGENT_PORT', '6831'))
        
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_agent_host,
            agent_port=jaeger_agent_port,
        )
        
        # Add span processor
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Instrument Django
        DjangoInstrumentor().instrument()
        
        # Instrument HTTP clients
        RequestsInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
        
        return tracer
    
    except ImportError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"OpenTelemetry not available: {e}")
        return None
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to setup OpenTelemetry: {e}")
        return None


def get_tracer(name: str = None):
    """
    Get OpenTelemetry tracer.
    
    Args:
        name: Tracer name (default: __name__)
        
    Returns:
        Tracer instance or None if not enabled
    """
    if not getattr(settings, 'OPENTELEMETRY_ENABLED', False):
        return None
    
    try:
        from opentelemetry import trace
        return trace.get_tracer(name or __name__)
    except ImportError:
        return None

