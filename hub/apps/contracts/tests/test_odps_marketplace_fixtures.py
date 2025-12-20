"""
Unit tests for ODPS marketplace test fixtures.

Tests verify that all ODPS marketplace test fixtures are valid ODPS documents
that pass schema validation. This ensures marketplace metadata is correctly
structured and can be used for testing marketplace functionality.
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import json
from pathlib import Path
from django.test import TestCase

try:
    import jsonschema
    from jsonschema import validate, Draft202012Validator, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    # Create mock classes for when jsonschema is not available
    class ValidationError(Exception):
        pass


class ODPSMarketplaceFixturesTest(TestCase):
    """Test ODPS marketplace test fixtures are valid"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for contracts app
        self.base_dir = Path(__file__).parent.parent
        self.schemas_dir = self.base_dir / "schemas" / "odps"

        # Get the fixtures directory
        # Test file is at: hub/apps/contracts/tests/test_odps_marketplace_fixtures.py
        # Project root (hub) is: hub/apps/contracts/tests -> hub/apps/contracts -> hub/apps -> hub
        # Fixtures are at: tests/fixtures/odps/ (relative to project root, not hub)
        hub_dir = Path(__file__).parent.parent.parent.parent  # hub/
        project_root = hub_dir.parent  # project root (parent of hub/)
        self.fixtures_base = project_root / "tests" / "fixtures" / "odps"
        self.marketplace_fixtures_dir = self.fixtures_base / "v4.1" / "marketplace"

        # Load ODPS 4.1 schema
        self.schema_path = self.schemas_dir / "v4.1" / "odps-schema.json"
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            self.schema = json.load(f)

    def test_marketplace_fixtures_directory_exists(self):
        """Test that marketplace fixtures directory exists"""
        self.assertTrue(
            self.marketplace_fixtures_dir.exists(),
            f"Marketplace fixtures directory should exist at: {self.marketplace_fixtures_dir}"
        )
        self.assertTrue(
            self.marketplace_fixtures_dir.is_dir(),
            f"Marketplace fixtures should be a directory: {self.marketplace_fixtures_dir}"
        )

    def test_pricing_plans_sample_is_valid(self):
        """Test that pricing plans sample is valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.marketplace_fixtures_dir / "sample-pricing-plans-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        # Validate against schema
        try:
            validate(instance=odps_doc, schema=self.schema)
        except ValidationError as e:
            self.fail(f"Pricing plans sample should be valid ODPS: {e}")

        # Verify marketplace.pricingPlans exists and is an array
        self.assertIn("product", odps_doc)
        self.assertIn("marketplace", odps_doc["product"])
        self.assertIn("pricingPlans", odps_doc["product"]["marketplace"])
        self.assertIsInstance(odps_doc["product"]["marketplace"]["pricingPlans"], list)
        self.assertGreater(
            len(odps_doc["product"]["marketplace"]["pricingPlans"]),
            0,
            "Should have at least one pricing plan"
        )

    def test_access_methods_sample_is_valid(self):
        """Test that access methods sample is valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.marketplace_fixtures_dir / "sample-access-methods-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        # Validate against schema
        try:
            validate(instance=odps_doc, schema=self.schema)
        except ValidationError as e:
            self.fail(f"Access methods sample should be valid ODPS: {e}")

        # Verify marketplace.accessMethods exists and is an object
        self.assertIn("product", odps_doc)
        self.assertIn("marketplace", odps_doc["product"])
        self.assertIn("accessMethods", odps_doc["product"]["marketplace"])
        self.assertIsInstance(odps_doc["product"]["marketplace"]["accessMethods"], dict)
        self.assertGreater(
            len(odps_doc["product"]["marketplace"]["accessMethods"]),
            0,
            "Should have at least one access method"
        )

    def test_payment_gateways_sample_is_valid(self):
        """Test that payment gateways sample is valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.marketplace_fixtures_dir / "sample-payment-gateways-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        # Validate against schema
        try:
            validate(instance=odps_doc, schema=self.schema)
        except ValidationError as e:
            self.fail(f"Payment gateways sample should be valid ODPS: {e}")

        # Verify marketplace.paymentGateways exists and is an object
        self.assertIn("product", odps_doc)
        self.assertIn("marketplace", odps_doc["product"])
        self.assertIn("paymentGateways", odps_doc["product"]["marketplace"])
        self.assertIsInstance(odps_doc["product"]["marketplace"]["paymentGateways"], dict)
        self.assertGreater(
            len(odps_doc["product"]["marketplace"]["paymentGateways"]),
            0,
            "Should have at least one payment gateway"
        )

    def test_complete_marketplace_sample_is_valid(self):
        """Test that complete marketplace sample is valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        fixture_path = self.marketplace_fixtures_dir / "sample-complete-marketplace-v4.1.json"
        self.assertTrue(fixture_path.exists(), f"Fixture should exist: {fixture_path}")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        # Validate against schema
        try:
            validate(instance=odps_doc, schema=self.schema)
        except ValidationError as e:
            self.fail(f"Complete marketplace sample should be valid ODPS: {e}")

        # Verify all marketplace components exist
        self.assertIn("product", odps_doc)
        self.assertIn("marketplace", odps_doc["product"])
        marketplace = odps_doc["product"]["marketplace"]

        # Should have pricing plans
        self.assertIn("pricingPlans", marketplace)
        self.assertIsInstance(marketplace["pricingPlans"], list)

        # Should have access methods
        self.assertIn("accessMethods", marketplace)
        self.assertIsInstance(marketplace["accessMethods"], dict)

        # Should have payment gateways
        self.assertIn("paymentGateways", marketplace)
        self.assertIsInstance(marketplace["paymentGateways"], dict)

    def test_all_marketplace_fixtures_are_valid(self):
        """Test that all marketplace fixture files are valid ODPS"""
        if not JSONSCHEMA_AVAILABLE:
            self.skipTest("jsonschema library not available")

        # Get all marketplace fixture files
        marketplace_files = list(self.marketplace_fixtures_dir.glob("sample-*.json"))
        self.assertGreater(
            len(marketplace_files),
            0,
            f"Should have at least one marketplace fixture file in {self.marketplace_fixtures_dir}"
        )

        validation_errors = []
        for fixture_path in marketplace_files:
            with self.subTest(fixture=fixture_path.name):
                try:
                    with open(fixture_path, 'r', encoding='utf-8') as f:
                        odps_doc = json.load(f)

                    # Validate against schema
                    try:
                        validate(instance=odps_doc, schema=self.schema)
                    except ValidationError as e:
                        validation_errors.append(
                            f"{fixture_path.name}: Validation failed: {e}"
                        )
                except json.JSONDecodeError as e:
                    validation_errors.append(
                        f"{fixture_path.name}: Invalid JSON: {e}"
                    )
                except Exception as e:
                    validation_errors.append(
                        f"{fixture_path.name}: Unexpected error: {e}"
                    )

        # All marketplace fixtures should be valid
        if validation_errors:
            self.fail(
                f"Some marketplace fixtures are not valid ODPS:\n"
                + "\n".join(f"  - {msg}" for msg in validation_errors)
            )

    def test_pricing_plans_have_required_structure(self):
        """Test that pricing plans have expected structure"""
        fixture_path = self.marketplace_fixtures_dir / "sample-pricing-plans-v4.1.json"
        if not fixture_path.exists():
            self.skipTest("Pricing plans fixture not found")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        pricing_plans = odps_doc["product"]["marketplace"]["pricingPlans"]

        # Verify each plan has basic structure
        for plan in pricing_plans:
            with self.subTest(plan_id=plan.get("planID", "unknown")):
                self.assertIn("planID", plan, "Pricing plan should have planID")
                self.assertIn("name", plan, "Pricing plan should have name")
                # Price or pricingModel should be present
                self.assertTrue(
                    "price" in plan or "pricingModel" in plan,
                    "Pricing plan should have price or pricingModel"
                )

    def test_access_methods_have_required_structure(self):
        """Test that access methods have expected structure"""
        fixture_path = self.marketplace_fixtures_dir / "sample-access-methods-v4.1.json"
        if not fixture_path.exists():
            self.skipTest("Access methods fixture not found")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        access_methods = odps_doc["product"]["marketplace"]["accessMethods"]

        # Verify access methods is an object with at least one method
        self.assertIsInstance(access_methods, dict)
        self.assertGreater(len(access_methods), 0, "Should have at least one access method")

        # Common access methods should have endpoint or url
        for method_name, method_config in access_methods.items():
            with self.subTest(method=method_name):
                self.assertIsInstance(method_config, dict, f"Access method {method_name} should be an object")
                # Most methods should have endpoint, url, or similar
                has_access_point = any(
                    key in method_config for key in ["endpoint", "url", "host", "bucket"]
                )
                self.assertTrue(
                    has_access_point,
                    f"Access method {method_name} should have endpoint, url, host, or bucket"
                )

    def test_payment_gateways_have_required_structure(self):
        """Test that payment gateways have expected structure"""
        fixture_path = self.marketplace_fixtures_dir / "sample-payment-gateways-v4.1.json"
        if not fixture_path.exists():
            self.skipTest("Payment gateways fixture not found")

        with open(fixture_path, 'r', encoding='utf-8') as f:
            odps_doc = json.load(f)

        payment_gateways = odps_doc["product"]["marketplace"]["paymentGateways"]

        # Verify payment gateways is an object with at least one gateway
        self.assertIsInstance(payment_gateways, dict)
        self.assertGreater(len(payment_gateways), 0, "Should have at least one payment gateway")

        # Each gateway should have enabled flag
        for gateway_name, gateway_config in payment_gateways.items():
            with self.subTest(gateway=gateway_name):
                self.assertIsInstance(gateway_config, dict, f"Payment gateway {gateway_name} should be an object")
                self.assertIn("enabled", gateway_config, f"Payment gateway {gateway_name} should have enabled flag")

