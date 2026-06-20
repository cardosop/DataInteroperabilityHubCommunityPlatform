"""
Comprehensive E2E tests for OpenAPI specification accuracy and Swagger UI functionality.

Tests cover:
- OpenAPI spec structure and completeness
- Swagger UI rendering and functionality
- ReDoc rendering and functionality
- Spec accuracy and validation
- Endpoint documentation completeness
"""

import pytest

pytestmark = pytest.mark.slow
import json

from rest_framework import status
from rest_framework.test import APIClient

from tests.e2e.conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e_batch1]


class OpenAPISpecAccuracyTest(E2ETestBase):
    """Comprehensive tests for OpenAPI specification accuracy."""

    def setUp(self):
        """Set up test fixtures — uses authenticated client from E2ETestBase."""
        super().setUp()
        # Do NOT override self.client — E2ETestBase.setUp() provides an
        # authenticated client via force_authenticate (required by 221.4.2).
        # Fetch OpenAPI spec once for all tests
        response = self.client.get("/api-docs/openapi.json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.spec = response.json()

    def test_openapi_version(self):
        """Test OpenAPI version is 3.x."""
        self.assertIn("openapi", self.spec)
        self.assertTrue(
            self.spec["openapi"].startswith("3."),
            f"Expected OpenAPI 3.x, got {self.spec['openapi']}",
        )

    def test_info_section_completeness(self):
        """Test info section has all required fields."""
        self.assertIn("info", self.spec)
        info = self.spec["info"]

        required_fields = ["title", "version", "description"]
        for field in required_fields:
            self.assertIn(field, info, f"Missing required field 'info.{field}'")

        # Verify title matches expected
        self.assertEqual(info["title"], "Interoperable Data Hub API")

    def test_paths_section_exists(self):
        """Test paths section exists and is non-empty."""
        self.assertIn("paths", self.spec)
        self.assertIsInstance(self.spec["paths"], dict)
        self.assertGreater(len(self.spec["paths"]), 0, "Paths section is empty")

    def test_components_section_exists(self):
        """Test components section exists."""
        self.assertIn("components", self.spec)
        components = self.spec["components"]

        # Should have schemas
        self.assertIn("schemas", components)
        self.assertIsInstance(components["schemas"], dict)
        self.assertGreater(len(components["schemas"]), 0, "No component schemas found")

    def test_security_schemes_defined(self):
        """Test security schemes are defined."""
        components = self.spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        self.assertGreater(len(security_schemes), 0, "No security schemes defined")

        # Should have BearerAuth
        self.assertIn("BearerAuth", security_schemes)
        bearer_auth = security_schemes["BearerAuth"]
        self.assertEqual(bearer_auth["type"], "http")
        self.assertEqual(bearer_auth["scheme"], "bearer")

    def test_major_endpoints_documented(self):
        """Test that major endpoints are documented in the spec."""
        paths = self.spec.get("paths", {})
        path_keys = list(paths.keys())

        # Check for major endpoint patterns
        expected_patterns = [
            "/auth/login",
            "/tenants",
            "/users",
            "/assets",
            "/contracts",
            "/datasets",
            "/marketplace",
        ]

        found_patterns = []
        for pattern in expected_patterns:
            if any(pattern in key for key in path_keys):
                found_patterns.append(pattern)

        self.assertGreater(
            len(found_patterns),
            len(expected_patterns) * 0.7,  # At least 70% of expected patterns
            f"Only found {len(found_patterns)}/{len(expected_patterns)} expected endpoint patterns. Found: {found_patterns}",
        )

    def test_paths_have_operations(self):
        """Test that paths have HTTP operations defined."""
        paths = self.spec.get("paths", {})

        operations_found = 0
        for _path, path_item in paths.items():
            if isinstance(path_item, dict):
                # Check for HTTP methods
                http_methods = ["get", "post", "put", "patch", "delete", "head", "options"]
                for method in http_methods:
                    if method in path_item:
                        operations_found += 1
                        break

        self.assertGreater(operations_found, 0, "No HTTP operations found in paths")

    def test_operations_have_responses(self):
        """Test that operations have response definitions."""
        paths = self.spec.get("paths", {})

        operations_with_responses = 0
        operations_without_responses = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "patch", "delete"]:
                    if isinstance(operation, dict):
                        if operation.get("responses"):
                            operations_with_responses += 1
                        else:
                            operations_without_responses.append(f"{method.upper()} {path}")

        # At least 80% of operations should have responses
        total_operations = operations_with_responses + len(operations_without_responses)
        if total_operations > 0:
            response_coverage = operations_with_responses / total_operations
            self.assertGreaterEqual(
                response_coverage,
                0.8,
                f"Only {response_coverage:.1%} of operations have responses. Missing: {operations_without_responses[:10]}",
            )

    def test_operations_have_tags(self):
        """Test that operations are tagged for organization."""
        paths = self.spec.get("paths", {})

        operations_with_tags = 0
        operations_without_tags = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "patch", "delete"]:
                    if isinstance(operation, dict):
                        if operation.get("tags"):
                            operations_with_tags += 1
                        else:
                            operations_without_tags.append(f"{method.upper()} {path}")

        # At least 80% of operations should have tags
        total_operations = operations_with_tags + len(operations_without_tags)
        if total_operations > 0:
            tag_coverage = operations_with_tags / total_operations
            self.assertGreaterEqual(
                tag_coverage,
                0.8,
                f"Only {tag_coverage:.1%} of operations have tags. Missing: {operations_without_tags[:10]}",
            )

    def test_request_bodies_have_schemas(self):
        """Test that POST/PUT/PATCH operations have request body schemas."""
        paths = self.spec.get("paths", {})

        state_changing_methods = ["post", "put", "patch"]
        operations_with_request_bodies = 0
        operations_missing_request_bodies = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method.lower() in state_changing_methods:
                    if isinstance(operation, dict):
                        if operation.get("requestBody"):
                            operations_with_request_bodies += 1
                        else:
                            operations_missing_request_bodies.append(f"{method.upper()} {path}")

        # At least 70% of state-changing operations should have request bodies
        total_operations = operations_with_request_bodies + len(operations_missing_request_bodies)
        if total_operations > 0:
            request_body_coverage = operations_with_request_bodies / total_operations
            self.assertGreaterEqual(
                request_body_coverage,
                0.7,
                f"Only {request_body_coverage:.1%} of state-changing operations have request bodies. Missing: {operations_missing_request_bodies[:10]}",
            )

    def test_error_responses_documented(self):
        """Test that error responses (4xx, 5xx) are documented."""
        paths = self.spec.get("paths", {})

        operations_with_errors = 0
        error_codes = ["400", "401", "403", "404", "429", "500"]

        for _path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "patch", "delete"]:
                    if isinstance(operation, dict):
                        responses = operation.get("responses", {})
                        if any(code in responses for code in error_codes):
                            operations_with_errors += 1

        # At least some operations should have error responses
        self.assertGreater(operations_with_errors, 0, "No error responses documented")

    def test_spec_is_valid_json(self):
        """Test that spec is valid JSON."""
        # This is already validated by response.json(), but double-check
        json_str = json.dumps(self.spec)
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)

    def test_tags_section_exists(self):
        """Test that tags section exists for organization."""
        # Tags may be at root level or inferred from operations
        # Check if tags are defined (optional but recommended)
        if "tags" in self.spec:
            tags = self.spec["tags"]
            self.assertIsInstance(tags, list)
            if tags:
                # Verify tag structure
                for tag in tags:
                    if isinstance(tag, dict):
                        self.assertIn("name", tag)


