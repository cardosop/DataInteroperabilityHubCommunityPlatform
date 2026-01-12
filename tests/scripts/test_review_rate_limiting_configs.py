#!/usr/bin/env python3
"""
Tests for rate limiting configuration review script

Tests the review and mapping of rate limiting configurations to endpoints.
"""

import sys
import tempfile
import unittest
import json
from pathlib import Path

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

# Import with proper handling
import importlib.util
spec = importlib.util.spec_from_file_location(
    "review_rate_limiting_configs",
    project_root / "scripts" / "review_rate_limiting_configs.py"
)
if spec and spec.loader:
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    RateLimitingConfigReviewer = module.RateLimitingConfigReviewer
    RateLimitRule = module.RateLimitRule
    EndpointRateLimitMapping = module.EndpointRateLimitMapping


class TestRateLimitingConfigReviewer(unittest.TestCase):
    """Test suite for RateLimitingConfigReviewer"""

    def setUp(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).parent.parent.parent
        self.hub_dir = self.project_root / "hub"
        self.reviewer = RateLimitingConfigReviewer(self.hub_dir)

    def test_review_endpoint_category_mappings(self):
        """Test endpoint category mapping review"""
        mappings = self.reviewer.review_endpoint_category_mappings()

        self.assertIsInstance(mappings, dict, "Should return a dictionary")
        self.assertGreater(len(mappings), 0, "Should find category mappings")

        # Check for expected categories
        expected_categories = ['auth', 'asset', 'contract', 'search', 'dq_run',
                              'compliance_run', 'file_upload', 'file_download']
        for category in expected_categories:
            if category in mappings:
                self.assertGreater(len(mappings[category]), 0,
                                 f"Category {category} should have endpoint patterns")

    def test_review_rate_limit_rules(self):
        """Test rate limit rules review"""
        rules = self.reviewer.review_rate_limit_rules()

        self.assertIsInstance(rules, list, "Should return a list")
        self.assertGreater(len(rules), 0, "Should find rate limit rules")

        # Check rule structure
        for rule in rules:
            self.assertIsInstance(rule, RateLimitRule)
            self.assertIn(rule.category, ['auth', 'asset', 'contract', 'search',
                                         'dq_run', 'compliance_run', 'file_upload',
                                         'file_download', 'contract_validation',
                                         'catalog_read', 'sparql_query',
                                         'transformation', 'general'])
            self.assertIn(rule.window, ['BURST', 'SUSTAINED', 'DAILY'])
            self.assertGreaterEqual(rule.default_limit, 0)
            self.assertGreaterEqual(rule.maximum_limit, 0)

    def test_map_rate_limiting_to_endpoints(self):
        """Test mapping rate limiting configs to endpoints"""
        test_endpoints = [
            {"path": "/api/v1/auth/login/", "method": "POST"},
            {"path": "/api/v1/assets/", "method": "GET"},
            {"path": "/api/v1/assets/", "method": "POST"},
            {"path": "/api/v1/contracts/", "method": "GET"},
            {"path": "/api/v1/dq/runs/", "method": "POST"},
        ]

        mappings = self.reviewer.map_rate_limiting_to_endpoints(test_endpoints)

        self.assertIsInstance(mappings, list)
        self.assertEqual(len(mappings), len(test_endpoints))

        # Check mapping structure
        for mapping in mappings:
            self.assertIsInstance(mapping, EndpointRateLimitMapping)
            self.assertIn(mapping.category, ['auth', 'asset', 'contract', 'search',
                                            'dq_run', 'compliance_run', 'file_upload',
                                            'file_download', 'contract_validation',
                                            'catalog_read', 'sparql_query',
                                            'transformation', 'general'])
            self.assertGreaterEqual(mapping.burst_limit, 0)
            self.assertGreaterEqual(mapping.sustained_limit, 0)
            self.assertGreaterEqual(mapping.daily_limit, 0)

    def test_extract_endpoints_from_codebase(self):
        """Test endpoint extraction from codebase"""
        endpoints = self.reviewer.extract_endpoints_from_codebase()

        self.assertIsInstance(endpoints, list)
        # Should extract at least some endpoints
        self.assertGreaterEqual(len(endpoints), 0)

        # Check endpoint structure
        for endpoint in endpoints[:5]:  # Check first 5
            self.assertIn('path', endpoint)
            self.assertIn('method', endpoint)

    def test_verify_all_rate_limiting_configs_reviewed(self):
        """Test verification that all rate limiting configs are reviewed"""
        # First review the configs
        self.reviewer.review_rate_limit_rules()

        verification = self.reviewer.verify_all_rate_limiting_configs_reviewed()

        self.assertIn("status", verification)
        self.assertIn("categories_reviewed", verification)
        self.assertIn("total_categories", verification)
        self.assertIn("rules_reviewed", verification)
        self.assertIn("expected_rules", verification)

        # Should have reviewed all categories
        self.assertEqual(verification["categories_reviewed"],
                        verification["total_categories"])

    def test_verify_rate_limiting_mapping(self):
        """Test verification of rate limiting mapping"""
        # First map some endpoints
        test_endpoints = [
            {"path": "/api/v1/auth/login/", "method": "POST"},
            {"path": "/api/v1/assets/", "method": "GET"},
        ]
        self.reviewer.map_rate_limiting_to_endpoints(test_endpoints)

        verification = self.reviewer.verify_rate_limiting_mapping()

        self.assertIn("status", verification)
        self.assertIn("endpoints_mapped", verification)
        self.assertIn("categories_with_endpoints", verification)
        self.assertIn("category_coverage", verification)
        self.assertIn("mapping_working", verification)

        self.assertTrue(verification["mapping_working"])

    def test_generate_report(self):
        """Test report generation"""
        # Set up reviewer with data
        self.reviewer.review_endpoint_category_mappings()
        self.reviewer.review_rate_limit_rules()
        test_endpoints = [
            {"path": "/api/v1/auth/login/", "method": "POST"},
            {"path": "/api/v1/assets/", "method": "GET"},
        ]
        self.reviewer.map_rate_limiting_to_endpoints(test_endpoints)

        # Generate report
        temp_file = Path(tempfile.mktemp(suffix='.json'))
        try:
            report = self.reviewer.generate_report(temp_file)

            self.assertTrue(temp_file.exists(), "Report file should exist")

            # Verify report structure
            with open(temp_file) as f:
                report_data = json.load(f)

            self.assertIn("summary", report_data)
            self.assertIn("rate_limit_rules", report_data)
            self.assertIn("endpoint_category_mappings", report_data)
            self.assertIn("endpoint_rate_limit_mappings", report_data)
            self.assertIn("generated_at", report_data)
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_category_mapping_for_auth_endpoints(self):
        """Test that auth endpoints map to AUTH category"""
        mappings = self.reviewer.review_endpoint_category_mappings()

        if 'auth' in mappings:
            auth_endpoints = mappings['auth']
            self.assertGreater(len(auth_endpoints), 0, "Should have auth endpoints")

            # Check that auth endpoints are in the list
            paths = [ep[0] for ep in auth_endpoints]
            self.assertTrue(any('/auth/' in path.lower() for path in paths),
                          "Should contain auth paths")

    def test_category_mapping_for_asset_endpoints(self):
        """Test that asset endpoints map correctly"""
        mappings = self.reviewer.review_endpoint_category_mappings()

        # Check asset category
        if 'asset' in mappings:
            asset_endpoints = mappings['asset']
            paths = [ep[0] for ep in asset_endpoints]
            methods = [ep[1] for ep in asset_endpoints]
            # Asset endpoints should have write methods
            self.assertTrue(any(m in ['POST', 'PUT', 'PATCH', 'DELETE'] for m in methods),
                          "Should have write methods for asset category")

        # Check catalog_read category (GET requests to assets)
        if 'catalog_read' in mappings:
            catalog_endpoints = mappings['catalog_read']
            paths = [ep[0] for ep in catalog_endpoints]
            methods = [ep[1] for ep in catalog_endpoints]
            # Catalog read should have GET methods
            self.assertTrue(any(m == 'GET' for m in methods),
                          "Should have GET methods for catalog_read category")

    def test_rate_limit_rules_have_all_windows(self):
        """Test that rate limit rules have all three time windows"""
        rules = self.reviewer.review_rate_limit_rules()

        # Group by category
        rules_by_category = {}
        for rule in rules:
            if rule.category not in rules_by_category:
                rules_by_category[rule.category] = []
            rules_by_category[rule.category].append(rule)

        # Each category should have 3 windows
        for category, category_rules in rules_by_category.items():
            windows = [rule.window for rule in category_rules]
            self.assertIn('BURST', windows, f"{category} should have BURST window")
            self.assertIn('SUSTAINED', windows, f"{category} should have SUSTAINED window")
            self.assertIn('DAILY', windows, f"{category} should have DAILY window")

    def test_maximum_limits_greater_than_defaults(self):
        """Test that maximum limits are greater than or equal to default limits"""
        rules = self.reviewer.review_rate_limit_rules()

        # Group by category and window
        limits_by_key = {}
        for rule in rules:
            key = (rule.category, rule.window)
            limits_by_key[key] = rule

        # Check that maximum >= default for each rule
        for key, rule in limits_by_key.items():
            self.assertGreaterEqual(rule.maximum_limit, rule.default_limit,
                                  f"Maximum limit should be >= default for {key}")

    def test_integration_with_real_codebase(self):
        """Integration test with real codebase - no mocks"""
        # Use actual project codebase
        reviewer = RateLimitingConfigReviewer(self.hub_dir)

        # Review category mappings
        mappings = reviewer.review_endpoint_category_mappings()
        self.assertGreater(len(mappings), 0, "Should find category mappings")

        # Review rate limit rules
        rules = reviewer.review_rate_limit_rules()
        self.assertGreater(len(rules), 0, "Should find rate limit rules")

        # Extract endpoints
        endpoints = reviewer.extract_endpoints_from_codebase()
        self.assertGreater(len(endpoints), 0, "Should extract endpoints")

        # Map endpoints
        endpoint_mappings = reviewer.map_rate_limiting_to_endpoints(endpoints)
        self.assertGreater(len(endpoint_mappings), 0, "Should map endpoints")

        # Verify configs reviewed
        configs_verification = reviewer.verify_all_rate_limiting_configs_reviewed()
        self.assertEqual(configs_verification["status"], "success")

        # Verify mapping
        mapping_verification = reviewer.verify_rate_limiting_mapping()
        self.assertTrue(mapping_verification["mapping_working"])


def main():
    """Run tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestRateLimitingConfigReviewer)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

