#!/usr/bin/env python3
"""
Comprehensive API Gateway Rules Checker Script

This script checks API gateway rules to:
- Review Traefik routing rules
- Review rate limiting rules in gateway
- Review authentication rules in gateway
- Map gateway rules to endpoints

Usage:
    python scripts/check_api_gateway_rules.py [--traefik-dir TRAEFIK_DIR]
                                              [--inventory INVENTORY_FILE] [--output OUTPUT_FILE]
"""

import re
import json
import yaml
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from datetime import datetime


@dataclass
class RoutingRule:
    """Represents a Traefik routing rule"""
    router_name: str
    rule: str
    path_prefix: Optional[str] = None
    host_pattern: Optional[str] = None
    service: str = ""
    middlewares: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    tls_enabled: bool = False
    config_file: str = ""


@dataclass
class RateLimitRule:
    """Represents a rate limiting rule"""
    middleware_name: str
    average: Optional[int] = None
    period: Optional[str] = None
    burst: Optional[int] = None
    applied_to_routers: List[str] = field(default_factory=list)
    config_file: str = ""


@dataclass
class AuthRule:
    """Represents an authentication rule"""
    middleware_name: str
    auth_type: str = ""  # forwardAuth, basicAuth, etc.
    auth_address: Optional[str] = None
    auth_response_headers: List[str] = field(default_factory=list)
    applied_to_routers: List[str] = field(default_factory=list)
    config_file: str = ""


