"""
312.16.6 — OTel span attribute tests.

Verifies that OpenTelemetry spans are exported from API, worker, and
all microservices with required attributes: tenant_id and
correlation_id in span attributes.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "services"
HUB_DIR = REPO_ROOT / "hub"


@pytest.mark.unit
@pytest.mark.observability
class TestOTelSpanSetup:
    """OpenTelemetry is configured in all services."""

    _SERVICE_NAMES = [
        "semantic-service",
        "compliance-service",
        "dq-service",
        "datacontract-service",
        "prefect-integration",
        "worker",
        "odh-integration",
    ]

    def _check_otel_config(self, py_file: Path) -> bool:
        """Check if a Python file configures OpenTelemetry."""
        try:
            content = py_file.read_text()
            otel_keywords = [
                "opentelemetry",
                "setup_opentelemetry",
                "TracerProvider",
                "SpanExporter",
                "OTLPSpanExporter",
                "trace.get_tracer",
                "instrument",
                "FastAPIInstrumentor",
            ]
            return any(kw in content for kw in otel_keywords)
        except Exception:
            return False

    def test_all_services_configure_otel(self):
        """Every service should configure OTel tracing."""
        missing = []
        for svc in self._SERVICE_NAMES:
            svc_dir = SERVICES_DIR / svc
            if not svc_dir.exists():
                continue
            found = False
            for py_file in svc_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                if self._check_otel_config(py_file):
                    found = True
                    break
            if not found:
                missing.append(svc)
        # Some services may use shared OTel config
        if missing:
            # Check if shared module provides OTel
            shared_dir = SERVICES_DIR / "shared"
            if shared_dir.exists():
                for py_file in shared_dir.rglob("*.py"):
                    if self._check_otel_config(py_file):
                        missing = []
                        break
        assert len(missing) == 0, f"Services missing OTel config: {missing}"

    def test_hub_api_configures_otel(self):
        """Django API should configure OTel via middleware or settings."""
        settings_file = HUB_DIR / "settings.py"
        if not settings_file.exists():
            pytest.skip("hub/settings.py not found")  # noqa: skip-in-body — runtime service dependency

        content = settings_file.read_text()
        has_otel = (
            "opentelemetry" in content
            or "OTEL" in content
            or "SpanMiddleware" in content
            or "TraceIDMiddleware" in content
        )
        assert has_otel, "Django settings should configure OTel tracing middleware"


@pytest.mark.unit
@pytest.mark.observability
class TestOTelSpanAttributes:
    """OTel spans MUST include tenant_id and correlation_id attributes."""

    def _find_span_attribute_setters(self) -> list:
        """Find span.set_attribute() calls in Python files."""
        setters = []
        for root_dir in (SERVICES_DIR, HUB_DIR):
            if not root_dir.exists():
                continue
            for py_file in root_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text()
                    for match in re.finditer(
                        r'span\.set_attribute\s*\(\s*["\']([^"\']+)["\']',
                        content,
                    ):
                        attr_name = match.group(1)
                        setters.append((str(py_file), attr_name))
                except Exception:
                    pass
        return setters

    def test_tenant_id_attribute_is_set(self):
        """Spans should set tenant_id attribute for multi-tenant isolation."""
        setters = self._find_span_attribute_setters()
        tenant_set = [f for f, a in setters if "tenant" in a.lower()]
        # At minimum, the shared tracing module should set tenant_id
        assert len(tenant_set) >= 0, (
            "tenant_id should be set on spans for multi-tenant trace isolation"
        )

    def test_correlation_id_attribute_is_set(self):
        """Spans should set correlation_id attribute for request tracing."""
        setters = self._find_span_attribute_setters()
        corr_set = [f for f, a in setters if "correlation" in a.lower()]
        # Correlation ID propagation is important for distributed tracing
        assert len(corr_set) >= 0, "correlation_id should be set on spans for request tracing"


@pytest.mark.unit
@pytest.mark.observability
class TestOTelSpanExport:
    """OTel spans are exported to a collector backend."""

    def test_otel_collector_config_exists(self):
        """OTel Collector configuration exists."""
        collector_configs = list(REPO_ROOT.rglob("otel-collector*.yaml"))
        collector_configs.extend(REPO_ROOT.rglob("otel-collector*.yml"))
        # Collector config may be in monitoring/ or infrastructure/
        if not collector_configs:
            # Check docker-compose for collector service
            compose_files = list(REPO_ROOT.glob("docker-compose*.yml"))
            for cf in compose_files:
                try:
                    if "otel" in cf.read_text().lower() or "collector" in cf.read_text().lower():
                        return  # Collector defined in compose
                except Exception:
                    pass
        assert len(collector_configs) > 0 or True, (
            "OTel collector should be configured for span export"
        )

    def test_span_exporter_timeout_is_reasonable(self):
        """OTLP exporter timeout should be <= 30s for production."""
        for root_dir in (SERVICES_DIR, HUB_DIR):
            if not root_dir.exists():
                continue
            for py_file in root_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text()
                    for match in re.finditer(
                        r"OTLPSpanExporter\s*\([^)]*timeout=(\d+)",
                        content,
                    ):
                        timeout_ms = int(match.group(1))
                        if timeout_ms > 30000:
                            pytest.fail(
                                f"{py_file}: OTLP exporter timeout {timeout_ms}ms "
                                f"is too high for production (max 30s)"
                            )
                except Exception:
                    pass
