"""
OpenTelemetry Configuration

Comprehensive OpenTelemetry setup for distributed tracing and metrics.
Supports both OTLP (OpenTelemetry Protocol) and Jaeger exporters.

This module provides:
- Service name and resource attribute configuration
- Trace exporter setup (OTLP or Jaeger)
- Django and HTTP client instrumentation
- Environment-aware configuration (dev/staging/production)

Usage:
    The configuration is automatically initialized when Django starts if
    OPENTELEMETRY_ENABLED=True in settings.

Environment Variables:
    OPENTELEMETRY_ENABLED: Enable OpenTelemetry (default: False)
    OPENTELEMETRY_EXPORTER: Exporter type - 'otlp' or 'jaeger' (default: 'otlp')
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint URL (default: 'http://localhost:4317')
    OTEL_EXPORTER_OTLP_PROTOCOL: OTLP protocol - 'grpc' or 'http/protobuf' (default: 'grpc')
    JAEGER_AGENT_HOST: Jaeger agent host (default: 'jaeger')
    JAEGER_AGENT_PORT: Jaeger agent port (default: 6831)
    OTEL_SERVICE_NAME: Service name (default: 'data-interoperability-hub-api')
    OTEL_SERVICE_VERSION: Service version (default: from settings.APP_VERSION or '1.0.0')
    OTEL_ENVIRONMENT: Environment name - 'development', 'staging', 'production' (default: based on DEBUG)
    OTEL_TRACES_SAMPLER: Sampling strategy - 'always_on', 'always_off', 'traceidratio' (default: based on environment)
    OTEL_TRACES_SAMPLER_ARG: Sampling rate for traceidratio (default: 1.0 for dev, 0.1 for prod)
"""

import logging
import os
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings

if TYPE_CHECKING:
    from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

# OpenTelemetry availability flag
OPENTELEMETRY_AVAILABLE = False
try:
    from opentelemetry import metrics, trace
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_OFF,
        ALWAYS_ON,
        TraceIdRatioBased,
    )

    OPENTELEMETRY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OpenTelemetry packages not available: {e}")
    OPENTELEMETRY_AVAILABLE = False


def get_service_name() -> str:
    """
    Get service name from environment or settings.

    Returns:
        Service name (default: 'data-interoperability-hub-api')
    """
    return os.getenv(
        "OTEL_SERVICE_NAME", getattr(settings, "OTEL_SERVICE_NAME", "data-interoperability-hub-api")
    )


def get_service_version() -> str:
    """
    Get service version from environment or settings.

    Returns:
        Service version — from OTEL_SERVICE_VERSION env var, then
        settings.OTEL_SERVICE_VERSION (populated from GIT_SHA build arg),
        then settings.APP_VERSION legacy fallback, then '1.0.0'.
    """
    # "unknown" is the sentinel used by the Dockerfile (ARG GIT_SHA=unknown)
    # and settings.py (default="unknown") when no real version is available.
    _SENTINEL = "unknown"

    # Check env var first (set by Dockerfile ENV OTEL_SERVICE_VERSION=${GIT_SHA})
    env_version = os.getenv("OTEL_SERVICE_VERSION")
    if env_version and env_version != _SENTINEL:
        return env_version
    # Check settings (populated from the same env var at startup)
    settings_version = getattr(settings, "OTEL_SERVICE_VERSION", None)
    if settings_version and settings_version != _SENTINEL:
        return settings_version
    # Legacy fallback
    app_version = getattr(settings, "APP_VERSION", None)
    if app_version:
        return app_version
    return "1.0.0"


