#!/usr/bin/env python3
"""
Generate Service Integration Impact Report

This script compiles service integration references from previous analysis tasks and generates
a comprehensive service integration matrix showing how services integrate with each other.

Dependencies:
- inter-service-communication-report.json (from task 9.6.1.3.2)
- service-client-audit.json (from task 9.6.1.3.1)
- gateway-config-review.json (from task 9.6.1.3.3)

Usage:
    python scripts/generate_service_integration_impact_report.py
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Optional


class ServiceIntegrationImpactAnalyzer:
    """Analyzer for service integration impact analysis"""

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.service_integrations: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.integration_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.service_details: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def load_analysis_data(self) -> Dict[str, Any]:
        """Load all analysis data from previous tasks"""
        data = {}

        # Load inter-service communication report
        inter_service_file = self.base_path / "docs" / "api-audit" / "inter-service-communication-report.json"
        if inter_service_file.exists():
            try:
                with open(inter_service_file, "r") as f:
                    data["inter_service_communication"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load inter-service communication report: {e}", file=sys.stderr)

        # Load service client audit report
        service_client_file = self.base_path / "docs" / "api-audit" / "service-client-audit.json"
        if service_client_file.exists():
            try:
                with open(service_client_file, "r") as f:
                    data["service_client_audit"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load service client audit report: {e}", file=sys.stderr)

        # Load gateway config review report
        gateway_file = self.base_path / "docs" / "api-audit" / "gateway-config-review.json"
        if gateway_file.exists():
            try:
                with open(gateway_file, "r") as f:
                    data["gateway_config"] = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load gateway config review report: {e}", file=sys.stderr)

        return data

    def compile_service_integrations(self, data: Dict[str, Any]) -> None:
        """Compile service integration references from all sources"""

        # Process inter-service communication data
        if "inter_service_communication" in data:
            self._process_inter_service_communication(data["inter_service_communication"])

        # Process service client audit data
        if "service_client_audit" in data:
            self._process_service_client_audit(data["service_client_audit"])

        # Process gateway config data
        if "gateway_config" in data:
            self._process_gateway_config(data["gateway_config"])

    def _process_inter_service_communication(self, report: Dict[str, Any]) -> None:
        """Process inter-service communication report"""
        dependencies = report.get("dependencies", {})
        service_calls = report.get("service_calls", [])

        for dep_key, dep_data in dependencies.items():
            # Handle both "source->target" and "source -> target" formats
            if " -> " in dep_key:
                source, target = dep_key.split(" -> ", 1)
            elif "->" in dep_key:
                source, target = dep_key.split("->", 1)
            else:
                # Skip malformed keys
                continue

            if source not in self.service_integrations:
                self.service_integrations[source] = {
                    "outbound": {},
                    "inbound": {},
                    "gateway_routes": [],
                    "service_clients": [],
                    "call_count": 0,
                    "endpoints": set()
                }

            if target not in self.service_integrations:
                self.service_integrations[target] = {
                    "outbound": {},
                    "inbound": {},
                    "gateway_routes": [],
                    "service_clients": [],
                    "call_count": 0,
                    "endpoints": set()
                }

            # Track outbound from source
            self.service_integrations[source]["outbound"][target] = {
                "call_count": dep_data.get("call_count", 0),
                "endpoints": dep_data.get("endpoints", []),
                "client_types": dep_data.get("client_types", [])
            }

            # Track inbound to target
            self.service_integrations[target]["inbound"][source] = {
                "call_count": dep_data.get("call_count", 0),
                "endpoints": dep_data.get("endpoints", []),
                "client_types": dep_data.get("client_types", [])
            }

            # Update integration matrix
            self.integration_matrix[source][target] += dep_data.get("call_count", 0)

            # Track endpoints
            for endpoint in dep_data.get("endpoints", []):
                self.service_integrations[source]["endpoints"].add(endpoint)
                self.service_integrations[target]["endpoints"].add(endpoint)

            # Update call counts
            self.service_integrations[source]["call_count"] += dep_data.get("call_count", 0)
            self.service_integrations[target]["call_count"] += dep_data.get("call_count", 0)

    def _process_service_client_audit(self, report: Dict[str, Any]) -> None:
        """Process service client audit report"""
        service_clients = report.get("service_clients", [])

        for client in service_clients:
            service_name = client.get("service_name", "").replace("-", "-")
            class_name = client.get("class_name", "")
            base_url = client.get("base_url", "")
            methods = client.get("methods", [])

            # Normalize service name
            normalized_name = self._normalize_service_name(service_name)

            if normalized_name not in self.service_integrations:
                self.service_integrations[normalized_name] = {
                    "outbound": {},
                    "inbound": {},
                    "gateway_routes": [],
                    "service_clients": [],
                    "call_count": 0,
                    "endpoints": set()
                }

            # Track service client
            client_info = {
                "class_name": class_name,
                "base_url": base_url,
                "file_path": client.get("file_path", ""),
                "methods": []
            }

            for method in methods:
                method_info = {
                    "method_name": method.get("method_name", ""),
                    "endpoints": [call.get("endpoint", "") for call in method.get("http_calls", [])],
                    "http_methods": [call.get("http_method", "") for call in method.get("http_calls", [])]
                }
                client_info["methods"].append(method_info)

                # Track endpoints
                for endpoint in method_info["endpoints"]:
                    self.service_integrations[normalized_name]["endpoints"].add(endpoint)

            self.service_integrations[normalized_name]["service_clients"].append(client_info)

    def _process_gateway_config(self, report: Dict[str, Any]) -> None:
        """Process gateway configuration review report"""
        traefik_review = report.get("traefik_review", {})
        ingress_review = report.get("ingress_review", {})

        # Process Traefik routers
        routers = traefik_review.get("routers", [])
        for router in routers:
            service_name = router.get("service", "")
            if service_name:
                normalized_name = self._normalize_service_name(service_name)

                if normalized_name not in self.service_integrations:
                    self.service_integrations[normalized_name] = {
                        "outbound": {},
                        "inbound": {},
                        "gateway_routes": [],
                        "service_clients": [],
                        "call_count": 0,
                        "endpoints": set()
                    }

                route_info = {
                    "router_name": router.get("router_name", ""),
                    "path_prefix": router.get("path_prefix", ""),
                    "host_pattern": router.get("host_pattern", ""),
                    "middlewares": router.get("middlewares", []),
                    "type": "traefik"
                }
                self.service_integrations[normalized_name]["gateway_routes"].append(route_info)

                # Track path prefix as endpoint
                if route_info["path_prefix"]:
                    self.service_integrations[normalized_name]["endpoints"].add(route_info["path_prefix"])

        # Process Kubernetes ingress rules
        ingress_rules = ingress_review.get("rules", [])
        for rule in ingress_rules:
            service_name = rule.get("service_name", "")
            if service_name:
                normalized_name = self._normalize_service_name(service_name)

                if normalized_name not in self.service_integrations:
                    self.service_integrations[normalized_name] = {
                        "outbound": {},
                        "inbound": {},
                        "gateway_routes": [],
                        "service_clients": [],
                        "call_count": 0,
                        "endpoints": set()
                    }

                route_info = {
                    "ingress_name": rule.get("ingress_name", ""),
                    "host": rule.get("host", ""),
                    "path": rule.get("path", ""),
                    "namespace": rule.get("namespace", ""),
                    "type": "kubernetes-ingress"
                }
                self.service_integrations[normalized_name]["gateway_routes"].append(route_info)

    def _normalize_service_name(self, name: str) -> str:
        """Normalize service name for consistent matching"""
        if not name:
            return name
        # Strip whitespace
        name = name.strip()
        # Remove common suffixes
        name = name.replace("-service", "").replace("_service", "")
        # Convert to lowercase
        name = name.lower()
        # Handle special cases
        name_mapping = {
            "d-q": "dq",
            "dq": "dq-service",
            "data-contract-c-l-i": "datacontract",
            "datacontract": "datacontract-service",
            "api": "api-service",
            "compliance": "compliance-service",
            "semantic": "semantic-service",
            "search": "search-service",
            "webhook": "webhook-service",
            "observability": "observability-service",
            "worker": "worker-service"
        }
        return name_mapping.get(name, name)

    def generate_integration_matrix(self) -> Dict[str, Dict[str, int]]:
        """Generate service integration matrix"""
        # Get all unique services
        all_services = set(self.service_integrations.keys())

        # Build matrix
        matrix = {}
        for source in sorted(all_services):
            matrix[source] = {}
            for target in sorted(all_services):
                if source == target:
                    matrix[source][target] = 0  # Self-references
                else:
                    # Count integrations from source to target
                    count = 0
                    if source in self.service_integrations:
                        outbound = self.service_integrations[source].get("outbound", {})
                        if target in outbound:
                            count = outbound[target].get("call_count", 0)
                    matrix[source][target] = count

        return matrix

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive service integration impact report"""
        # Convert sets to lists for JSON serialization
        report_data = {}
        for service, details in self.service_integrations.items():
            report_data[service] = {
                "outbound": details["outbound"],
                "inbound": details["inbound"],
                "gateway_routes": details["gateway_routes"],
                "service_clients": details["service_clients"],
                "call_count": details["call_count"],
                "endpoint_count": len(details["endpoints"]),
                "endpoints": sorted(list(details["endpoints"]))
            }

        matrix = self.generate_integration_matrix()

        # Calculate summary statistics
        total_services = len(self.service_integrations)
        total_integrations = sum(
            len(details.get("outbound", {}))
            for details in self.service_integrations.values()
        )
        total_service_calls = sum(
            details.get("call_count", 0)
            for details in self.service_integrations.values()
        )

        return {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_services": total_services,
                "total_integrations": total_integrations,
                "total_service_calls": total_service_calls,
                "services": sorted(list(self.service_integrations.keys()))
            },
            "service_integrations": report_data,
            "integration_matrix": matrix
        }

    def generate_markdown_report(self, report: Dict[str, Any]) -> str:
        """Generate markdown report"""
        md_lines = []

        md_lines.append("# Service Integration Impact Report\n")
        md_lines.append(f"**Generated:** {report['generated_at']}\n")

        # Summary
        summary = report["summary"]
        md_lines.append("## Summary\n")
        md_lines.append(f"- **Total Services:** {summary['total_services']}")
        md_lines.append(f"- **Total Integrations:** {summary['total_integrations']}")
        md_lines.append(f"- **Total Service Calls:** {summary['total_service_calls']}")
        md_lines.append(f"- **Services Involved:** {', '.join(summary['services'])}\n")

        # Integration Matrix
        md_lines.append("## Service Integration Matrix\n")
        md_lines.append("This matrix shows the number of service calls from each source service to each target service.\n")
        md_lines.append("\n| Source → Target | " + " | ".join(summary['services']) + " |")
        md_lines.append("|" + "---|" * (len(summary['services']) + 1))

        matrix = report["integration_matrix"]
        for source in summary['services']:
            row = [source]
            for target in summary['services']:
                count = matrix.get(source, {}).get(target, 0)
                row.append(str(count) if count > 0 else "-")
            md_lines.append("| " + " | ".join(row) + " |")

        md_lines.append("\n")

        # Service Details
        md_lines.append("## Service Integration Details\n")

        for service_name in sorted(report["service_integrations"].keys()):
            service_data = report["service_integrations"][service_name]
            md_lines.append(f"### {service_name}\n")

            # Outbound integrations
            if service_data.get("outbound"):
                md_lines.append("#### Outbound Integrations\n")
                for target, details in service_data["outbound"].items():
                    md_lines.append(f"- **{target}**: {details['call_count']} calls")
                    if details.get("endpoints"):
                        md_lines.append(f"  - Endpoints: {', '.join(details['endpoints'][:5])}")
                        if len(details['endpoints']) > 5:
                            md_lines.append(f"  - ... and {len(details['endpoints']) - 5} more")
                    md_lines.append("")

            # Inbound integrations
            if service_data.get("inbound"):
                md_lines.append("#### Inbound Integrations\n")
                for source, details in service_data["inbound"].items():
                    md_lines.append(f"- **{source}**: {details['call_count']} calls")
                    if details.get("endpoints"):
                        md_lines.append(f"  - Endpoints: {', '.join(details['endpoints'][:5])}")
                        if len(details['endpoints']) > 5:
                            md_lines.append(f"  - ... and {len(details['endpoints']) - 5} more")
                    md_lines.append("")

            # Gateway routes
            if service_data.get("gateway_routes"):
                md_lines.append("#### Gateway Routes\n")
                for route in service_data["gateway_routes"]:
                    if route.get("type") == "traefik":
                        md_lines.append(f"- **Traefik Router**: {route.get('router_name', 'N/A')}")
                        if route.get("path_prefix"):
                            md_lines.append(f"  - Path Prefix: `{route['path_prefix']}`")
                        if route.get("middlewares"):
                            md_lines.append(f"  - Middlewares: {', '.join(route['middlewares'])}")
                    elif route.get("type") == "kubernetes-ingress":
                        md_lines.append(f"- **Kubernetes Ingress**: {route.get('ingress_name', 'N/A')}")
                        if route.get("host"):
                            md_lines.append(f"  - Host: `{route['host']}`")
                        if route.get("path"):
                            md_lines.append(f"  - Path: `{route['path']}`")
                    md_lines.append("")

            # Service clients
            if service_data.get("service_clients"):
                md_lines.append("#### Service Clients\n")
                for client in service_data["service_clients"]:
                    md_lines.append(f"- **{client.get('class_name', 'N/A')}**")
                    md_lines.append(f"  - Base URL: `{client.get('base_url', 'N/A')}`")
                    md_lines.append(f"  - Methods: {len(client.get('methods', []))}")
                    md_lines.append("")

            # Endpoints
            if service_data.get("endpoints"):
                md_lines.append(f"#### Endpoints ({service_data['endpoint_count']})\n")
                endpoints = service_data["endpoints"][:10]
                for endpoint in endpoints:
                    md_lines.append(f"- `{endpoint}`")
                if len(service_data["endpoints"]) > 10:
                    md_lines.append(f"- ... and {len(service_data['endpoints']) - 10} more endpoints")
                md_lines.append("")

            md_lines.append("---\n")

        return "\n".join(md_lines)


