#!/usr/bin/env python3
"""
Tests for API inventory review script

Tests the review and comparison of API inventory with actual endpoints.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

# Import with proper handling
import importlib.util

spec = importlib.util.spec_from_file_location(
    "review_api_inventory", project_root / "scripts" / "review_api_inventory.py"
)
if spec and spec.loader:
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    APIInventoryReviewer = module.APIInventoryReviewer
    InventoryEndpoint = module.InventoryEndpoint
    Discrepancy = module.Discrepancy


class TestAPIInventoryReviewer(unittest.TestCase):
    """Test suite for APIInventoryReviewer"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create mock inventory file
        inventory_dir = self.temp_path / "docs" / "api-audit"
        inventory_dir.mkdir(parents=True)

        inventory_content = """# Current API Inventory

## Endpoints by Application

### Assets (3 endpoints)

**Base Route**: `/api/v1/assets/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/assets/` | `AssetViewSet.list` | list | Standard |
| POST | `/api/v1/assets/` | `AssetViewSet.create` | create | Standard |
| GET | `/api/v1/assets/{id}/` | `AssetViewSet.retrieve` | retrieve | Standard |

### Contracts (2 endpoints)

**Base Route**: `/api/v1/contracts/`

| Method | Path | View | Action | Type |
|--------|------|------|--------|------|
| GET | `/api/v1/contracts/` | `ContractViewSet.list` | list | Standard |
| POST | `/api/v1/contracts/` | `ContractViewSet.create` | create | Standard |
"""

        self.inventory_file = inventory_dir / "current-api-inventory.md"
        self.inventory_file.write_text(inventory_content)

        # Create mock hub directory with minimal structure
        hub_dir = self.temp_path / "hub"
        hub_dir.mkdir()
        (hub_dir / "urls.py").write_text("# Main URLs")

        self.hub_dir = hub_dir

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_inventory_file(self):
        """Test parsing inventory markdown file"""
        reviewer = APIInventoryReviewer(self.inventory_file, self.hub_dir)
        endpoints = reviewer.parse_inventory_file()

        self.assertGreater(len(endpoints), 0, "Should parse endpoints from inventory")
        self.assertEqual(len(endpoints), 5, "Should parse 5 endpoints")

        # Check first endpoint
        first = endpoints[0]
        self.assertEqual(first.method, "GET")
        self.assertEqual(first.path, "/api/v1/assets/")
        self.assertEqual(first.application, "Assets")

    def test_normalize_path(self):
        """Test path normalization"""
        reviewer = APIInventoryReviewer(self.inventory_file, self.hub_dir)

        test_cases = [
            ("/api/v1/assets/", "/api/v1/assets/"),
            ("`/api/v1/contracts/`", "/api/v1/contracts/"),
            ("/api/v1/assets", "/api/v1/assets"),
        ]

        for input_path, expected in test_cases:
            normalized = reviewer._normalize_path(input_path)
            self.assertEqual(normalized, expected, f"Failed to normalize: {input_path}")

    def test_compare_endpoints(self):
        """Test endpoint comparison"""
        reviewer = APIInventoryReviewer(self.inventory_file, self.hub_dir)
        reviewer.parse_inventory_file()

        # Create mock actual endpoints
        from dataclasses import dataclass

        @dataclass
        class MockEndpoint:
            path: str
            method: str
            view_class: str | None = None
            file_path: str | None = None

        reviewer.actual_endpoints = [
            MockEndpoint(path="/api/v1/assets/", method="GET"),
            MockEndpoint(path="/api/v1/assets/", method="POST"),
            MockEndpoint(path="/api/v1/assets/{id}/", method="GET"),
            MockEndpoint(path="/api/v1/contracts/", method="GET"),
            MockEndpoint(path="/api/v1/contracts/", method="POST"),
            MockEndpoint(path="/api/v1/new-endpoint/", method="GET"),  # New endpoint
        ]

        discrepancies = reviewer.compare_endpoints()

        # Should find new endpoint missing in inventory
        missing_in_inventory = [d for d in discrepancies if d.type == "missing_in_inventory"]
        self.assertGreater(
            len(missing_in_inventory), 0, "Should find endpoints missing in inventory"
        )

    def test_verify_inventory_accuracy(self):
        """Test inventory accuracy verification"""
        reviewer = APIInventoryReviewer(self.inventory_file, self.hub_dir)
        reviewer.parse_inventory_file()

        # Create mock actual endpoints
        from dataclasses import dataclass

        @dataclass
        class MockEndpoint:
            path: str
            method: str
            view_class: str | None = None
            file_path: str | None = None

        reviewer.actual_endpoints = [
            MockEndpoint(path="/api/v1/assets/", method="GET"),
            MockEndpoint(path="/api/v1/assets/", method="POST"),
        ]

        accuracy = reviewer.verify_inventory_accuracy()

        self.assertIn("status", accuracy)
        self.assertIn("total_inventory_endpoints", accuracy)
        self.assertIn("total_actual_endpoints", accuracy)
        self.assertIn("accuracy_percentage", accuracy)
        self.assertGreaterEqual(accuracy["accuracy_percentage"], 0)
        self.assertLessEqual(accuracy["accuracy_percentage"], 100)

    def test_verify_discrepancy_detection(self):
        """Test discrepancy detection verification"""
        reviewer = APIInventoryReviewer(self.inventory_file, self.hub_dir)
        reviewer.parse_inventory_file()

        # Create some discrepancies
        reviewer.discrepancies = [
            Discrepancy(type="missing_in_inventory", details="Test discrepancy")
        ]

        detection = reviewer.verify_discrepancy_detection()

        self.assertIn("status", detection)
        self.assertIn("total_discrepancies", detection)
        self.assertIn("detection_working", detection)
        self.assertEqual(detection["total_discrepancies"], 1)
        self.assertTrue(detection["detection_working"])

    def test_generate_report(self):
        """Test report generation"""
        reviewer = APIInventoryReviewer(self.inventory_file, self.hub_dir)
        reviewer.parse_inventory_file()

        # Create mock actual endpoints
        from dataclasses import dataclass

        @dataclass
        class MockEndpoint:
            path: str
            method: str
            view_class: str | None = None
            file_path: str | None = None

        reviewer.actual_endpoints = [
            MockEndpoint(path="/api/v1/assets/", method="GET"),
        ]

        reviewer.compare_endpoints()

        output_file = self.temp_path / "report.json"
        reviewer.generate_report(output_file)

        self.assertTrue(output_file.exists(), "Report file should exist")

        # Verify report structure
        with open(output_file) as f:
            report_data = json.load(f)

        self.assertIn("summary", report_data)
        self.assertIn("discrepancies", report_data)
        self.assertIn("generated_at", report_data)

    def test_handles_missing_inventory_file(self):
        """Test handling of missing inventory file"""
        missing_file = self.temp_path / "nonexistent.md"
        reviewer = APIInventoryReviewer(missing_file, self.hub_dir)

        endpoints = reviewer.parse_inventory_file()
        self.assertEqual(len(endpoints), 0, "Should return empty list for missing file")

    def test_handles_empty_inventory(self):
        """Test handling of empty inventory"""
        empty_file = self.temp_path / "empty.md"
        empty_file.write_text("# Empty Inventory\n\nNo endpoints here.")

        reviewer = APIInventoryReviewer(empty_file, self.hub_dir)
        endpoints = reviewer.parse_inventory_file()

        self.assertEqual(len(endpoints), 0, "Should handle empty inventory")

    def test_integration_with_real_codebase(self):
        """Integration test with real codebase - no mocks"""
        # Use actual project files
        project_root = Path(__file__).parent.parent.parent
        real_inventory_file = project_root / "docs" / "api-audit" / "current-api-inventory.md"
        real_hub_dir = project_root / "hub"

        # Skip if files don't exist (e.g., in CI without full repo)
        if not real_inventory_file.exists() or not real_hub_dir.exists():
            self.skipTest("Real codebase files not available")

        reviewer = APIInventoryReviewer(real_inventory_file, real_hub_dir)

        # Parse inventory
        inventory_endpoints = reviewer.parse_inventory_file()
        self.assertGreater(len(inventory_endpoints), 0, "Should parse real inventory file")

        # Extract actual endpoints
        actual_endpoints = reviewer.extract_actual_endpoints()
        self.assertGreater(len(actual_endpoints), 0, "Should extract real endpoints")

        # Compare
        discrepancies = reviewer.compare_endpoints()
        self.assertIsInstance(discrepancies, list, "Should return list of discrepancies")

        # Verify accuracy
        accuracy = reviewer.verify_inventory_accuracy()
        self.assertIn("accuracy_percentage", accuracy)
        self.assertIn("missing_in_inventory", accuracy)
        self.assertIn("missing_in_codebase", accuracy)

        # Verify discrepancy detection
        detection = reviewer.verify_discrepancy_detection()
        self.assertIn("total_discrepancies", detection)
        self.assertTrue(detection["detection_working"])

    def test_report_structure_completeness(self):
        """Test that report contains all required fields"""
        reviewer = APIInventoryReviewer(self.inventory_file, self.hub_dir)
        reviewer.parse_inventory_file()

        # Create mock actual endpoints
        from dataclasses import dataclass

        @dataclass
        class MockEndpoint:
            path: str
            method: str
            view_class: str | None = None
            file_path: str | None = None

        reviewer.actual_endpoints = [
            MockEndpoint(path="/api/v1/assets/", method="GET"),
            MockEndpoint(path="/api/v1/assets/", method="POST"),
        ]

        reviewer.compare_endpoints()

        output_file = self.temp_path / "report.json"
        report = reviewer.generate_report(output_file)

        # Verify all required fields exist
        required_fields = ["generated_at", "inventory_file", "summary", "discrepancies"]

        for field in required_fields:
            self.assertIn(field, report, f"Report should contain '{field}'")

        # Verify summary structure
        summary_fields = [
            "total_inventory_endpoints",
            "total_actual_endpoints",
            "total_discrepancies",
            "accuracy",
            "discrepancy_detection",
        ]

        for field in summary_fields:
            self.assertIn(field, report["summary"], f"Summary should contain '{field}'")

        # Verify discrepancies structure
        self.assertIn("by_type", report["discrepancies"])
        self.assertIn("all", report["discrepancies"])


def main():
    """Run tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAPIInventoryReviewer)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
