"""TDD pins for the cost-budget observability (openspec
add-databricks-cost-guardrails task 7.6) — metrics, alert rules, and the
Grafana dashboard (the 3.8 test_warehouse_fleet_observability
conventions).

The budget metrics (``hub/apps/databricks_admin/metrics.py``) are the
SAME window read the enforcement computes on every dispatch and the U9
budget page refreshes. The alert rules
(``monitoring/prometheus/alerts/databricks-cost-budget.yml``) and the
dashboard
(``monitoring/grafana/dashboards/databricks-cost-budget.json``) are REAL
artifacts — the pins validate they parse and reference exactly the
emitted metrics (drift pins both directions). The emission pins (the
gauge stamped by the enforcement, the counter by the crossing, the
gauge refreshed by the page) live in the REAL-surface suites
(test_budget_crossing.py / test_budget_page.py) via the module-boundary
recorder seam.
"""

import json
from pathlib import Path

import yaml
from django.test import TestCase

PROJECT_ROOT = Path(__file__).resolve().parents[4]

BUDGET_METRIC_NAMES = (
    "databricks_cost_budget_consumed_ratio",
    "databricks_cost_budget_crossings_total",
)


class TestBudgetMetricRegistration(TestCase):
    def test_budget_metric_names_are_registered(self):
        from hub.apps.databricks_admin import metrics

        for name in BUDGET_METRIC_NAMES:
            metric = getattr(metrics, name, None)
            assert metric is not None, f"{name} must be registered in metrics.py"
            # prometheus_client strips the mandatory _total suffix from a
            # Counter's `_name` (the EXPORTED name keeps it) — the two
            # counter names therefore compare with the suffix re-added.
            exported = metric._name
            if name.endswith("_total") and not exported.endswith("_total"):
                exported = f"{exported}_total"
            assert exported == name


class TestBudgetAlerts(TestCase):
    """The alert rules exist, parse, and pin the budget metrics."""

    def setUp(self):
        self.alerts_file = (
            PROJECT_ROOT / "monitoring" / "prometheus" / "alerts" / "databricks-cost-budget.yml"
        )

    def test_alerts_file_exists_and_parses(self):
        assert self.alerts_file.is_file(), "databricks-cost-budget.yml must exist"
        config = yaml.safe_load(self.alerts_file.read_text())
        assert "groups" in config
        group = next(g for g in config["groups"] if g["name"] == "databricks_cost_budget")
        assert len(group["rules"]) == 2

    def test_at_or_over_alert_pins_the_ratio_gauge_and_boundary(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksCostBudgetAtOrOver"
        )
        assert "databricks_cost_budget_consumed_ratio" in rule["expr"]
        assert ">= 1" in rule["expr"], "the alert fires at the budget boundary"
        assert rule["labels"]["severity"] == "warning"
        assert rule.get("for") == "5m"

    def test_crossing_fired_alert_pins_the_counter(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksCostBudgetCrossingFired"
        )
        assert "databricks_cost_budget_crossings_total" in rule["expr"]
        assert rule["labels"]["severity"] == "info"


class TestBudgetDashboard(TestCase):
    """The Grafana dashboard exists, parses, and pins the budget metrics."""

    def setUp(self):
        self.dashboard_file = (
            PROJECT_ROOT / "monitoring" / "grafana" / "dashboards" / "databricks-cost-budget.json"
        )

    def test_dashboard_exists_and_parses(self):
        assert self.dashboard_file.is_file(), "databricks-cost-budget.json must exist"
        payload = json.loads(self.dashboard_file.read_text())
        assert payload["dashboard"]["title"] == "Databricks — Cost Budgets"
        assert payload["dashboard"]["uid"] == "databricks-cost-budget"
        assert len(payload["dashboard"]["panels"]) >= 3

    def test_dashboard_references_only_the_budget_metrics(self):
        payload = json.loads(self.dashboard_file.read_text())
        exprs = []
        for panel in payload["dashboard"]["panels"]:
            for target in panel.get("targets", []):
                if target.get("expr"):
                    exprs.append(target["expr"])
        referenced = {name for name in BUDGET_METRIC_NAMES if any(name in e for e in exprs)}
        assert referenced == set(BUDGET_METRIC_NAMES), (
            "every budget metric appears on the dashboard and no panel "
            "references a metric the module does not emit"
        )
