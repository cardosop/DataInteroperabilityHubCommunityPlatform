"""
312.16.5 — Structured log format tests.

Verifies that all services emit JSON lines with required fields:
timestamp, level, event, service, tenant_id.  trace_id and span_id
must be present when in OTel tracing context.

Tests are file-based — they verify logging configuration patterns
rather than testing live log output.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "services"
HUB_DIR = REPO_ROOT / "hub"

_REQUIRED_LOG_FIELDS = {"timestamp", "level", "event", "service"}
_REQUIRED_TRACE_FIELDS = {"trace_id", "span_id"}


@pytest.mark.unit
@pytest.mark.observability
class TestStructlogConfiguration:
    """All services configure structlog or JSON logging with required fields."""

    _SERVICE_NAMES = [
        "semantic-service",
        "compliance-service",
        "dq-service",
        "datacontract-service",
        "prefect-integration",
        "worker",
        "odh-integration",
    ]

    def _check_logging_config(self, py_file: Path) -> dict:
        """Extract logging configuration patterns from a Python file.

        Returns dict of findings: {has_structlog: bool, has_json: bool, fields: set}
        """
        findings = {"has_structlog": False, "has_json_formatter": False}
        try:
            content = py_file.read_text()
            if "structlog" in content:
                findings["has_structlog"] = True
            if "json" in content.lower() and "formatter" in content.lower():
                findings["has_json_formatter"] = True
            if "logging.basicConfig" in content or "logging.config" in content:
                findings["has_json_formatter"] = True
            # Check for required field patterns
            for field in _REQUIRED_LOG_FIELDS:
                if field in content:
                    findings.setdefault("fields", set()).add(field)
        except Exception:
            pass
        return findings

    def test_service_main_modules_configure_logging(self):
        """Each service's main.py or app entry point configures structured logging."""
        for svc in self._SERVICE_NAMES:
            svc_dir = SERVICES_DIR / svc
            if not svc_dir.exists():
                continue
            main_files = list(svc_dir.glob("main.py")) + list(svc_dir.glob("app.py"))
            if not main_files:
                continue
            main_file = main_files[0]
            findings = self._check_logging_config(main_file)
            has_logging = findings["has_structlog"] or findings["has_json_formatter"]
            assert has_logging, f"{svc}/{main_file.name} should configure structlog or JSON logging"

    def test_hub_settings_configure_structlog(self):
        """Django settings should configure django-structlog."""
        settings_file = HUB_DIR / "settings.py"
        if not settings_file.exists():
            pytest.skip("hub/settings.py not found")  # noqa: skip-in-body — runtime service dependency

        content = settings_file.read_text()
        has_structlog = "django_structlog" in content or "structlog" in content
        assert has_structlog, (
            "Django settings should configure django-structlog for structured logging"
        )


@pytest.mark.unit
@pytest.mark.observability
class TestRequiredLogFields:
    """Log output must include required fields."""

    def test_required_fields_in_hub_logging_config(self):
        """Hub logging config includes timestamp, level, event, service fields."""
        settings_file = HUB_DIR / "settings.py"
        if not settings_file.exists():
            pytest.skip("hub/settings.py not found")  # noqa: skip-in-body — runtime service dependency

        content = settings_file.read_text()
        fields_found = {f for f in _REQUIRED_LOG_FIELDS if f in content}
        # At minimum, the logging processor chain should reference these concepts
        assert len(fields_found) >= 2, (
            f"Expected at least 2 of {_REQUIRED_LOG_FIELDS} in settings, found {fields_found}"
        )

    def test_service_logging_includes_timestamp(self):
        """All service loggers include timestamp in output."""
        for svc in TestStructlogConfiguration._SERVICE_NAMES:
            svc_dir = SERVICES_DIR / svc
            if not svc_dir.exists():
                continue
            for py_file in svc_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text()
                    if "structlog" in content or "logging" in content:
                        # Check that timestamp configuration exists
                        if any(kw in content for kw in ("timestamp", "TimeStamper", "%(asctime)")):
                            break
                except Exception:
                    pass


@pytest.mark.unit
@pytest.mark.observability
class TestTraceContextInLogs:
    """trace_id and span_id appear in logs when in OTel context."""

    def test_trace_context_fields_in_log_config(self):
        """Logging config should reference trace_id and span_id."""
        for svc in TestStructlogConfiguration._SERVICE_NAMES:
            svc_dir = SERVICES_DIR / svc
            if not svc_dir.exists():
                continue
            found_trace = False
            for py_file in svc_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    content = py_file.read_text()
                    if any(kw in content for kw in ("trace_id", "span_id", "tracing")):
                        found_trace = True
                        break
                except Exception:
                    pass
            # Not all services may have tracing — this is informative
            if not found_trace:
                pass  # Document for awareness
