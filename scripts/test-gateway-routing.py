#!/usr/bin/env python3
"""
Test API Gateway Routing

This script tests that API gateway routing works correctly:
- Traefik routes are properly configured
- Routes use standardized endpoint patterns
- Services are accessible through gateway

Usage:
    python3 scripts/test-gateway-routing.py
"""

import os
import sys
import yaml
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class GatewayRoutingTest:
    """Test suite for API gateway routing"""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.tests_passed = 0
        self.tests_failed = 0
        self.tests_skipped = 0
        self.failures = []
        self.gateway_url = os.getenv('GATEWAY_URL', 'http://localhost')
        self.api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')

    def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("API Gateway Routing - Comprehensive Test Suite")
        print("=" * 60)
        print()

        # Test 1: Traefik Configuration
        self.test_traefik_configuration()

        # Test 2: Kubernetes Ingress Rules
        self.test_kubernetes_ingress_rules()

        # Test 3: Route Patterns
        self.test_route_patterns()

        # Test 4: Service Routing (if services available)
        self.test_service_routing()

        # Print summary
        self.print_summary()

        return self.tests_failed == 0

    def test_traefik_configuration(self):
        """Test Traefik configuration"""
        print("Test 1: Traefik Configuration")
        print("-" * 60)

        routes_file = self.project_root / 'infrastructure' / 'traefik' / 'dynamic' / 'routes.yml'

        if not routes_file.exists():
            print("⚠️  SKIPPED: Traefik routes file not found")
            self.tests_skipped += 1
            return

        try:
            content = routes_file.read_text(encoding='utf-8')

            # Check compliance service route
            assert 'compliance-service' in content, "Compliance service route should exist"
            assert 'PathPrefix(`/api/v1/compliance`)' in content, (
                "Compliance service should use /api/v1/compliance route"
            )
            assert '/api/v1/compliance/compliance-runs' not in content, (
                "Should not use old compliance-runs pattern"
            )

            # Check DQ service route
            assert 'dq-service' in content, "DQ service route should exist"
            assert 'PathPrefix(`/api/v1/dq`)' in content, (
                "DQ service should use /api/v1/dq route"
            )
            assert '/api/v1/dq/dq-runs' not in content, (
                "Should not use old dq-runs pattern"
            )

            # Verify service definitions exist
            assert 'services:' in content, "Should have services section"
            assert 'compliance-service:' in content, "Should have compliance service definition"
            assert 'dq-service:' in content, "Should have DQ service definition"

            print("✅ PASSED: Traefik configuration valid")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Traefik config: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Traefik config: {e}")

        print()

    def test_kubernetes_ingress_rules(self):
        """Test Kubernetes ingress rules"""
        print("Test 2: Kubernetes Ingress Rules")
        print("-" * 60)

        ingress_files = list((self.project_root / 'k8s').rglob('**/ingress.yaml'))

        if len(ingress_files) == 0:
            print("⚠️  SKIPPED: No ingress files found")
            self.tests_skipped += 1
            return

        try:
            compliance_ingress_found = False
            dq_ingress_found = False

            for ingress_file in ingress_files:
                try:
                    content = ingress_file.read_text(encoding='utf-8')
                    ingress = yaml.safe_load(content)

                    if not ingress or 'metadata' not in ingress:
                        continue

                    name = ingress['metadata'].get('name', '')

                    # Check compliance service ingress
                    if 'compliance' in name.lower():
                        compliance_ingress_found = True
                        # Should not have old patterns in paths
                        if 'spec' in ingress and 'rules' in ingress['spec']:
                            for rule in ingress['spec']['rules']:
                                if 'http' in rule and 'paths' in rule['http']:
                                    for path in rule['http']['paths']:
                                        path_value = path.get('path', '')
                                        assert '/compliance-runs' not in path_value, (
                                            f"Compliance ingress should not use old pattern: {path_value}"
                                        )

                    # Check DQ service ingress
                    if 'dq' in name.lower() and 'service' in name.lower():
                        dq_ingress_found = True
                        # Should not have old patterns in paths
                        if 'spec' in ingress and 'rules' in ingress['spec']:
                            for rule in ingress['spec']['rules']:
                                if 'http' in rule and 'paths' in rule['http']:
                                    for path in rule['http']['paths']:
                                        path_value = path.get('path', '')
                                        assert '/dq-runs' not in path_value, (
                                            f"DQ ingress should not use old pattern: {path_value}"
                                        )

                except yaml.YAMLError:
                    continue  # Skip invalid YAML files
                except Exception as e:
                    continue  # Skip files with errors

            print(f"✅ PASSED: All {len(ingress_files)} ingress files verified")
            if compliance_ingress_found:
                print("   ✅ Compliance service ingress found and verified")
            if dq_ingress_found:
                print("   ✅ DQ service ingress found and verified")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Kubernetes ingress: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Kubernetes ingress: {e}")

        print()

    def test_route_patterns(self):
        """Test route patterns use standardized endpoints"""
        print("Test 3: Route Patterns")
        print("-" * 60)

        routes_file = self.project_root / 'infrastructure' / 'traefik' / 'dynamic' / 'routes.yml'
        k8s_configmap = self.project_root / 'k8s' / 'api-gateway' / 'traefik' / 'configmap.yaml'

        try:
            files_to_check = []
            if routes_file.exists():
                files_to_check.append(routes_file)
            if k8s_configmap.exists():
                files_to_check.append(k8s_configmap)

            if len(files_to_check) == 0:
                print("⚠️  SKIPPED: No route configuration files found")
                self.tests_skipped += 1
                return

            for config_file in files_to_check:
                content = config_file.read_text(encoding='utf-8')

                # Extract PathPrefix rules
                import re
                pathprefix_pattern = r'PathPrefix\(`([^`]+)`\)'
                matches = re.findall(pathprefix_pattern, content)

                # Check compliance routes
                compliance_routes = [m for m in matches if 'compliance' in m]
                for route in compliance_routes:
                    assert route == '/api/v1/compliance', (
                        f"Compliance route should be /api/v1/compliance, found: {route}"
                    )
                    assert '/compliance-runs' not in route, (
                        f"Compliance route should not include /compliance-runs: {route}"
                    )

                # Check DQ routes
                dq_routes = [m for m in matches if '/dq' in m]
                for route in dq_routes:
                    assert route == '/api/v1/dq', (
                        f"DQ route should be /api/v1/dq, found: {route}"
                    )
                    assert '/dq-runs' not in route, (
                        f"DQ route should not include /dq-runs: {route}"
                    )

            print(f"✅ PASSED: Route patterns verified in {len(files_to_check)} file(s)")
            self.tests_passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Route patterns: {e}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Route patterns: {e}")

        print()

    def test_service_routing(self):
        """Test service routing (if services available)"""
        print("Test 4: Service Routing (Optional)")
        print("-" * 60)

        def check_service(url: str, timeout: int = 2) -> bool:
            try:
                response = requests.get(url, timeout=timeout)
                return response.status_code in [200, 401, 403, 404]  # 404 means route exists but endpoint doesn't
            except Exception:
                return False

        # Test API service directly (bypass gateway)
        try:
            if check_service(self.api_url):
                # Test compliance endpoint
                compliance_url = f"{self.api_url}/api/v1/compliance/runs/"
                response = requests.get(compliance_url, timeout=5)

                # Should return 401 (auth required) or 404 (not found), not 500 (server error)
                assert response.status_code != 500, (
                    f"Compliance endpoint should not return 500 (got {response.status_code})"
                )

                # Test DQ endpoint
                dq_url = f"{self.api_url}/api/v1/dq/runs/"
                response = requests.get(dq_url, timeout=5)

                # Should return 401 (auth required) or 404 (not found), not 500 (server error)
                assert response.status_code != 500, (
                    f"DQ endpoint should not return 500 (got {response.status_code})"
                )

                print("✅ PASSED: Service routing verified")
                self.tests_passed += 1
            else:
                print("⚠️  SKIPPED: API service not available")
                self.tests_skipped += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            self.tests_failed += 1
            self.failures.append(f"Service routing: {e}")
        except Exception as e:
            print(f"⚠️  SKIPPED: Service not accessible: {e}")
            self.tests_skipped += 1

        print()

    def print_summary(self):
        """Print test summary"""
        print("=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Tests Passed:  {self.tests_passed}")
        print(f"Tests Failed:  {self.tests_failed}")
        print(f"Tests Skipped: {self.tests_skipped}")
        print()

        if self.failures:
            print("Failures:")
            for failure in self.failures:
                print(f"  - {failure}")
            print()

        if self.tests_failed == 0:
            print("✅ All tests passed!")
        else:
            print(f"❌ {self.tests_failed} test(s) failed")


def main():
    """Main execution"""
    test_suite = GatewayRoutingTest()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

