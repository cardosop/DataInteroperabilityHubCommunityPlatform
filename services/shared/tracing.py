"""
Shared OpenTelemetry Tracing for FastAPI Services

Provides OpenTelemetry setup for FastAPI services with Jaeger exporter.
"""
import os
from typing import Optional


def setup_opentelemetry_fastapi(service_name: str) -> Optional[object]:
    """
    Set up OpenTelemetry distributed tracing for FastAPI services.
    
    Args:
        service_name: Name of the service (e.g., 'semantic-service', 'dq-service')
        
    Returns:
        Tracer instance or None if not enabled
    """
    if not os.getenv('OPENTELEMETRY_ENABLED', 'false').lower() == 'true':
        return None
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
        
        # Determine sampling rate (100% in dev, 10% in production)
        is_production = os.getenv('ENVIRONMENT', 'development') == 'production'
        sampling_rate = 0.10 if is_production else 1.0
        
        # Create resource with service name
        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.getenv('APP_VERSION', '1.0.0'),
        })
        
        # Set tracer provider with sampling
        tracer_provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(sampling_rate)
        )
        trace.set_tracer_provider(tracer_provider)
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
        tracer_provider.add_span_processor(span_processor)
        
        # Instrument FastAPI (will be done in main.py after app creation)
        # Instrument HTTP clients
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


def get_tracer_fastapi(name: str = None) -> Optional[object]:
    """
    Get OpenTelemetry tracer for FastAPI services.
    
    Args:
        name: Tracer name (default: __name__)
        
    Returns:
        Tracer instance or None if not enabled
    """
    if not os.getenv('OPENTELEMETRY_ENABLED', 'false').lower() == 'true':
        return None
    
    try:
        from opentelemetry import trace
        return trace.get_tracer(name or __name__)
    except ImportError:
        return None

