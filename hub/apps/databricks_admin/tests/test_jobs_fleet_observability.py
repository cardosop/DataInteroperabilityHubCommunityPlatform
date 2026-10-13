"""TDD pins for the Databricks job-fleet observability (openspec
add-databricks-jobs task 4.5) — metrics, alert rules, and the Grafana
dashboard (the 1.10 test_uc_sync_alerts / 3.8 fleet conventions).

The fleet metrics (``hub/apps/databricks_admin/metrics.py``) are emitted
from the REAL surfaces: the 4.2 mirror refresh stamps the last-success
anchor + per-lifecycle-state counts + the running-since anchors, and
the 4.4 poller records terminal outcomes through the
``record_job_run_outcome`` wrapper. The alert rules
(``monitoring/prometheus/alerts/databricks-jobs.yml``) and the dashboard
(``monitoring/grafana/dashboards/databricks-jobs.json``) are REAL
artifacts — the pins validate they parse and reference exactly the
emitted metrics (drift pins both directions, the 1.10 convention).
"""

import json
from pathlib import Path

import pytest
import yaml
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

PROJECT_ROOT = Path(__file__).resolve().parents[4]

JOB_METRIC_NAMES = (
    "databricks_jobs_mirror_last_success_timestamp",
    "databricks_job_run_state_count",
    "databricks_job_run_started_since_timestamp",
    "databricks_job_runs_total",
)


class TestJobsFleetAlerts(TestCase):
    """The alert rules exist, parse, and pin the fleet metrics."""

    def setUp(self):
        self.alerts_file = (
            PROJECT_ROOT / "monitoring" / "prometheus" / "alerts" / "databricks-jobs.yml"
        )

    def test_alerts_file_exists_and_parses(self):
        assert self.alerts_file.is_file(), "databricks-jobs.yml must exist"
        config = yaml.safe_load(self.alerts_file.read_text())
        assert "groups" in config
        group = next(g for g in config["groups"] if g["name"] == "databricks_jobs")
        assert len(group["rules"]) == 3

    def test_run_failed_alert_pins_the_outcome_counter(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksJobRunFailed"
        )
        assert 'databricks_job_runs_total{outcome="FAILED"}' in rule["expr"]
        assert rule["labels"]["severity"] == "warning"

    def test_running_too_long_alert_pins_the_gauge_and_threshold(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksJobRunningTooLong"
        )
        assert "databricks_job_run_started_since_timestamp" in rule["expr"]
        assert rule["labels"]["severity"] == "warning"
        # A run still non-terminal 30 minutes after it first appeared is
        # long (jobs legitimately run minutes-to-tens-of-minutes; a
        # stuck run past the half-hour mark is the anomaly).
        assert "1800" in rule["expr"]

    def test_run_rate_anomaly_alert_pins_the_failure_ratio(self):
        config = yaml.safe_load(self.alerts_file.read_text())
        rule = next(
            r
            for g in config["groups"]
            for r in g["rules"]
            if r["alert"] == "DatabricksJobRunRateAnomaly"
        )
        assert "databricks_job_runs_total" in rule["expr"]
        assert rule["labels"]["severity"] == "warning"
        # A 30-minute window whose failure share exceeds 25% is the
        # anomaly (the uc-sync ratio precedent).
        assert "0.25" in rule["expr"]


class TestJobsFleetDashboard(TestCase):
    """The Grafana dashboard exists, parses, and pins the fleet metrics."""

    def setUp(self):
        self.dashboard_file = (
            PROJECT_ROOT / "monitoring" / "grafana" / "dashboards" / "databricks-jobs.json"
        )

    def test_dashboard_exists_and_parses(self):
        assert self.dashboard_file.is_file(), "databricks-jobs.json must exist"
        payload = json.loads(self.dashboard_file.read_text())
        assert payload["dashboard"]["title"] == "Databricks — Jobs Fleet"
        assert payload["dashboard"]["uid"] == "databricks-jobs"
        assert len(payload["dashboard"]["panels"]) >= 5

    def test_dashboard_references_every_job_metric(self):
        payload = json.loads(self.dashboard_file.read_text())
        exprs = []
        for panel in payload["dashboard"]["panels"]:
            for target in panel.get("targets", []):
                if target.get("expr"):
                    exprs.append(target["expr"])
        referenced = {name for name in JOB_METRIC_NAMES if any(name in e for e in exprs)}
        assert referenced == set(JOB_METRIC_NAMES), (
            f"dashboard must consume exactly the job-fleet metrics; found {referenced}"
        )

    def test_artifact_metric_names_match_the_emitter(self):
        # The drift pin: every EXPORTED job metric name (the names the
        # artifacts query — counters carry their _total suffix) appears
        # in the observability artifacts (the 1.10 convention).
        from hub.apps.databricks_admin import metrics

        emitted = set()
        for name in JOB_METRIC_NAMES:
            exported = getattr(metrics, name)._name
            if name.endswith("_total") and not exported.endswith("_total"):
                exported = f"{exported}_total"
            emitted.add(exported)
        artifact_text = (
            self.dashboard_file.read_text()
            + (
                PROJECT_ROOT / "monitoring" / "prometheus" / "alerts" / "databricks-jobs.yml"
            ).read_text()
        )
        for name in emitted:
            assert name in artifact_text, (
                f"metric {name} is emitted but absent from the 4.5 artifacts"
            )