def main():
    """Main entry point"""
    analyzer = ServiceIntegrationImpactAnalyzer()

    print("=" * 80)
    print("Service Integration Impact Report Generator")
    print("=" * 80)
    print()

    print("Loading analysis data...")
    data = analyzer.load_analysis_data()

    if not data:
        print("Error: No analysis data found. Please run previous analysis tasks first.", file=sys.stderr)
        sys.exit(1)

    print("Compiling service integrations...")
    analyzer.compile_service_integrations(data)

    print("Generating report...")
    report = analyzer.generate_report()

    # Save JSON report
    output_dir = Path("docs/api-audit")
    output_dir.mkdir(parents=True, exist_ok=True)

    json_file = output_dir / "service-integration-impact.json"
    with open(json_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  JSON report saved to: {json_file}")

    # Generate and save Markdown report
    md_content = analyzer.generate_markdown_report(report)
    md_file = output_dir / "service-integration-impact.md"
    with open(md_file, "w") as f:
        f.write(md_content)
    print(f"  Markdown report saved to: {md_file}")

    print()
    print("=" * 80)
    print("Report Generation Complete")
    print("=" * 80)
    print()
    print(f"Summary:")
    print(f"  Total Services: {report['summary']['total_services']}")
    print(f"  Total Integrations: {report['summary']['total_integrations']}")
    print(f"  Total Service Calls: {report['summary']['total_service_calls']}")
    print(f"  Services: {', '.join(report['summary']['services'])}")


if __name__ == "__main__":
    main()

