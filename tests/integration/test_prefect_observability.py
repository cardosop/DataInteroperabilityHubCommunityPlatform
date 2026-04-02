"""
Phase 25.21 — Observability: Prometheus metrics and alerts for Prefect.

Static validation tests (no Django, no running services required):
  - alerts.yml contains the 3 Prefect alert rules with correct structure
  - main.py defines the 4 required metric objects
  - circuit_breaker.py emits the gauge on state transitions
  - deployment_sync.py increments retry counter

Run:
    pytest tests/integration/test_prefect_observability.py -v --noconftest
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent
_ALERTS_PATH = _ROOT / "monitoring" / "prometheus" / "alerts.yml"
_MAIN_PY = _ROOT / "services" / "prefect-integration" / "main.py"
_CB_PY = _ROOT / "services" / "prefect-integration" / "circuit_breaker.py"
_DS_PY = _ROOT / "services" / "prefect-integration" / "deployment_sync.py"


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture(scope="module")
def alerts_yaml() -> dict:
    with open(_ALERTS_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def prefect_alert_rules(alerts_yaml) -> list[dict]:
    """Extract rules from the hub_prefect_alerts group."""
    for group in alerts_yaml.get("groups", []):
        if group.get("name") == "hub_prefect_alerts":
            return group.get("rules", [])
    pytest.fail("Alert group 'hub_prefect_alerts' not found")


@pytest.fixture(scope="module")
def main_py_source() -> str:
    return _MAIN_PY.read_text()


@pytest.fixture(scope="module")
def cb_py_source() -> str:
    return _CB_PY.read_text()


@pytest.fixture(scope="module")
def ds_py_source() -> str:
    return _DS_PY.read_text()


# -------------------------------------------------------------------
# 25.21.1 — Metric definitions in main.py
# -------------------------------------------------------------------

class TestMetricDefinitions:

    def test_operations_total_counter_defined(self, main_py_source):
        assert '"prefect_deployment_operations_total"' in main_py_source

    def test_operations_total_has_tenant_id_label(self, main_py_source):
        # Find the Counter definition and verify tenant_id is a label
        match = re.search(
            r'Counter\(\s*"prefect_deployment_operations_total".*?\)',
            main_py_source, re.DOTALL,
        )
        assert match, "Counter definition not found"
        assert "tenant_id" in match.group()

    def test_duration_histogram_defined(self, main_py_source):
        assert '"prefect_deployment_duration_seconds"' in main_py_source

    def test_duration_histogram_has_buckets(self, main_py_source):
        match = re.search(
            r'Histogram\(\s*"prefect_deployment_duration_seconds".*?\)',
            main_py_source, re.DOTALL,
        )
        assert match, "Histogram definition not found"
        assert "buckets" in match.group()

    def test_retries_counter_defined(self, main_py_source):
        assert '"prefect_deployment_retries_total"' in main_py_source

    def test_circuit_breaker_gauge_defined(self, main_py_source):
        assert '"prefect_circuit_breaker_state"' in main_py_source

    def test_gauge_import(self, main_py_source):
        """Gauge must be imported from prometheus_client."""
        assert "Gauge" in main_py_source
        assert "from prometheus_client import" in main_py_source

    def test_circuit_breaker_gauge_initialized_at_startup(
        self, main_py_source,
    ):
        """Both sync and delete circuits must be set to closed
        at module level so Prometheus has data from first scrape."""
        assert 'for _circuit_name in ("sync", "delete")' in main_py_source
        assert '"closed"' in main_py_source


# -------------------------------------------------------------------
# 25.21.1 — Metrics instrumentation
# -------------------------------------------------------------------

class TestMetricsInstrumentation:

    def test_sync_endpoint_records_success(self, main_py_source):
        assert 'operation="sync", status="success"' in main_py_source

    def test_sync_endpoint_records_failure(self, main_py_source):
        assert 'operation="sync", status="failure"' in main_py_source

    def test_delete_endpoint_records_success(self, main_py_source):
        assert 'operation="delete", status="success"' in main_py_source

    def test_delete_endpoint_records_failure(self, main_py_source):
        assert 'operation="delete", status="failure"' in main_py_source

    def test_trigger_endpoint_records_success(self, main_py_source):
        assert re.search(
            r'operation="trigger".*status="success"',
            main_py_source, re.DOTALL,
        )

    def test_trigger_endpoint_records_failure(self, main_py_source):
        assert re.search(
            r'operation="trigger".*status="failure"',
            main_py_source, re.DOTALL,
        )

    def test_delete_duration_tracked(self, main_py_source):
        assert 'operation="delete"' in main_py_source
        # Verify .observe() is called for delete
        assert re.search(
            r'duration_seconds\.labels\(operation="delete"\)\.observe',
            main_py_source,
        )

    def test_trigger_duration_tracked(self, main_py_source):
        assert re.search(
            r'duration_seconds\.labels\(\s*operation="trigger"',
            main_py_source,
        )


# -------------------------------------------------------------------
# 25.21.1 — Retry counter in deployment_sync.py
# -------------------------------------------------------------------

class TestRetryInstrumentation:

    def test_retry_counter_incremented(self, ds_py_source):
        assert "prefect_deployment_retries_total" in ds_py_source

    def test_retry_increment_inside_try_except(self, ds_py_source):
        """Retry metric must be wrapped in try/except so it
        never breaks the retry loop."""
        # Find the block that imports and increments
        idx = ds_py_source.find("prefect_deployment_retries_total")
        assert idx != -1
        # Walk backward to find 'try:'
        before = ds_py_source[:idx]
        assert "try:" in before[before.rfind("\n\n"):]


# -------------------------------------------------------------------
# 25.21.1 — Circuit breaker gauge emission
# -------------------------------------------------------------------

class TestCircuitBreakerGauge:

    def test_emit_cb_gauge_function_exists(self, cb_py_source):
        assert "def _emit_cb_gauge(" in cb_py_source

    def test_gauge_emitted_on_open(self, cb_py_source):
        """record_failure → open must emit gauge."""
        assert cb_py_source.count("_emit_cb_gauge(") >= 3

    def test_gauge_emitted_on_half_open(self, cb_py_source):
        assert "_STATE_HALF_OPEN" in cb_py_source
        # Verify _emit_cb_gauge is called near half_open transition
        assert "_emit_cb_gauge(self.operation, _STATE_HALF_OPEN)" \
            in cb_py_source

    def test_gauge_emitted_on_close(self, cb_py_source):
        assert "_emit_cb_gauge(self.operation, _STATE_CLOSED)" \
            in cb_py_source

    def test_gauge_wrapped_in_try_except(self, cb_py_source):
        """Gauge emission must not break circuit breaker."""
        fn_start = cb_py_source.find("def _emit_cb_gauge(")
        fn_body = cb_py_source[fn_start:fn_start + 500]
        assert "try:" in fn_body
        assert "except Exception" in fn_body


# -------------------------------------------------------------------
# 25.21.2 — Alert rules in alerts.yml
# -------------------------------------------------------------------

class TestAlertRules:

    def test_alerts_yaml_valid(self, alerts_yaml):
        assert isinstance(alerts_yaml, dict)
        assert "groups" in alerts_yaml

    def test_prefect_alert_group_exists(self, prefect_alert_rules):
        assert len(prefect_alert_rules) >= 3

    def test_integration_service_down_alert(self, prefect_alert_rules):
        rule = _find_rule(prefect_alert_rules,
                          "PrefectIntegrationServiceDown")
        assert rule is not None, "Alert not found"
        assert rule["labels"]["severity"] == "critical"
        assert "2m" in rule["for"]
        assert 'up{job="prefect-integration-service"}' in rule["expr"]

    def test_high_failure_rate_alert(self, prefect_alert_rules):
        rule = _find_rule(prefect_alert_rules,
                          "PrefectDeploymentSyncHighFailureRate")
        assert rule is not None, "Alert not found"
        assert rule["labels"]["severity"] == "warning"
        assert "5m" in rule["for"]
        assert "prefect_deployment_operations_total" in rule["expr"]
        assert "0.2" in rule["expr"]

    def test_worker_down_alert(self, prefect_alert_rules):
        rule = _find_rule(prefect_alert_rules, "PrefectWorkerDown")
        assert rule is not None, "Alert not found"
        assert rule["labels"]["severity"] == "critical"
        assert "5m" in rule["for"]
        assert "kube_deployment_status_replicas_ready" in rule["expr"]

    def test_all_alerts_have_required_fields(self, prefect_alert_rules):
        for rule in prefect_alert_rules:
            name = rule.get("alert", "<unnamed>")
            assert "expr" in rule, f"{name}: missing expr"
            assert "for" in rule, f"{name}: missing for"
            assert "labels" in rule, f"{name}: missing labels"
            assert "severity" in rule["labels"], \
                f"{name}: missing severity"
            assert "annotations" in rule, f"{name}: missing annotations"
            assert "summary" in rule["annotations"], \
                f"{name}: missing summary annotation"
            assert "description" in rule["annotations"], \
                f"{name}: missing description annotation"

    def test_all_alerts_have_runbook_url(self, prefect_alert_rules):
        for rule in prefect_alert_rules:
            name = rule.get("alert", "<unnamed>")
            assert "runbook_url" in rule.get("annotations", {}), \
                f"{name}: missing runbook_url annotation"


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _find_rule(rules: list[dict], alert_name: str):
    for r in rules:
        if r.get("alert") == alert_name:
            return r
    return None
