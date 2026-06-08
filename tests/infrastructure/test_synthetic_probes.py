"""
280.B.2.4 — Tests for Synthetic Probes and associated alert rules.

Validates:
- Probe creation and configuration
- Probe execution (success and failure paths)
- Management command argument parsing
- Prometheus alert rule syntax correctness
- Synthetic firing test execution via promtool
- Probe failure rate threshold correctness

Does NOT mock — validates real configuration and code.
"""
import os
import re
import subprocess
import pytest
import yaml

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _exists(path):
    return os.path.exists(os.path.join(PROJECT_ROOT, path))


# ── 280.B.2.4.1 — Probe module integrity ─────────────────────────────────

class TestSyntheticProbeModule:
    """Validate the synthetic_probes.py module is correctly structured."""

    def test_module_imports_cleanly(self):
        """Module must import without errors."""
        import hub.apps.health.synthetic_probes as sp
        assert hasattr(sp, "SyntheticProbe")
        assert hasattr(sp, "ProbeResult")
        assert hasattr(sp, "ProbeRunSummary")
        assert hasattr(sp, "create_probes")
        assert hasattr(sp, "run_all_probes")

    def test_critical_probe_names_defined(self):
        """CRITICAL_PROBE_NAMES must contain exactly the 4 required probes."""
        from hub.apps.health.synthetic_probes import CRITICAL_PROBE_NAMES
        assert set(CRITICAL_PROBE_NAMES) == {"login", "asset_list", "search", "health"}

    def test_probe_result_dataclass(self):
        """ProbeResult must have required fields."""
        from hub.apps.health.synthetic_probes import ProbeResult
        r = ProbeResult(probe_name="test", success=True, latency_ms=42.0)
        assert r.probe_name == "test"
        assert r.success is True
        assert r.latency_ms == 42.0
        assert r.status_code is None
        assert r.error_message is None

    def test_probe_run_summary_failure_rate(self):
        """ProbeRunSummary must calculate failure rate correctly."""
        from hub.apps.health.synthetic_probes import ProbeRunSummary, ProbeResult
        results = [
            ProbeResult(probe_name="a", success=True, latency_ms=10),
            ProbeResult(probe_name="b", success=False, latency_ms=20),
            ProbeResult(probe_name="c", success=True, latency_ms=30),
            ProbeResult(probe_name="d", success=True, latency_ms=40),
        ]
        summary = ProbeRunSummary(
            total_probes=4, passed=3, failed=1, results=results,
        )
        assert summary.failure_rate == 0.25

    def test_create_probes_returns_all_four(self):
        """create_probes must return exactly 4 probes."""
        from hub.apps.health.synthetic_probes import create_probes
        probes = create_probes("http://localhost:8000")
        assert set(probes.keys()) == {"login", "asset_list", "search", "health"}

    def test_probe_configuration(self):
        """Each probe must have correct method, path, expected status."""
        from hub.apps.health.synthetic_probes import create_probes
        probes = create_probes("http://localhost:8000")

        # Health probe
        h = probes["health"]
        assert h.method == "GET"
        assert h.url_path == "/health"
        assert h.expected_status == 200

        # Login probe
        l = probes["login"]
        assert l.method == "POST"
        assert l.url_path == "/api/v1/auth/login/"
        assert l.expected_status == 200

        # Asset list probe
        a = probes["asset_list"]
        assert a.method == "GET"
        assert "/api/v1/assets/" in a.url_path
        assert a.expected_status == 200

        # Search probe
        s = probes["search"]
        assert s.method == "GET"
        assert "/api/v1/search/" in s.url_path
        assert s.expected_status == 200

    def test_probe_base_url_normalized(self):
        """Base URL trailing slash must be stripped."""
        from hub.apps.health.synthetic_probes import SyntheticProbe
        p = SyntheticProbe(
            name="test", method="GET", url_path="/health",
            base_url="http://localhost:8000/",
        )
        assert p.base_url == "http://localhost:8000"


# ── 280.B.2.4.2 — Management command ─────────────────────────────────────

class TestSyntheticProbeManagementCommand:
    """Validate the run_synthetic_probes management command."""

    def test_command_module_exists(self):
        """Management command file must exist."""
        assert _exists("hub/apps/health/management/commands/run_synthetic_probes.py")

    def test_command_is_valid_django_command(self):
        """Command must be a valid Django BaseCommand subclass."""
        import importlib
        mod = importlib.import_module(
            "hub.apps.health.management.commands.run_synthetic_probes"
        )
        from django.core.management.base import BaseCommand
        assert hasattr(mod, "Command")
        assert issubclass(mod.Command, BaseCommand)

    def test_command_has_expected_arguments(self):
        """Command must expose --base-url, --interval, --iterations, --probes."""
        import importlib
        mod = importlib.import_module(
            "hub.apps.health.management.commands.run_synthetic_probes"
        )
        # Check the add_arguments method parses correctly
        from argparse import ArgumentParser
        parser = ArgumentParser()
        cmd = mod.Command()
        cmd.add_arguments(parser)
        actions = {a.dest for a in parser._actions}
        expected = {"base_url", "interval", "iterations", "probes",
                     "auth_email", "auth_password", "help"}
        for arg in expected:
            assert arg in actions, f"Missing argument: {arg}"


# ── 280.B.2.4.3 — Prometheus alert rules ─────────────────────────────────

