"""
Shared constants for monitoring integration tests.

Single source of truth for required Grafana dashboards (MONITORING_TEST_PLAN.md).
No mocks; used by test_grafana_dashboards, test_monitoring_infrastructure,
and test_monitoring_configurations.
"""

# Required Grafana dashboard filenames under monitoring/grafana/dashboards/
REQUIRED_GRAFANA_DASHBOARDS = (
    "system-health.json",
    "api-performance.json",
    "job-processing.json",
    "tenant-usage.json",
    "database-performance.json",
    "services-overview.json",
    "event-bus-health.json",
)
