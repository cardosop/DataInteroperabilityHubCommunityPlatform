#!/usr/bin/env python3
"""
Tests for Gateway Configuration Review Script

Tests the comprehensive review of Traefik and Kubernetes ingress configurations.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.review_gateway_configs import (
    EndpointMapper,
    GatewayConfigReviewer,
    KubernetesIngressParser,
    TraefikConfigParser,
)


class TestTraefikConfigParser(unittest.TestCase):
    """Test Traefik configuration parser"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = TraefikConfigParser()

    def test_parse_routes_yml(self):
        """Test parsing Traefik routes.yml file"""
        routes_content = """
http:
  routers:
    contract-service:
      rule: "PathPrefix(`/api/v1/contracts`)"
      service: contract-service
      middlewares:
        - auth-middleware
        - rate-limit-middleware
  services:
    contract-service:
      loadBalancer:
        servers:
          - url: "http://contract-service:8001"
  middlewares:
    auth-middleware:
      forwardAuth:
        address: "http://api-service:8000/api/v1/auth/validate"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(routes_content)
            temp_path = f.name

        try:
            result = self.parser.parse_routes_file(Path(temp_path))
            self.assertIn("routers", result)
            self.assertIn("contract-service", result["routers"])
            self.assertEqual(
                result["routers"]["contract-service"]["rule"], "PathPrefix(`/api/v1/contracts`)"
            )
            self.assertIn("services", result)
            self.assertIn("middlewares", result)
        finally:
            Path(temp_path).unlink()

    def test_extract_routing_rules(self):
        """Test extracting routing rules from parsed config"""
        config = {
            "routers": {
                "contract-service": {
                    "rule": "PathPrefix(`/api/v1/contracts`)",
                    "service": "contract-service",
                    "middlewares": ["auth-middleware"],
                }
            }
        }
        rules = self.parser.extract_routing_rules(config)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["router_name"], "contract-service")
        self.assertEqual(rules[0]["path_prefix"], "/api/v1/contracts")

    def test_extract_service_definitions(self):
        """Test extracting service definitions"""
        config = {
            "services": {
                "contract-service": {
                    "loadBalancer": {"servers": [{"url": "http://contract-service:8001"}]}
                }
            }
        }
        services = self.parser.extract_service_definitions(config)
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]["service_name"], "contract-service")
        self.assertEqual(services[0]["url"], "http://contract-service:8001")

    def test_extract_middlewares(self):
        """Test extracting middleware definitions"""
        config = {
            "middlewares": {
                "auth-middleware": {
                    "forwardAuth": {"address": "http://api-service:8000/api/v1/auth/validate"}
                }
            }
        }
        middlewares = self.parser.extract_middlewares(config)
        self.assertEqual(len(middlewares), 1)
        self.assertEqual(middlewares[0]["name"], "auth-middleware")
        self.assertIn("forwardAuth", middlewares[0]["config"])


class TestKubernetesIngressParser(unittest.TestCase):
    """Test Kubernetes ingress parser"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = KubernetesIngressParser()

    def test_parse_ingress_yaml(self):
        """Test parsing Kubernetes ingress YAML"""
        ingress_content = """
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-service-ingress
  namespace: default
spec:
  ingressClassName: nginx
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(ingress_content)
            temp_path = f.name

        try:
            result = self.parser.parse_ingress_file(Path(temp_path))
            self.assertIsNotNone(result)
            self.assertEqual(result["metadata"]["name"], "api-service-ingress")
            self.assertIn("spec", result)
        finally:
            Path(temp_path).unlink()

    def test_extract_ingress_rules(self):
        """Test extracting ingress rules"""
        ingress = {
            "metadata": {"name": "api-service-ingress", "namespace": "default"},
            "spec": {
                "rules": [
                    {
                        "host": "api.example.com",
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {"name": "api-service", "port": {"number": 8000}}
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
        }
        rules = self.parser.extract_ingress_rules(ingress)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["host"], "api.example.com")
        self.assertEqual(rules[0]["path"], "/")
        self.assertEqual(rules[0]["service_name"], "api-service")
        self.assertEqual(rules[0]["service_port"], 8000)


class TestEndpointMapper(unittest.TestCase):
    """Test endpoint mapper"""

    def setUp(self):
        """Set up test fixtures"""
        self.mapper = EndpointMapper()

    def test_map_traefik_routes_to_endpoints(self):
        """Test mapping Traefik routes to endpoints"""
        traefik_routes = [
            {
                "router_name": "contract-service",
                "path_prefix": "/api/v1/contracts",
                "service": "contract-service",
            }
        ]
        django_endpoints = [
            {"path": "/api/v1/contracts/", "method": "GET", "name": "contract-list"},
            {"path": "/api/v1/contracts/{id}/", "method": "GET", "name": "contract-detail"},
        ]
        mappings = self.mapper.map_traefik_routes_to_endpoints(traefik_routes, django_endpoints)
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["route"], "contract-service")
        self.assertEqual(len(mappings[0]["endpoints"]), 2)

    def test_map_ingress_rules_to_endpoints(self):
        """Test mapping ingress rules to endpoints"""
        ingress_rules = [
            {
                "ingress_name": "api-service-ingress",
                "namespace": "default",
                "host": "api.example.com",
                "path": "/",
                "service_name": "api-service",
                "service_port": 8000,
            }
        ]
        django_endpoints = [
            {"path": "/api/v1/contracts/", "method": "GET"},
            {"path": "/api/v1/assets/", "method": "GET"},
        ]
        mappings = self.mapper.map_ingress_rules_to_endpoints(ingress_rules, django_endpoints)
        self.assertEqual(len(mappings), 1)
        self.assertIn("endpoints", mappings[0])
        self.assertEqual(mappings[0]["ingress"], "api-service-ingress")
        self.assertEqual(mappings[0]["host"], "api.example.com")
        self.assertEqual(len(mappings[0]["endpoints"]), 2)


class TestGatewayConfigReviewer(unittest.TestCase):
    """Test gateway configuration reviewer"""

    def setUp(self):
        """Set up test fixtures"""
        self.reviewer = GatewayConfigReviewer(project_root=str(project_root))

    @patch("scripts.review_gateway_configs.Path")
    def test_find_traefik_configs(self, mock_path):
        """Test finding Traefik configuration files"""
        mock_traefik_dir = Mock()
        mock_routes_file = Mock()
        mock_routes_file.is_file.return_value = True
        mock_routes_file.name = "routes.yml"
        mock_traefik_dir.glob.return_value = [mock_routes_file]
        mock_path.return_value = mock_traefik_dir

        configs = self.reviewer.find_traefik_configs()
        self.assertIsInstance(configs, list)

    @patch("scripts.review_gateway_configs.Path")
    def test_find_ingress_configs(self, mock_path):
        """Test finding Kubernetes ingress files"""
        mock_k8s_dir = Mock()
        mock_ingress_file = Mock()
        mock_ingress_file.is_file.return_value = True
        mock_ingress_file.name = "ingress.yaml"
        mock_k8s_dir.rglob.return_value = [mock_ingress_file]
        mock_path.return_value = mock_k8s_dir

        configs = self.reviewer.find_ingress_configs()
        self.assertIsInstance(configs, list)

    def test_validate_traefik_config(self):
        """Test validating Traefik configuration"""
        config = {
            "routers": {
                "test-router": {"rule": "PathPrefix(`/api/v1/test`)", "service": "test-service"}
            },
            "services": {
                "test-service": {"loadBalancer": {"servers": [{"url": "http://test-service:8000"}]}}
            },
        }
        issues = self.reviewer.validate_traefik_config(config)
        self.assertIsInstance(issues, list)

    def test_validate_ingress_config(self):
        """Test validating ingress configuration"""
        ingress = {
            "metadata": {"name": "test-ingress"},
            "spec": {
                "rules": [
                    {
                        "host": "test.example.com",
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "backend": {
                                        "service": {
                                            "name": "test-service",
                                            "port": {"number": 8000},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
        }
        issues = self.reviewer.validate_ingress_config(ingress)
        self.assertIsInstance(issues, list)


class TestGatewayConfigReviewerIntegration(unittest.TestCase):
    """Integration tests using actual configuration files"""

    def setUp(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).parent.parent.parent
        self.reviewer = GatewayConfigReviewer(project_root=str(self.project_root))

    def test_find_actual_traefik_configs(self):
        """Test finding actual Traefik configuration files in repository"""
        configs = self.reviewer.find_traefik_configs()
        self.assertGreater(len(configs), 0, "Should find at least one Traefik config file")

        # Verify expected files exist
        config_paths = [str(c.relative_to(self.project_root)) for c in configs]
        expected_docker_compose = "infrastructure/traefik/dynamic/routes.yml"
        expected_k8s = "k8s/api-gateway/traefik/configmap.yaml"

        self.assertIn(
            expected_docker_compose,
            config_paths,
            f"Should find Docker Compose Traefik config: {expected_docker_compose}",
        )
        self.assertIn(
            expected_k8s, config_paths, f"Should find Kubernetes Traefik config: {expected_k8s}"
        )

    def test_find_actual_ingress_configs(self):
        """Test finding actual Kubernetes ingress files in repository"""
        configs = self.reviewer.find_ingress_configs()
        self.assertGreater(len(configs), 0, "Should find at least one ingress file")

        # Verify we find ingress files in k8s directory
        config_paths = [str(c.relative_to(self.project_root)) for c in configs]
        ingress_paths = [p for p in config_paths if "ingress.yaml" in p]
        self.assertGreater(len(ingress_paths), 0, "Should find ingress.yaml files")

    def test_review_actual_traefik_configs(self):
        """Test reviewing actual Traefik configurations"""
        review = self.reviewer.review_traefik_configs()

        self.assertIn("config_files", review)
        self.assertIn("routers", review)
        self.assertIn("services", review)
        self.assertIn("middlewares", review)
        self.assertIn("issues", review)

        # Verify we found routers
        self.assertGreater(len(review["routers"]), 0, "Should find at least one router")

        # Verify router structure
        for router in review["routers"]:
            self.assertIn("router_name", router)
            self.assertIn("service", router)
            self.assertIn("middlewares", router)

    def test_review_actual_ingress_configs(self):
        """Test reviewing actual Kubernetes ingress configurations"""
        review = self.reviewer.review_ingress_configs()

        self.assertIn("ingress_files", review)
        self.assertIn("rules", review)
        self.assertIn("issues", review)

        # Verify we found ingress rules
        self.assertGreater(len(review["rules"]), 0, "Should find at least one ingress rule")

        # Verify rule structure
        for rule in review["rules"]:
            self.assertIn("ingress_name", rule)
            self.assertIn("host", rule)
            self.assertIn("service_name", rule)
            self.assertIn("service_port", rule)

    def test_map_actual_gateway_rules_to_endpoints(self):
        """Test mapping actual gateway rules to endpoints"""
        mappings = self.reviewer.map_gateway_rules_to_endpoints()

        self.assertIn("traefik_mappings", mappings)
        self.assertIn("ingress_mappings", mappings)
        self.assertIn("total_endpoints", mappings)

        # Verify we have mappings
        self.assertGreater(
            len(mappings["traefik_mappings"]), 0, "Should have Traefik route mappings"
        )
        self.assertGreater(
            len(mappings["ingress_mappings"]), 0, "Should have ingress rule mappings"
        )

        # Verify endpoint count
        self.assertGreater(mappings["total_endpoints"], 0, "Should map to at least some endpoints")

    def test_generate_actual_report(self):
        """Test generating actual review report"""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            report = self.reviewer.generate_report(output_dir=output_dir)

            # Verify report structure
            self.assertIn("timestamp", report)
            self.assertIn("traefik_review", report)
            self.assertIn("ingress_review", report)
            self.assertIn("mappings", report)
            self.assertIn("summary", report)

            # Verify files were created
            json_file = output_dir / "gateway-config-review.json"
            md_file = output_dir / "gateway-config-review.md"

            self.assertTrue(json_file.exists(), "JSON report should be created")
            self.assertTrue(md_file.exists(), "Markdown report should be created")

            # Verify JSON file is valid
            import json

            with open(json_file) as f:
                json_data = json.load(f)
            self.assertIsInstance(json_data, dict)

    def test_traefik_routers_have_valid_services(self):
        """Test that all Traefik routers reference valid services"""
        review = self.reviewer.review_traefik_configs()

        router_services = {r["service"] for r in review["routers"] if r.get("service")}
        defined_services = {s["service_name"] for s in review["services"]}

        # Check for routers referencing non-existent services
        missing_services = router_services - defined_services
        # api-service is allowed as it's used by auth middleware
        missing_services.discard("api-service")

        self.assertEqual(
            len(missing_services), 0, f"Routers reference undefined services: {missing_services}"
        )

    def test_ingress_rules_have_valid_structure(self):
        """Test that ingress rules have valid structure"""
        review = self.reviewer.review_ingress_configs()

        for rule in review["rules"]:
            # Verify required fields
            self.assertIsNotNone(rule.get("ingress_name"), "Rule should have ingress_name")
            self.assertIsNotNone(rule.get("host"), "Rule should have host")
            self.assertIsNotNone(rule.get("service_name"), "Rule should have service_name")
            self.assertIsNotNone(rule.get("service_port"), "Rule should have service_port")

            # Verify port is a number
            self.assertIsInstance(
                rule.get("service_port"),
                int,
                f"Service port should be integer: {rule.get('service_port')}",
            )

    def test_traefik_middlewares_are_defined(self):
        """Test that Traefik routers reference defined middlewares"""
        review = self.reviewer.review_traefik_configs()

        router_middlewares = set()
        for router in review["routers"]:
            router_middlewares.update(router.get("middlewares", []))

        defined_middlewares = {m["name"] for m in review["middlewares"]}

        # Check for routers referencing non-existent middlewares
        missing_middlewares = router_middlewares - defined_middlewares
        self.assertEqual(
            len(missing_middlewares),
            0,
            f"Routers reference undefined middlewares: {missing_middlewares}",
        )

    def test_traefik_configs_match_docker_compose(self):
        """Test that Traefik configurations match docker-compose.yml service definitions"""
        import yaml

        # Load docker-compose.yml
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file) as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})

        # Get Traefik review
        review = self.reviewer.review_traefik_configs()

        # Check that services referenced in Traefik configs exist in docker-compose
        traefik_service_names = {s["service_name"] for s in review["services"]}

        # Extract service names from docker-compose (remove port suffix)
        compose_service_names = set(services.keys())

        # Check for services in Traefik that don't exist in docker-compose
        # Some services might be external or in different compose files, so we'll just log warnings
        missing_in_compose = traefik_service_names - compose_service_names
        if missing_in_compose:
            # These might be external services or in other compose files, which is OK
            print(f"Info: Traefik services not in main docker-compose.yml: {missing_in_compose}")

        # Verify at least some services match
        matching_services = traefik_service_names & compose_service_names
        self.assertGreater(
            len(matching_services),
            0,
            "At least some Traefik services should exist in docker-compose.yml",
        )

    def test_traefik_service_urls_are_valid(self):
        """Test that Traefik service URLs have valid format"""
        review = self.reviewer.review_traefik_configs()

        for service in review["services"]:
            url = service.get("url", "")
            self.assertTrue(
                url.startswith("http://") or url.startswith("https://"),
                f"Service URL should start with http:// or https://: {url}",
            )

            # Verify URL has host and port
            host = service.get("host")
            port = service.get("port")
            self.assertIsNotNone(host, f"Service should have host: {service}")
            self.assertIsNotNone(port, f"Service should have port: {service}")
            self.assertIsInstance(port, int, f"Port should be integer: {port}")


if __name__ == "__main__":
    unittest.main()
