#!/usr/bin/env python3
"""
Generate Infrastructure Impact Report

Compiles infrastructure component references from:
- Docker Compose configurations
- Kubernetes configurations
- CI/CD workflows review
- Monitoring and observability review
- Rate limiting configurations review
- API gateway rules review

Task: 9.6.1.6.5 - Generate infrastructure impact report
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import yaml


class InfrastructureImpactReporter:
    """Generate comprehensive infrastructure impact report."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.docker_compose_file = project_root / "docker-compose.yml"
        self.k8s_dir = project_root / "k8s"
        self.docs_dir = project_root / "docs" / "api-audit"
        self.monitoring_dir = project_root / "monitoring"

        # Review report files
        self.cicd_review = self.docs_dir / "cicd-workflows-review.json"
        self.monitoring_review = project_root / "monitoring_review_report.json"
        self.rate_limiting_review = self.docs_dir / "rate-limiting-review.json"
        self.gateway_review = self.docs_dir / "api-gateway-rules-audit.json"

        # Results storage
        self.infrastructure_components: Dict[str, Any] = {
            "docker_compose": {},
            "kubernetes": {},
            "monitoring": {},
            "gateway": {},
            "rate_limiting": {},
            "cicd": {}
        }

    def extract_docker_compose_services(self) -> Dict[str, Any]:
        """Extract services from Docker Compose configuration."""
        print("\n=== Extracting Docker Compose Services ===")

        services = {
            "infrastructure": [],
            "application": [],
            "monitoring": [],
            "gateway": [],
            "orchestration": [],
            "total_count": 0
        }

        if not self.docker_compose_file.exists():
            print(f"  Warning: Docker Compose file not found: {self.docker_compose_file}")
            return services

        try:
            with open(self.docker_compose_file, 'r') as f:
                compose_data = yaml.safe_load(f)

            if not compose_data or 'services' not in compose_data:
                print("  Warning: No services found in Docker Compose file")
                return services

            # Categorize services
            infrastructure_services = ['postgres', 'redis', 'minio', 'fuseki']
            monitoring_services = ['prometheus', 'grafana', 'jaeger', 'alertmanager']
            gateway_services = ['traefik']
            orchestration_services = ['prefect-server', 'prefect-db', 'prefect-worker', 'prefect-integration-service']

            for service_name, service_config in compose_data['services'].items():
                service_info = {
                    "name": service_name,
                    "image": service_config.get('image', 'N/A'),
                    "ports": service_config.get('ports', []),
                    "volumes": service_config.get('volumes', []),
                    "depends_on": service_config.get('depends_on', []),
                    "networks": service_config.get('networks', []),
                    "healthcheck": service_config.get('healthcheck', {}),
                    "environment": list(service_config.get('environment', {}).keys()) if isinstance(service_config.get('environment'), dict) else []
                }

                if service_name in infrastructure_services:
                    services["infrastructure"].append(service_info)
                elif service_name in monitoring_services:
                    services["monitoring"].append(service_info)
                elif service_name in gateway_services:
                    services["gateway"].append(service_info)
                elif service_name in orchestration_services:
                    services["orchestration"].append(service_info)
                else:
                    services["application"].append(service_info)

                services["total_count"] += 1

            print(f"  Found {services['total_count']} services:")
            print(f"    - Infrastructure: {len(services['infrastructure'])}")
            print(f"    - Application: {len(services['application'])}")
            print(f"    - Monitoring: {len(services['monitoring'])}")
            print(f"    - Gateway: {len(services['gateway'])}")
            print(f"    - Orchestration: {len(services['orchestration'])}")

        except Exception as e:
            print(f"  Error parsing Docker Compose file: {e}")

        self.infrastructure_components["docker_compose"] = services
        return services

    def extract_kubernetes_components(self) -> Dict[str, Any]:
        """Extract components from Kubernetes configurations."""
        print("\n=== Extracting Kubernetes Components ===")

        components = {
            "services": [],
            "deployments": [],
            "statefulsets": [],
            "configmaps": [],
            "secrets": [],
            "persistent_volume_claims": [],
            "ingresses": [],
            "namespaces": [],
            "network_policies": [],
            "total_count": 0
        }

        if not self.k8s_dir.exists():
            print(f"  Warning: Kubernetes directory not found: {self.k8s_dir}")
            return components

        # Find all Kubernetes manifests
        for yaml_file in self.k8s_dir.rglob("*.yaml"):
            if "overlays" in str(yaml_file):
                continue  # Skip overlay files

            try:
                with open(yaml_file, 'r') as f:
                    manifests = list(yaml.safe_load_all(f))

                for manifest in manifests:
                    if not manifest or 'kind' not in manifest:
                        continue

                    kind = manifest['kind']
                    metadata = manifest.get('metadata', {})
                    name = metadata.get('name', 'unknown')
                    namespace = metadata.get('namespace', 'default')

                    component_info = {
                        "name": name,
                        "namespace": namespace,
                        "file": str(yaml_file.relative_to(self.project_root))
                    }

                    # Track which resources we're counting
                    counted = False

                    if kind == "Service":
                        components["services"].append(component_info)
                        counted = True
                    elif kind == "Deployment":
                        components["deployments"].append(component_info)
                        counted = True
                    elif kind == "StatefulSet":
                        components["statefulsets"].append(component_info)
                        counted = True
                    elif kind == "ConfigMap":
                        components["configmaps"].append(component_info)
                        counted = True
                    elif kind == "Secret":
                        components["secrets"].append(component_info)
                        counted = True
                    elif kind == "PersistentVolumeClaim":
                        components["persistent_volume_claims"].append(component_info)
                        counted = True
                    elif kind == "Ingress":
                        components["ingresses"].append(component_info)
                        counted = True
                    elif kind == "Namespace":
                        components["namespaces"].append(component_info)
                        counted = True
                    elif kind == "NetworkPolicy":
                        components["network_policies"].append(component_info)
                        counted = True

                    # Only increment total if we actually counted this resource
                    if counted:
                        components["total_count"] += 1

            except Exception as e:
                print(f"  Warning: Could not parse {yaml_file}: {e}")

        print(f"  Found {components['total_count']} Kubernetes components:")
        print(f"    - Services: {len(components['services'])}")
        print(f"    - Deployments: {len(components['deployments'])}")
        print(f"    - StatefulSets: {len(components['statefulsets'])}")
        print(f"    - ConfigMaps: {len(components['configmaps'])}")
        print(f"    - Secrets: {len(components['secrets'])}")
        print(f"    - PVCs: {len(components['persistent_volume_claims'])}")
        print(f"    - Ingresses: {len(components['ingresses'])}")
        print(f"    - Namespaces: {len(components['namespaces'])}")
        print(f"    - Network Policies: {len(components['network_policies'])}")

        self.infrastructure_components["kubernetes"] = components
        return components

    def load_review_reports(self) -> Dict[str, Any]:
        """Load and compile data from review reports."""
        print("\n=== Loading Review Reports ===")

        reports = {
            "cicd": {},
            "monitoring": {},
            "rate_limiting": {},
            "gateway": {}
        }

        # Load CI/CD review
        if self.cicd_review.exists():
            try:
                with open(self.cicd_review, 'r') as f:
                    reports["cicd"] = json.load(f)
                print(f"  Loaded CI/CD review: {len(reports['cicd'].get('workflows', []))} workflows")
            except Exception as e:
                print(f"  Warning: Could not load CI/CD review: {e}")

        # Load monitoring review
        if self.monitoring_review.exists():
            try:
                with open(self.monitoring_review, 'r') as f:
                    reports["monitoring"] = json.load(f)
                print(f"  Loaded monitoring review: {reports['monitoring'].get('summary', {}).get('endpoints_found', 0)} endpoints")
            except Exception as e:
                print(f"  Warning: Could not load monitoring review: {e}")

        # Load rate limiting review
        if self.rate_limiting_review.exists():
            try:
                with open(self.rate_limiting_review, 'r') as f:
                    reports["rate_limiting"] = json.load(f)
                print(f"  Loaded rate limiting review: {reports['rate_limiting'].get('summary', {}).get('total_categories', 0)} categories")
            except Exception as e:
                print(f"  Warning: Could not load rate limiting review: {e}")

        # Load gateway review
        if self.gateway_review.exists():
            try:
                with open(self.gateway_review, 'r') as f:
                    reports["gateway"] = json.load(f)
                print(f"  Loaded gateway review: {reports['gateway'].get('summary', {}).get('routing_rules', 0)} routing rules")
            except Exception as e:
                print(f"  Warning: Could not load gateway review: {e}")

        self.infrastructure_components["cicd"] = reports["cicd"]
        self.infrastructure_components["monitoring"] = reports["monitoring"]
        self.infrastructure_components["rate_limiting"] = reports["rate_limiting"]
        self.infrastructure_components["gateway"] = reports["gateway"]

        return reports

    def compile_infrastructure_components_list(self) -> Dict[str, Any]:
        """Compile comprehensive infrastructure components list."""
        print("\n=== Compiling Infrastructure Components List ===")

        components_list = {
            "infrastructure_services": [],
            "application_services": [],
            "monitoring_services": [],
            "gateway_services": [],
            "orchestration_services": [],
            "kubernetes_resources": {},
            "configuration_references": {}
        }

        # From Docker Compose
        docker_services = self.infrastructure_components.get("docker_compose", {})
        components_list["infrastructure_services"] = [
            s["name"] for s in docker_services.get("infrastructure", [])
        ]
        components_list["application_services"] = [
            s["name"] for s in docker_services.get("application", [])
        ]
        components_list["monitoring_services"] = [
            s["name"] for s in docker_services.get("monitoring", [])
        ]
        components_list["gateway_services"] = [
            s["name"] for s in docker_services.get("gateway", [])
        ]
        components_list["orchestration_services"] = [
            s["name"] for s in docker_services.get("orchestration", [])
        ]

        # From Kubernetes
        k8s_components = self.infrastructure_components.get("kubernetes", {})
        components_list["kubernetes_resources"] = {
            "services": len(k8s_components.get("services", [])),
            "deployments": len(k8s_components.get("deployments", [])),
            "statefulsets": len(k8s_components.get("statefulsets", [])),
            "configmaps": len(k8s_components.get("configmaps", [])),
            "secrets": len(k8s_components.get("secrets", [])),
            "persistent_volume_claims": len(k8s_components.get("persistent_volume_claims", [])),
            "ingresses": len(k8s_components.get("ingresses", [])),
            "namespaces": len(k8s_components.get("namespaces", [])),
            "network_policies": len(k8s_components.get("network_policies", []))
        }

        # Configuration references
        components_list["configuration_references"] = {
            "cicd_workflows": len(self.infrastructure_components.get("cicd", {}).get("workflows", [])),
            "monitoring_endpoints": self.infrastructure_components.get("monitoring", {}).get("summary", {}).get("endpoints_found", 0),
            "rate_limiting_categories": self.infrastructure_components.get("rate_limiting", {}).get("summary", {}).get("total_categories", 0),
            "gateway_routing_rules": self.infrastructure_components.get("gateway", {}).get("summary", {}).get("routing_rules", 0)
        }

        print(f"  Compiled components list:")
        print(f"    - Infrastructure services: {len(components_list['infrastructure_services'])}")
        print(f"    - Application services: {len(components_list['application_services'])}")
        print(f"    - Monitoring services: {len(components_list['monitoring_services'])}")
        print(f"    - Gateway services: {len(components_list['gateway_services'])}")
        print(f"    - Orchestration services: {len(components_list['orchestration_services'])}")
        print(f"    - Kubernetes resources: {sum(components_list['kubernetes_resources'].values())}")

        return components_list

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive infrastructure impact report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "docker_compose_services": self.infrastructure_components.get("docker_compose", {}).get("total_count", 0),
                "kubernetes_components": self.infrastructure_components.get("kubernetes", {}).get("total_count", 0),
                "infrastructure_services": len(self.infrastructure_components.get("docker_compose", {}).get("infrastructure", [])),
                "application_services": len(self.infrastructure_components.get("docker_compose", {}).get("application", [])),
                "monitoring_services": len(self.infrastructure_components.get("docker_compose", {}).get("monitoring", [])),
                "gateway_services": len(self.infrastructure_components.get("docker_compose", {}).get("gateway", [])),
                "orchestration_services": len(self.infrastructure_components.get("docker_compose", {}).get("orchestration", []))
            },
            "docker_compose": self.infrastructure_components.get("docker_compose", {}),
            "kubernetes": self.infrastructure_components.get("kubernetes", {}),
            "monitoring": {
                "summary": self.infrastructure_components.get("monitoring", {}).get("summary", {}),
                "prometheus_scrape_configs": len(self.infrastructure_components.get("monitoring", {}).get("prometheus", {}).get("scrape_configs", []))
            },
            "gateway": {
                "summary": self.infrastructure_components.get("gateway", {}).get("summary", {}),
                "routing_rules_count": self.infrastructure_components.get("gateway", {}).get("summary", {}).get("routing_rules", 0),
                "rate_limiting_rules_count": self.infrastructure_components.get("gateway", {}).get("summary", {}).get("rate_limiting_rules", 0)
            },
            "rate_limiting": {
                "summary": self.infrastructure_components.get("rate_limiting", {}).get("summary", {}),
                "categories_count": self.infrastructure_components.get("rate_limiting", {}).get("summary", {}).get("total_categories", 0)
            },
            "cicd": {
                "summary": self.infrastructure_components.get("cicd", {}).get("summary", {}),
                "workflows_count": self.infrastructure_components.get("cicd", {}).get("summary", {}).get("total_workflows", 0)
            },
            "components_list": self.compile_infrastructure_components_list()
        }

        return report

    def save_markdown_report(self, output_file: Path):
        """Save report as Markdown."""
        report = self.generate_report()

        markdown_content = f"""# Infrastructure Impact Analysis

**Generated:** {report['generated_at']}

## Executive Summary

This report provides a comprehensive analysis of all infrastructure components in the Meshant platform, including Docker Compose services, Kubernetes resources, monitoring configurations, API gateway rules, rate limiting configurations, and CI/CD workflows.

### Key Statistics

- **Docker Compose Services**: {report['summary']['docker_compose_services']}
- **Kubernetes Components**: {report['summary']['kubernetes_components']}
- **Infrastructure Services**: {report['summary']['infrastructure_services']}
- **Application Services**: {report['summary']['application_services']}
- **Monitoring Services**: {report['summary']['monitoring_services']}
- **Gateway Services**: {report['summary']['gateway_services']}
- **Orchestration Services**: {report['summary']['orchestration_services']}

## Docker Compose Infrastructure

### Infrastructure Services

"""

        # Add infrastructure services
        for service in report['docker_compose'].get('infrastructure', []):
            markdown_content += f"- **{service['name']}**\n"
            markdown_content += f"  - Image: `{service['image']}`\n"
            if service.get('ports'):
                markdown_content += f"  - Ports: {', '.join(str(p) for p in service['ports'])}\n"
            markdown_content += "\n"

        markdown_content += "### Application Services\n\n"
        for service in report['docker_compose'].get('application', []):
            markdown_content += f"- **{service['name']}**\n"
            markdown_content += f"  - Image: `{service['image']}`\n"
            if service.get('ports'):
                markdown_content += f"  - Ports: {', '.join(str(p) for p in service['ports'])}\n"
            markdown_content += "\n"

        markdown_content += "### Monitoring Services\n\n"
        for service in report['docker_compose'].get('monitoring', []):
            markdown_content += f"- **{service['name']}**\n"
            markdown_content += f"  - Image: `{service['image']}`\n"
            if service.get('ports'):
                markdown_content += f"  - Ports: {', '.join(str(p) for p in service['ports'])}\n"
            markdown_content += "\n"

        markdown_content += "## Kubernetes Infrastructure\n\n"
        k8s_resources = report['components_list']['kubernetes_resources']
        markdown_content += f"- **Services**: {k8s_resources['services']}\n"
        markdown_content += f"- **Deployments**: {k8s_resources['deployments']}\n"
        markdown_content += f"- **StatefulSets**: {k8s_resources['statefulsets']}\n"
        markdown_content += f"- **ConfigMaps**: {k8s_resources['configmaps']}\n"
        markdown_content += f"- **Secrets**: {k8s_resources['secrets']}\n"
        markdown_content += f"- **Persistent Volume Claims**: {k8s_resources['persistent_volume_claims']}\n"
        markdown_content += f"- **Ingresses**: {k8s_resources['ingresses']}\n"
        markdown_content += f"- **Namespaces**: {k8s_resources['namespaces']}\n"
        markdown_content += f"- **Network Policies**: {k8s_resources['network_policies']}\n\n"

        markdown_content += "## Monitoring and Observability\n\n"
        monitoring_summary = report.get('monitoring', {}).get('summary', {})
        markdown_content += f"- **Endpoints Monitored**: {monitoring_summary.get('endpoints_found', 0)}\n"
        markdown_content += f"- **Prometheus Scrape Configs**: {report.get('monitoring', {}).get('prometheus_scrape_configs', 0)}\n"
        markdown_content += f"- **Grafana Queries**: {monitoring_summary.get('grafana_queries_reviewed', 0)}\n"
        markdown_content += f"- **Jaeger Operation Patterns**: {monitoring_summary.get('jaeger_operation_patterns', 0)}\n\n"

        markdown_content += "## API Gateway\n\n"
        gateway_summary = report.get('gateway', {}).get('summary', {})
        markdown_content += f"- **Routing Rules**: {gateway_summary.get('routing_rules', 0)}\n"
        markdown_content += f"- **Rate Limiting Rules**: {gateway_summary.get('rate_limiting_rules', 0)}\n"
        markdown_content += f"- **Authentication Rules**: {gateway_summary.get('authentication_rules', 0)}\n"
        markdown_content += f"- **Mapped Endpoints**: {gateway_summary.get('mapped_endpoints', 0)}\n\n"

        markdown_content += "## Rate Limiting\n\n"
        rate_limiting_summary = report.get('rate_limiting', {}).get('summary', {})
        markdown_content += f"- **Categories**: {rate_limiting_summary.get('total_categories', 0)}\n"
        markdown_content += f"- **Rate Limit Rules**: {rate_limiting_summary.get('total_rate_limit_rules', 0)}\n"
        markdown_content += f"- **Endpoint Mappings**: {rate_limiting_summary.get('total_endpoint_mappings', 0)}\n\n"

        markdown_content += "## CI/CD Infrastructure\n\n"
        cicd_summary = report.get('cicd', {}).get('summary', {})
        markdown_content += f"- **Total Workflows**: {cicd_summary.get('total_workflows', 0)}\n"
        markdown_content += f"- **Endpoint References**: {cicd_summary.get('total_endpoint_references', 0)}\n"
        markdown_content += f"- **Workflow Types**: {len(cicd_summary.get('workflows_by_type', {}))}\n\n"

        markdown_content += "## Infrastructure Components List\n\n"
        components_list = report['components_list']
        markdown_content += "### Infrastructure Services\n\n"
        for service in components_list['infrastructure_services']:
            markdown_content += f"- {service}\n"

        markdown_content += "\n### Application Services\n\n"
        for service in components_list['application_services']:
            markdown_content += f"- {service}\n"

        markdown_content += "\n### Monitoring Services\n\n"
        for service in components_list['monitoring_services']:
            markdown_content += f"- {service}\n"

        markdown_content += "\n### Gateway Services\n\n"
        for service in components_list['gateway_services']:
            markdown_content += f"- {service}\n"

        markdown_content += "\n### Orchestration Services\n\n"
        for service in components_list['orchestration_services']:
            markdown_content += f"- {service}\n"

        markdown_content += "\n## References\n\n"
        markdown_content += "- CI/CD Workflows Review: `docs/api-audit/cicd-workflows-review.json`\n"
        markdown_content += "- Monitoring Review: `monitoring_review_report.json`\n"
        markdown_content += "- Rate Limiting Review: `docs/api-audit/rate-limiting-review.json`\n"
        markdown_content += "- Gateway Rules Audit: `docs/api-audit/api-gateway-rules-audit.json`\n"

        # Save file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(markdown_content)

        print(f"\n=== Report saved to {output_file} ===")

    def save_json_report(self, output_file: Path):
        """Save report as JSON."""
        report = self.generate_report()

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"=== JSON report saved to {output_file} ===")