class APIGatewayRulesChecker:
    """Checks API gateway rules comprehensively"""

    def __init__(
        self,
        traefik_config_dir: str = "infrastructure/traefik",
        endpoint_inventory_file: str = "docs/api-audit/endpoint-inventory-current.json",
        base_path: str = "."
    ):
        self.base_path = Path(base_path)
        self.traefik_config_dir = self.base_path / traefik_config_dir
        self.endpoint_inventory_file = self.base_path / endpoint_inventory_file

        if not self.endpoint_inventory_file.exists():
            raise FileNotFoundError(
                f"Endpoint inventory file not found: {self.endpoint_inventory_file}"
            )

        # Load endpoint inventory
        self.known_endpoints: Dict[str, Set[str]] = {}  # endpoint_path -> set of methods
        self._load_endpoint_inventory()

        # All rules found
        self.routing_rules: List[RoutingRule] = []
        self.rate_limit_rules: List[RateLimitRule] = []
        self.auth_rules: List[AuthRule] = []

    def _load_endpoint_inventory(self):
        """Load endpoint inventory from JSON file"""
        try:
            with open(self.endpoint_inventory_file, 'r', encoding='utf-8') as f:
                inventory_data = json.load(f)

            # Handle different inventory formats
            if 'inventory' in inventory_data:
                endpoints = inventory_data['inventory'].get('endpoints', [])
            elif 'endpoints' in inventory_data:
                endpoints = inventory_data['endpoints']
            else:
                endpoints = []

            for endpoint_info in endpoints:
                if isinstance(endpoint_info, dict):
                    endpoint_path = endpoint_info.get('full_path') or endpoint_info.get('endpoint_path') or endpoint_info.get('path', '')
                    methods = endpoint_info.get('methods', []) or []

                    if endpoint_path:
                        normalized = self.normalize_endpoint(endpoint_path)
                        if normalized not in self.known_endpoints:
                            self.known_endpoints[normalized] = set()
                        if isinstance(methods, list):
                            self.known_endpoints[normalized].update(m.upper() for m in methods)
                        elif isinstance(methods, str):
                            self.known_endpoints[normalized].add(methods.upper())

        except Exception as e:
            print(f"Warning: Error loading endpoint inventory: {e}", file=sys.stderr)

    def normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint path for comparison"""
        # Remove query parameters
        endpoint = endpoint.split('?')[0]
        # Remove fragments
        endpoint = endpoint.split('#')[0]
        # Normalize trailing slash
        if endpoint and not endpoint.endswith('/') and '/api/' in endpoint and endpoint != '/api/v1':
            endpoint += '/'
        return endpoint

    def find_traefik_configs(self) -> List[Path]:
        """Find all Traefik configuration files"""
        configs = []

        if not self.traefik_config_dir.exists():
            return configs

        # Look for routes.yml in dynamic directory
        dynamic_dir = self.traefik_config_dir / "dynamic"
        if dynamic_dir.exists():
            routes_file = dynamic_dir / "routes.yml"
            if routes_file.exists():
                configs.append(routes_file)

        # Look for configmap.yaml in k8s directory (only if not in a test directory)
        # Check if we're in a test temp directory - if so, don't search project k8s
        try:
            # If traefik_config_dir is within base_path and base_path is not a temp directory
            if (self.traefik_config_dir.is_relative_to(self.base_path) and
                '/tmp/' not in str(self.base_path) and
                '/pytest-' not in str(self.base_path)):
                k8s_traefik_dir = self.base_path / "k8s" / "api-gateway" / "traefik"
                if k8s_traefik_dir.exists() and k8s_traefik_dir != self.traefik_config_dir:
                    configmap_file = k8s_traefik_dir / "configmap.yaml"
                    if configmap_file.exists():
                        configs.append(configmap_file)
        except (ValueError, AttributeError):
            # Path comparison failed, skip k8s search
            pass

        return configs

    def extract_routing_rules(self) -> List[RoutingRule]:
        """Extract routing rules from Traefik configurations"""
        rules = []
        config_files = self.find_traefik_configs()

        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)

                # Handle different config structures
                http_config = content.get('http', {})
                if not http_config and 'data' in content:
                    # Kubernetes ConfigMap format
                    routes_yml = content.get('data', {}).get('routes.yml', '')
                    if routes_yml:
                        content = yaml.safe_load(routes_yml)
                        http_config = content.get('http', {})

                routers = http_config.get('routers', {})

                for router_name, router_config in routers.items():
                    rule_str = router_config.get('rule', '')
                    path_prefix = self._extract_path_prefix(rule_str)
                    host_pattern = self._extract_host_pattern(rule_str)

                    # Try to get relative path
                    try:
                        relative_path = str(config_file.relative_to(self.base_path))
                    except ValueError:
                        relative_path = str(config_file)

                    routing_rule = RoutingRule(
                        router_name=router_name,
                        rule=rule_str,
                        path_prefix=path_prefix,
                        host_pattern=host_pattern,
                        service=router_config.get('service', ''),
                        middlewares=router_config.get('middlewares', []) or [],
                        entry_points=router_config.get('entryPoints', []) or [],
                        tls_enabled=bool(router_config.get('tls')),
                        config_file=relative_path
                    )
                    rules.append(routing_rule)

            except Exception as e:
                print(f"Error processing {config_file}: {e}", file=sys.stderr)

        self.routing_rules = rules
        return rules

    def extract_rate_limiting_rules(self) -> List[RateLimitRule]:
        """Extract rate limiting rules from Traefik configurations"""
        rate_limit_rules = []
        config_files = self.find_traefik_configs()

        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)

                # Handle different config structures
                http_config = content.get('http', {})
                if not http_config and 'data' in content:
                    routes_yml = content.get('data', {}).get('routes.yml', '')
                    if routes_yml:
                        content = yaml.safe_load(routes_yml)
                        http_config = content.get('http', {})

                middlewares = http_config.get('middlewares', {})
                routers = http_config.get('routers', {})

                # Find routers using rate limit middleware
                rate_limit_middleware_names = []
                for middleware_name, middleware_config in middlewares.items():
                    if 'rateLimit' in middleware_config:
                        rate_limit_config = middleware_config.get('rateLimit', {})

                        # Try to get relative path
                        try:
                            relative_path = str(config_file.relative_to(self.base_path))
                        except ValueError:
                            relative_path = str(config_file)

                        rate_limit_rule = RateLimitRule(
                            middleware_name=middleware_name,
                            average=rate_limit_config.get('average'),
                            period=rate_limit_config.get('period'),
                            burst=rate_limit_config.get('burst'),
                            config_file=relative_path
                        )
                        rate_limit_rules.append(rate_limit_rule)
                        rate_limit_middleware_names.append(middleware_name)

                # Find routers using these middlewares
                for router_name, router_config in routers.items():
                    router_middlewares = router_config.get('middlewares', []) or []
                    for middleware_name in rate_limit_middleware_names:
                        if middleware_name in router_middlewares:
                            # Find the corresponding rate limit rule and add router
                            for rate_limit_rule in rate_limit_rules:
                                if rate_limit_rule.middleware_name == middleware_name:
                                    if router_name not in rate_limit_rule.applied_to_routers:
                                        rate_limit_rule.applied_to_routers.append(router_name)

            except Exception as e:
                print(f"Error processing {config_file}: {e}", file=sys.stderr)

        self.rate_limit_rules = rate_limit_rules
        return rate_limit_rules

    def extract_authentication_rules(self) -> List[AuthRule]:
        """Extract authentication rules from Traefik configurations"""
        auth_rules = []
        config_files = self.find_traefik_configs()

        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)

                # Handle different config structures
                http_config = content.get('http', {})
                if not http_config and 'data' in content:
                    routes_yml = content.get('data', {}).get('routes.yml', '')
                    if routes_yml:
                        content = yaml.safe_load(routes_yml)
                        http_config = content.get('http', {})

                middlewares = http_config.get('middlewares', {})
                routers = http_config.get('routers', {})

                # Find auth middlewares
                auth_middleware_names = []
                for middleware_name, middleware_config in middlewares.items():
                    auth_type = None
                    auth_address = None
                    auth_response_headers = []

                    if 'forwardAuth' in middleware_config:
                        auth_type = 'forwardAuth'
                        forward_auth = middleware_config.get('forwardAuth', {})
                        auth_address = forward_auth.get('address')
                        auth_response_headers = forward_auth.get('authResponseHeaders', []) or []
                    elif 'basicAuth' in middleware_config:
                        auth_type = 'basicAuth'
                    elif 'digestAuth' in middleware_config:
                        auth_type = 'digestAuth'

                    if auth_type:
                        # Try to get relative path
                        try:
                            relative_path = str(config_file.relative_to(self.base_path))
                        except ValueError:
                            relative_path = str(config_file)

                        auth_rule = AuthRule(
                            middleware_name=middleware_name,
                            auth_type=auth_type,
                            auth_address=auth_address,
                            auth_response_headers=auth_response_headers,
                            config_file=relative_path
                        )
                        auth_rules.append(auth_rule)
                        auth_middleware_names.append(middleware_name)

                # Find routers using these middlewares
                for router_name, router_config in routers.items():
                    router_middlewares = router_config.get('middlewares', []) or []
                    for middleware_name in auth_middleware_names:
                        if middleware_name in router_middlewares:
                            # Find the corresponding auth rule and add router
                            for auth_rule in auth_rules:
                                if auth_rule.middleware_name == middleware_name:
                                    if router_name not in auth_rule.applied_to_routers:
                                        auth_rule.applied_to_routers.append(router_name)

            except Exception as e:
                print(f"Error processing {config_file}: {e}", file=sys.stderr)

        self.auth_rules = auth_rules
        return auth_rules

    def _extract_path_prefix(self, rule: str) -> Optional[str]:
        """Extract path prefix from Traefik rule"""
        match = re.search(r'PathPrefix\(`([^`]+)`\)', rule)
        return match.group(1) if match else None

    def _extract_host_pattern(self, rule: str) -> Optional[str]:
        """Extract host pattern from Traefik rule"""
        match = re.search(r'Host\(`([^`]+)`\)', rule)
        return match.group(1) if match else None

    def map_gateway_rules_to_endpoints(self) -> Dict[str, Any]:
        """Map gateway rules to endpoints"""
        mappings = {
            'routing_rules': [],
            'mapped_endpoints': 0,
            'unmapped_routes': []
        }

        for routing_rule in self.routing_rules:
            if not routing_rule.path_prefix:
                continue

            # Find matching endpoints
            matching_endpoints = []
            for endpoint_path, methods in self.known_endpoints.items():
                if endpoint_path.startswith(routing_rule.path_prefix):
                    matching_endpoints.append({
                        'path': endpoint_path,
                        'methods': sorted(list(methods))
                    })

            if matching_endpoints:
                mappings['routing_rules'].append({
                    'router_name': routing_rule.router_name,
                    'path_prefix': routing_rule.path_prefix,
                    'service': routing_rule.service,
                    'endpoints': matching_endpoints,
                    'endpoint_count': len(matching_endpoints)
                })
                mappings['mapped_endpoints'] += len(matching_endpoints)
            else:
                mappings['unmapped_routes'].append({
                    'router_name': routing_rule.router_name,
                    'path_prefix': routing_rule.path_prefix,
                    'service': routing_rule.service
                })

        return mappings

    def validate_all_rules(self) -> Dict[str, Any]:
        """Validate all gateway rules comprehensively"""
        print("🔍 Finding Traefik configuration files...")
        configs = self.find_traefik_configs()
        print(f"   Found {len(configs)} configuration files")

        print("🔍 Extracting routing rules...")
        routing_rules = self.extract_routing_rules()
        print(f"   Found {len(routing_rules)} routing rules")

        print("🔍 Extracting rate limiting rules...")
        rate_limit_rules = self.extract_rate_limiting_rules()
        print(f"   Found {len(rate_limit_rules)} rate limiting rules")

        print("🔍 Extracting authentication rules...")
        auth_rules = self.extract_authentication_rules()
        print(f"   Found {len(auth_rules)} authentication rules")

        print("🔍 Mapping gateway rules to endpoints...")
        mappings = self.map_gateway_rules_to_endpoints()
        print(f"   Mapped {mappings['mapped_endpoints']} endpoints")
        print(f"   Unmapped routes: {len(mappings['unmapped_routes'])}")

        return {
            'summary': {
                'generated_at': datetime.now().isoformat(),
                'config_files_found': len(configs),
                'routing_rules': len(routing_rules),
                'rate_limiting_rules': len(rate_limit_rules),
                'authentication_rules': len(auth_rules),
                'mapped_endpoints': mappings['mapped_endpoints'],
                'unmapped_routes': len(mappings['unmapped_routes']),
                'known_endpoints_in_inventory': len(self.known_endpoints)
            },
            'routing_rules': [asdict(rule) for rule in routing_rules],
            'rate_limiting_rules': [asdict(rule) for rule in rate_limit_rules],
            'authentication_rules': [asdict(rule) for rule in auth_rules],
            'mappings': mappings
        }

    def generate_report(self, output_file: str):
        """Generate JSON report"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = self.validate_all_rules()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n📊 Report generated: {output_path}")
        print(f"   Routing rules: {results['summary']['routing_rules']}")
        print(f"   Rate limiting rules: {results['summary']['rate_limiting_rules']}")
        print(f"   Authentication rules: {results['summary']['authentication_rules']}")
        print(f"   Mapped endpoints: {results['summary']['mapped_endpoints']}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Check API gateway rules (Traefik routing, rate limiting, authentication)"
    )
    parser.add_argument(
        '--traefik-dir',
        default='infrastructure/traefik',
        help='Directory containing Traefik configuration files (default: infrastructure/traefik)'
    )
    parser.add_argument(
        '--inventory',
        default='docs/api-audit/endpoint-inventory-current.json',
        help='Endpoint inventory JSON file (default: docs/api-audit/endpoint-inventory-current.json)'
    )
    parser.add_argument(
        '--output',
        default='docs/api-audit/api-gateway-rules-audit.json',
        help='Output JSON report file (default: docs/api-audit/api-gateway-rules-audit.json)'
    )
    parser.add_argument(
        '--base-path',
        default='.',
        help='Base path of the project (default: .)'
    )

    args = parser.parse_args()

    try:
        checker = APIGatewayRulesChecker(
            traefik_config_dir=args.traefik_dir,
            endpoint_inventory_file=args.inventory,
            base_path=args.base_path
        )

        checker.generate_report(args.output)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