def get_environment() -> str:
    """
    Determine environment name.

    Priority:
      1. OTEL_ENVIRONMENT env var (explicit override)
      2. settings.ENVIRONMENT (Django canonical environment, set by Phase 1 guard)
      3. DEBUG flag heuristic (development fallback)

    Returns:
        Environment name: 'development', 'staging', or 'production'
    """
    env_name = os.getenv("OTEL_ENVIRONMENT", "").lower()
    if env_name in ("development", "staging", "production"):
        return env_name

    # Use the Django ENVIRONMENT setting as the canonical source
    # (set in settings.py from the ENVIRONMENT env var, e.g. 'production')
    django_env = getattr(settings, "ENVIRONMENT", "").lower()
    if django_env in ("development", "staging", "production"):
        return django_env

    # Final heuristic fallback
    return "development" if getattr(settings, "DEBUG", False) else "production"


def get_sampling_config() -> tuple:
    """
    Get trace sampling configuration based on environment.

    Returns:
        Tuple of (sampler, sampling_rate)
        - development: Always on (100%)
        - staging: 50% sampling
        - production: 10% sampling (configurable)
    """
    sampler_type = os.getenv("OTEL_TRACES_SAMPLER", "").lower()
    environment = get_environment()

    # Check for explicit sampler configuration
    if sampler_type == "always_on":
        return ALWAYS_ON, 1.0
    elif sampler_type == "always_off":
        return ALWAYS_OFF, 0.0
    elif sampler_type == "traceidratio":
        sampling_rate = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))
        return TraceIdRatioBased(sampling_rate), sampling_rate

    # Environment-based defaults
    if environment == "development":
        return ALWAYS_ON, 1.0
    elif environment == "staging":
        sampling_rate = 0.5
        return TraceIdRatioBased(sampling_rate), sampling_rate
    else:  # production
        sampling_rate = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "0.1"))
        return TraceIdRatioBased(sampling_rate), sampling_rate


def create_resource() -> Optional["Resource"]:
    """
    Create OpenTelemetry resource with service attributes.

    Standard OTEL keys (service.name, service.version, deployment.environment,
    service.namespace) are always resolved dynamically via helper functions so
    they respect environment variables, Django override_settings, and the full
    fallback chain.  settings.OTEL_RESOURCE_ATTRIBUTES supplies any additional
    custom keys (e.g. deployment.region added by Vault).

    Returns:
        Resource instance or None if OpenTelemetry not available
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None

    # Start with any extra keys from settings (custom labels, etc.)
    resource_attributes: dict[str, str] = dict(getattr(settings, "OTEL_RESOURCE_ATTRIBUTES", {}))

    # Always resolve standard keys dynamically — the helpers inspect
    # env vars and current settings, so they stay correct even when
    # settings are overridden (e.g. in tests) or the pre-built dict
    # carries stale/sentinel values from module-load time.
    resource_attributes["service.name"] = get_service_name()
    resource_attributes["service.version"] = get_service_version()
    resource_attributes["deployment.environment"] = get_environment()
    resource_attributes["service.namespace"] = getattr(settings, "OTEL_SERVICE_NAMESPACE", "hub")

    # Optional deployment-specific attributes (set via Django settings or Vault)
    if hasattr(settings, "DEPLOYMENT_REGION"):
        resource_attributes["deployment.region"] = settings.DEPLOYMENT_REGION
    if hasattr(settings, "INSTANCE_ID"):
        resource_attributes["service.instance.id"] = settings.INSTANCE_ID

    return Resource.create(resource_attributes)


def create_otlp_exporter():
    """
    Create OTLP trace exporter.

    Returns:
        OTLP exporter instance or None if not available
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        )

        # Support both gRPC and HTTP/protobuf protocols
        protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").lower()

        if protocol == "http/protobuf":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter as HTTPOTLPSpanExporter,
            )

            exporter = HTTPOTLPSpanExporter(endpoint=endpoint)
        else:
            exporter = OTLPSpanExporter(endpoint=endpoint)

        logger.info(f"OTLP exporter configured: endpoint={endpoint}, protocol={protocol}")
        return exporter
    except ImportError:
        logger.warning("OTLP exporter not available. Install opentelemetry-exporter-otlp")
        return None


