#!/usr/bin/env python3
"""
Integration tests for API gateway rules checker script

Tests the script against actual project Traefik configuration files
and Docker Compose environment. No mocks or stubs used.
"""

import json
import pytest
import yaml
from pathlib import Path
import sys

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from check_api_gateway_rules import APIGatewayRulesChecker


class TestAPIGatewayRulesCheckerIntegration:
    """Integration tests using actual project files"""

    @pytest.fixture
    def project_root_path(self):
        """Get project root path"""
        return project_root

    @pytest.fixture
    def actual_traefik_config_dir(self, project_root_path):
        """Get actual Traefik configuration directory"""
        return project_root_path / "infrastructure" / "traefik"

    @pytest.fixture
    def actual_endpoint_inventory(self, project_root_path):
        """Get actual endpoint inventory file"""
        inventory_file = project_root_path / "docs" / "api-audit" / "endpoint-inventory-current.json"
        if not inventory_file.exists():
            # Try proposed inventory as fallback
            inventory_file = project_root_path / "docs" / "api-audit" / "endpoint-inventory-proposed.json"
        return str(inventory_file)

    def test_find_actual_traefik_configs(self, actual_traefik_config_dir, actual_endpoint_inventory):
        """Test finding actual Traefik configuration files"""
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(actual_traefik_config_dir),
            endpoint_inventory_file=actual_endpoint_inventory,
            base_path=str(project_root)
        )

        configs = checker.find_traefik_configs()
        assert len(configs) > 0, "Should find at least one Traefik config file"

        # Verify Docker Compose routes.yml exists
        docker_compose_routes = actual_traefik_config_dir / "dynamic" / "routes.yml"
        assert docker_compose_routes.exists(), "Docker Compose routes.yml should exist"
        assert any(str(docker_compose_routes) == str(c) for c in configs), \
            "Should find Docker Compose routes.yml"

    def test_extract_actual_routing_rules(self, actual_traefik_config_dir, actual_endpoint_inventory):
        """Test extracting routing rules from actual Traefik configs"""
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(actual_traefik_config_dir),
            endpoint_inventory_file=actual_endpoint_inventory,
            base_path=str(project_root)
        )

        rules = checker.extract_routing_rules()
        assert len(rules) > 0, "Should extract routing rules from actual configs"

        # Verify we have expected services
        router_names = [r.router_name for r in rules]
        expected_services = ['contract-service', 'asset-service', 'dataset-service']
        for service in expected_services:
            assert any(service in name for name in router_names), \
                f"Should find routing rule for {service}"

    def test_extract_actual_rate_limiting_rules(self, actual_traefik_config_dir, actual_endpoint_inventory):
        """Test extracting rate limiting rules from actual configs"""
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(actual_traefik_config_dir),
            endpoint_inventory_file=actual_endpoint_inventory,
            base_path=str(project_root)
        )

        rate_limit_rules = checker.extract_rate_limiting_rules()
        assert len(rate_limit_rules) > 0, "Should find rate limiting rules"

        # Verify rate limit configuration
        for rule in rate_limit_rules:
            assert rule.average is not None, "Rate limit rule should have average configured"
            assert rule.period is not None, "Rate limit rule should have period configured"
            assert len(rule.applied_to_routers) > 0, \
                f"Rate limit rule {rule.middleware_name} should be applied to at least one router"

    def test_extract_actual_authentication_rules(self, actual_traefik_config_dir, actual_endpoint_inventory):
        """Test extracting authentication rules from actual configs"""
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(actual_traefik_config_dir),
            endpoint_inventory_file=actual_endpoint_inventory,
            base_path=str(project_root)
        )

        auth_rules = checker.extract_authentication_rules()
        assert len(auth_rules) > 0, "Should find authentication rules"

        # Verify auth configuration
        for rule in auth_rules:
            assert rule.auth_type, f"Auth rule {rule.middleware_name} should have auth_type"
            if rule.auth_type == 'forwardAuth':
                assert rule.auth_address, \
                    f"forwardAuth rule {rule.middleware_name} should have auth_address"
            assert len(rule.applied_to_routers) > 0, \
                f"Auth rule {rule.middleware_name} should be applied to at least one router"

    def test_map_actual_gateway_rules_to_endpoints(self, actual_traefik_config_dir, actual_endpoint_inventory):
        """Test mapping actual gateway rules to endpoints"""
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(actual_traefik_config_dir),
            endpoint_inventory_file=actual_endpoint_inventory,
            base_path=str(project_root)
        )

        # Extract rules first
        checker.extract_routing_rules()
        mappings = checker.map_gateway_rules_to_endpoints()

        assert 'routing_rules' in mappings
        assert 'mapped_endpoints' in mappings
        assert mappings['mapped_endpoints'] > 0, \
            "Should map at least some endpoints to gateway rules"

        # Verify mappings have expected structure
        for mapping in mappings['routing_rules']:
            assert 'router_name' in mapping
            assert 'path_prefix' in mapping
            assert 'endpoints' in mapping
            assert 'endpoint_count' in mapping

    def test_validate_actual_all_rules(self, actual_traefik_config_dir, actual_endpoint_inventory):
        """Test comprehensive validation of actual rules"""
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(actual_traefik_config_dir),
            endpoint_inventory_file=actual_endpoint_inventory,
            base_path=str(project_root)
        )

        results = checker.validate_all_rules()

        # Verify summary
        assert 'summary' in results
        summary = results['summary']
        assert summary['routing_rules'] > 0
        assert summary['rate_limiting_rules'] > 0
        assert summary['authentication_rules'] > 0

        # Verify all rule types are present
        assert len(results['routing_rules']) > 0
        assert len(results['rate_limiting_rules']) > 0
        assert len(results['authentication_rules']) > 0
        assert 'mappings' in results

    def test_generate_actual_report(self, actual_traefik_config_dir, actual_endpoint_inventory, tmp_path):
        """Test generating report from actual configs"""
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(actual_traefik_config_dir),
            endpoint_inventory_file=actual_endpoint_inventory,
            base_path=str(project_root)
        )

        report_file = tmp_path / "integration-gateway-rules-report.json"
        checker.generate_report(str(report_file))

        assert report_file.exists(), "Report file should be created"

        # Verify report structure
        report_data = json.loads(report_file.read_text())
        assert 'summary' in report_data
        assert 'routing_rules' in report_data
        assert 'rate_limiting_rules' in report_data
        assert 'authentication_rules' in report_data
        assert 'mappings' in report_data

        # Verify report has meaningful data
        assert report_data['summary']['routing_rules'] > 0
        assert report_data['summary']['mapped_endpoints'] > 0

    def test_docker_compose_routes_yml_structure(self, actual_traefik_config_dir):
        """Test that Docker Compose routes.yml has correct structure"""
        routes_file = actual_traefik_config_dir / "dynamic" / "routes.yml"
        assert routes_file.exists(), "Docker Compose routes.yml should exist"

        with open(routes_file, 'r') as f:
            content = yaml.safe_load(f)

        assert 'http' in content, "Should have http section"
        http_config = content['http']
        assert 'routers' in http_config, "Should have routers section"
        assert 'middlewares' in http_config, "Should have middlewares section"

        # Verify routers have required fields
        routers = http_config['routers']
        assert len(routers) > 0, "Should have at least one router"

        for router_name, router_config in routers.items():
            assert 'rule' in router_config, f"Router {router_name} should have rule"
            assert 'service' in router_config, f"Router {router_name} should have service"

        # Verify middlewares exist
        middlewares = http_config['middlewares']
        assert len(middlewares) > 0, "Should have at least one middleware"

    def test_rate_limit_middleware_configuration(self, actual_traefik_config_dir):
        """Test that rate limit middleware is properly configured"""
        routes_file = actual_traefik_config_dir / "dynamic" / "routes.yml"
        with open(routes_file, 'r') as f:
            content = yaml.safe_load(f)

        middlewares = content['http']['middlewares']
        rate_limit_found = False

        for middleware_name, middleware_config in middlewares.items():
            if 'rateLimit' in middleware_config:
                rate_limit_found = True
                rate_limit_config = middleware_config['rateLimit']
                assert 'average' in rate_limit_config, \
                    f"Rate limit middleware {middleware_name} should have average"
                assert 'period' in rate_limit_config, \
                    f"Rate limit middleware {middleware_name} should have period"
                assert isinstance(rate_limit_config['average'], int), \
                    f"Rate limit average should be integer"
                break

        assert rate_limit_found, "Should have at least one rate limit middleware"

    def test_auth_middleware_configuration(self, actual_traefik_config_dir):
        """Test that auth middleware is properly configured"""
        routes_file = actual_traefik_config_dir / "dynamic" / "routes.yml"
        with open(routes_file, 'r') as f:
            content = yaml.safe_load(f)

        middlewares = content['http']['middlewares']
        auth_found = False

        for middleware_name, middleware_config in middlewares.items():
            if 'forwardAuth' in middleware_config:
                auth_found = True
                forward_auth = middleware_config['forwardAuth']
                assert 'address' in forward_auth, \
                    f"Auth middleware {middleware_name} should have address"
                assert forward_auth['address'].startswith('http'), \
                    f"Auth address should be HTTP URL"
                break

        assert auth_found, "Should have at least one auth middleware"

    def test_routers_use_middlewares(self, actual_traefik_config_dir):
        """Test that routers reference existing middlewares"""
        routes_file = actual_traefik_config_dir / "dynamic" / "routes.yml"
        with open(routes_file, 'r') as f:
            content = yaml.safe_load(f)

        routers = content['http']['routers']
        middlewares = content['http']['middlewares']
        middleware_names = set(middlewares.keys())

        for router_name, router_config in routers.items():
            router_middlewares = router_config.get('middlewares', [])
            for middleware_name in router_middlewares:
                assert middleware_name in middleware_names, \
                    f"Router {router_name} references non-existent middleware {middleware_name}"

