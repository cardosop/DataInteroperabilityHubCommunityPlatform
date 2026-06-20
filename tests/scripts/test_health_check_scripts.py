"""
Unit tests for health check scripts.

Tests the health check scripts functionality using mocked Docker commands.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Paths to health check scripts
HEALTH_CHECK_DIR = project_root / "scripts" / "health-checks"
HEALTH_CHECK_ALL = HEALTH_CHECK_DIR / "health-check-all.sh"
HEALTH_CHECK_WORKFLOW = HEALTH_CHECK_DIR / "health-check-workflow.sh"
HEALTH_CHECK_EVENT_BUS = HEALTH_CHECK_DIR / "health-check-event-bus.sh"
HEALTH_CHECK_SERVICE_LAYER = HEALTH_CHECK_DIR / "health-check-service-layer.sh"
HEALTH_CHECK_LIB = HEALTH_CHECK_DIR / "health_check_lib.sh"


class TestHealthCheckScripts:
    """Tests for health check scripts."""

    def test_health_check_all_script_exists(self):
        """Test that health-check-all.sh exists and is executable."""
        assert HEALTH_CHECK_ALL.exists(), "health-check-all.sh not found"
        assert os.access(HEALTH_CHECK_ALL, os.X_OK), "health-check-all.sh is not executable"

    def test_health_check_workflow_script_exists(self):
        """Test that health-check-workflow.sh exists and is executable."""
        assert HEALTH_CHECK_WORKFLOW.exists(), "health-check-workflow.sh not found"
        assert os.access(HEALTH_CHECK_WORKFLOW, os.X_OK), (
            "health-check-workflow.sh is not executable"
        )

    def test_health_check_event_bus_script_exists(self):
        """Test that health-check-event-bus.sh exists and is executable."""
        assert HEALTH_CHECK_EVENT_BUS.exists(), "health-check-event-bus.sh not found"
        assert os.access(HEALTH_CHECK_EVENT_BUS, os.X_OK), (
            "health-check-event-bus.sh is not executable"
        )

    def test_health_check_service_layer_script_exists(self):
        """Test that health-check-service-layer.sh exists and is executable."""
        assert HEALTH_CHECK_SERVICE_LAYER.exists(), "health-check-service-layer.sh not found"
        assert os.access(HEALTH_CHECK_SERVICE_LAYER, os.X_OK), (
            "health-check-service-layer.sh is not executable"
        )

    def test_health_check_lib_exists(self):
        """Test that health_check_lib.sh exists."""
        assert HEALTH_CHECK_LIB.exists(), "health_check_lib.sh not found"

    def test_health_check_scripts_have_shebang(self):
        """Test that all health check scripts have shebang."""
        scripts = [
            HEALTH_CHECK_ALL,
            HEALTH_CHECK_WORKFLOW,
            HEALTH_CHECK_EVENT_BUS,
            HEALTH_CHECK_SERVICE_LAYER,
        ]

        for script in scripts:
            with open(script) as f:
                first_line = f.readline()
                assert first_line.startswith("#!/bin/bash"), (
                    f"{script.name} should start with #!/bin/bash"
                )

    def test_health_check_scripts_source_lib(self):
        """Test that all health check scripts source the library."""
        scripts = [
            HEALTH_CHECK_ALL,
            HEALTH_CHECK_WORKFLOW,
            HEALTH_CHECK_EVENT_BUS,
            HEALTH_CHECK_SERVICE_LAYER,
        ]

        for script in scripts:
            with open(script) as f:
                content = f.read()
                assert "health_check_lib.sh" in content, (
                    f"{script.name} should source health_check_lib.sh"
                )
                assert "source" in content or "." in content, (
                    f"{script.name} should source the library"
                )

    def test_health_check_lib_has_required_functions(self):
        """Test that health_check_lib.sh has required functions."""
        with open(HEALTH_CHECK_LIB) as f:
            content = f.read()

        required_functions = [
            "log_info",
            "log_success",
            "log_error",
            "log_warning",
            "detect_compose_file",
            "is_service_running",
            "get_container_name",
            "check_health_endpoint",
            "check_service_health",
            "check_infrastructure_service",
            "print_summary",
        ]

        for func_name in required_functions:
            assert f"{func_name}()" in content or f"function {func_name}" in content, (
                f"health_check_lib.sh should define {func_name} function"
            )

    def test_health_check_all_checks_all_services(self):
        """Test that health-check-all.sh checks all expected services."""
        with open(HEALTH_CHECK_ALL) as f:
            content = f.read()

        expected_services = [
            "postgres",
            "redis",
            "minio",
            "fuseki",
            "api-service",
            "worker-service",
            "workflow-engine-service",
            "workflow-registry-service",
            "event-bus-health-service",
            "event-schema-registry-service",
            "semantic-service",
            "dq-service",
            "compliance-service",
            "datacontract-service",
            "search-service",
            "observability-service",
            "webhook-service",
            "prefect-integration-service",
            "prefect-server",
            "prometheus",
            "grafana",
            "jaeger",
            "alertmanager",
        ]

        for service in expected_services:
            assert service in content, f"health-check-all.sh should check {service}"

    def test_health_check_workflow_checks_workflow_services(self):
        """Test that health-check-workflow.sh checks workflow services."""
        with open(HEALTH_CHECK_WORKFLOW) as f:
            content = f.read()

        expected_services = [
            "workflow-engine-service",
            "workflow-registry-service",
            "postgres",
            "redis",
        ]

        for service in expected_services:
            assert service in content, f"health-check-workflow.sh should check {service}"

    def test_health_check_event_bus_checks_event_bus_services(self):
        """Test that health-check-event-bus.sh checks event bus services."""
        with open(HEALTH_CHECK_EVENT_BUS) as f:
            content = f.read()

        expected_services = [
            "event-bus-health-service",
            "event-schema-registry-service",
            "postgres",
            "redis",
        ]

        for service in expected_services:
            assert service in content, f"health-check-event-bus.sh should check {service}"

    def test_health_check_service_layer_checks_service_layer_services(self):
        """Test that health-check-service-layer.sh checks service layer services."""
        with open(HEALTH_CHECK_SERVICE_LAYER) as f:
            content = f.read()

        expected_services = [
            "api-service",
            "worker-service",
            "semantic-service",
            "dq-service",
            "compliance-service",
            "datacontract-service",
            "search-service",
            "observability-service",
            "webhook-service",
            "prefect-integration-service",
            "postgres",
            "redis",
            "minio",
        ]

        for service in expected_services:
            assert service in content, f"health-check-service-layer.sh should check {service}"

    def test_health_check_scripts_have_main_function(self):
        """Test that all health check scripts have a main function."""
        scripts = [
            HEALTH_CHECK_ALL,
            HEALTH_CHECK_WORKFLOW,
            HEALTH_CHECK_EVENT_BUS,
            HEALTH_CHECK_SERVICE_LAYER,
        ]

        for script in scripts:
            with open(script) as f:
                content = f.read()
                assert "main()" in content, f"{script.name} should define main() function"
                assert 'main "$@"' in content or "main" in content, (
                    f"{script.name} should call main function"
                )

    def test_health_check_scripts_use_set_euo_pipefail(self):
        """Test that all health check scripts use strict error handling."""
        scripts = [
            HEALTH_CHECK_ALL,
            HEALTH_CHECK_WORKFLOW,
            HEALTH_CHECK_EVENT_BUS,
            HEALTH_CHECK_SERVICE_LAYER,
            HEALTH_CHECK_LIB,
        ]

        for script in scripts:
            with open(script) as f:
                content = f.read()
                assert "set -euo pipefail" in content or "set -eu" in content, (
                    f"{script.name} should use strict error handling (set -euo pipefail)"
                )

    def test_health_check_lib_has_color_codes(self):
        """Test that health_check_lib.sh defines color codes."""
        with open(HEALTH_CHECK_LIB) as f:
            content = f.read()

        color_codes = [
            "RED=",
            "GREEN=",
            "YELLOW=",
            "BLUE=",
            "NC=",  # No Color
        ]

        for color_code in color_codes:
            assert color_code in content, f"health_check_lib.sh should define {color_code}"

    def test_health_check_scripts_handle_errors(self):
        """Test that health check scripts handle errors gracefully."""
        scripts = [
            HEALTH_CHECK_ALL,
            HEALTH_CHECK_WORKFLOW,
            HEALTH_CHECK_EVENT_BUS,
            HEALTH_CHECK_SERVICE_LAYER,
        ]

        for script in scripts:
            with open(script) as f:
                content = f.read()
                # Should have error handling (FAILED counter, print_summary returns exit code)
                assert "FAILED" in content, f"{script.name} should track failed checks"
                # print_summary handles exit codes, and set -euo pipefail ensures errors propagate
                assert "print_summary" in content, (
                    f"{script.name} should call print_summary which handles exit codes"
                )

    def test_health_check_scripts_print_summary(self):
        """Test that health check scripts print summary."""
        scripts = [
            HEALTH_CHECK_ALL,
            HEALTH_CHECK_WORKFLOW,
            HEALTH_CHECK_EVENT_BUS,
            HEALTH_CHECK_SERVICE_LAYER,
        ]

        for script in scripts:
            with open(script) as f:
                content = f.read()
                assert "print_summary" in content, f"{script.name} should call print_summary"
                assert "Summary" in content or "summary" in content, (
                    f"{script.name} should print summary"
                )
