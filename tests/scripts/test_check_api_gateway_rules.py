#!/usr/bin/env python3
"""
Tests for API gateway rules checker script

Tests the comprehensive checking of Traefik routing rules, rate limiting rules,
authentication rules, and mapping gateway rules to endpoints.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from check_api_gateway_rules import (
    APIGatewayRulesChecker,
)


class TestAPIGatewayRulesChecker:
    """Test suite for APIGatewayRulesChecker"""

    @pytest.fixture
    def temp_traefik_config(self, tmp_path):
        """Create temporary Traefik configuration files"""
        traefik_dir = tmp_path / "infrastructure" / "traefik" / "dynamic"
        traefik_dir.mkdir(parents=True)

        routes_config = {
            "http": {
                "routers": {
                    "contract-service": {
                        "rule": "PathPrefix(`/api/v1/contracts`)",
                        "service": "contract-service",
                        "middlewares": [
                            "auth-middleware",
                            "rate-limit-middleware",
                            "tracing-middleware",
                        ],
                        "entryPoints": ["websecure"],
                    },
                    "asset-service": {
                        "rule": "PathPrefix(`/api/v1/assets`)",
                        "service": "asset-service",
                        "middlewares": ["auth-middleware", "rate-limit-middleware"],
                        "entryPoints": ["websecure"],
                    },
                },
                "middlewares": {
                    "auth-middleware": {
                        "forwardAuth": {
                            "address": "http://api-service:8000/api/v1/auth/validate",
                            "authResponseHeaders": ["X-User-Id", "X-Tenant-Id"],
                        }
                    },
                    "rate-limit-middleware": {
                        "rateLimit": {"average": 100, "period": "1s", "burst": 200}
                    },
                    "tracing-middleware": {
                        "headers": {"customRequestHeaders": {"X-Forwarded-For": ""}}
                    },
                },
            }
        }

        routes_file = traefik_dir / "routes.yml"
        routes_file.write_text(yaml.dump(routes_config))

        # Return the infrastructure directory (parent of traefik)
        return tmp_path / "infrastructure"

    @pytest.fixture
    def endpoint_inventory(self, tmp_path):
        """Create a sample endpoint inventory JSON file"""
        inventory_file = tmp_path / "endpoint-inventory.json"
        inventory_data = {
            "inventory": {
                "summary": {"total_endpoints": 5, "total_services": 1},
                "endpoints": [
                    {
                        "type": "path",
                        "full_path": "/api/v1/contracts/",
                        "methods": ["GET", "POST"],
                        "service": "contracts",
                    },
                    {
                        "type": "path",
                        "full_path": "/api/v1/contracts/{id}/",
                        "methods": ["GET", "PUT", "DELETE"],
                        "service": "contracts",
                    },
                    {
                        "type": "path",
                        "full_path": "/api/v1/assets/",
                        "methods": ["GET", "POST"],
                        "service": "assets",
                    },
                ],
            }
        }
        inventory_file.write_text(json.dumps(inventory_data, indent=2))
        return str(inventory_file)

    def test_checker_initialization(self, temp_traefik_config, endpoint_inventory):
        """Test checker initialization"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(traefik_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(base_path),
        )

        assert checker.traefik_config_dir == Path(traefik_dir)
        assert checker.endpoint_inventory_file == Path(endpoint_inventory)

    def test_find_traefik_configs(self, temp_traefik_config, endpoint_inventory):
        """Test finding Traefik configuration files"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(traefik_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(base_path),
        )

        configs = checker.find_traefik_configs()
        assert len(configs) > 0
        assert any("routes.yml" in str(c) for c in configs)

    def test_extract_routing_rules(self, temp_traefik_config, endpoint_inventory):
        """Test extracting routing rules"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(traefik_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(base_path),
        )

        rules = checker.extract_routing_rules()
        assert len(rules) > 0
        assert any(r.path_prefix == "/api/v1/contracts" for r in rules)

    def test_extract_rate_limiting_rules(self, temp_traefik_config, endpoint_inventory):
        """Test extracting rate limiting rules"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(traefik_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(base_path),
        )

        rate_limit_rules = checker.extract_rate_limiting_rules()
        assert len(rate_limit_rules) > 0
        assert any("rate-limit-middleware" in r.middleware_name for r in rate_limit_rules)

    def test_extract_authentication_rules(self, temp_traefik_config, endpoint_inventory):
        """Test extracting authentication rules"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(traefik_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(base_path),
        )

        auth_rules = checker.extract_authentication_rules()
        assert len(auth_rules) > 0
        assert any("auth-middleware" in r.middleware_name for r in auth_rules)

    def test_map_gateway_rules_to_endpoints(self, temp_traefik_config, endpoint_inventory):
        """Test mapping gateway rules to endpoints"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(traefik_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(base_path),
        )

        # Extract rules first
        checker.extract_routing_rules()
        mappings = checker.map_gateway_rules_to_endpoints()
        assert "routing_rules" in mappings
        assert "mapped_endpoints" in mappings
        assert len(mappings["routing_rules"]) > 0

    def test_validate_all_rules(self, temp_traefik_config, endpoint_inventory):
        """Test comprehensive validation of all rules"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(traefik_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(base_path),
        )

        results = checker.validate_all_rules()
        assert "summary" in results
        assert "routing_rules" in results
        assert "rate_limiting_rules" in results
        assert "authentication_rules" in results
        assert "mappings" in results

    def test_generate_report(self, temp_traefik_config, endpoint_inventory, tmp_path):
        """Test report generation"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(traefik_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(base_path),
        )

        report_file = tmp_path / "gateway-rules-report.json"
        checker.generate_report(str(report_file))

        assert report_file.exists()
        report_data = json.loads(report_file.read_text())
        assert "summary" in report_data
        assert "routing_rules" in report_data

    def test_missing_config_files(self, tmp_path, endpoint_inventory):
        """Test handling of missing configuration files"""
        empty_dir = tmp_path / "empty_traefik"
        empty_dir.mkdir()

        checker = APIGatewayRulesChecker(
            traefik_config_dir=str(empty_dir),
            endpoint_inventory_file=endpoint_inventory,
            base_path=str(tmp_path),
        )

        configs = checker.find_traefik_configs()
        assert len(configs) == 0

        rules = checker.extract_routing_rules()
        assert len(rules) == 0

    def test_missing_inventory_file(self, temp_traefik_config):
        """Test behavior with missing inventory file"""
        traefik_dir = temp_traefik_config / "traefik"
        base_path = temp_traefik_config.parent
        with pytest.raises(FileNotFoundError):
            APIGatewayRulesChecker(
                traefik_config_dir=str(traefik_dir),
                endpoint_inventory_file="nonexistent.json",
                base_path=str(base_path),
            )