def main():
    """Main execution function."""
    import sys

    project_root = Path(__file__).parent.parent
    reporter = InfrastructureImpactReporter(project_root)

    # Extract components
    reporter.extract_docker_compose_services()
    reporter.extract_kubernetes_components()
    reporter.load_review_reports()

    # Generate reports
    markdown_output = project_root / "docs" / "api-audit" / "infrastructure-impact-analysis.md"
    json_output = project_root / "docs" / "api-audit" / "infrastructure-impact-analysis.json"

    reporter.save_markdown_report(markdown_output)
    reporter.save_json_report(json_output)

    # Print summary
    report = reporter.generate_report()
    print("\n" + "="*80)
    print("INFRASTRUCTURE IMPACT REPORT SUMMARY")
    print("="*80)
    print(f"\nDocker Compose Services: {report['summary']['docker_compose_services']}")
    print(f"Kubernetes Components: {report['summary']['kubernetes_components']}")
    print(f"Infrastructure Services: {report['summary']['infrastructure_services']}")
    print(f"Application Services: {report['summary']['application_services']}")
    print(f"Monitoring Services: {report['summary']['monitoring_services']}")
    print(f"Gateway Services: {report['summary']['gateway_services']}")
    print(f"Orchestration Services: {report['summary']['orchestration_services']}")
    print("\n" + "="*80)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

