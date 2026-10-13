"""Shared DoD gate (openspec add-databricks-control-plane — "Ops &
observability") — the control-plane dashboard, the alert-rule wiring,
and the synthetic firing coverage.

The Grafana dashboard
(``monitoring/grafana/dashboards/databricks-control-plane.json``) is
the estate rollup: one view across the six metric families the control
plane emits (``hub/apps/databricks_admin/metrics.py``). The six
databricks alert rule files are REAL ops artifacts — these pins also
guard the wiring root-cause fix: the files existed and CI linted them,
but NO prometheus config loaded them into ``rule_files``, so no
databricks alert could ever fire in any environment. The synthetic
firing file (``monitoring/prometheus/alerts/
databricks-control-plane-synthetic-firing.yml``, the Phase 228
convention) exercises every estate alert via ``promtool test rules``;
the prometheus-alerts-test.yml workflow picks it up through the
``*-synthetic-firing.yml`` glob.

Pin conventions: the 1.10 test_uc_sync_alerts pattern (drift pins read
the REAL artifacts and cross-check them against the REAL emitter) and
the test_odps_alerts pattern ("Prometheus config should include … in
rule_files").
"""

import json
import re
from pathlib import Path

import yaml
from django.test import TestCase

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
MONITORING = PROJECT_ROOT / "monitoring"

DATABRICKS_RULE_FILES = [
    "databricks-uc-sync.yml",
    "databricks-uc-approvals.yml",
    "databricks-warehouses.yml",
    "databricks-jobs.yml",
    "databricks-cost-budget.yml",
    "databricks-dlt.yml",
]

# One prometheus config per deployment surface (verified against the
# compose mounts: dev+staging → prometheus.yml, core overlay →
# prometheus.core.yml, production → prometheus.production.yml, test →
# prometheus-test.yml).
PROMETHEUS_CONFIGS = [
    "prometheus.yml",
    "prometheus.core.yml",
    "prometheus.production.yml",
    "prometheus-test.yml",
]

DASHBOARD_FILE = MONITORING / "grafana" / "dashboards" / "databricks-control-plane.json"
SYNTHETIC_FILE = (
    MONITORING / "prometheus" / "alerts" / "databricks-control-plane-synthetic-firing.yml"
)

# The estate's complete metric surface (hub/apps/databricks_admin/
# metrics.py). One module attribute per metric — the drift pin reads the
# REAL prometheus_client objects and compares their names against the
# artifacts.
ESTATE_METRIC_ATTRS = [
    "databricks_uc_sync_runs_total",
    "databricks_uc_sync_duration_seconds",
    "databricks_uc_sync_rows_total",
    "databricks_uc_sync_last_success_timestamp",
    "databricks_uc_change_requests_total",
    "databricks_uc_approval_duration_seconds",
    "databricks_uc_change_pending_approvals",
    "databricks_uc_change_oldest_pending_seconds",
    "databricks_warehouse_mirror_last_success_timestamp",
    "databricks_warehouse_state_count",
    "databricks_warehouse_starting_since_timestamp",
    "databricks_warehouse_pool_borrows_total",
    "databricks_warehouse_pool_exhausted_total",
    "databricks_warehouse_pool_in_use",
    "databricks_jobs_mirror_last_success_timestamp",
    "databricks_job_run_state_count",
    "databricks_job_run_started_since_timestamp",
    "databricks_job_runs_total",
    "databricks_cost_budget_consumed_ratio",
    "databricks_cost_budget_crossings_total",
    "databricks_dlt_updates_total",
]


def _collect_alert_names(rule_files: list[str]) -> set[str]:
    names: set[str] = set()
    for name in rule_files:
        config = yaml.safe_load((MONITORING / "prometheus" / "alerts" / name).read_text())
        for group in config["groups"]:
            for rule in group["rules"]:
                names.add(rule["alert"])
    return names