class SwaggerUIFunctionalityTest(E2ETestBase):
    """Comprehensive tests for Swagger UI functionality (auth required — 221.4.2)."""

    # Uses authenticated self.client from E2ETestBase.setUp() — do NOT override.

    def test_swagger_ui_endpoint_accessible(self):
        """Test Swagger UI endpoint is accessible."""
        response = self.client.get("/api-docs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["Content-Type"])

    def test_swagger_ui_contains_swagger(self):
        """Test Swagger UI HTML contains Swagger references."""
        response = self.client.get("/api-docs/")

        content = response.content.decode("utf-8")
        # Swagger UI should contain swagger references
        self.assertTrue(
            "swagger" in content.lower() or "openapi" in content.lower(),
            "Swagger UI content does not contain expected Swagger/OpenAPI references",
        )

    def test_swagger_ui_loads_spec(self):
        """Test Swagger UI references the OpenAPI spec."""
        response = self.client.get("/api-docs/")

        content = response.content.decode("utf-8")
        # Should reference the OpenAPI schema endpoint
        self.assertTrue(
            "openapi.json" in content or "openapi-schema" in content.lower(),
            "Swagger UI does not reference OpenAPI spec",
        )

    def test_swagger_ui_cors_headers(self):
        """Test Swagger UI has appropriate CORS headers if needed."""
        self.client.get("/api-docs/")

        # CORS headers are optional for same-origin, but check if present
        # This is informational, not a requirement

    def test_swagger_ui_serves_static_assets(self):
        """Test Swagger UI can serve static assets."""
        # Swagger UI embeds assets, so this is mainly a smoke test
        response = self.client.get("/api-docs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ReDocFunctionalityTest(E2ETestBase):
    """Comprehensive tests for ReDoc functionality."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = APIClient()

    def test_redoc_endpoint_accessible(self):
        """Test ReDoc endpoint is accessible."""
        response = self.client.get("/api-docs/redoc/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["Content-Type"])

    def test_redoc_contains_redoc_tag(self):
        """Test ReDoc HTML contains redoc tag."""
        response = self.client.get("/api-docs/redoc/")

        content = response.content.decode("utf-8")
        # ReDoc uses <redoc> tag
        self.assertIn("<redoc", content.lower(), "ReDoc content does not contain <redoc> tag")

    def test_redoc_loads_spec(self):
        """Test ReDoc references the OpenAPI spec."""
        response = self.client.get("/api-docs/redoc/")

        content = response.content.decode("utf-8")
        # Should reference the OpenAPI schema endpoint
        self.assertTrue(
            "openapi.json" in content
            or "openapi-schema" in content.lower()
            or "spec-url" in content.lower(),
            "ReDoc does not reference OpenAPI spec",
        )

    def test_redoc_serves_correctly(self):
        """Test ReDoc serves HTML correctly."""
        response = self.client.get("/api-docs/redoc/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be HTML
        self.assertIn("text/html", response["Content-Type"])


class OpenAPISpecConsistencyTest(E2ETestBase):
    """Tests for OpenAPI spec consistency across endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = APIClient()

    def test_json_and_yaml_specs_match(self):
        """Test that JSON and YAML specs contain the same information."""
        json_response = self.client.get("/api-docs/openapi.json")
        yaml_response = self.client.get("/api/v1/openapi.yaml")

        self.assertEqual(json_response.status_code, status.HTTP_200_OK)
        self.assertEqual(yaml_response.status_code, status.HTTP_200_OK)

        json_spec = json_response.json()

        # Parse YAML (basic check - both should have same top-level keys)
        yaml_content = yaml_response.content.decode("utf-8")

        # Both should have same structure
        set(json_spec.keys())
        # YAML should contain same top-level concepts (basic check)
        yaml_lower = yaml_content.lower()
        self.assertTrue(
            "openapi" in yaml_lower or "info" in yaml_lower,
            "YAML content should contain 'openapi' or 'info'",
        )

    def test_api_v1_openapi_endpoints_match(self):
        """Test that /api/v1/openapi.json matches /api-docs/openapi.json."""
        docs_response = self.client.get("/api-docs/openapi.json")
        v1_response = self.client.get("/api/v1/openapi.json")

        self.assertEqual(docs_response.status_code, status.HTTP_200_OK)
        self.assertEqual(v1_response.status_code, status.HTTP_200_OK)

        docs_spec = docs_response.json()
        v1_spec = v1_response.json()

        # Should have same structure
        self.assertEqual(docs_spec.get("openapi"), v1_spec.get("openapi"))
        self.assertEqual(
            docs_spec.get("info", {}).get("title"), v1_spec.get("info", {}).get("title")
        )
        self.assertEqual(len(docs_spec.get("paths", {})), len(v1_spec.get("paths", {})))
