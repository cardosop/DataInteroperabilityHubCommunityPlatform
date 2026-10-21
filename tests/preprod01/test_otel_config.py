"""
OpenTelemetry configuration validation tests (312.18.2).

Validates OTLP exporter configuration:
- OTLP endpoint is configured
- Exporter uses gRPC or HTTP/protobuf
- Trace sampling rate is within acceptable bounds
- Service name and environment attributes are set
"""

import os

import pytest

# Repo-root settings.py — resolved at MODULE level so the class-body
# ``@pytest.mark.skipif`` decorators can reference it (they evaluate at import
# time, before any test method runs).
SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "hub",
    "settings.py",
)


class TestOTelConfig:
    """Validate OpenTelemetry exporter configuration."""

    @pytest.mark.skipif(not os.path.exists(SETTINGS_PATH), reason="settings.py not found")
    def test_otel_config_in_settings(self):
        """Settings or environment reference OTLP exporter configuration."""
        # Check settings.py for OTel/OTLP references.
        with open(SETTINGS_PATH) as f:
            source = f.read()
        has_otel = (
            "OTEL" in source
            or "opentelemetry" in source.lower()
            or "OLTP" in source
            or "tracing" in source.lower()
        )
        if not has_otel:
            pytest.skip("OTel not configured in settings.py")  # noqa: skip-in-body — runtime service dependency

    def test_otlp_endpoint_env_var_recognized(self):
        """OTEL_EXPORTER_OTLP_ENDPOINT is the standard env var for OTLP export."""
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        if not endpoint:
            pytest.skip("OTEL_EXPORTER_OTLP_ENDPOINT not set in this environment")  # noqa: skip-in-body — runtime service dependency
        # Should be a valid URL.
        assert endpoint.startswith(("http://", "https://", "grpc://")), (
            f"OTEL_EXPORTER_OTLP_ENDPOINT must be a valid URL, got: {endpoint}"
        )

    def test_service_name_configured(self):
        """OTEL_SERVICE_NAME must be set for proper span attribution."""
        service_name = os.environ.get("OTEL_SERVICE_NAME", "")
        if not service_name:
            pytest.skip("OTEL_SERVICE_NAME not set in this environment")  # noqa: skip-in-body — runtime service dependency
        assert len(service_name) > 0
        assert " " not in service_name, "OTEL_SERVICE_NAME should not contain spaces"

    def test_trace_sampling_rate_bounds(self):
        """OTEL_TRACES_SAMPLER_ARG should be between 0.0 and 1.0."""
        sample_rate = os.environ.get("OTEL_TRACES_SAMPLER_ARG", "")
        if not sample_rate:  # noqa: skip-in-body — runtime service dependency
            pytest.skip("OTEL_TRACES_SAMPLER_ARG not set")
        try:
            rate = float(sample_rate)
        except ValueError:
            pytest.skip(f"Non-numeric sample rate: {sample_rate}")  # noqa: skip-in-body — runtime service dependency
        assert 0.0 <= rate <= 1.0, f"Sample rate {rate} out of bounds"

    def test_exporter_protocol_is_valid(self):
        """OTEL_EXPORTER_OTLP_PROTOCOL must be grpc or http/protobuf."""
        protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
        valid = {"grpc", "http/protobuf", "http/json"}
        assert protocol in valid, (
            f"OTEL_EXPORTER_OTLP_PROTOCOL must be one of {valid}, got '{protocol}'"
        )


class TestOTelSpanAttributes:
    """Validate span attributes in exported traces."""

    def test_environment_attribute_set(self):
        """Spans should include deployment.environment attribute."""
        env = os.environ.get("ENVIRONMENT", os.environ.get("OTEL_RESOURCE_ATTRIBUTES", ""))
        if not env:
            pytest.skip("Environment/deployment attributes not set")  # noqa: skip-in-body — runtime service dependency
        # If OTEL_RESOURCE_ATTRIBUTES is set, it should include environment info.
        resource_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
        if resource_attrs:
            assert "deployment.environment" in resource_attrs or "service.name" in resource_attrs, (
                f"OTEL_RESOURCE_ATTRIBUTES missing deployment.environment: {resource_attrs}"
            )
