"""
Integration tests validating Phase 17 — Observability and optional infra.

Validates:
- 17.1 Event bus: EVENT_BUS.md has "Publishers by service"
- 17.2 Tracing: MONITORING.md documents W3C trace context and service coverage
- 17.3 Optional: frontend depends_on api-service condition service_healthy;
  DATA_RESIDENCY_RETENTION.md exists
"""
import pytest
import yaml
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent


@pytest.mark.integration
class TestPhase17EventBusDocumentation:
    """17.1 Event bus documentation."""

    def test_event_bus_doc_has_publishers_by_service(self):
        """EVENT_BUS.md must contain 'Publishers by service' section."""
        path = project_root / "docs" / "EVENT_BUS.md"
        assert path.exists(), "docs/EVENT_BUS.md should exist"
        content = path.read_text()
        assert "Publishers by service" in content or "publishers by service" in content.lower(), (
            "EVENT_BUS.md should document publishers by service (Phase 17.1.1)"
        )

    def test_event_bus_doc_lists_api_service_and_microservices(self):
        """EVENT_BUS.md must mention api-service and non-publishing services."""
        path = project_root / "docs" / "EVENT_BUS.md"
        content = path.read_text()
        assert "api-service" in content or "api_service" in content, (
            "EVENT_BUS.md should list api-service as publisher"
        )
        # At least one of semantic/dq/compliance/webhook documented as N/A or Not yet
        keywords = ["semantic-service", "dq-service", "compliance-service", "webhook-service", "N/A", "Not yet"]
        assert any(k in content for k in keywords), (
            "EVENT_BUS.md should document which microservices do not publish"
        )


@pytest.mark.integration
class TestPhase17TracingDocumentation:
    """17.2 Tracing consistency documentation."""

    def test_monitoring_doc_has_w3c_trace_context(self):
        """MONITORING.md must document W3C trace context and service coverage."""
        path = project_root / "docs" / "MONITORING.md"
        assert path.exists(), "docs/MONITORING.md should exist"
        content = path.read_text()
        assert "W3C" in content and ("trace context" in content.lower() or "traceparent" in content.lower()), (
            "MONITORING.md should document W3C trace context (Phase 17.2.1)"
        )

    def test_monitoring_doc_lists_services_tracing(self):
        """MONITORING.md must list which services use trace context."""
        path = project_root / "docs" / "MONITORING.md"
        content = path.read_text()
        assert "api-service" in content and "API Gateway" in content, (
            "MONITORING.md should list api-service and API Gateway trace coverage"
        )


@pytest.mark.integration
class TestPhase17DependsOnAndDataResidency:
    """17.3 Optional: depends_on and data residency."""

    @pytest.fixture(scope="class")
    def docker_compose_config(self):
        """Load docker-compose.yml."""
        path = project_root / "docker-compose.yml"
        assert path.exists(), "docker-compose.yml should exist"
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def test_frontend_depends_on_api_service_healthy(self, docker_compose_config):
        """Frontend must depend on api-service with condition service_healthy (Phase 17.3.1)."""
        services = docker_compose_config.get("services", {})
        frontend = services.get("frontend", {})
        assert frontend, "frontend service should exist"
        depends_on = frontend.get("depends_on", {})
        if isinstance(depends_on, list):
            assert "api-service" in depends_on, "frontend should depend on api-service"
            return
        assert "api-service" in depends_on, "frontend should depend on api-service"
        api_dep = depends_on["api-service"]
        if isinstance(api_dep, dict):
            assert api_dep.get("condition") == "service_healthy", (
                "frontend should use condition: service_healthy for api-service"
            )
        else:
            # legacy: depends_on: [api-service] without condition
            pytest.fail("frontend should use depends_on: api-service: condition: service_healthy")

    def test_data_residency_retention_doc_exists(self):
        """DATA_RESIDENCY_RETENTION.md must exist (Phase 17.3.3)."""
        path = project_root / "docs" / "DATA_RESIDENCY_RETENTION.md"
        assert path.exists(), "docs/DATA_RESIDENCY_RETENTION.md should exist (Phase 17.3.3)"

    def test_data_residency_doc_covers_audit_dlq_jobs(self):
        """DATA_RESIDENCY_RETENTION.md must mention audit, DLQ, job history."""
        path = project_root / "docs" / "DATA_RESIDENCY_RETENTION.md"
        content = path.read_text()
        assert "audit" in content.lower(), "Doc should describe audit events storage/retention"
        assert "DLQ" in content or "dead letter" in content.lower(), "Doc should describe DLQ"
        assert "job" in content.lower(), "Doc should describe job history"