class ControlPlaneDashboardTests(TestCase):
    """The estate-rollup dashboard exists, parses, and pins the estate
    metrics (the 1.10 dashboard-pin pattern)."""

    def setUp(self):
        self.dashboard_file = DASHBOARD_FILE

    def test_dashboard_exists_and_parses(self):
        assert self.dashboard_file.is_file(), "databricks-control-plane.json must exist"
        payload = json.loads(self.dashboard_file.read_text())
        assert payload["dashboard"]["title"] == "Databricks — Control Plane"
        assert payload["dashboard"]["uid"] == "databricks-control-plane"
        assert len(payload["dashboard"]["panels"]) >= 20

    def test_dashboard_references_every_estate_metric(self):
        # Drift pin: every metric the emitter registers must appear in the
        # dashboard (prometheus_client strips the mandatory _total suffix
        # from a Counter's Python-side _name; the wire name in the artifact
        # keeps it — substring matching handles both, the 1.10 pattern).
        from hub.apps.databricks_admin import metrics

        dashboard_text = self.dashboard_file.read_text()
        for attr in ESTATE_METRIC_ATTRS:
            name = getattr(metrics, attr)._name
            assert name in dashboard_text, (
                f"metric {name} is emitted but absent from the control-plane dashboard"
            )

    def test_dashboard_references_no_foreign_metrics(self):
        # Reverse drift pin: every databricks_* metric name the dashboard
        # queries must be one the estate ACTUALLY emits (catches renamed /
        # retired metrics and copy-paste artifacts). A metric's wire name
        # may carry prometheus_client's auto suffixes: Counter → _total,
        # Histogram → _bucket/_sum/_count (the _bucket form is what the
        # histogram_quantile targets query).
        from hub.apps.databricks_admin import metrics

        allowed = {
            wire
            for attr in ESTATE_METRIC_ATTRS
            for wire in (
                getattr(metrics, attr)._name,
                getattr(metrics, attr)._name + "_total",
                getattr(metrics, attr)._name + "_bucket",
                getattr(metrics, attr)._name + "_sum",
                getattr(metrics, attr)._name + "_count",
            )
        }
        payload = json.loads(self.dashboard_file.read_text())
        referenced: set[str] = set()
        for panel in payload["dashboard"]["panels"]:
            for target in panel.get("targets", []):
                if not target.get("expr"):
                    continue
                referenced.update(re.findall(r"databricks_[a-z0-9_]+", target["expr"]))
        foreign = referenced - allowed
        assert not foreign, f"dashboard references non-estate metrics: {sorted(foreign)}"


class ControlPlaneAlertWiringTests(TestCase):
    """Every prometheus config loads the six databricks rule files (the
    root-cause fix: the files existed but NO config loaded them) and
    every referenced rule file resolves on disk (the test_odps_alerts
    "rule_files" pin pattern)."""

    def _rule_files_of(self, config_name: str) -> list[str]:
        path = MONITORING / "prometheus" / config_name
        assert path.is_file(), f"{config_name} must exist"
        config = yaml.safe_load(path.read_text())
        return list(config.get("rule_files", []))

    def test_every_prometheus_config_loads_the_databricks_rule_files(self):
        for config_name in PROMETHEUS_CONFIGS:
            rule_files = self._rule_files_of(config_name)
            for rule in DATABRICKS_RULE_FILES:
                entry = f"alerts/{rule}"
                assert entry in rule_files, (
                    f"{config_name} must include {entry} in rule_files — "
                    "without it the databricks alerts never load"
                )

    def test_every_referenced_rule_file_resolves_on_disk(self):
        alerts_dir = MONITORING / "prometheus" / "alerts"
        for config_name in PROMETHEUS_CONFIGS:
            for entry in self._rule_files_of(config_name):
                if not entry.startswith("alerts/"):
                    continue
                path = MONITORING / "prometheus" / entry
                assert path.is_file(), (
                    f"{config_name} references {entry} which does not exist "
                    f"(prometheus would fail to start; expected at {path})"
                )
        # Sanity: the databricks files themselves exist.
        for rule in DATABRICKS_RULE_FILES:
            assert (alerts_dir / rule).is_file()


class ControlPlaneSyntheticFiringTests(TestCase):
    """The synthetic firing file exercises every estate alert (the Phase
    228 convention) and is picked up by the CI glob."""

    def test_synthetic_file_exists_and_references_the_estate_rules(self):
        assert SYNTHETIC_FILE.is_file(), "databricks-control-plane-synthetic-firing.yml must exist"
        config = yaml.safe_load(SYNTHETIC_FILE.read_text())
        assert sorted(config["rule_files"]) == sorted(DATABRICKS_RULE_FILES)

    def test_every_estate_alert_has_a_firing_test(self):
        # Bidirectional coverage pin: the synthetic file must fire-test
        # every alert the estate rules define, and only those (a new alert
        # without a test — or a test for a deleted alert — fails here).
        config = yaml.safe_load(SYNTHETIC_FILE.read_text())
        covered = {
            expected["alertname"]
            for test in config["tests"]
            for expected in test.get("alert_rule_test", [])
        }
        defined = _collect_alert_names(DATABRICKS_RULE_FILES)
        assert covered == defined, (
            f"synthetic firing coverage drift: "
            f"defined-only={sorted(defined - covered)}, "
            f"tested-only={sorted(covered - defined)}"
        )

    def test_synthetic_file_matches_the_ci_glob(self):
        # prometheus-alerts-test.yml runs `promtool test rules` over
        # `monitoring/prometheus/alerts/*-synthetic-firing.yml` and
        # EXCLUDES the same glob from `promtool check rules` — the name
        # must keep the pattern or CI silently stops exercising the file.
        assert SYNTHETIC_FILE.name.endswith("-synthetic-firing.yml")
        assert SYNTHETIC_FILE.name.startswith("databricks-")
