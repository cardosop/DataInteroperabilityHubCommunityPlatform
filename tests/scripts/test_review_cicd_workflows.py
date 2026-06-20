#!/usr/bin/env python3
"""
Tests for CI/CD workflow review script

Tests the review and extraction of endpoint references from CI/CD workflows.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

# Import with proper handling
import importlib.util

spec = importlib.util.spec_from_file_location(
    "review_cicd_workflows", project_root / "scripts" / "review_cicd_workflows.py"
)
if spec and spec.loader:
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    CICDWorkflowReviewer = module.CICDWorkflowReviewer
    WorkflowEndpointReference = module.WorkflowEndpointReference
    WorkflowReview = module.WorkflowReview


class TestCICDWorkflowReviewer(unittest.TestCase):
    """Test suite for CICDWorkflowReviewer"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create workflows directory
        workflows_dir = self.temp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create test workflow files
        ci_workflow = workflows_dir / "ci.yml"
        ci_workflow.write_text("""name: CI

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run tests
        run: |
          pytest tests/unit/ -v
          curl -f http://localhost:8000/api/v1/health/

      - name: Test API endpoints
        env:
          API_URL: http://localhost:8000/api/v1
        run: |
          curl -X GET http://localhost:8000/api/v1/contracts/
""")

        e2e_workflow = workflows_dir / "e2e.yml"
        e2e_workflow.write_text("""name: E2E Tests

on:
  push:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - name: Wait for services
        run: |
          curl -f http://localhost:8080/health
          curl -f http://localhost:8081/healthz

      - name: Run E2E tests
        env:
          DATACONTRACT_SERVICE_URL: http://localhost:8080
          DQ_SERVICE_URL: http://localhost:8083
        run: |
          pytest tests/e2e/ -v
""")

        openapi_workflow = workflows_dir / "openapi-validation.yml"
        openapi_workflow.write_text("""name: OpenAPI Validation

on:
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - name: Generate OpenAPI schema
        run: |
          python hub/manage.py spectacular --file openapi-schema.json

      - name: Validate schema
        run: |
          python scripts/validate-openapi-specs.py
""")

        self.workflows_dir = workflows_dir

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_review_all_workflows(self):
        """Test reviewing all workflows"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)
        reviewer.review_all_workflows()

        self.assertGreater(len(reviewer.workflows), 0, "Should review workflows")
        self.assertEqual(len(reviewer.workflows), 3, "Should review 3 workflows")

    def test_determine_workflow_type(self):
        """Test workflow type determination"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)

        # Test E2E workflow
        e2e_content = "name: E2E Tests\njobs:\n  e2e:\n    steps: []"
        wf_type = reviewer._determine_workflow_type("E2E Tests", e2e_content, ["e2e"])
        self.assertEqual(wf_type, "e2e")

        # Test OpenAPI workflow
        openapi_content = "name: OpenAPI Validation\njobs:\n  validate:\n    steps: []"
        wf_type = reviewer._determine_workflow_type(
            "OpenAPI Validation", openapi_content, ["validate"]
        )
        self.assertEqual(wf_type, "openapi_validation")

        # Test API testing workflow
        api_content = "name: API Tests\njobs:\n  test:\n    steps:\n      - run: pytest tests/api/"
        wf_type = reviewer._determine_workflow_type("API Tests", api_content, ["test"])
        self.assertEqual(wf_type, "api_testing")

    def test_extract_endpoint_references(self):
        """Test endpoint reference extraction"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)
        reviewer.review_all_workflows()

        self.assertGreater(len(reviewer.endpoint_references), 0, "Should find endpoint references")

        # Check for expected endpoints
        paths = [ref.endpoint_path for ref in reviewer.endpoint_references]
        self.assertIn("/api/v1/health/", paths or ["/health"])
        self.assertIn("/api/v1/contracts/", paths or ["/contracts/"])

    def test_has_api_testing(self):
        """Test API testing detection"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)

        content = """
        jobs:
          test:
            steps:
              - run: pytest tests/api/
        """
        workflow_data = yaml.safe_load(content)
        has_api = reviewer._has_api_testing(content, workflow_data)
        self.assertTrue(has_api, "Should detect API testing")

    def test_has_openapi_validation(self):
        """Test OpenAPI validation detection"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)

        content = """
        jobs:
          validate:
            steps:
              - run: python manage.py spectacular
        """
        workflow_data = yaml.safe_load(content)
        has_openapi = reviewer._has_openapi_validation(content, workflow_data)
        self.assertTrue(has_openapi, "Should detect OpenAPI validation")

    def test_has_e2e_tests(self):
        """Test E2E tests detection"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)

        content = """
        name: E2E Tests
        jobs:
          e2e:
            steps: []
        """
        workflow_data = yaml.safe_load(content)
        has_e2e = reviewer._has_e2e_tests(content, workflow_data)
        self.assertTrue(has_e2e, "Should detect E2E tests")

    def test_normalize_endpoint_path(self):
        """Test endpoint path normalization"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)

        test_cases = [
            ("/api/v1/health/", "/api/v1/health/"),
            ("http://localhost:8000/api/v1/contracts/", "/api/v1/contracts/"),
            ("`/api/v1/assets/`", "/api/v1/assets/"),
        ]

        for input_path, expected in test_cases:
            normalized = reviewer._normalize_endpoint_path(input_path)
            self.assertEqual(normalized, expected, f"Failed to normalize: {input_path}")

    def test_verify_all_workflows_reviewed(self):
        """Test verification that all workflows are reviewed"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)
        reviewer.review_all_workflows()

        verification = reviewer.verify_all_workflows_reviewed()

        self.assertIn("status", verification)
        self.assertIn("total_workflow_files", verification)
        self.assertIn("reviewed_workflows", verification)
        self.assertGreaterEqual(verification["reviewed_workflows"], 0)

    def test_verify_workflow_reference_extraction(self):
        """Test verification of workflow reference extraction"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)
        reviewer.review_all_workflows()

        verification = reviewer.verify_workflow_reference_extraction()

        self.assertIn("status", verification)
        self.assertIn("total_references", verification)
        self.assertIn("extraction_working", verification)
        self.assertTrue(verification["extraction_working"])

    def test_generate_report(self):
        """Test report generation"""
        reviewer = CICDWorkflowReviewer(self.workflows_dir)
        reviewer.review_all_workflows()

        output_file = self.temp_path / "report.json"
        reviewer.generate_report(output_file)

        self.assertTrue(output_file.exists(), "Report file should exist")

        # Verify report structure
        with open(output_file) as f:
            report_data = json.load(f)

        self.assertIn("summary", report_data)
        self.assertIn("workflows", report_data)
        self.assertIn("endpoint_references", report_data)
        self.assertIn("generated_at", report_data)

    def test_handles_missing_workflows_dir(self):
        """Test handling of missing workflows directory"""
        missing_dir = self.temp_path / "nonexistent"
        reviewer = CICDWorkflowReviewer(missing_dir)

        reviewer.review_all_workflows()

        self.assertEqual(len(reviewer.workflows), 0, "Should handle missing directory gracefully")

    def test_integration_with_real_workflows(self):
        """Integration test with real workflows - no mocks"""
        # Use actual project workflows
        project_root = Path(__file__).parent.parent.parent
        real_workflows_dir = project_root / ".github" / "workflows"

        # Skip if workflows don't exist
        if not real_workflows_dir.exists():
            self.skipTest("Real workflows directory not available")

        reviewer = CICDWorkflowReviewer(real_workflows_dir)
        reviewer.review_all_workflows()

        self.assertGreater(len(reviewer.workflows), 0, "Should review real workflows")

        # Verify extraction works
        verification = reviewer.verify_workflow_reference_extraction()
        self.assertTrue(verification["extraction_working"])


def main():
    """Run tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCICDWorkflowReviewer)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
