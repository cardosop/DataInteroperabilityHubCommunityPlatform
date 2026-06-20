#!/usr/bin/env python3
"""
Comprehensive Monitoring and Observability Review Script

Reviews and maps all monitoring configurations to API endpoints:
- Prometheus metrics (endpoint labels)
- Grafana dashboards (query patterns)
- Jaeger traces (operation names)
- Log aggregation (URL patterns)

Task: 9.6.1.6.2 - Check monitoring and observability
"""

import json
import re
import sys
from pathlib import Path
from typing import Any


class MonitoringReviewer:
    """Comprehensive monitoring and observability configuration reviewer."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.monitoring_dir = project_root / "monitoring"
        self.hub_dir = project_root / "hub"
        self.services_dir = project_root / "services"
        self.k8s_dir = project_root / "k8s"

        # Results storage
        self.prometheus_metrics: dict[str, Any] = {}
        self.grafana_queries: list[dict[str, Any]] = []
        self.jaeger_operations: dict[str, list[str]] = {}
        self.log_patterns: dict[str, list[str]] = {}
        self.endpoint_mapping: dict[str, dict[str, Any]] = {}

        # Endpoint registry
        self.endpoints: set[str] = set()

    def extract_endpoints_from_urls(self) -> set[str]:
        """Extract all API endpoints from Django URL configuration."""
        endpoints = set()

        # Main API routes
        api_urls_file = self.hub_dir / "apps" / "api" / "urls.py"
        if api_urls_file.exists():
            content = api_urls_file.read_text()
            # Extract path patterns
            path_patterns = re.findall(r"path\(['\"]([^'\"]+)['\"]", content)
            re.findall(r"include\(['\"]([^'\"]+)['\"]", content)

            for pattern in path_patterns:
                if pattern.startswith("/"):
                    endpoints.add(pattern)
                else:
                    endpoints.add(f"/api/v1/{pattern}")

        # Extract from all app urls.py files
        for urls_file in self.hub_dir.rglob("**/urls.py"):
            if "migrations" in str(urls_file):
                continue

            try:
                content = urls_file.read_text()
                # Extract path patterns
                path_patterns = re.findall(r"path\(['\"]([^'\"]+)['\"]", content)
                re_path_patterns = re.findall(r"re_path\(['\"]([^'\"]+)['\"]", content)

                for pattern in path_patterns + re_path_patterns:
                    if pattern.startswith("/"):
                        endpoints.add(pattern)
                    elif not pattern.startswith("^"):
                        endpoints.add(f"/api/v1/{pattern}")
            except Exception as e:
                print(f"Warning: Could not parse {urls_file}: {e}")

        return endpoints

    def review_prometheus_metrics(self) -> dict[str, Any]:
        """Review Prometheus metrics configuration for endpoint labels."""
        print("\n=== Reviewing Prometheus Metrics ===")

        results = {
            "scrape_configs": [],
            "metrics_with_endpoint_labels": [],
            "endpoint_labels_found": set(),
            "services_monitored": [],
        }

        # Review prometheus.yml
        prometheus_config = self.monitoring_dir / "prometheus" / "prometheus.yml"
        if prometheus_config.exists():
            content = prometheus_config.read_text()

            # Extract scrape configs
            scrape_pattern = r"job_name:\s*['\"]([^'\"]+)['\"]"
            jobs = re.findall(scrape_pattern, content)
            results["services_monitored"] = jobs

            # Extract metrics_path
            metrics_path_pattern = r"metrics_path:\s*['\"]([^'\"]+)['\"]"
            re.findall(metrics_path_pattern, content)

            print(f"  Found {len(jobs)} scrape jobs")
            for job in jobs:
                results["scrape_configs"].append(
                    {"job_name": job, "metrics_path": "/metrics" if job != "prometheus" else None}
                )

        # Review metrics definitions in code
        otel_metrics_file = self.hub_dir / "apps" / "observability" / "otel_metrics.py"
        if otel_metrics_file.exists():
            content = otel_metrics_file.read_text()

            # Find metrics with route/endpoint labels
            re.findall(r"expected_labels=\([^)]*['\"]route['\"][^)]*\)", content)

            # Extract metric names with route labels
            metric_pattern = r"(\w+)\s*=\s*_(?:Counter|Histogram|UpDownCounter)Wrapper\s*\([^)]*expected_labels=\([^)]*['\"]route['\"]"
            metrics = re.findall(metric_pattern, content, re.MULTILINE)

            for metric in metrics:
                results["metrics_with_endpoint_labels"].append(metric)
                results["endpoint_labels_found"].add("route")

            # Check for method labels (often used with routes)
            method_pattern = r"expected_labels=\([^)]*['\"]method['\"]"
            if re.search(method_pattern, content):
                results["endpoint_labels_found"].add("method")

            print(
                f"  Found {len(results['metrics_with_endpoint_labels'])} metrics with route labels"
            )

        # Review FastAPI service metrics
        shared_metrics_file = self.services_dir / "shared" / "metrics.py"
        if shared_metrics_file.exists():
            content = shared_metrics_file.read_text()

            # Extract metrics with route labels
            route_label_pattern = r"\[['\"]route['\"]"
            if re.search(route_label_pattern, content):
                results["endpoint_labels_found"].add("route")
                results["endpoint_labels_found"].add("service")
                print("  Found FastAPI service metrics with route labels")

        results["endpoint_labels_found"] = list(results["endpoint_labels_found"])
        self.prometheus_metrics = results
        return results

    def review_grafana_dashboards(self) -> list[dict[str, Any]]:
        """Review Grafana dashboards for query patterns."""
        print("\n=== Reviewing Grafana Dashboards ===")

        queries = []
        dashboards_dir = self.monitoring_dir / "grafana" / "dashboards"

        if not dashboards_dir.exists():
            print(f"  Warning: Dashboards directory not found: {dashboards_dir}")
            return queries

        dashboard_files = list(dashboards_dir.glob("*.json"))
        print(f"  Found {len(dashboard_files)} dashboard files")

        for dashboard_file in dashboard_files:
            try:
                with open(dashboard_file) as f:
                    dashboard_data = json.load(f)

                dashboard_name = dashboard_data.get("dashboard", {}).get(
                    "title", dashboard_file.stem
                )
                panels = dashboard_data.get("dashboard", {}).get("panels", [])

                for panel in panels:
                    targets = panel.get("targets", [])
                    for target in targets:
                        expr = target.get("expr", "")
                        if expr:
                            # Extract endpoint-related labels from PromQL queries
                            route_labels = re.findall(r"route['\"]?\s*[=}]", expr)
                            method_labels = re.findall(r"method['\"]?\s*[=}]", expr)
                            service_labels = re.findall(r"service['\"]?\s*[=}]", expr)

                            # Extract metric names
                            metric_names = re.findall(r"(\w+)\s*\{", expr)

                            queries.append(
                                {
                                    "dashboard": dashboard_name,
                                    "panel": panel.get("title", "Unknown"),
                                    "query": expr,
                                    "has_route_label": bool(route_labels),
                                    "has_method_label": bool(method_labels),
                                    "has_service_label": bool(service_labels),
                                    "metrics_used": list(set(metric_names)),
                                    "legend_format": target.get("legendFormat", ""),
                                }
                            )
            except Exception as e:
                print(f"  Warning: Could not parse dashboard {dashboard_file}: {e}")

        print(f"  Reviewed {len(queries)} queries across {len(dashboard_files)} dashboards")
        self.grafana_queries = queries
        return queries

    def review_jaeger_traces(self) -> dict[str, list[str]]:
        """Review Jaeger tracing configuration for operation names."""
        print("\n=== Reviewing Jaeger Tracing Configuration ===")

        operations = {
            "django_operations": [],
            "fastapi_operations": [],
            "operation_patterns": [],
            "span_attributes": [],
        }

        # Review Django tracing middleware
        span_middleware_file = (
            self.hub_dir / "apps" / "observability" / "middleware" / "span_middleware.py"
        )
        if span_middleware_file.exists():
            content = span_middleware_file.read_text()

            # Extract span name patterns - look for f-strings with HTTP method and route
            span_name_patterns = [
                r'f?"HTTP\s+(\w+)\s+([^"]+)"',
                r"span_name\s*=\s*([^\n]+)",
                r'start_as_current_span\s*\(\s*f?"([^"]+)"',
            ]

            for pattern in span_name_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple):
                        if len(match) == 2:
                            operations["django_operations"].append(f"HTTP {match[0]} {match[1]}")
                        else:
                            operations["operation_patterns"].append(str(match[0]))
                    else:
                        operations["operation_patterns"].append(str(match))

            # Extract span attributes that include route/path
            if '"http.route"' in content or "'http.route'" in content:
                operations["span_attributes"].append("http.route")
            if '"http.method"' in content or "'http.method'" in content:
                operations["span_attributes"].append("http.method")
            if '"http.url"' in content or "'http.url'" in content:
                operations["span_attributes"].append("http.url")

            print(f"  Found {len(operations['django_operations'])} Django operation patterns")
            print(f"  Found {len(operations['span_attributes'])} span attributes")

        # Review FastAPI tracing
        shared_tracing_file = self.services_dir / "shared" / "tracing.py"
        if shared_tracing_file.exists():
            content = shared_tracing_file.read_text()

            # FastAPI instrumentation creates spans automatically
            # Check for service name patterns
            service_pattern = r"service_name:\s*['\"]([^'\"]+)['\"]"
            services = re.findall(service_pattern, content)
            operations["fastapi_operations"] = [f"{service}.*" for service in services]

            # Check for resource attributes
            resource_pattern = r"service\.name['\"]?\s*:\s*['\"]?([^'\"]+)['\"]?"
            resource_services = re.findall(resource_pattern, content)
            operations["fastapi_operations"].extend([f"{s}.*" for s in resource_services])

            print(f"  Found {len(operations['fastapi_operations'])} FastAPI service patterns")

        # Review span instrumentation
        span_instrumentation_file = (
            self.hub_dir / "apps" / "observability" / "span_instrumentation.py"
        )
        if span_instrumentation_file.exists():
            content = span_instrumentation_file.read_text()

            # Extract service call patterns
            service_call_patterns = [
                r'span_name\s*=\s*f?"([^"]+)"',
                r'f?"([^"]+)"\s*,\s*kind=',
                r'start_as_current_span\s*\(\s*f?"([^"]+)"',
            ]

            for pattern in service_call_patterns:
                matches = re.findall(pattern, content)
                operations["operation_patterns"].extend(matches)

            # Check for endpoint attribute
            if '"service.endpoint"' in content or "'service.endpoint'" in content:
                operations["span_attributes"].append("service.endpoint")

            print(f"  Found {len(operations['operation_patterns'])} additional operation patterns")

        # Review OpenTelemetry config
        otel_config_file = self.hub_dir / "apps" / "observability" / "otel_config.py"
        if otel_config_file.exists():
            content = otel_config_file.read_text()

            # Check for Django instrumentation
            if "DjangoInstrumentor" in content:
                operations["operation_patterns"].append("DjangoInstrumentor (auto-instrumentation)")

            # Check for FastAPI instrumentation
            if "FastAPIInstrumentor" in content:
                operations["operation_patterns"].append(
                    "FastAPIInstrumentor (auto-instrumentation)"
                )

        self.jaeger_operations = operations
        return operations

    def review_log_aggregation(self) -> dict[str, list[str]]:
        """Review log aggregation configuration for URL patterns."""
        print("\n=== Reviewing Log Aggregation Configuration ===")

        patterns = {"promtail_configs": [], "loki_patterns": [], "log_url_patterns": []}

        # Review Promtail configuration
        promtail_config = self.k8s_dir / "logging" / "promtail" / "configmap.yaml"
        if promtail_config.exists():
            content = promtail_config.read_text()

            # Extract scrape configs (handle YAML embedded in YAML)
            job_pattern = r"job_name:\s*['\"]?([^'\"]+)['\"]?"
            jobs = re.findall(job_pattern, content)
            patterns["promtail_configs"] = list(set(jobs))

            # Extract path patterns (including embedded YAML)
            path_pattern = r"__path__:\s*['\"]?([^'\"]+)['\"]?"
            paths = re.findall(path_pattern, content)
            patterns["log_url_patterns"].extend(paths)

            # Extract label patterns that might include URL/endpoint info
            label_pattern = r"target_label:\s*['\"]?([^'\"]+)['\"]?"
            labels = re.findall(label_pattern, content)
            if "pod" in labels or "container" in labels:
                patterns["log_url_patterns"].append("Kubernetes pod/container labels")

            print(f"  Found {len(patterns['promtail_configs'])} Promtail scrape jobs")

        # Review Django logging configuration
        settings_file = self.hub_dir / "settings.py"
        if settings_file.exists():
            content = settings_file.read_text()

            # Check for structured logging with URL patterns
            url_log_pattern = r"['\"]path['\"]|['\"]url['\"]|['\"]endpoint['\"]|request\.path"
            if re.search(url_log_pattern, content):
                patterns["log_url_patterns"].append("Django request.path in logging config")
                print("  Found Django logging with URL patterns")

        # Review observability logging
        logging_file = self.hub_dir / "apps" / "observability" / "logging.py"
        if logging_file.exists():
            content = logging_file.read_text()

            # Check for URL logging
            if "request.path" in content or "http.route" in content or "http.url" in content:
                patterns["log_url_patterns"].append("structlog with http.route/http.url")
                print("  Found structlog with HTTP route patterns")

        # Review middleware that logs URLs
        middleware_files = [
            self.hub_dir / "apps" / "observability" / "middleware" / "span_middleware.py",
            self.hub_dir / "apps" / "api" / "middleware" / "tracing.py",
        ]

        for middleware_file in middleware_files:
            if middleware_file.exists():
                content = middleware_file.read_text()
                if "request.path" in content or "http.route" in content:
                    patterns["log_url_patterns"].append(f"{middleware_file.name} logs request.path")

        self.log_patterns = patterns
        return patterns

    def map_monitoring_to_endpoints(self) -> dict[str, dict[str, Any]]:
        """Map all monitoring configurations to endpoints."""
        print("\n=== Mapping Monitoring Configs to Endpoints ===")

        mapping = {}

        # Get all endpoints
        endpoints = self.extract_endpoints_from_urls()
        self.endpoints = endpoints
        print(f"  Found {len(endpoints)} API endpoints")

        # Map Prometheus metrics
        for metric in self.prometheus_metrics.get("metrics_with_endpoint_labels", []):
            for endpoint in endpoints:
                if endpoint not in mapping:
                    mapping[endpoint] = {
                        "endpoint": endpoint,
                        "prometheus_metrics": [],
                        "grafana_queries": [],
                        "jaeger_operations": [],
                        "log_patterns": [],
                    }
                mapping[endpoint]["prometheus_metrics"].append(metric)

        # Map Grafana queries
        for query in self.grafana_queries:
            if query.get("has_route_label"):
                # Try to match queries to endpoints
                for endpoint in endpoints:
                    if endpoint not in mapping:
                        mapping[endpoint] = {
                            "endpoint": endpoint,
                            "prometheus_metrics": [],
                            "grafana_queries": [],
                            "jaeger_operations": [],
                            "log_patterns": [],
                        }
                    # Check if query mentions this endpoint pattern
                    endpoint_pattern = endpoint.replace("/", "\\/").replace("{id}", ".*")
                    if re.search(endpoint_pattern, query["query"], re.IGNORECASE):
                        mapping[endpoint]["grafana_queries"].append(
                            {
                                "dashboard": query["dashboard"],
                                "panel": query["panel"],
                                "query": query["query"],
                            }
                        )

        # Map Jaeger operations
        for operation_pattern in self.jaeger_operations.get("operation_patterns", []):
            for endpoint in endpoints:
                if endpoint not in mapping:
                    mapping[endpoint] = {
                        "endpoint": endpoint,
                        "prometheus_metrics": [],
                        "grafana_queries": [],
                        "jaeger_operations": [],
                        "log_patterns": [],
                    }
                # Check if operation pattern matches endpoint
                if (
                    endpoint in operation_pattern
                    or operation_pattern.replace("{id}", ".*") in endpoint
                ):
                    mapping[endpoint]["jaeger_operations"].append(operation_pattern)

        # Map log patterns
        for log_pattern in self.log_patterns.get("log_url_patterns", []):
            for endpoint in endpoints:
                if endpoint not in mapping:
                    mapping[endpoint] = {
                        "endpoint": endpoint,
                        "prometheus_metrics": [],
                        "grafana_queries": [],
                        "jaeger_operations": [],
                        "log_patterns": [],
                    }
                mapping[endpoint]["log_patterns"].append(log_pattern)

        self.endpoint_mapping = mapping
        print(f"  Mapped monitoring configs to {len(mapping)} endpoints")
        return mapping

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive monitoring review report."""
        report = {
            "summary": {
                "endpoints_found": len(self.endpoints),
                "prometheus_metrics_with_endpoints": len(
                    self.prometheus_metrics.get("metrics_with_endpoint_labels", [])
                ),
                "grafana_queries_reviewed": len(self.grafana_queries),
                "jaeger_operation_patterns": len(
                    self.jaeger_operations.get("operation_patterns", [])
                ),
                "log_patterns_found": len(self.log_patterns.get("log_url_patterns", [])),
                "endpoints_mapped": len(self.endpoint_mapping),
            },
            "prometheus": self.prometheus_metrics,
            "grafana": {
                "total_queries": len(self.grafana_queries),
                "queries_with_route_labels": len(
                    [q for q in self.grafana_queries if q.get("has_route_label")]
                ),
                "queries_with_method_labels": len(
                    [q for q in self.grafana_queries if q.get("has_method_label")]
                ),
                "queries_with_service_labels": len(
                    [q for q in self.grafana_queries if q.get("has_service_label")]
                ),
                "sample_queries": self.grafana_queries[:10],
            },
            "jaeger": self.jaeger_operations,
            "logging": self.log_patterns,
            "endpoint_mapping": self.endpoint_mapping,
        }

        return report

    def save_report(self, output_file: Path):
        """Save review report to JSON file."""
        report = self.generate_report()

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n=== Report saved to {output_file} ===")

    def print_summary(self):
        """Print summary of review findings."""
        print("\n" + "=" * 80)
        print("MONITORING AND OBSERVABILITY REVIEW SUMMARY")
        print("=" * 80)

        print(f"\nEndpoints Found: {len(self.endpoints)}")
        print(
            f"Prometheus Metrics with Endpoint Labels: {len(self.prometheus_metrics.get('metrics_with_endpoint_labels', []))}"
        )
        print(f"Grafana Queries Reviewed: {len(self.grafana_queries)}")
        print(
            f"  - With route labels: {len([q for q in self.grafana_queries if q.get('has_route_label')])}"
        )
        print(
            f"  - With method labels: {len([q for q in self.grafana_queries if q.get('has_method_label')])}"
        )
        print(
            f"Jaeger Operation Patterns: {len(self.jaeger_operations.get('operation_patterns', []))}"
        )
        print(f"Log Patterns Found: {len(self.log_patterns.get('log_url_patterns', []))}")
        print(f"Endpoints Mapped: {len(self.endpoint_mapping)}")

        print("\n" + "=" * 80)


def main():
    """Main execution function."""
    project_root = Path(__file__).parent.parent
    reviewer = MonitoringReviewer(project_root)

    # Run all reviews
    reviewer.review_prometheus_metrics()
    reviewer.review_grafana_dashboards()
    reviewer.review_jaeger_traces()
    reviewer.review_log_aggregation()
    reviewer.map_monitoring_to_endpoints()

    # Generate and save report
    output_file = project_root / "monitoring_review_report.json"
    reviewer.save_report(output_file)
    reviewer.print_summary()

    # Return exit code based on findings
    if len(reviewer.endpoints) == 0:
        print("\nWARNING: No endpoints found!")
        return 1

    if len(reviewer.prometheus_metrics.get("metrics_with_endpoint_labels", [])) == 0:
        print("\nWARNING: No Prometheus metrics with endpoint labels found!")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