def create_jaeger_exporter():
    """
    Create Jaeger trace exporter.

    Returns:
        Jaeger exporter instance or None if not available
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None

    try:
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter

        agent_host = os.getenv("JAEGER_AGENT_HOST", "jaeger")
        agent_port = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

        exporter = JaegerExporter(
            agent_host_name=agent_host,
            agent_port=agent_port,
        )

        logger.info(f"Jaeger exporter configured: host={agent_host}, port={agent_port}")
        return exporter
    except ImportError:
        logger.warning("Jaeger exporter not available. Install opentelemetry-exporter-jaeger")
        return None


def setup_opentelemetry_tracing() -> object | None:
    """
    Set up OpenTelemetry distributed tracing.

    Configures:
    - Service name and resource attributes
    - Trace exporter (OTLP or Jaeger)
    - Sampling strategy based on environment
    - Django and HTTPX instrumentation

    Returns:
        Tracer instance or None if not enabled/available
    """
    if not OPENTELEMETRY_AVAILABLE:
        logger.warning("OpenTelemetry packages not available")
        return None

    if not getattr(settings, "OPENTELEMETRY_ENABLED", False):
        logger.debug("OpenTelemetry tracing disabled")
        return None

    try:
        # Create resource
        resource = create_resource()
        if resource is None:
            logger.error("Failed to create OpenTelemetry resource")
            return None

        # Get sampling configuration
        # Use adaptive sampler if available, otherwise use standard sampler
        try:
            from hub.apps.observability.trace_sampling import get_adaptive_sampler

            # Get base sampling rate
            _, base_sampling_rate = get_sampling_config()

            # Create adaptive sampler
            adaptive_sampler = get_adaptive_sampler(base_sampling_rate=base_sampling_rate)
            if adaptive_sampler:
                sampler = adaptive_sampler
                logger.info(f"Using adaptive trace sampler with base rate: {base_sampling_rate}")
            else:
                sampler, sampling_rate = get_sampling_config()
        except ImportError:
            # Fallback to standard sampler if adaptive sampler not available
            sampler, sampling_rate = get_sampling_config()

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource, sampler=sampler)
        trace.set_tracer_provider(tracer_provider)

        # Determine exporter type
        exporter_type = os.getenv("OPENTELEMETRY_EXPORTER", "otlp").lower()

        # Create exporter
        if exporter_type == "jaeger":
            exporter = create_jaeger_exporter()
        else:  # default to OTLP
            exporter = create_otlp_exporter()

        if exporter is None:
            logger.error(f"Failed to create {exporter_type} exporter")
            return None

        # Add span processor
        span_processor = BatchSpanProcessor(exporter)
        tracer_provider.add_span_processor(span_processor)

        # Get tracer
        tracer = trace.get_tracer(__name__)

        # Instrument Django
        DjangoInstrumentor().instrument()
        logger.info("Django instrumentation enabled")

        # Instrument HTTPX client
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX client instrumentation enabled")

        # Log configuration
        environment = get_environment()
        service_name = get_service_name()
        logger.info(
            f"OpenTelemetry tracing configured: "
            f"service={service_name}, environment={environment}, "
            f"sampling_rate={sampling_rate}, exporter={exporter_type}"
        )

        return tracer

    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry tracing: {e}", exc_info=True)
        return None


def get_tracer(name: str | None = None) -> object | None:
    """
    Get OpenTelemetry tracer instance.

    Args:
        name: Tracer name (default: __name__)

    Returns:
        Tracer instance or None if not enabled/available
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None

    if not getattr(settings, "OPENTELEMETRY_ENABLED", False):
        return None

    try:
        return trace.get_tracer(name or __name__)
    except Exception:
        return None


def get_current_span():
    """
    Get current active span.

    Returns:
        Current span or None if not available
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None

    try:
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return span
        return None
    except Exception:
        return None


def add_span_attributes(attributes: dict[str, Any]):
    """
    Add attributes to the current span.

    Args:
        attributes: Dictionary of attribute key-value pairs
    """
    span = get_current_span()
    if span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
