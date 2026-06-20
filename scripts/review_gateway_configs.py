#!/usr/bin/env python3
"""
Comprehensive Gateway Configuration Review Script

Reviews Traefik route configurations, Kubernetes ingress rules, and API gateway
configurations. Maps gateway rules to endpoints and generates a comprehensive report.

This script:
1. Reviews Traefik route configurations (Docker Compose and Kubernetes)
2. Reviews Kubernetes ingress rules
3. Reviews API gateway configurations
4. Maps gateway rules to Django endpoints
5. Validates configuration consistency
6. Generates comprehensive review report

Usage:
    python scripts/review_gateway_configs.py [--output-dir docs/api-audit]
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TraefikConfigParser:
    """Parser for Traefik configuration files"""

    def parse_routes_file(self, file_path: Path) -> dict[str, Any]:
        """Parse Traefik routes.yml file"""
        with open(file_path) as f:
            content = yaml.safe_load(f)
        return content.get("http", {})

    def extract_routing_rules(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract routing rules from Traefik config"""
        rules = []
        routers = config.get("routers", {})

        for router_name, router_config in routers.items():
            rule = router_config.get("rule", "")
            service = router_config.get("service", "")
            middlewares = router_config.get("middlewares", [])
            entry_points = router_config.get("entryPoints", [])

            # Extract path prefix from rule
            path_prefix = self._extract_path_prefix(rule)
            host_pattern = self._extract_host_pattern(rule)

            rules.append(
                {
                    "router_name": router_name,
                    "rule": rule,
                    "path_prefix": path_prefix,
                    "host_pattern": host_pattern,
                    "service": service,
                    "middlewares": middlewares,
                    "entry_points": entry_points,
                    "tls": router_config.get("tls", {}),
                }
            )

        return rules

    def extract_service_definitions(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract service definitions from Traefik config"""
        services = []
        service_defs = config.get("services", {})

        for service_name, service_config in service_defs.items():
            load_balancer = service_config.get("loadBalancer", {})
            servers = load_balancer.get("servers", [])

            for server in servers:
                url = server.get("url", "")
                services.append(
                    {
                        "service_name": service_name,
                        "url": url,
                        "host": self._extract_host_from_url(url),
                        "port": self._extract_port_from_url(url),
                    }
                )

        return services

    def extract_middlewares(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract middleware definitions from Traefik config"""
        middlewares = []
        middleware_defs = config.get("middlewares", {})

        for middleware_name, middleware_config in middleware_defs.items():
            middlewares.append(
                {
                    "name": middleware_name,
                    "config": middleware_config,
                    "type": self._identify_middleware_type(middleware_config),
                }
            )

        return middlewares

    def _extract_path_prefix(self, rule: str) -> str | None:
        """Extract path prefix from Traefik rule"""
        match = re.search(r"PathPrefix\(`([^`]+)`\)", rule)
        return match.group(1) if match else None

    def _extract_host_pattern(self, rule: str) -> str | None:
        """Extract host pattern from Traefik rule"""
        match = re.search(r"Host\(`([^`]+)`\)", rule)
        return match.group(1) if match else None

    def _extract_host_from_url(self, url: str) -> str | None:
        """Extract host from URL"""
        match = re.search(r"://([^:/]+)", url)
        return match.group(1) if match else None

    def _extract_port_from_url(self, url: str) -> int | None:
        """Extract port from URL"""
        match = re.search(r":(\d+)(?:/|$)", url)
        return int(match.group(1)) if match else None

    def _identify_middleware_type(self, config: dict[str, Any]) -> str:
        """Identify middleware type from configuration"""
        if "forwardAuth" in config:
            return "auth"
        elif "rateLimit" in config:
            return "rate_limit"
        elif "headers" in config:
            if "accessControlAllowOriginList" in config.get("headers", {}):
                return "cors"
            else:
                return "headers"
        elif "stripPrefix" in config:
            return "strip_prefix"
        else:
            return "unknown"


class KubernetesIngressParser:
    """Parser for Kubernetes ingress configurations"""

    def parse_ingress_file(self, file_path: Path) -> dict[str, Any]:
        """Parse Kubernetes ingress YAML file"""
        with open(file_path) as f:
            content = yaml.safe_load(f)
        return content

    def extract_ingress_rules(self, ingress: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract ingress rules from Kubernetes ingress"""
        rules = []
        metadata = ingress.get("metadata", {})
        spec = ingress.get("spec", {})
        ingress_rules = spec.get("rules", [])

        for rule in ingress_rules:
            host = rule.get("host", "")
            http_paths = rule.get("http", {}).get("paths", [])

            for path_config in http_paths:
                path = path_config.get("path", "/")
                path_type = path_config.get("pathType", "Prefix")
                backend = path_config.get("backend", {})
                service = backend.get("service", {})
                service_name = service.get("name", "")
                service_port = service.get("port", {}).get("number")

                # Extract TLS configuration
                tls_hosts = []
                tls_secret = None
                tls_configs = spec.get("tls", [])
                for tls_config in tls_configs:
                    if host in tls_config.get("hosts", []):
                        tls_hosts = tls_config.get("hosts", [])
                        tls_secret = tls_config.get("secretName")
                        break

                rules.append(
                    {
                        "ingress_name": metadata.get("name", ""),
                        "namespace": metadata.get("namespace", "default"),
                        "host": host,
                        "path": path,
                        "path_type": path_type,
                        "service_name": service_name,
                        "service_port": service_port,
                        "ingress_class": spec.get("ingressClassName", ""),
                        "annotations": metadata.get("annotations", {}),
                        "tls_hosts": tls_hosts,
                        "tls_secret": tls_secret,
                    }
                )

        return rules


class DjangoEndpointExtractor:
    """Extract Django endpoints from URL patterns"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.endpoints: list[dict[str, Any]] = []

    def extract_endpoints(self) -> list[dict[str, Any]]:
        """Extract all Django endpoints from URL patterns"""
        # Try to load from existing inventory if available
        inventory_file = (
            self.project_root / "docs" / "api-audit" / "endpoint-inventory-current.json"
        )
        if inventory_file.exists():
            try:
                with open(inventory_file) as f:
                    inventory_data = json.load(f)
                    # Handle different inventory structures
                    if "inventory" in inventory_data:
                        endpoints = inventory_data["inventory"].get("endpoints", [])
                    elif "endpoints" in inventory_data:
                        endpoints = inventory_data["endpoints"]
                    else:
                        endpoints = []

                    if endpoints:
                        # Normalize endpoint format for mapping
                        normalized = []
                        for ep in endpoints:
                            full_path = ep.get("full_path", ep.get("path", ""))
                            if full_path:
                                normalized.append(
                                    {
                                        "path": full_path,
                                        "method": ep.get("methods", ["GET"])[0]
                                        if ep.get("methods")
                                        else "GET",
                                        "name": ep.get("name", ""),
                                        "service": ep.get("service", ""),
                                    }
                                )
                        return normalized
            except Exception as e:
                print(f"Warning: Could not load endpoint inventory: {e}", file=sys.stderr)

        # Try proposed inventory as fallback
        proposed_file = (
            self.project_root / "docs" / "api-audit" / "endpoint-inventory-proposed.json"
        )
        if proposed_file.exists():
            try:
                with open(proposed_file) as f:
                    inventory_data = json.load(f)
                    if "inventory" in inventory_data:
                        endpoints = inventory_data["inventory"].get("endpoints", [])
                    elif "endpoints" in inventory_data:
                        endpoints = inventory_data["endpoints"]
                    else:
                        endpoints = []

                    if endpoints:
                        normalized = []
                        for ep in endpoints:
                            full_path = ep.get("full_path", ep.get("path", ""))
                            if full_path:
                                normalized.append(
                                    {
                                        "path": full_path,
                                        "method": ep.get("methods", ["GET"])[0]
                                        if ep.get("methods")
                                        else "GET",
                                        "name": ep.get("name", ""),
                                        "service": ep.get("service", ""),
                                    }
                                )
                        return normalized
            except Exception:
                pass

        # Fallback: extract from Django URLs
        return self._extract_from_urls()

    def _extract_from_urls(self) -> list[dict[str, Any]]:
        """Extract endpoints from Django URL patterns"""
        # This is a simplified extraction - in practice, you'd use Django's URL resolver
        # For now, return empty list as we'll rely on the inventory file
        return []


class EndpointMapper:
    """Map gateway rules to Django endpoints"""

    def map_traefik_routes_to_endpoints(
        self, traefik_routes: list[dict[str, Any]], django_endpoints: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Map Traefik routes to Django endpoints"""
        mappings = []

        for route in traefik_routes:
            path_prefix = route.get("path_prefix", "")
            if not path_prefix:
                continue

            matching_endpoints = [
                ep for ep in django_endpoints if ep.get("path", "").startswith(path_prefix)
            ]

            mappings.append(
                {
                    "route": route["router_name"],
                    "path_prefix": path_prefix,
                    "service": route.get("service", ""),
                    "endpoints": matching_endpoints,
                    "endpoint_count": len(matching_endpoints),
                }
            )

        return mappings

    def map_ingress_rules_to_endpoints(
        self, ingress_rules: list[dict[str, Any]], django_endpoints: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Map Kubernetes ingress rules to Django endpoints"""
        mappings = []

        for rule in ingress_rules:
            path = rule.get("path", "/")
            host = rule.get("host", "")

            # For root path, match all endpoints
            if path == "/":
                matching_endpoints = django_endpoints
            else:
                matching_endpoints = [
                    ep for ep in django_endpoints if ep.get("path", "").startswith(path)
                ]

            mappings.append(
                {
                    "ingress": rule["ingress_name"],
                    "host": host,
                    "path": path,
                    "service": rule.get("service_name", ""),
                    "namespace": rule.get("namespace", ""),
                    "endpoints": matching_endpoints,
                    "endpoint_count": len(matching_endpoints),
                }
            )

        return mappings


class GatewayConfigReviewer:
    """Comprehensive gateway configuration reviewer"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.traefik_parser = TraefikConfigParser()
        self.ingress_parser = KubernetesIngressParser()
        self.endpoint_extractor = DjangoEndpointExtractor(self.project_root)
        self.endpoint_mapper = EndpointMapper()

        self.traefik_configs: list[dict[str, Any]] = []
        self.ingress_configs: list[dict[str, Any]] = []
        self.issues: list[dict[str, Any]] = []
        self.mappings: dict[str, Any] = {}

    def find_traefik_configs(self) -> list[Path]:
        """Find all Traefik configuration files"""
        configs = []

        # Docker Compose Traefik configs
        traefik_dir = self.project_root / "infrastructure" / "traefik"
        if traefik_dir.exists():
            routes_file = traefik_dir / "dynamic" / "routes.yml"
            if routes_file.exists():
                configs.append(routes_file)

        # Kubernetes Traefik configs
        k8s_traefik_dir = self.project_root / "k8s" / "api-gateway" / "traefik"
        if k8s_traefik_dir.exists():
            configmap_file = k8s_traefik_dir / "configmap.yaml"
            if configmap_file.exists():
                configs.append(configmap_file)

        return configs

    def find_ingress_configs(self) -> list[Path]:
        """Find all Kubernetes ingress configuration files"""
        ingress_files = []
        k8s_dir = self.project_root / "k8s"

        if k8s_dir.exists():
            for ingress_file in k8s_dir.rglob("ingress.yaml"):
                if ingress_file.is_file():
                    ingress_files.append(ingress_file)

        return ingress_files

    def review_traefik_configs(self) -> dict[str, Any]:
        """Review all Traefik configurations"""
        configs = self.find_traefik_configs()
        results = {
            "config_files": [],
            "routers": [],
            "services": [],
            "middlewares": [],
            "issues": [],
        }

        for config_file in configs:
            try:
                config_data = self.traefik_parser.parse_routes_file(config_file)

                # Extract components
                routers = self.traefik_parser.extract_routing_rules(config_data)
                services = self.traefik_parser.extract_service_definitions(config_data)
                middlewares = self.traefik_parser.extract_middlewares(config_data)

                # Validate
                issues = self.validate_traefik_config(config_data)

                results["config_files"].append(
                    {
                        "path": str(config_file.relative_to(self.project_root)),
                        "type": "docker-compose"
                        if "infrastructure" in str(config_file)
                        else "kubernetes",
                    }
                )
                results["routers"].extend(routers)
                results["services"].extend(services)
                results["middlewares"].extend(middlewares)
                results["issues"].extend(issues)

            except Exception as e:
                results["issues"].append(
                    {
                        "type": "error",
                        "file": str(config_file.relative_to(self.project_root)),
                        "message": f"Failed to parse config: {e!s}",
                    }
                )

        return results

    def review_ingress_configs(self) -> dict[str, Any]:
        """Review all Kubernetes ingress configurations"""
        ingress_files = self.find_ingress_configs()
        results = {"ingress_files": [], "rules": [], "issues": []}

        for ingress_file in ingress_files:
            try:
                ingress_data = self.ingress_parser.parse_ingress_file(ingress_file)
                rules = self.ingress_parser.extract_ingress_rules(ingress_data)
                issues = self.validate_ingress_config(ingress_data)

                results["ingress_files"].append(
                    {
                        "path": str(ingress_file.relative_to(self.project_root)),
                        "name": ingress_data.get("metadata", {}).get("name", ""),
                        "namespace": ingress_data.get("metadata", {}).get("namespace", "default"),
                    }
                )
                results["rules"].extend(rules)
                results["issues"].extend(issues)

            except Exception as e:
                results["issues"].append(
                    {
                        "type": "error",
                        "file": str(ingress_file.relative_to(self.project_root)),
                        "message": f"Failed to parse ingress: {e!s}",
                    }
                )

        return results

    def validate_traefik_config(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Validate Traefik configuration"""
        issues = []
        routers = config.get("routers", {})
        services = config.get("services", {})

        # Check for routers without services
        for router_name, router_config in routers.items():
            service_name = router_config.get("service", "")
            if service_name and service_name not in services:
                issues.append(
                    {
                        "type": "warning",
                        "component": "router",
                        "name": router_name,
                        "message": f"Router references non-existent service: {service_name}",
                    }
                )

        # Check for services without routers
        service_names = set(services.keys())
        router_service_names = {
            router_config.get("service", "") for router_config in routers.values()
        }
        orphaned_services = (
            service_names - router_service_names - {"api-service"}
        )  # api-service may be used by auth middleware
        for service_name in orphaned_services:
            issues.append(
                {
                    "type": "info",
                    "component": "service",
                    "name": service_name,
                    "message": "Service defined but not referenced by any router",
                }
            )

        return issues

    def validate_ingress_config(self, ingress: dict[str, Any]) -> list[dict[str, Any]]:
        """Validate Kubernetes ingress configuration"""
        issues = []
        metadata = ingress.get("metadata", {})
        spec = ingress.get("spec", {})

        # Check for missing ingress class
        if not spec.get("ingressClassName"):
            issues.append(
                {
                    "type": "warning",
                    "component": "ingress",
                    "name": metadata.get("name", ""),
                    "message": "Missing ingressClassName",
                }
            )

        # Check for missing TLS configuration
        rules = spec.get("rules", [])
        tls_configs = spec.get("tls", [])
        tls_hosts = set()
        for tls_config in tls_configs:
            tls_hosts.update(tls_config.get("hosts", []))

        for rule in rules:
            host = rule.get("host", "")
            if host and host not in tls_hosts:
                issues.append(
                    {
                        "type": "info",
                        "component": "ingress",
                        "name": metadata.get("name", ""),
                        "host": host,
                        "message": "Host defined without TLS configuration",
                    }
                )

        return issues

    def map_gateway_rules_to_endpoints(self) -> dict[str, Any]:
        """Map gateway rules to Django endpoints"""
        django_endpoints = self.endpoint_extractor.extract_endpoints()

        # Review Traefik configs
        traefik_review = self.review_traefik_configs()
        traefik_mappings = self.endpoint_mapper.map_traefik_routes_to_endpoints(
            traefik_review["routers"], django_endpoints
        )

        # Review ingress configs
        ingress_review = self.review_ingress_configs()
        ingress_mappings = self.endpoint_mapper.map_ingress_rules_to_endpoints(
            ingress_review["rules"], django_endpoints
        )

        return {
            "traefik_mappings": traefik_mappings,
            "ingress_mappings": ingress_mappings,
            "total_endpoints": len(django_endpoints),
            "traefik_routes": len(traefik_mappings),
            "ingress_rules": len(ingress_mappings),
        }

    def generate_report(self, output_dir: Path | None = None) -> dict[str, Any]:
        """Generate comprehensive review report"""
        if output_dir is None:
            output_dir = self.project_root / "docs" / "api-audit"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Perform reviews
        traefik_review = self.review_traefik_configs()
        ingress_review = self.review_ingress_configs()
        mappings = self.map_gateway_rules_to_endpoints()

        # Compile report
        report = {
            "timestamp": datetime.now().isoformat(),
            "traefik_review": traefik_review,
            "ingress_review": ingress_review,
            "mappings": mappings,
            "summary": {
                "traefik_configs": len(traefik_review["config_files"]),
                "traefik_routers": len(traefik_review["routers"]),
                "traefik_services": len(traefik_review["services"]),
                "traefik_middlewares": len(traefik_review["middlewares"]),
                "ingress_files": len(ingress_review["ingress_files"]),
                "ingress_rules": len(ingress_review["rules"]),
                "total_issues": len(traefik_review["issues"]) + len(ingress_review["issues"]),
                "mapped_endpoints": mappings["total_endpoints"],
            },
        }

        # Save JSON report
        json_file = output_dir / "gateway-config-review.json"
        with open(json_file, "w") as f:
            json.dump(report, f, indent=2)

        # Generate markdown report
        md_file = output_dir / "gateway-config-review.md"
        self._generate_markdown_report(report, md_file)

        return report

    def _generate_markdown_report(self, report: dict[str, Any], output_file: Path):
        """Generate markdown report"""
        with open(output_file, "w") as f:
            f.write("# Gateway Configuration Review Report\n\n")
            f.write(f"**Generated:** {report['timestamp']}\n\n")

            # Summary
            summary = report["summary"]
            f.write("## Summary\n\n")
            f.write(f"- **Traefik Configs:** {summary['traefik_configs']}\n")
            f.write(f"- **Traefik Routers:** {summary['traefik_routers']}\n")
            f.write(f"- **Traefik Services:** {summary['traefik_services']}\n")
            f.write(f"- **Traefik Middlewares:** {summary['traefik_middlewares']}\n")
            f.write(f"- **Ingress Files:** {summary['ingress_files']}\n")
            f.write(f"- **Ingress Rules:** {summary['ingress_rules']}\n")
            f.write(f"- **Total Issues:** {summary['total_issues']}\n")
            f.write(f"- **Mapped Endpoints:** {summary['mapped_endpoints']}\n\n")

            # Traefik Review
            f.write("## Traefik Configuration Review\n\n")
            traefik = report["traefik_review"]
            f.write(f"### Configuration Files ({len(traefik['config_files'])})\n\n")
            for config_file in traefik["config_files"]:
                f.write(f"- **{config_file['path']}** ({config_file['type']})\n")
            f.write("\n")

            f.write(f"### Routers ({len(traefik['routers'])})\n\n")
            for router in traefik["routers"]:
                f.write(f"- **{router['router_name']}**\n")
                f.write(f"  - Path Prefix: `{router.get('path_prefix', 'N/A')}`\n")
                f.write(f"  - Service: `{router.get('service', 'N/A')}`\n")
                f.write(f"  - Middlewares: {', '.join(router.get('middlewares', []))}\n")
            f.write("\n")

            # Ingress Review
            f.write("## Kubernetes Ingress Review\n\n")
            ingress = report["ingress_review"]
            f.write(f"### Ingress Files ({len(ingress['ingress_files'])})\n\n")
            for ingress_file in ingress["ingress_files"]:
                f.write(f"- **{ingress_file['path']}**\n")
                f.write(f"  - Name: `{ingress_file['name']}`\n")
                f.write(f"  - Namespace: `{ingress_file['namespace']}`\n")
            f.write("\n")

            f.write(f"### Ingress Rules ({len(ingress['rules'])})\n\n")
            for rule in ingress["rules"]:
                f.write(f"- **{rule['ingress_name']}**\n")
                f.write(f"  - Host: `{rule.get('host', 'N/A')}`\n")
                f.write(f"  - Path: `{rule.get('path', 'N/A')}`\n")
                f.write(
                    f"  - Service: `{rule.get('service_name', 'N/A')}:{rule.get('service_port', 'N/A')}`\n"
                )
            f.write("\n")

            # Mappings
            f.write("## Gateway to Endpoint Mappings\n\n")
            mappings = report["mappings"]
            f.write(f"### Traefik Route Mappings ({len(mappings['traefik_mappings'])})\n\n")
            for mapping in mappings["traefik_mappings"]:
                f.write(f"- **{mapping['route']}** (`{mapping['path_prefix']}`)\n")
                f.write(f"  - Service: `{mapping['service']}`\n")
                f.write(f"  - Endpoints: {mapping['endpoint_count']}\n")
            f.write("\n")

            f.write(f"### Ingress Rule Mappings ({len(mappings['ingress_mappings'])})\n\n")
            for mapping in mappings["ingress_mappings"]:
                f.write(f"- **{mapping['ingress']}** (`{mapping['host']}`)\n")
                f.write(f"  - Service: `{mapping['service']}`\n")
                f.write(f"  - Endpoints: {mapping['endpoint_count']}\n")
            f.write("\n")

            # Issues
            all_issues = traefik["issues"] + ingress["issues"]
            if all_issues:
                f.write("## Issues\n\n")
                for issue in all_issues:
                    f.write(f"- **{issue['type'].upper()}**: {issue.get('message', 'N/A')}\n")
                    if "file" in issue:
                        f.write(f"  - File: `{issue['file']}`\n")
                f.write("\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Review gateway configurations")
    parser.add_argument(
        "--output-dir", type=str, default="docs/api-audit", help="Output directory for reports"
    )
    parser.add_argument("--project-root", type=str, default=".", help="Project root directory")

    args = parser.parse_args()

    reviewer = GatewayConfigReviewer(project_root=args.project_root)
    output_dir = Path(args.output_dir)

    print("=" * 80)
    print("Gateway Configuration Review")
    print("=" * 80)
    print()

    print("Reviewing Traefik configurations...")
    traefik_review = reviewer.review_traefik_configs()
    print(f"  Found {len(traefik_review['config_files'])} config files")
    print(f"  Found {len(traefik_review['routers'])} routers")
    print(f"  Found {len(traefik_review['services'])} services")
    print(f"  Found {len(traefik_review['middlewares'])} middlewares")
    print(f"  Found {len(traefik_review['issues'])} issues")
    print()

    print("Reviewing Kubernetes ingress configurations...")
    ingress_review = reviewer.review_ingress_configs()
    print(f"  Found {len(ingress_review['ingress_files'])} ingress files")
    print(f"  Found {len(ingress_review['rules'])} ingress rules")
    print(f"  Found {len(ingress_review['issues'])} issues")
    print()

    print("Mapping gateway rules to endpoints...")
    mappings = reviewer.map_gateway_rules_to_endpoints()
    print(f"  Mapped {mappings['traefik_routes']} Traefik routes")
    print(f"  Mapped {mappings['ingress_rules']} ingress rules")
    print(f"  Total endpoints: {mappings['total_endpoints']}")
    print()

    print("Generating report...")
    report = reviewer.generate_report(output_dir=output_dir)
    print(f"  Report saved to: {output_dir / 'gateway-config-review.json'}")
    print(f"  Markdown report saved to: {output_dir / 'gateway-config-review.md'}")
    print()

    print("=" * 80)
    print("Review Complete")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  Traefik Configs: {report['summary']['traefik_configs']}")
    print(f"  Traefik Routers: {report['summary']['traefik_routers']}")
    print(f"  Ingress Files: {report['summary']['ingress_files']}")
    print(f"  Ingress Rules: {report['summary']['ingress_rules']}")
    print(f"  Total Issues: {report['summary']['total_issues']}")
    print(f"  Mapped Endpoints: {report['summary']['mapped_endpoints']}")


if __name__ == "__main__":
    main()