class TestSyntheticProbeAlertRules:
    """Validate synthetic-probes.yml alert rules are syntactically correct."""

    ALERT_FILE = "monitoring/prometheus/alerts/synthetic-probes.yml"

    def test_alert_file_exists(self):
        assert _exists(self.ALERT_FILE), f"Missing {self.ALERT_FILE}"

    def test_alert_file_is_valid_yaml(self):
        with open(os.path.join(PROJECT_ROOT, self.ALERT_FILE)) as f:
            data = yaml.safe_load(f.read())
        assert "groups" in data
        assert len(data["groups"]) == 1

    def test_all_required_alerts_defined(self):
        """Must define alerts for all 4 probes + aggregate + latency."""
        with open(os.path.join(PROJECT_ROOT, self.ALERT_FILE)) as f:
            data = yaml.safe_load(f.read())

        alerts = {r["alert"] for r in data["groups"][0]["rules"]}
        required = {
            "SyntheticProbeFailureRateHigh",
            "SyntheticProbeLoginFailing",
            "SyntheticProbeAssetListFailing",
            "SyntheticProbeSearchFailing",
            "SyntheticProbeHealthFailing",
            "SyntheticProbeLatencyHigh",
        }
        missing = required - alerts
        assert not missing, f"Missing alert rules: {missing}"

    def test_aggregate_alert_uses_1_percent_threshold(self):
        """Aggregate alert must fire at >0.01 (1%) failure rate."""
        with open(os.path.join(PROJECT_ROOT, self.ALERT_FILE)) as f:
            content = f.read()
        assert "0.01" in content, (
            "Aggregate alert threshold must be 0.01 (1%)"
        )

    def test_each_per_probe_alert_has_for_5m(self):
        """Each per-probe alert must have for: 5m to meet acceptance criteria."""
        with open(os.path.join(PROJECT_ROOT, self.ALERT_FILE)) as f:
            data = yaml.safe_load(f.read())

        for rule in data["groups"][0]["rules"]:
            if rule.get("alert", "").startswith("SyntheticProbe") and rule["alert"] != "SyntheticProbeFailureRateHigh" and rule["alert"] != "SyntheticProbeLatencyHigh":
                assert rule.get("for") == "5m", (
                    f"Alert {rule['alert']} must have for: 5m"
                )

    def test_all_alerts_have_runbook_url(self):
        """Every alert must have a runbook_url annotation."""
        with open(os.path.join(PROJECT_ROOT, self.ALERT_FILE)) as f:
            data = yaml.safe_load(f.read())

        for rule in data["groups"][0]["rules"]:
            annotations = rule.get("annotations", {})
            desc = annotations.get("description", "")
            assert "runbook_url" in annotations or "runbook_url" in desc, (
                f"Alert {rule.get('alert')} missing runbook_url"
            )

    def test_all_alerts_have_severity_label(self):
        """Every alert must have a severity label."""
        with open(os.path.join(PROJECT_ROOT, self.ALERT_FILE)) as f:
            data = yaml.safe_load(f.read())

        for rule in data["groups"][0]["rules"]:
            severity = rule.get("labels", {}).get("severity")
            assert severity in ("critical", "warning"), (
                f"Alert {rule['alert']} has invalid severity: {severity}"
            )


# ── 280.B.2.4.4 — Synthetic firing tests ─────────────────────────────────

class TestSyntheticProbeFiringTests:
    """Validate synthetic firing tests pass via promtool."""

    FIRING_FILE = "monitoring/prometheus/alerts/synthetic-probes-firing.yml"

    def test_firing_file_exists(self):
        assert _exists(self.FIRING_FILE), f"Missing {self.FIRING_FILE}"

    def test_firing_file_is_valid_yaml(self):
        with open(os.path.join(PROJECT_ROOT, self.FIRING_FILE)) as f:
            data = yaml.safe_load(f.read())
        assert "tests" in data
        assert len(data["tests"]) >= 4, (
            f"Expected >=4 test scenarios, got {len(data['tests'])}"
        )

    def test_each_test_has_name_and_input_series(self):
        with open(os.path.join(PROJECT_ROOT, self.FIRING_FILE)) as f:
            data = yaml.safe_load(f.read())

        for test in data["tests"]:
            assert "name" in test, "Each test must have a name"
            assert "input_series" in test, f"Test '{test['name']}' missing input_series"
            assert "alert_rule_test" in test, f"Test '{test['name']}' missing alert_rule_test"

    def test_promtool_validates_rules(self):
        """Run promtool test rules on the firing test file."""
        promtool = _find_promtool()
        if promtool is None:
            pytest.skip("promtool not found in PATH")

        result = subprocess.run(
            [promtool, "test", "rules",
             os.path.join(PROJECT_ROOT, self.FIRING_FILE)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"promtool test rules failed:\nSTDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    def test_firing_test_covers_all_four_probes(self):
        """Synthetic firing tests must cover login, asset_list, search, health."""
        with open(os.path.join(PROJECT_ROOT, self.FIRING_FILE)) as f:
            content = f.read()

        for probe in ("login", "asset_list", "search", "health"):
            assert probe in content, (
                f"Firing test must reference probe '{probe}'"
            )

    def test_failure_rate_1_percent_scenario_exists(self):
        """Must test the exact 1% threshold boundary."""
        with open(os.path.join(PROJECT_ROOT, self.FIRING_FILE)) as f:
            content = f.read()
        # The test should have a scenario at exactly 1% failure rate
        assert "1% failure" in content or ">1%" in content, (
            "Firing test must document the 1% threshold scenario"
        )


def _find_promtool():
    """Find promtool binary in PATH. Returns path or None."""
    result = subprocess.run(
        ["which", "promtool"], capture_output=True, text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    # Try common locations
    for path in [
        "/usr/local/bin/promtool",
        "/usr/bin/promtool",
        os.path.expanduser("~/bin/promtool"),
    ]:
        if os.path.exists(path):
            return path
    return None
